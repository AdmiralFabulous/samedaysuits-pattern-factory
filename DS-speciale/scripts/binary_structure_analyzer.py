#!/usr/bin/env python3
"""
Comprehensive binary structure analyzer for PDS files.
Looks for compression, string anchors, section markers, and coordinate arrays.
"""

import struct
import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import math
import zlib


def check_compression_signatures(data: bytes) -> List[Dict]:
    """Check for common compression signatures."""
    signatures = [
        (b"\x78\x9c", "zlib_default"),
        (b"\x78\x01", "zlib_no_compression"),
        (b"\x78\xda", "zlib_best_compression"),
        (b"\x78\x5e", "zlib_low_compression"),
        (b"\x1f\x8b", "gzip"),
        (b"\x04\x22\x4d\x18", "lz4"),
        (b"PK\x03\x04", "zip"),
        (b"\x42\x5a\x68", "bzip2"),
        (b"\xfd\x37\x7a\x58\x5a\x00", "xz"),
        (b"\x28\xb5\x2f\xfd", "zstd"),
    ]

    found = []
    for sig, name in signatures:
        offset = 0
        while True:
            pos = data.find(sig, offset)
            if pos == -1:
                break
            found.append({"type": name, "offset": pos, "signature_hex": sig.hex()})
            offset = pos + 1

    return found


def try_zlib_decompress(
    data: bytes, offset: int, max_size: int = 1000000
) -> Optional[Dict]:
    """Try to decompress zlib data at given offset."""
    try:
        # Try different window sizes
        for wbits in [15, -15, 31, 47]:
            try:
                decompressor = zlib.decompressobj(wbits)
                decompressed = decompressor.decompress(data[offset : offset + max_size])
                return {
                    "offset": offset,
                    "compressed_size_approx": len(data[offset:])
                    - len(decompressor.unused_data),
                    "decompressed_size": len(decompressed),
                    "wbits": wbits,
                    "preview_hex": decompressed[:100].hex(),
                    "preview_ascii": decompressed[:100].decode(
                        "ascii", errors="replace"
                    ),
                }
            except:
                continue
    except:
        pass
    return None


def find_strings(data: bytes, min_length: int = 4) -> List[Dict]:
    """Find ASCII and UTF-16LE strings."""
    strings = []

    # ASCII strings
    ascii_pattern = re.compile(rb"[\x20-\x7e]{" + str(min_length).encode() + rb",}")
    for match in ascii_pattern.finditer(data):
        strings.append(
            {
                "offset": match.start(),
                "encoding": "ascii",
                "length": len(match.group()),
                "value": match.group().decode("ascii"),
            }
        )

    # UTF-16LE strings (common in Windows apps)
    # Look for sequences of ASCII char + \x00
    i = 0
    while i < len(data) - min_length * 2:
        if data[i + 1 : i + 2] == b"\x00" and 0x20 <= data[i] <= 0x7E:
            # Potential UTF-16LE string
            chars = []
            j = i
            while j < len(data) - 1:
                if data[j + 1] == 0 and 0x20 <= data[j] <= 0x7E:
                    chars.append(chr(data[j]))
                    j += 2
                else:
                    break
            if len(chars) >= min_length:
                strings.append(
                    {
                        "offset": i,
                        "encoding": "utf16le",
                        "length": len(chars),
                        "value": "".join(chars),
                    }
                )
                i = j
                continue
        i += 1

    return strings


def find_piece_names(data: bytes, piece_names: List[str]) -> List[Dict]:
    """Search for specific piece names in binary."""
    found = []

    for name in piece_names:
        # Try ASCII
        ascii_bytes = name.encode("ascii")
        offset = 0
        while True:
            pos = data.find(ascii_bytes, offset)
            if pos == -1:
                break
            found.append({"name": name, "offset": pos, "encoding": "ascii"})
            offset = pos + 1

        # Try UTF-16LE
        utf16_bytes = name.encode("utf-16-le")
        offset = 0
        while True:
            pos = data.find(utf16_bytes, offset)
            if pos == -1:
                break
            found.append({"name": name, "offset": pos, "encoding": "utf16le"})
            offset = pos + 1

    return sorted(found, key=lambda x: x["offset"])


def find_float64_arrays(
    data: bytes, min_count: int = 10, value_range: Tuple[float, float] = (-500, 500)
) -> List[Dict]:
    """Find sequences of float64 (double) values."""
    results = []
    min_val, max_val = value_range

    # Only check 8-byte aligned offsets
    i = 0
    while i < len(data) - 16:
        try:
            val = struct.unpack("<d", data[i : i + 8])[0]

            if min_val < val < max_val and not math.isnan(val) and not math.isinf(val):
                # Found a plausible value, try to extend
                sequence = []
                j = i
                while j < len(data) - 8:
                    v = struct.unpack("<d", data[j : j + 8])[0]
                    if (
                        min_val < v < max_val
                        and not math.isnan(v)
                        and not math.isinf(v)
                    ):
                        sequence.append(v)
                        j += 8
                    else:
                        break

                if len(sequence) >= min_count:
                    # Check if it looks like XY pairs
                    is_xy = len(sequence) % 2 == 0
                    if is_xy and len(sequence) >= 4:
                        # Compute bbox
                        xs = sequence[0::2]
                        ys = sequence[1::2]
                        bbox = (min(xs), min(ys), max(xs), max(ys))
                        bbox_width = bbox[2] - bbox[0]
                        bbox_height = bbox[3] - bbox[1]
                    else:
                        bbox = None
                        bbox_width = None
                        bbox_height = None

                    results.append(
                        {
                            "offset": i,
                            "count": len(sequence),
                            "point_count": len(sequence) // 2 if is_xy else None,
                            "values_preview": sequence[:20],
                            "is_xy_pairs": is_xy,
                            "bbox": bbox,
                            "bbox_width": bbox_width,
                            "bbox_height": bbox_height,
                        }
                    )
                    i = j
                    continue
        except:
            pass
        i += 8  # Move to next aligned position

    return results


def find_float32_arrays(
    data: bytes, min_count: int = 20, value_range: Tuple[float, float] = (-500, 500)
) -> List[Dict]:
    """Find sequences of float32 values that could be contour coordinates."""
    results = []
    min_val, max_val = value_range

    # Only check 4-byte aligned offsets
    i = 0
    while i < len(data) - 8:
        try:
            val = struct.unpack("<f", data[i : i + 4])[0]

            if min_val < val < max_val and not math.isnan(val) and not math.isinf(val):
                # Found a plausible value, try to extend
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
                    is_xy = len(sequence) % 2 == 0
                    if is_xy and len(sequence) >= 4:
                        xs = sequence[0::2]
                        ys = sequence[1::2]
                        bbox = (min(xs), min(ys), max(xs), max(ys))
                        bbox_width = bbox[2] - bbox[0]
                        bbox_height = bbox[3] - bbox[1]
                    else:
                        bbox = None
                        bbox_width = None
                        bbox_height = None

                    results.append(
                        {
                            "offset": i,
                            "count": len(sequence),
                            "point_count": len(sequence) // 2 if is_xy else None,
                            "values_preview": [round(v, 4) for v in sequence[:30]],
                            "is_xy_pairs": is_xy,
                            "bbox": bbox,
                            "bbox_width": round(bbox_width, 4) if bbox_width else None,
                            "bbox_height": round(bbox_height, 4)
                            if bbox_height
                            else None,
                        }
                    )
                    i = j
                    continue
        except:
            pass
        i += 4

    return results


def analyze_section_structure(data: bytes, xml_end: int) -> Dict:
    """Analyze the structure of post-XML binary data."""
    post_xml = data[xml_end:]

    # Look for section markers (repeated patterns, counts, etc.)
    result = {
        "post_xml_offset": xml_end,
        "post_xml_size": len(post_xml),
        "compression": check_compression_signatures(post_xml),
        "sections": [],
    }

    # Check first 256 bytes for header-like structure
    if len(post_xml) >= 256:
        header_int32s = []
        for i in range(0, 64, 4):
            val = struct.unpack("<I", post_xml[i : i + 4])[0]
            header_int32s.append(
                {
                    "offset": xml_end + i,
                    "relative": i,
                    "value": val,
                    "hex": post_xml[i : i + 4].hex(),
                }
            )
        result["post_xml_header_int32s"] = header_int32s

    # Try to decompress if zlib signature found
    for comp in result["compression"]:
        if "zlib" in comp["type"]:
            decomp_result = try_zlib_decompress(post_xml, comp["offset"] - xml_end)
            if decomp_result:
                decomp_result["offset"] += xml_end  # Adjust to absolute offset
                result["decompression_success"] = decomp_result
                break

    return result


def match_geometry_to_pieces(
    float_arrays: List[Dict], pieces_info: List[Dict]
) -> List[Dict]:
    """Try to match float arrays to known piece dimensions."""
    matches = []

    for arr in float_arrays:
        if not arr.get("bbox_width") or not arr.get("bbox_height"):
            continue

        w = arr["bbox_width"]
        h = arr["bbox_height"]

        for piece in pieces_info:
            for size_info in piece.get("size_info", []):
                target_w = size_info.get("size_x", 0)
                target_h = size_info.get("size_y", 0)

                # Check if bbox matches (within 5% tolerance)
                if target_w > 0 and target_h > 0:
                    w_match = abs(w - target_w) / target_w < 0.05
                    h_match = abs(h - target_h) / target_h < 0.05

                    # Also check swapped (width/height could be reversed)
                    w_match_swap = abs(h - target_w) / target_w < 0.05
                    h_match_swap = abs(w - target_h) / target_h < 0.05

                    if (w_match and h_match) or (w_match_swap and h_match_swap):
                        matches.append(
                            {
                                "array_offset": arr["offset"],
                                "array_point_count": arr["point_count"],
                                "array_bbox": arr["bbox"],
                                "array_width": w,
                                "array_height": h,
                                "piece_name": piece["name"],
                                "size_name": size_info["name"],
                                "target_width": target_w,
                                "target_height": target_h,
                                "swapped": w_match_swap
                                and h_match_swap
                                and not (w_match and h_match),
                            }
                        )

    return matches


def main():
    if len(sys.argv) < 2:
        print("Usage: python binary_structure_analyzer.py <pds_file> [canonical_json]")
        sys.exit(1)

    pds_path = Path(sys.argv[1])
    canonical_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"Analyzing: {pds_path.name}")
    print("=" * 60)

    data = pds_path.read_bytes()
    print(f"File size: {len(data):,} bytes")

    # Find XML boundaries
    xml_start = data.find(b"<?xml")
    xml_end_marker = data.find(b"</STYLE>")
    if xml_end_marker == -1:
        xml_end_marker = data.find(b"</MARKER>")
    xml_end = xml_end_marker + len(b"</STYLE>") if xml_end_marker > 0 else 0

    print(f"XML section: {xml_start} - {xml_end} ({xml_end - xml_start:,} bytes)")
    print(f"Post-XML data: {len(data) - xml_end:,} bytes")

    # Load canonical JSON if provided
    pieces_info = []
    piece_names = []
    if canonical_path and canonical_path.exists():
        with open(canonical_path) as f:
            canonical = json.load(f)
        pieces_info = canonical.get("pieces", [])
        piece_names = [p["name"] for p in pieces_info]
        print(f"Loaded canonical: {len(pieces_info)} pieces")

    results = {
        "filename": pds_path.name,
        "filesize": len(data),
        "xml_start": xml_start,
        "xml_end": xml_end,
        "post_xml_size": len(data) - xml_end,
    }

    # 1. Check for compression
    print("\n1. Checking for compression signatures...")
    compression = check_compression_signatures(data[xml_end:])
    results["compression_signatures"] = compression
    if compression:
        print(f"   Found {len(compression)} compression signatures:")
        for c in compression[:5]:
            print(f"     {c['type']} at offset {xml_end + c['offset']}")
    else:
        print("   No compression signatures found")

    # 2. Search for piece names
    print("\n2. Searching for piece names in binary...")
    if piece_names:
        name_locations = find_piece_names(data, piece_names)
        results["piece_name_locations"] = name_locations
        print(f"   Found {len(name_locations)} piece name occurrences:")
        for loc in name_locations[:10]:
            print(f"     '{loc['name']}' at offset {loc['offset']} ({loc['encoding']})")

    # 3. Find float64 arrays
    print("\n3. Searching for float64 coordinate arrays...")
    post_xml_data = data[xml_end:]
    f64_arrays = find_float64_arrays(post_xml_data, min_count=8)
    for arr in f64_arrays:
        arr["offset"] += xml_end  # Convert to absolute offset
    results["float64_arrays"] = f64_arrays[:20]
    print(f"   Found {len(f64_arrays)} potential float64 arrays")
    for arr in f64_arrays[:5]:
        print(
            f"     Offset {arr['offset']}: {arr['point_count']} points, bbox {arr['bbox_width']:.1f} x {arr['bbox_height']:.1f}"
            if arr["bbox_width"]
            else f"     Offset {arr['offset']}: {arr['count']} values"
        )

    # 4. Find float32 arrays
    print("\n4. Searching for float32 coordinate arrays...")
    f32_arrays = find_float32_arrays(post_xml_data, min_count=20)
    for arr in f32_arrays:
        arr["offset"] += xml_end
    results["float32_arrays"] = f32_arrays[:30]
    print(f"   Found {len(f32_arrays)} potential float32 arrays")
    for arr in f32_arrays[:5]:
        if arr["bbox_width"]:
            print(
                f"     Offset {arr['offset']}: {arr['point_count']} points, bbox {arr['bbox_width']:.1f} x {arr['bbox_height']:.1f}"
            )
        else:
            print(f"     Offset {arr['offset']}: {arr['count']} values")

    # 5. Try to match arrays to known piece dimensions
    print("\n5. Matching arrays to piece dimensions...")
    if pieces_info:
        geometry_matches = match_geometry_to_pieces(
            f64_arrays + f32_arrays, pieces_info
        )
        results["geometry_matches"] = geometry_matches
        print(f"   Found {len(geometry_matches)} potential geometry matches:")
        for m in geometry_matches[:10]:
            print(
                f"     Offset {m['array_offset']}: {m['piece_name']}/{m['size_name']} - {m['array_point_count']} points"
            )
            print(
                f"       Array: {m['array_width']:.2f} x {m['array_height']:.2f}, Target: {m['target_width']:.2f} x {m['target_height']:.2f}"
            )

    # 6. Analyze section structure
    print("\n6. Analyzing post-XML structure...")
    section_analysis = analyze_section_structure(data, xml_end)
    results["section_analysis"] = section_analysis

    if section_analysis.get("decompression_success"):
        d = section_analysis["decompression_success"]
        print(
            f"   Successfully decompressed {d['decompressed_size']:,} bytes from offset {d['offset']}"
        )

    # Save results
    output_path = (
        pds_path.parent.parent
        / "out"
        / "binary_analysis"
        / f"{pds_path.stem}_structure.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_path}")

    return results


if __name__ == "__main__":
    main()
