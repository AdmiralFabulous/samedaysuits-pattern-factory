#!/usr/bin/env python3
"""
Binary geometry parser for PDS and MRK files.
Attempts to locate and decode actual contour point coordinates from binary data.
"""

import struct
import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
import math


@dataclass
class Point2D:
    x: float
    y: float


@dataclass
class BinaryPiece:
    """A piece extracted from binary with actual geometry."""

    name: str
    contour_points: List[Point2D]
    bbox: Tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    area_estimate: float


def find_float_arrays(
    data: bytes, min_count: int = 4, value_range: Tuple[float, float] = (-5000, 5000)
) -> List[Dict]:
    """
    Find sequences of plausible float32 values that could be coordinate arrays.

    Returns list of {offset, count, values} for potential coordinate arrays.
    """
    results = []
    i = 0
    min_val, max_val = value_range

    while i < len(data) - 8:
        # Try to read float32 at this offset
        try:
            val = struct.unpack("<f", data[i : i + 4])[0]

            # Check if it's a plausible coordinate value
            if min_val < val < max_val and not math.isnan(val) and not math.isinf(val):
                # Try to read more floats from here
                sequence = []
                j = i
                while j < len(data) - 4:
                    v = struct.unpack("<f", data[j : j + 4])[0]
                    if (
                        min_val < v < max_val
                        and not math.isnan(v)
                        and not math.isinf(v)
                    ):
                        sequence.append(v)
                        j += 4
                    else:
                        break

                if len(sequence) >= min_count:
                    results.append(
                        {
                            "offset": i,
                            "count": len(sequence),
                            "values": sequence[:20],  # Preview first 20
                            "is_xy_pairs": len(sequence) % 2 == 0,
                        }
                    )
                    i = j  # Skip past this sequence
                    continue
        except:
            pass

        i += 1

    return results


def search_for_known_value(
    data: bytes, value: float, tolerance: float = 0.01
) -> List[int]:
    """
    Search binary data for a specific float32 value.
    Returns list of offsets where the value is found.
    """
    matches = []
    for i in range(0, len(data) - 4, 1):  # Check every byte offset
        try:
            val = struct.unpack("<f", data[i : i + 4])[0]
            if abs(val - value) < tolerance:
                matches.append(i)
        except:
            pass
    return matches


def parse_header(data: bytes) -> Dict:
    """
    Parse the file header structure.
    Based on observations: magic(4) + flags/version(4) + section info...
    """
    if len(data) < 64:
        return {}

    header = {"magic": data[:4].hex(), "int32_values": []}

    # Read first 16 int32 values
    for i in range(16):
        offset = i * 4
        val = struct.unpack("<I", data[offset : offset + 4])[0]
        header["int32_values"].append(
            {
                "offset": offset,
                "unsigned": val,
                "signed": struct.unpack("<i", data[offset : offset + 4])[0],
            }
        )

    return header


def analyze_mrk_structure(filepath: Path) -> Dict:
    """
    Analyze MRK file structure in detail.
    MRK files contain nested piece placements - positions should be in binary.
    """
    data = filepath.read_bytes()

    result = {
        "filename": filepath.name,
        "filesize": len(data),
        "header": parse_header(data),
        "xml_info": {},
        "binary_sections": [],
        "coordinate_candidates": [],
    }

    # Find XML section
    xml_start = data.find(b"<?xml")
    if xml_start >= 0:
        # Find closing tag
        for closing in [b"</MARKER>", b"</STYLE>"]:
            xml_end = data.find(closing, xml_start)
            if xml_end >= 0:
                xml_end += len(closing)
                result["xml_info"] = {
                    "start": xml_start,
                    "end": xml_end,
                    "size": xml_end - xml_start,
                }
                break

    # Analyze sections before and after XML
    xml_start = result["xml_info"].get("start", 0)
    xml_end = result["xml_info"].get("end", 0)

    # Pre-XML section (header + maybe some tables)
    if xml_start > 0:
        pre_xml = data[:xml_start]
        result["binary_sections"].append(
            {
                "name": "pre_xml_header",
                "start": 0,
                "end": xml_start,
                "size": len(pre_xml),
            }
        )

    # Post-XML section (likely binary geometry/images)
    if xml_end > 0 and xml_end < len(data):
        post_xml = data[xml_end:]
        result["binary_sections"].append(
            {
                "name": "post_xml_data",
                "start": xml_end,
                "end": len(data),
                "size": len(post_xml),
            }
        )

        # Look for float arrays in post-XML section
        float_arrays = find_float_arrays(post_xml)
        for arr in float_arrays[:10]:  # Top 10 candidates
            arr["absolute_offset"] = xml_end + arr["offset"]
            result["coordinate_candidates"].append(arr)

    return result


def analyze_pds_structure(filepath: Path) -> Dict:
    """
    Analyze PDS file structure in detail.
    PDS files contain piece definitions with contour geometry.
    """
    data = filepath.read_bytes()

    result = {
        "filename": filepath.name,
        "filesize": len(data),
        "header": parse_header(data),
        "xml_info": {},
        "jpeg_info": {},
        "binary_sections": [],
        "coordinate_candidates": [],
    }

    # Find JPEG section
    jpeg_start = data.find(b"\xff\xd8\xff")
    if jpeg_start >= 0:
        jpeg_end = data.find(b"\xff\xd9", jpeg_start)
        if jpeg_end >= 0:
            jpeg_end += 2
            result["jpeg_info"] = {
                "start": jpeg_start,
                "end": jpeg_end,
                "size": jpeg_end - jpeg_start,
            }

    # Find XML section
    xml_start = data.find(b"<?xml")
    if xml_start >= 0:
        for closing in [b"</STYLE>", b"</MARKER>"]:
            xml_end = data.find(closing, xml_start)
            if xml_end >= 0:
                xml_end += len(closing)
                result["xml_info"] = {
                    "start": xml_start,
                    "end": xml_end,
                    "size": xml_end - xml_start,
                }
                break

    # Identify all sections
    sections = []

    # Header
    first_content = min(
        result["jpeg_info"].get("start", len(data)),
        result["xml_info"].get("start", len(data)),
    )
    if first_content > 0:
        sections.append(
            {"name": "header", "start": 0, "end": first_content, "size": first_content}
        )

    # After XML
    xml_end = result["xml_info"].get("end", 0)
    if xml_end > 0 and xml_end < len(data):
        post_xml_size = len(data) - xml_end
        sections.append(
            {
                "name": "post_xml_data",
                "start": xml_end,
                "end": len(data),
                "size": post_xml_size,
            }
        )

        # This is likely where actual geometry is stored
        post_xml = data[xml_end:]

        # Look for float arrays
        float_arrays = find_float_arrays(post_xml)
        for arr in float_arrays[:20]:  # Top 20 candidates
            arr["absolute_offset"] = xml_end + arr["offset"]
            result["coordinate_candidates"].append(arr)

    result["binary_sections"] = sections

    return result


def correlate_with_xml(binary_analysis: Dict, canonical_json: Dict) -> Dict:
    """
    Try to correlate binary float candidates with known values from XML.
    """
    correlations = []

    # Extract known values from canonical JSON
    known_values = []

    if canonical_json.get("type") == "marker":
        # Extract placement positions
        for style in canonical_json.get("styles", []):
            for size_name, placements in style.get("sizes", {}).items():
                for p in placements:
                    pos = p.get("position", {})
                    known_values.append(
                        {
                            "source": f"placement_{p.get('piece_name')}_{size_name}",
                            "x": pos.get("x_center"),
                            "y": pos.get("y_center"),
                        }
                    )
                    geom = p.get("geometry", {})
                    if geom.get("size_x"):
                        known_values.append(
                            {
                                "source": f"size_{p.get('piece_name')}",
                                "x": geom.get("size_x"),
                                "y": geom.get("size_y"),
                            }
                        )

    elif canonical_json.get("type") == "pattern":
        # Extract piece size info
        for piece in canonical_json.get("pieces", []):
            for si in piece.get("size_info", []):
                known_values.append(
                    {
                        "source": f"piece_{piece.get('name')}_{si.get('name')}",
                        "x": si.get("size_x"),
                        "y": si.get("size_y"),
                    }
                )

    # Search for known values in coordinate candidates
    for candidate in binary_analysis.get("coordinate_candidates", []):
        values = candidate.get("values", [])
        for kv in known_values:
            for i, v in enumerate(values):
                if kv.get("x") and abs(v - kv["x"]) < 0.1:
                    correlations.append(
                        {
                            "type": "x_match",
                            "known_source": kv["source"],
                            "known_value": kv["x"],
                            "found_value": v,
                            "offset": candidate["absolute_offset"] + i * 4,
                            "index_in_array": i,
                        }
                    )
                if kv.get("y") and abs(v - kv["y"]) < 0.1:
                    correlations.append(
                        {
                            "type": "y_match",
                            "known_source": kv["source"],
                            "known_value": kv["y"],
                            "found_value": v,
                            "offset": candidate["absolute_offset"] + i * 4,
                            "index_in_array": i,
                        }
                    )

    return {
        "known_values_count": len(known_values),
        "correlations": correlations[:50],  # Limit output
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python binary_geometry.py <input_file> <output_json>")
        print(
            "       python binary_geometry.py <input_file> <canonical_json> <output_json>"
        )
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if len(sys.argv) == 3:
        output_path = Path(sys.argv[2])
        canonical_json = None
    else:
        canonical_path = Path(sys.argv[2])
        output_path = Path(sys.argv[3])
        with open(canonical_path, "r", encoding="utf-8") as f:
            canonical_json = json.load(f)

    print(f"Analyzing: {input_path.name}")

    if input_path.suffix.upper() == ".MRK":
        analysis = analyze_mrk_structure(input_path)
    else:
        analysis = analyze_pds_structure(input_path)

    # Correlate with canonical if available
    if canonical_json:
        print("Correlating with canonical JSON...")
        analysis["correlations"] = correlate_with_xml(analysis, canonical_json)

    # Save analysis
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2)

    print(f"\nResults:")
    print(f"  File size: {analysis['filesize']:,} bytes")
    if "xml_info" in analysis and analysis["xml_info"]:
        print(
            f"  XML section: {analysis['xml_info']['start']} - {analysis['xml_info']['end']} ({analysis['xml_info']['size']:,} bytes)"
        )
    if "jpeg_info" in analysis and analysis["jpeg_info"]:
        print(
            f"  JPEG section: {analysis['jpeg_info']['start']} - {analysis['jpeg_info']['end']} ({analysis['jpeg_info']['size']:,} bytes)"
        )
    print(f"  Coordinate candidates: {len(analysis.get('coordinate_candidates', []))}")
    if canonical_json and "correlations" in analysis:
        print(
            f"  Correlations found: {len(analysis['correlations'].get('correlations', []))}"
        )

    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
