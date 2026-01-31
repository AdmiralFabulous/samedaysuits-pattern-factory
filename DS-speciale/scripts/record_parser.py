#!/usr/bin/env python3
"""
Parse the structured records in the post-XML section of PDS files.
Based on hex exploration, the post-XML section contains size/variation records.
"""

import struct
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json


def read_string(data: bytes, offset: int) -> Tuple[str, int]:
    """Read a length-prefixed string (1 byte length + string)."""
    if offset >= len(data):
        return "", offset

    length = data[offset]
    if offset + 1 + length > len(data):
        return "", offset

    try:
        string = data[offset + 1 : offset + 1 + length].decode(
            "ascii", errors="replace"
        )
        return string, offset + 1 + length
    except:
        return "", offset


def scan_for_size_records(data: bytes, start_offset: int = 0) -> List[Dict]:
    """Scan for size records like 'XS', 'Small', 'Medium', etc."""
    records = []
    known_sizes = [b"XS", b"Small", b"Medium", b"Large", b"XL", b"2XL", b"3XL", b"4XL"]

    for size_name in known_sizes:
        offset = start_offset
        while True:
            pos = data.find(size_name, offset)
            if pos == -1:
                break

            # Check if this is a length-prefixed string
            if pos > 0 and data[pos - 1] == len(size_name):
                # Found a length-prefixed string
                # Look at surrounding bytes for record structure
                record_start = pos - 10 if pos >= 10 else 0
                record_end = (
                    pos + len(size_name) + 30
                    if pos + len(size_name) + 30 <= len(data)
                    else len(data)
                )

                context = data[record_start:record_end]

                records.append(
                    {
                        "size_name": size_name.decode("ascii"),
                        "offset": pos,
                        "length_prefix_offset": pos - 1,
                        "context_hex": context.hex(),
                        "context_ascii": context.decode("ascii", errors="replace"),
                    }
                )

            offset = pos + 1

    return sorted(records, key=lambda x: x["offset"])


def parse_size_block(data: bytes, start: int) -> Dict:
    """Parse a size block starting at the given offset."""
    result = {"start": start, "fields": []}

    offset = start

    # Try to parse fields
    for i in range(20):
        if offset >= len(data) - 4:
            break

        # Read potential type indicator and length
        field_type = data[offset]

        if field_type == 0x14:  # Seems to be a record type marker
            if offset + 2 < len(data):
                sub_type = data[offset + 1]
                str_len = data[offset + 2]

                if str_len < 50 and offset + 3 + str_len <= len(data):
                    try:
                        string_val = data[offset + 3 : offset + 3 + str_len].decode(
                            "ascii"
                        )
                        result["fields"].append(
                            {
                                "type": "string",
                                "offset": offset,
                                "marker": hex(field_type),
                                "sub_type": hex(sub_type),
                                "value": string_val,
                            }
                        )
                        offset += 3 + str_len
                        continue
                    except:
                        pass

        # Try reading as different types
        if offset + 4 <= len(data):
            u32 = struct.unpack("<I", data[offset : offset + 4])[0]
            f32 = struct.unpack("<f", data[offset : offset + 4])[0]

            result["fields"].append(
                {
                    "type": "raw",
                    "offset": offset,
                    "hex": data[offset : offset + 4].hex(),
                    "u32": u32,
                    "f32": f32 if -1e10 < f32 < 1e10 else "N/A",
                }
            )

        offset += 1

        if offset - start > 100:
            break

    return result


def analyze_post_xml_structure(data: bytes, xml_end: int) -> Dict:
    """Analyze the structured section after XML."""
    post_xml = data[xml_end:]

    print(f"Post-XML section: {len(post_xml):,} bytes starting at {xml_end}")

    # Find the file path string that appears first
    result = {
        "xml_end": xml_end,
        "post_xml_size": len(post_xml),
        "file_path": None,
        "size_records": [],
        "piece_records": [],
    }

    # Look for size records
    print("\nScanning for size records...")
    size_records = scan_for_size_records(data, xml_end)
    result["size_records"] = size_records

    print(f"Found {len(size_records)} size name occurrences:")
    for rec in size_records[:20]:
        print(f"  {rec['size_name']:10s} at offset {rec['offset']}")

    # Look for piece name records
    print("\nScanning for piece names...")
    piece_names = [b"Front", b"Back", b"Right Sleeve", b"Left Sleeve", b"Neck Binding"]
    piece_records = []

    for name in piece_names:
        offset = xml_end
        while True:
            pos = data.find(name, offset)
            if pos == -1:
                break

            if pos > 0:
                # Check preceding bytes
                pre_bytes = data[max(0, pos - 20) : pos]
                post_bytes = data[pos : min(len(data), pos + len(name) + 20)]

                piece_records.append(
                    {
                        "name": name.decode("ascii"),
                        "offset": pos,
                        "pre_hex": pre_bytes.hex(),
                        "post_hex": post_bytes.hex(),
                        "context": data[
                            max(0, pos - 5) : min(len(data), pos + len(name) + 15)
                        ].decode("ascii", errors="replace"),
                    }
                )

            offset = pos + 1

    result["piece_records"] = sorted(piece_records, key=lambda x: x["offset"])

    print(f"\nFound {len(piece_records)} piece name occurrences:")
    for rec in piece_records[:10]:
        ctx = rec["context"].encode("ascii", errors="replace").decode("ascii")
        print(f"  {rec['name']:15s} at offset {rec['offset']} - context: {repr(ctx)}")

    return result


def find_grading_data(data: bytes, xml_end: int) -> List[Dict]:
    """Look for grading rule data which might contain coordinate deltas."""
    post_xml = data[xml_end:]

    # Grading typically involves small coordinate adjustments per size
    # Look for patterns of small floats that might be grading deltas

    results = []

    # Search for sequences of small floats (-10 to +10 range typical for grading)
    i = 0
    while i < len(post_xml) - 32:
        sequence = []
        j = i

        while j < len(post_xml) - 4:
            try:
                val = struct.unpack("<f", post_xml[j : j + 4])[0]
                if -50 < val < 50 and val != 0:
                    sequence.append((j + xml_end, val))
                    j += 4
                else:
                    break
            except:
                break

        if len(sequence) >= 8:  # At least 4 XY pairs
            values = [s[1] for s in sequence]
            results.append(
                {
                    "offset": i + xml_end,
                    "count": len(sequence),
                    "values": values[:20],
                    "range": (min(values), max(values)),
                }
            )
            i = j
        else:
            i += 4

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python record_parser.py <pds_file>")
        sys.exit(1)

    pds_path = Path(sys.argv[1])
    data = pds_path.read_bytes()

    print(f"File: {pds_path.name}")
    print(f"Size: {len(data):,} bytes")

    # Find XML end
    xml_end = data.find(b"</STYLE>")
    if xml_end == -1:
        xml_end = data.find(b"</MARKER>")
    if xml_end > 0:
        xml_end += len(b"</STYLE>")

    print(f"XML ends at: {xml_end}")

    # Analyze structure
    analysis = analyze_post_xml_structure(data, xml_end)

    # Look for grading data
    print("\n" + "=" * 60)
    print("Looking for grading/delta data...")
    grading = find_grading_data(data, xml_end)
    print(f"Found {len(grading)} potential grading sequences")
    for g in grading[:5]:
        print(f"  @{g['offset']}: {g['count']} values, range {g['range']}")
        print(f"    preview: {[round(v, 4) for v in g['values'][:10]]}")

    # Let's look at the actual hex around the first size record
    if analysis["size_records"]:
        first_size = analysis["size_records"][0]
        print("\n" + "=" * 60)
        print(
            f"Detailed look at first size record ('{first_size['size_name']}' at {first_size['offset']}):"
        )

        # Get 200 bytes around the record
        start = max(xml_end, first_size["offset"] - 50)
        end = min(len(data), first_size["offset"] + 150)
        context = data[start:end]

        # Hex dump
        for i in range(0, len(context), 16):
            hex_part = " ".join(f"{b:02x}" for b in context[i : i + 16])
            ascii_part = "".join(
                chr(b) if 32 <= b < 127 else "." for b in context[i : i + 16]
            )
            print(f"{start + i:08x}  {hex_part:<48}  {ascii_part}")

    # Save analysis
    output_path = (
        pds_path.parent.parent
        / "out"
        / "binary_analysis"
        / f"{pds_path.stem}_records.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=2)

    print(f"\nAnalysis saved to: {output_path}")


if __name__ == "__main__":
    main()
