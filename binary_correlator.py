#!/usr/bin/env python3
"""
Binary Correlator - Known Plaintext Attack on PDS Files

Uses coordinates extracted from Optitex DXF exports to find matching
float values in PDS binary files, revealing the geometry storage format.

Strategy:
1. Load known coordinates from DXF oracle
2. Search PDS binary for matching float32/float64 values
3. Identify patterns in successful matches
4. Determine coordinate storage structure

Author: Claude
Date: 2026-01-30
"""

import os
import struct
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import math


@dataclass
class CoordinateMatch:
    """A match between a known coordinate and binary location."""

    value: float
    offset: int
    format: str  # 'float32' or 'float64'
    context_hex: str  # Surrounding bytes for analysis


def load_oracle_coordinates(oracle_json_path: str) -> List[Tuple[float, float]]:
    """Load coordinates from extracted oracle JSON."""
    with open(oracle_json_path, "r") as f:
        data = json.load(f)

    coords = []
    for piece in data["pieces"]:
        for point in piece["contour_points"]:
            coords.append((point["x"], point["y"]))

    return coords


def search_float32(data: bytes, target: float, tolerance: float = 0.001) -> List[int]:
    """Search for float32 values matching target within tolerance."""
    matches = []
    for i in range(len(data) - 3):
        try:
            value = struct.unpack("<f", data[i : i + 4])[0]
            if abs(value - target) < tolerance:
                matches.append(i)
        except:
            pass
    return matches


def search_float64(data: bytes, target: float, tolerance: float = 0.0001) -> List[int]:
    """Search for float64 values matching target within tolerance."""
    matches = []
    for i in range(len(data) - 7):
        try:
            value = struct.unpack("<d", data[i : i + 8])[0]
            if abs(value - target) < tolerance:
                matches.append(i)
        except:
            pass
    return matches


def get_context(data: bytes, offset: int, before: int = 16, after: int = 16) -> str:
    """Get hex context around an offset."""
    start = max(0, offset - before)
    end = min(len(data), offset + after)
    return data[start:end].hex()


def analyze_pds_binary(pds_path: str, coordinates: List[Tuple[float, float]]) -> Dict:
    """Analyze PDS binary looking for coordinate matches."""
    print(f"\n=== Analyzing PDS Binary: {pds_path} ===")

    with open(pds_path, "rb") as f:
        data = f.read()

    print(f"File size: {len(data)} bytes")

    # Print header info
    magic = data[:4].hex()
    print(f"Magic bytes: {magic}")

    results = {
        "file": pds_path,
        "size": len(data),
        "magic": magic,
        "float32_matches": [],
        "float64_matches": [],
        "coordinate_pairs": [],
    }

    # Take sample of coordinates to search (not all - too slow)
    sample_coords = coordinates[:50] + coordinates[-50:]  # First and last 50
    unique_values = set()
    for x, y in sample_coords:
        unique_values.add(x)
        unique_values.add(y)

    print(f"\nSearching for {len(unique_values)} unique coordinate values...")

    # Search for float32 matches
    print("\n1. Searching as float32 (4 bytes, little-endian)...")
    float32_hits = {}
    for val in list(unique_values)[:20]:  # Sample first 20
        matches = search_float32(data, val, tolerance=0.01)
        if matches:
            float32_hits[val] = matches
            results["float32_matches"].append(
                {"value": val, "offsets": matches, "count": len(matches)}
            )

    if float32_hits:
        print(f"   Found {len(float32_hits)} values with float32 matches")
        for val, offsets in list(float32_hits.items())[:5]:
            print(f"   {val:.4f}: {len(offsets)} matches at {offsets[:3]}...")
    else:
        print("   No float32 matches found")

    # Search for float64 matches
    print("\n2. Searching as float64 (8 bytes, little-endian)...")
    float64_hits = {}
    for val in list(unique_values)[:20]:
        matches = search_float64(data, val, tolerance=0.001)
        if matches:
            float64_hits[val] = matches
            results["float64_matches"].append(
                {"value": val, "offsets": matches, "count": len(matches)}
            )

    if float64_hits:
        print(f"   Found {len(float64_hits)} values with float64 matches")
        for val, offsets in list(float64_hits.items())[:5]:
            print(f"   {val:.4f}: {len(offsets)} matches at {offsets[:3]}...")
    else:
        print("   No float64 matches found")

    # Look for coordinate pairs (X followed by Y within reasonable distance)
    print("\n3. Searching for coordinate pairs...")
    pair_hits = []
    for x, y in sample_coords[:10]:
        x_matches = search_float64(data, x, tolerance=0.01)
        for x_offset in x_matches[:5]:  # Limit search
            # Look for Y value within 8-16 bytes of X
            for y_offset in [x_offset + 8, x_offset + 12, x_offset + 16]:
                if y_offset + 8 <= len(data):
                    try:
                        y_val = struct.unpack("<d", data[y_offset : y_offset + 8])[0]
                        if abs(y_val - y) < 0.01:
                            pair_hits.append(
                                {
                                    "x": x,
                                    "y": y,
                                    "x_offset": x_offset,
                                    "y_offset": y_offset,
                                    "gap": y_offset - x_offset,
                                    "context": get_context(data, x_offset, 8, 24),
                                }
                            )
                    except:
                        pass

    if pair_hits:
        print(f"   Found {len(pair_hits)} coordinate pairs!")
        results["coordinate_pairs"] = pair_hits
        for hit in pair_hits[:3]:
            print(
                f"   ({hit['x']:.4f}, {hit['y']:.4f}) at offsets {hit['x_offset']}, {hit['y_offset']} (gap: {hit['gap']})"
            )
            print(f"   Context: {hit['context']}")
    else:
        print("   No coordinate pairs found")

    # Analyze binary structure
    print("\n4. Analyzing binary structure...")

    # Look for zlib compressed sections
    zlib_markers = []
    for i in range(len(data) - 2):
        if data[i : i + 2] == b"\x78\x9c" or data[i : i + 2] == b"\x78\xda":
            zlib_markers.append(i)

    if zlib_markers:
        print(f"   Found {len(zlib_markers)} potential zlib compressed sections")
        print(f"   Offsets: {zlib_markers[:5]}...")
        results["zlib_offsets"] = zlib_markers

    # Look for record-like structures
    print("\n5. Looking for repetitive structures (records)...")

    # Find repeated 4-byte patterns
    pattern_counts = {}
    for i in range(0, len(data) - 4, 4):
        pattern = data[i : i + 4]
        if pattern not in pattern_counts:
            pattern_counts[pattern] = 0
        pattern_counts[pattern] += 1

    common_patterns = sorted(pattern_counts.items(), key=lambda x: -x[1])[:10]
    print("   Most common 4-byte patterns:")
    for pattern, count in common_patterns[:5]:
        print(f"     {pattern.hex()}: {count} occurrences")

    return results


def decompress_zlib_sections(pds_path: str, offsets: List[int]) -> Dict[int, bytes]:
    """Try to decompress zlib sections and search for coordinates."""
    import zlib

    with open(pds_path, "rb") as f:
        data = f.read()

    decompressed = {}
    for offset in offsets[:5]:  # Try first 5
        for length in [1000, 5000, 10000, 50000]:
            try:
                chunk = data[offset : offset + length]
                decompressed_data = zlib.decompress(chunk)
                decompressed[offset] = decompressed_data
                print(
                    f"   Decompressed {len(decompressed_data)} bytes from offset {offset}"
                )
                break
            except:
                continue

    return decompressed


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent

    # Load oracle coordinates
    oracle_path = (
        base_dir / "DS-speciale" / "oracle" / "extracted" / "Basic Tee_2D_oracle.json"
    )
    if not oracle_path.exists():
        print("ERROR: Oracle JSON not found. Run extract_oracle_data.py first.")
        return

    print(f"Loading oracle coordinates from {oracle_path}...")
    coordinates = load_oracle_coordinates(str(oracle_path))
    print(f"Loaded {len(coordinates)} coordinate pairs")

    # Sample coordinates for display
    print("\nSample coordinates from DXF oracle:")
    for i, (x, y) in enumerate(coordinates[:5]):
        print(f"  Point {i}: ({x:.4f}, {y:.4f})")

    # Analyze PDS binary
    pds_path = base_dir / "DS-speciale" / "inputs" / "pds" / "Basic Tee_2D.PDS"
    if not pds_path.exists():
        pds_path = base_dir / "ExampleFiles" / "pds" / "Basic Tee_2D.PDS"

    if not pds_path.exists():
        print(f"ERROR: PDS file not found at {pds_path}")
        return

    results = analyze_pds_binary(str(pds_path), coordinates)

    # If zlib sections found, try to decompress and search
    if "zlib_offsets" in results and results["zlib_offsets"]:
        print("\n6. Searching within decompressed zlib sections...")
        decompressed = decompress_zlib_sections(str(pds_path), results["zlib_offsets"])

        for offset, decompressed_data in decompressed.items():
            print(f"\n   Searching decompressed section from offset {offset}...")

            # Search for coordinates in decompressed data
            for x, y in coordinates[:10]:
                x_matches = search_float64(decompressed_data, x, tolerance=0.01)
                if x_matches:
                    print(
                        f"   Found X={x:.4f} at decompressed offsets: {x_matches[:3]}"
                    )

    # Summary
    print("\n" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)

    if results["float64_matches"]:
        print(f"\nFloat64 matches: {len(results['float64_matches'])} values found")
        print("-> Coordinates likely stored as 8-byte doubles")
    elif results["float32_matches"]:
        print(f"\nFloat32 matches: {len(results['float32_matches'])} values found")
        print("-> Coordinates likely stored as 4-byte floats")
    else:
        print("\nNo direct coordinate matches found in raw binary")
        print("-> Coordinates may be compressed or transformed")

    if results["coordinate_pairs"]:
        print(f"\nCoordinate pairs found: {len(results['coordinate_pairs'])}")
        gaps = [p["gap"] for p in results["coordinate_pairs"]]
        print(f"Gap between X and Y: {set(gaps)} bytes")
        print("-> This reveals the point record structure!")

    # Save results
    output_path = (
        base_dir / "DS-speciale" / "oracle" / "extracted" / "binary_analysis.json"
    )
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
