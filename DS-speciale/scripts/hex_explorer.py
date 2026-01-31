#!/usr/bin/env python3
"""
Hex explorer for PDS files - examine raw binary structure.
"""

import struct
import sys
import zlib
from pathlib import Path
from typing import List, Dict, Tuple
import math


def hex_dump(
    data: bytes, start: int = 0, length: int = 256, bytes_per_line: int = 16
) -> str:
    """Generate hex dump with ASCII interpretation."""
    lines = []
    for i in range(0, min(length, len(data)), bytes_per_line):
        offset = start + i
        hex_part = " ".join(f"{b:02x}" for b in data[i : i + bytes_per_line])
        ascii_part = "".join(
            chr(b) if 32 <= b < 127 else "." for b in data[i : i + bytes_per_line]
        )
        lines.append(f"{offset:08x}  {hex_part:<{bytes_per_line * 3}}  {ascii_part}")
    return "\n".join(lines)


def interpret_bytes(data: bytes, offset: int = 0) -> Dict:
    """Interpret bytes at offset as various data types."""
    result = {}

    if len(data) >= 4:
        result["uint32_le"] = struct.unpack("<I", data[:4])[0]
        result["int32_le"] = struct.unpack("<i", data[:4])[0]
        result["float32_le"] = struct.unpack("<f", data[:4])[0]

    if len(data) >= 8:
        result["uint64_le"] = struct.unpack("<Q", data[:8])[0]
        result["int64_le"] = struct.unpack("<q", data[:8])[0]
        result["float64_le"] = struct.unpack("<d", data[:8])[0]

    if len(data) >= 2:
        result["uint16_le"] = struct.unpack("<H", data[:2])[0]
        result["int16_le"] = struct.unpack("<h", data[:2])[0]

    return result


def analyze_header(data: bytes) -> None:
    """Analyze the file header structure."""
    print("\n=== FILE HEADER ANALYSIS ===")
    print(hex_dump(data, 0, 128))

    print("\n--- Header fields ---")
    print(f"Magic: {data[0:4].hex()} ({struct.unpack('<I', data[0:4])[0]})")

    # Dump first 32 uint32 values
    print("\nFirst 32 uint32 values:")
    for i in range(32):
        offset = i * 4
        if offset + 4 <= len(data):
            val = struct.unpack("<I", data[offset : offset + 4])[0]
            print(f"  [{offset:4d}] {val:10d}  (0x{val:08x})")


def analyze_post_xml(data: bytes, xml_end: int) -> None:
    """Analyze structure immediately after XML."""
    print(f"\n=== POST-XML ANALYSIS (starting at {xml_end}) ===")
    post_xml = data[xml_end:]

    print("\nFirst 256 bytes after XML:")
    print(hex_dump(post_xml, xml_end, 256))

    # Try to identify structure
    print("\n--- Interpreting header values ---")
    for i in range(0, 64, 4):
        if i + 8 <= len(post_xml):
            vals = interpret_bytes(post_xml[i : i + 8], xml_end + i)
            print(
                f"[{xml_end + i:6d}] u32={vals.get('uint32_le', 'N/A'):10d}, i32={vals.get('int32_le', 'N/A'):10d}, f32={vals.get('float32_le', 'N/A'):.4f}"
            )


def analyze_decompressed(data: bytes, zlib_offset: int) -> None:
    """Analyze decompressed zlib data."""
    print(f"\n=== DECOMPRESSING DATA AT {zlib_offset} ===")

    try:
        decompressor = zlib.decompressobj(15)
        decompressed = decompressor.decompress(data[zlib_offset:])
        print(f"Decompressed: {len(decompressed):,} bytes")

        print("\nFirst 512 bytes of decompressed data:")
        print(hex_dump(decompressed, 0, 512))

        # Look for patterns
        print("\n--- Pattern analysis ---")

        # Count occurrences of common sizes
        sizes_4 = {}
        for i in range(0, len(decompressed) - 4, 4):
            val = struct.unpack("<I", decompressed[i : i + 4])[0]
            if 1 < val < 10000:  # Reasonable counts
                sizes_4[val] = sizes_4.get(val, 0) + 1

        print("Most common uint32 values (1-10000):")
        for val, count in sorted(sizes_4.items(), key=lambda x: -x[1])[:20]:
            print(f"  {val:5d}: {count:3d} occurrences")

        # Look for sequential patterns that might indicate record structure
        print("\n--- Trying to detect record structure ---")

        # Check if data looks like fixed-size records
        for record_size in [8, 12, 16, 20, 24, 32, 40, 48, 64]:
            if len(decompressed) >= record_size * 10:
                # Check variance between records
                records = []
                for i in range(
                    0, min(len(decompressed), record_size * 100), record_size
                ):
                    records.append(decompressed[i : i + record_size])

                # Check if first byte of each record is similar
                first_bytes = [r[0] for r in records if len(r) > 0]
                unique_first = len(set(first_bytes))

                print(
                    f"  Record size {record_size}: {len(records)} records, {unique_first} unique first bytes"
                )

        # Look for float64 sequences
        print("\n--- Looking for float64 sequences ---")
        f64_sequences = []
        i = 0
        while i < len(decompressed) - 16:
            vals = []
            j = i
            while j < len(decompressed) - 8:
                try:
                    v = struct.unpack("<d", decompressed[j : j + 8])[0]
                    if -1000 < v < 1000 and not math.isnan(v) and not math.isinf(v):
                        vals.append(v)
                        j += 8
                    else:
                        break
                except:
                    break

            if len(vals) >= 4:
                f64_sequences.append(
                    {
                        "offset": i,
                        "count": len(vals),
                        "preview": vals[:10],
                        "min": min(vals),
                        "max": max(vals),
                    }
                )
                i = j
            else:
                i += 8

        print(f"Found {len(f64_sequences)} float64 sequences")
        for seq in f64_sequences[:10]:
            print(
                f"  @{seq['offset']:6d}: {seq['count']:4d} values, range [{seq['min']:.2f}, {seq['max']:.2f}]"
            )
            print(f"           preview: {[round(v, 4) for v in seq['preview']]}")

        # Save decompressed data for further analysis
        output_path = (
            Path(sys.argv[1]).parent.parent
            / "out"
            / "binary_analysis"
            / "decompressed_main.bin"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(decompressed)
        print(f"\nSaved decompressed data to: {output_path}")

    except Exception as e:
        print(f"Decompression failed: {e}")


def find_zlib_streams(data: bytes) -> List[int]:
    """Find all zlib stream offsets."""
    offsets = []
    for sig in [b"\x78\xda", b"\x78\x9c", b"\x78\x5e", b"\x78\x01"]:
        offset = 0
        while True:
            pos = data.find(sig, offset)
            if pos == -1:
                break
            offsets.append(pos)
            offset = pos + 1
    return sorted(set(offsets))


def main():
    if len(sys.argv) < 2:
        print("Usage: python hex_explorer.py <pds_file>")
        sys.exit(1)

    pds_path = Path(sys.argv[1])
    data = pds_path.read_bytes()

    print(f"File: {pds_path.name}")
    print(f"Size: {len(data):,} bytes")

    # Find XML boundaries
    xml_start = data.find(b"<?xml")
    xml_end = data.find(b"</STYLE>")
    if xml_end > 0:
        xml_end += len(b"</STYLE>")

    print(f"XML: {xml_start} - {xml_end} ({xml_end - xml_start:,} bytes)")
    print(f"Post-XML: {len(data) - xml_end:,} bytes")

    # Analyze header
    analyze_header(data)

    # Analyze post-XML
    analyze_post_xml(data, xml_end)

    # Find and analyze zlib streams
    zlib_offsets = find_zlib_streams(data)
    print(f"\n=== ZLIB STREAMS ({len(zlib_offsets)} found) ===")
    for offset in zlib_offsets:
        print(f"  {offset}")

    # Analyze largest decompressed stream
    if zlib_offsets:
        # Find largest
        largest = None
        largest_size = 0
        for offset in zlib_offsets:
            try:
                decompressor = zlib.decompressobj(15)
                decompressed = decompressor.decompress(data[offset:])
                if len(decompressed) > largest_size:
                    largest = offset
                    largest_size = len(decompressed)
            except:
                pass

        if largest:
            analyze_decompressed(data, largest)


if __name__ == "__main__":
    main()
