#!/usr/bin/env python3
"""
Deep binary search for known values in PDS files.
Searches for specific float/double values from the canonical JSON.
"""

import struct
import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import math


def search_float32(data: bytes, value: float, tolerance: float = 0.01) -> List[Dict]:
    """Search for float32 little-endian value."""
    matches = []
    for i in range(len(data) - 4):
        try:
            val = struct.unpack("<f", data[i : i + 4])[0]
            if not math.isnan(val) and not math.isinf(val):
                if abs(val - value) <= tolerance:
                    matches.append(
                        {
                            "offset": i,
                            "type": "float32_le",
                            "target": value,
                            "found": val,
                            "diff": abs(val - value),
                        }
                    )
        except:
            pass
    return matches


def search_float64(data: bytes, value: float, tolerance: float = 0.01) -> List[Dict]:
    """Search for float64/double little-endian value."""
    matches = []
    for i in range(len(data) - 8):
        try:
            val = struct.unpack("<d", data[i : i + 8])[0]
            if not math.isnan(val) and not math.isinf(val):
                if abs(val - value) <= tolerance:
                    matches.append(
                        {
                            "offset": i,
                            "type": "float64_le",
                            "target": value,
                            "found": val,
                            "diff": abs(val - value),
                        }
                    )
        except:
            pass
    return matches


def search_int32(data: bytes, value: int) -> List[Dict]:
    """Search for int32 little-endian value."""
    matches = []
    target_bytes = struct.pack("<i", value)
    for i in range(len(data) - 4):
        if data[i : i + 4] == target_bytes:
            matches.append(
                {"offset": i, "type": "int32_le", "target": value, "found": value}
            )
    return matches


def search_scaled_int(
    data: bytes, value: float, scales: List[float] = [10, 100, 1000, 10000]
) -> List[Dict]:
    """Search for value stored as scaled integer (value * scale)."""
    matches = []
    for scale in scales:
        scaled_value = int(round(value * scale))
        # Try both signed and unsigned
        for i in range(len(data) - 4):
            try:
                val_signed = struct.unpack("<i", data[i : i + 4])[0]
                val_unsigned = struct.unpack("<I", data[i : i + 4])[0]

                if val_signed == scaled_value:
                    matches.append(
                        {
                            "offset": i,
                            "type": f"int32_scaled_{scale}",
                            "target": value,
                            "found_raw": val_signed,
                            "found_scaled": val_signed / scale,
                        }
                    )
                if val_unsigned == scaled_value:
                    matches.append(
                        {
                            "offset": i,
                            "type": f"uint32_scaled_{scale}",
                            "target": value,
                            "found_raw": val_unsigned,
                            "found_scaled": val_unsigned / scale,
                        }
                    )
            except:
                pass

    # Also try int16
    for scale in scales:
        scaled_value = int(round(value * scale))
        if -32768 <= scaled_value <= 65535:
            for i in range(len(data) - 2):
                try:
                    val_signed = struct.unpack("<h", data[i : i + 2])[0]
                    val_unsigned = struct.unpack("<H", data[i : i + 2])[0]

                    if val_signed == scaled_value:
                        matches.append(
                            {
                                "offset": i,
                                "type": f"int16_scaled_{scale}",
                                "target": value,
                                "found_raw": val_signed,
                                "found_scaled": val_signed / scale,
                            }
                        )
                    if val_unsigned == scaled_value and val_unsigned != val_signed:
                        matches.append(
                            {
                                "offset": i,
                                "type": f"uint16_scaled_{scale}",
                                "target": value,
                                "found_raw": val_unsigned,
                                "found_scaled": val_unsigned / scale,
                            }
                        )
                except:
                    pass

    return matches


def extract_context(data: bytes, offset: int, context_bytes: int = 32) -> Dict:
    """Extract context around an offset."""
    start = max(0, offset - context_bytes)
    end = min(len(data), offset + context_bytes)

    context_data = data[start:end]

    # Try to interpret neighboring values
    neighbors = []
    for j in range(-4, 5):
        neighbor_offset = offset + j * 4
        if 0 <= neighbor_offset <= len(data) - 4:
            try:
                f32 = struct.unpack("<f", data[neighbor_offset : neighbor_offset + 4])[
                    0
                ]
                if not math.isnan(f32) and not math.isinf(f32) and abs(f32) < 10000:
                    neighbors.append(
                        {
                            "relative": j * 4,
                            "offset": neighbor_offset,
                            "float32": round(f32, 4),
                        }
                    )
            except:
                pass

    return {"hex": context_data.hex(), "neighbors": neighbors}


def main():
    if len(sys.argv) < 3:
        print("Usage: python deep_binary_search.py <pds_file> <canonical_json>")
        sys.exit(1)

    pds_path = Path(sys.argv[1])
    canonical_path = Path(sys.argv[2])

    print(f"Loading {pds_path.name}...")
    data = pds_path.read_bytes()

    print(f"Loading canonical JSON...")
    with open(canonical_path, "r", encoding="utf-8") as f:
        canonical = json.load(f)

    # Collect target values to search for
    targets = []

    for piece in canonical.get("pieces", []):
        piece_name = piece.get("name", "unknown")
        for size_info in piece.get("size_info", []):
            size_name = size_info.get("name", "unknown")
            # Add all numeric values
            for key in [
                "size_x",
                "size_y",
                "area",
                "perimeter",
                "sew_area",
                "sew_perimeter",
            ]:
                val = size_info.get(key)
                if val and val != 0:
                    targets.append(
                        {
                            "piece": piece_name,
                            "size": size_name,
                            "field": key,
                            "value": val,
                        }
                    )

        # Also search for position values
        pos = piece.get("position", {})
        if pos.get("x"):
            targets.append(
                {
                    "piece": piece_name,
                    "size": "base",
                    "field": "position_x",
                    "value": pos["x"],
                }
            )
        if pos.get("y"):
            targets.append(
                {
                    "piece": piece_name,
                    "size": "base",
                    "field": "position_y",
                    "value": pos["y"],
                }
            )

    print(f"\nSearching for {len(targets)} target values...")
    print(f"File size: {len(data):,} bytes")

    # Find XML boundaries to focus search
    xml_start = data.find(b"<?xml")
    xml_end = data.find(b"</STYLE>")
    if xml_end > 0:
        xml_end += len(b"</STYLE>")

    print(f"XML: bytes {xml_start} - {xml_end}")
    print(f"Post-XML data: {len(data) - xml_end:,} bytes")

    # Search only in post-XML section (more efficient)
    post_xml = data[xml_end:] if xml_end > 0 else data
    post_xml_offset = xml_end if xml_end > 0 else 0

    results = {}

    # Search for a sample of key values (not all, for speed)
    sample_targets = targets[:20]  # First 20 targets

    for t in sample_targets:
        key = f"{t['piece']}_{t['size']}_{t['field']}"
        value = t["value"]

        print(f"  Searching for {key} = {value}...")

        # Search float32
        f32_matches = search_float32(post_xml, value, 0.001)
        for m in f32_matches:
            m["offset"] += post_xml_offset

        # Search float64
        f64_matches = search_float64(post_xml, value, 0.001)
        for m in f64_matches:
            m["offset"] += post_xml_offset

        # Search scaled integers
        scaled_matches = search_scaled_int(post_xml, value, [10, 100, 1000])
        for m in scaled_matches:
            m["offset"] += post_xml_offset

        all_matches = f32_matches + f64_matches + scaled_matches

        if all_matches:
            results[key] = {
                "target": t,
                "matches": all_matches[:10],  # Limit matches
                "total_matches": len(all_matches),
            }

            # Add context for first match
            if all_matches:
                first = all_matches[0]
                results[key]["context"] = extract_context(data, first["offset"])

    # Summary
    print(f"\n{'=' * 60}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 60}")

    if not results:
        print("No matches found with standard encodings.")
        print("\nTrying alternative approaches...")

        # Try searching the entire file for any known value
        test_value = 27.772  # size_x of Front/Small
        print(f"\nSearching entire file for {test_value} (Front/Small size_x)...")

        f32_all = search_float32(data, test_value, 0.1)
        f64_all = search_float64(data, test_value, 0.1)

        print(f"  float32 matches: {len(f32_all)}")
        print(f"  float64 matches: {len(f64_all)}")

        # Try looking for values in different units (mm vs cm vs inches)
        print("\nTrying unit conversions...")
        for unit_scale, unit_name in [
            (10.0, "mm"),
            (0.393701, "inches"),
            (100.0, "0.1mm"),
        ]:
            scaled_val = test_value * unit_scale
            f32_scaled = search_float32(data, scaled_val, 1.0)
            print(
                f"  {test_value} cm = {scaled_val:.2f} {unit_name}: {len(f32_scaled)} float32 matches"
            )
            if f32_scaled:
                for m in f32_scaled[:3]:
                    print(f"    offset {m['offset']}: {m['found']:.4f}")
    else:
        for key, result in results.items():
            print(f"\n{key}:")
            print(f"  Target: {result['target']['value']}")
            print(f"  Matches: {result['total_matches']}")
            for m in result["matches"][:3]:
                print(
                    f"    {m['type']} at offset {m['offset']}: {m.get('found', m.get('found_scaled'))}"
                )

    # Save detailed results
    output_path = (
        pds_path.parent.parent
        / "out"
        / "binary_analysis"
        / f"{pds_path.stem}_deep_search.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
