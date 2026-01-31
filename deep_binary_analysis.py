#!/usr/bin/env python3
"""
Deep Binary Analysis - Extract and decode PDS geometry sections.

Based on initial findings:
- Coordinates are likely float32
- Multiple zlib compressed sections exist
- Need to find the geometry storage pattern

Author: Claude
Date: 2026-01-30
"""

import os
import struct
import zlib
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional


def decompress_all_zlib(data: bytes) -> Dict[int, bytes]:
    """Find and decompress all zlib sections."""
    results = {}

    # Look for zlib headers
    i = 0
    while i < len(data) - 2:
        # Common zlib headers: 78 9c (default), 78 da (best), 78 01 (no compression)
        if data[i : i + 2] in [b"\x78\x9c", b"\x78\xda", b"\x78\x01"]:
            # Try different chunk sizes
            for max_len in [1000, 5000, 10000, 50000, 100000]:
                if i + max_len > len(data):
                    max_len = len(data) - i
                try:
                    chunk = data[i : i + max_len]
                    decompressed = zlib.decompress(chunk)
                    results[i] = {
                        "compressed_size": len(chunk),
                        "decompressed_size": len(decompressed),
                        "data": decompressed,
                    }
                    print(
                        f"  Decompressed zlib at offset {i}: {len(decompressed)} bytes"
                    )
                    break
                except zlib.error:
                    continue
        i += 1

    return results


def find_float_arrays(data: bytes, min_floats: int = 10) -> List[Dict]:
    """Find arrays of float32 values that look like coordinates."""
    arrays = []
    i = 0

    while i < len(data) - min_floats * 4:
        # Check if this looks like a float array
        floats = []
        valid = True

        for j in range(min_floats):
            try:
                val = struct.unpack("<f", data[i + j * 4 : i + j * 4 + 4])[0]
                # Check if value is reasonable for coordinates (-1000 to 1000 cm)
                if not (-1000 < val < 1000) or val != val:  # nan check
                    valid = False
                    break
                floats.append(val)
            except:
                valid = False
                break

        if valid:
            # Extend to find full array
            full_array = list(floats)
            k = min_floats
            while i + k * 4 + 4 <= len(data):
                try:
                    val = struct.unpack("<f", data[i + k * 4 : i + k * 4 + 4])[0]
                    if -1000 < val < 1000 and val == val:
                        full_array.append(val)
                        k += 1
                    else:
                        break
                except:
                    break

            if len(full_array) >= min_floats:
                arrays.append(
                    {
                        "offset": i,
                        "count": len(full_array),
                        "values": full_array[:20],  # Sample
                        "min": min(full_array),
                        "max": max(full_array),
                    }
                )
                i += len(full_array) * 4
            else:
                i += 4
        else:
            i += 1

    return arrays


def analyze_structure(data: bytes) -> Dict:
    """Analyze overall structure of PDS file."""
    result = {"size": len(data), "magic": data[:4].hex(), "sections": []}

    # Header analysis
    header_size = struct.unpack("<I", data[4:8])[0] if len(data) > 8 else 0
    result["header_size"] = header_size

    # Find embedded strings
    strings = []
    current_string = b""
    for i, b in enumerate(data):
        if 32 <= b < 127:  # Printable ASCII
            current_string += bytes([b])
        else:
            if len(current_string) >= 8:  # Minimum string length
                strings.append(
                    {
                        "offset": i - len(current_string),
                        "text": current_string.decode("ascii"),
                    }
                )
            current_string = b""

    result["strings"] = strings[:50]  # First 50

    return result


def extract_geometry_from_section(
    data: bytes, offset_hint: int = 0
) -> List[Tuple[float, float]]:
    """Extract coordinate pairs from a binary section."""
    coords = []

    # Try different interpretations

    # Attempt 1: Consecutive float32 pairs
    for i in range(0, len(data) - 8, 8):
        try:
            x = struct.unpack("<f", data[i : i + 4])[0]
            y = struct.unpack("<f", data[i + 4 : i + 8])[0]

            # Validate as coordinates
            if -500 < x < 500 and -500 < y < 500 and x == x and y == y:
                coords.append((x, y))
        except:
            pass

    return coords


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent
    pds_path = base_dir / "DS-speciale" / "inputs" / "pds" / "Basic Tee_2D.PDS"

    if not pds_path.exists():
        pds_path = base_dir / "ExampleFiles" / "pds" / "Basic Tee_2D.PDS"

    print(f"=== Deep Binary Analysis: {pds_path} ===\n")

    with open(pds_path, "rb") as f:
        data = f.read()

    print(f"File size: {len(data)} bytes")

    # 1. Analyze structure
    print("\n1. Analyzing file structure...")
    structure = analyze_structure(data)
    print(f"   Magic: {structure['magic']}")
    print(f"   Significant strings found: {len(structure['strings'])}")
    for s in structure["strings"][:10]:
        print(f"     @{s['offset']}: {s['text'][:50]}...")

    # 2. Find and decompress zlib sections
    print("\n2. Finding and decompressing zlib sections...")
    zlib_sections = decompress_all_zlib(data)
    print(f"   Found {len(zlib_sections)} zlib sections")

    # 3. Search decompressed sections for float arrays
    print("\n3. Searching for float arrays in decompressed data...")
    all_float_arrays = []

    for offset, section in zlib_sections.items():
        print(
            f"\n   Section at offset {offset} ({section['decompressed_size']} bytes):"
        )
        decompressed = section["data"]

        # Look for float arrays
        float_arrays = find_float_arrays(decompressed)

        if float_arrays:
            print(f"     Found {len(float_arrays)} potential float arrays")
            for arr in float_arrays[:3]:
                print(
                    f"       @{arr['offset']}: {arr['count']} floats, range [{arr['min']:.2f}, {arr['max']:.2f}]"
                )
                print(f"         Sample: {[f'{v:.2f}' for v in arr['values'][:8]]}")
                all_float_arrays.append({"source_offset": offset, **arr})
        else:
            print("     No float arrays found")

        # Try extracting coordinate pairs
        coords = extract_geometry_from_section(decompressed)
        if coords:
            print(f"     Extracted {len(coords)} potential coordinate pairs")
            print(f"       Sample: {coords[:5]}")

    # 4. Also search raw binary (after header) for float arrays
    print("\n4. Searching raw binary for float arrays...")

    # Skip header and JPEG (look after offset ~5000)
    raw_float_arrays = find_float_arrays(data[5000:], min_floats=20)
    if raw_float_arrays:
        print(f"   Found {len(raw_float_arrays)} potential float arrays in raw binary")
        for arr in raw_float_arrays[:5]:
            actual_offset = arr["offset"] + 5000
            print(f"     @{actual_offset}: {arr['count']} floats")
            print(f"       Sample: {[f'{v:.2f}' for v in arr['values'][:8]]}")

    # 5. Hexdump interesting sections
    print("\n5. Hexdump of key sections...")

    # Look for XML section (contains piece info)
    xml_start = data.find(b"<?xml")
    if xml_start != -1:
        print(f"   XML starts at offset {xml_start}")
        # Look for geometry-like data before XML
        pre_xml = data[max(0, xml_start - 100) : xml_start]
        print(f"   100 bytes before XML: {pre_xml.hex()}")

    # Summary
    print("\n" + "=" * 60)
    print("DEEP ANALYSIS SUMMARY")
    print("=" * 60)

    # Load oracle coordinates for comparison
    oracle_path = (
        base_dir / "DS-speciale" / "oracle" / "extracted" / "Basic Tee_2D_oracle.json"
    )
    if oracle_path.exists():
        with open(oracle_path, "r") as f:
            oracle = json.load(f)

        # Get some known coordinates
        known_coords = []
        for piece in oracle["pieces"]:
            for p in piece["contour_points"][:5]:
                known_coords.append((p["x"], p["y"]))

        print(f"\nKnown coordinates from DXF oracle:")
        for i, (x, y) in enumerate(known_coords[:5]):
            print(f"  {i}: ({x:.4f}, {y:.4f})")

        # Check if any extracted float arrays contain these values
        print(f"\nSearching for known coordinates in extracted float arrays...")

        for x, y in known_coords[:3]:
            print(f"\n  Looking for X={x:.4f}:")

            for arr in all_float_arrays:
                for i, v in enumerate(arr["values"]):
                    if abs(v - x) < 0.1:
                        print(
                            f"    MATCH! Found {v:.4f} at array @{arr['source_offset']}+{i * 4}"
                        )

    print("\n\nConclusion: The geometry is likely stored in zlib-compressed sections.")
    print("Next step: Map the decompressed data structure to extract actual contours.")


if __name__ == "__main__":
    main()
