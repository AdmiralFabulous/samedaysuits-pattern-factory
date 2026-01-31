#!/usr/bin/env python3
"""
Binary reconnaissance for PDS and MRK files.
Extracts: header analysis, section boundaries, embedded content (XML, JPEG).
Outputs section_map.json + extracted blobs.
"""

import struct
import json
import re
import os
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional
import hashlib


@dataclass
class EmbeddedContent:
    """Represents embedded content found in the binary."""

    type: str  # 'xml', 'jpeg', 'unknown'
    start_offset: int
    end_offset: int
    size: int
    preview: str  # First 100 chars/bytes as string
    signature: str  # Magic bytes as hex


@dataclass
class HeaderAnalysis:
    """Analysis of file header."""

    magic: str  # First 4 bytes as hex
    magic_ascii: str  # First 4 bytes as ASCII (if printable)
    header_int32_le: List[int]  # First 64 bytes as int32 little-endian
    header_float32_le: List[float]  # First 64 bytes as float32 little-endian
    likely_version: Optional[str]
    likely_section_count: Optional[int]


@dataclass
class SectionMap:
    """Complete section map for a binary file."""

    filename: str
    filesize: int
    sha256: str
    file_type: str  # 'pds' or 'mrk'
    header: HeaderAnalysis
    embedded_content: List[EmbeddedContent]
    string_table_candidates: List[Dict]
    notes: List[str]


def sha256_file(filepath: Path) -> str:
    """Calculate SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def find_xml_sections(data: bytes) -> List[Tuple[int, int, str]]:
    """Find XML sections in binary data."""
    results = []

    # Look for XML declaration or common root tags
    patterns = [
        (b"<?xml", b"?>"),
        (b"<STYLE>", b"</STYLE>"),
        (b"<MARKER>", b"</MARKER>"),
        (b"<OPTITEX>", b"</OPTITEX>"),
        (b"<Pieces>", b"</Pieces>"),
    ]

    # Find all <?xml starts
    xml_decl_pattern = re.compile(b"<\\?xml[^?]*\\?>")
    for match in xml_decl_pattern.finditer(data):
        start = match.start()
        # Try to find the end of this XML document
        # Look for common closing tags
        end_candidates = []
        for closing in [b"</STYLE>", b"</MARKER>", b"</Pieces>", b"</Document>"]:
            pos = data.find(closing, start)
            if pos != -1:
                end_candidates.append(pos + len(closing))

        if end_candidates:
            end = min(end_candidates)
            preview = data[start : start + 200].decode("utf-8", errors="replace")
            results.append((start, end, preview[:100]))

    # Also look for XML-like content without declaration
    for start_tag, end_tag in patterns:
        pos = 0
        while True:
            start = data.find(start_tag, pos)
            if start == -1:
                break
            end = data.find(end_tag, start)
            if end != -1:
                end += len(end_tag)
                # Check if this overlaps with already found XML
                overlaps = any(s <= start < e or s < end <= e for s, e, _ in results)
                if not overlaps:
                    preview = data[start : start + 200].decode(
                        "utf-8", errors="replace"
                    )
                    results.append((start, end, preview[:100]))
            pos = start + 1

    return sorted(results, key=lambda x: x[0])


def find_jpeg_sections(data: bytes) -> List[Tuple[int, int]]:
    """Find JPEG sections in binary data."""
    results = []

    # JPEG starts with FFD8FF, ends with FFD9
    jpeg_start = b"\xff\xd8\xff"
    jpeg_end = b"\xff\xd9"

    pos = 0
    while True:
        start = data.find(jpeg_start, pos)
        if start == -1:
            break
        end = data.find(jpeg_end, start)
        if end != -1:
            end += 2  # Include the end marker
            results.append((start, end))
        pos = start + 1

    return results


def extract_strings(data: bytes, min_length: int = 6) -> List[Dict]:
    """Extract ASCII strings from binary."""
    results = []
    current_string = []
    current_start = 0

    for i, byte in enumerate(data):
        if 32 <= byte < 127:
            if not current_string:
                current_start = i
            current_string.append(chr(byte))
        else:
            if len(current_string) >= min_length:
                s = "".join(current_string)
                # Filter out likely garbage
                if not all(c in ".-_/\\" for c in s):
                    results.append(
                        {
                            "offset": current_start,
                            "length": len(s),
                            "string": s[:100],  # Truncate long strings
                        }
                    )
            current_string = []

    return results[:50]  # Limit output


def analyze_header(data: bytes) -> HeaderAnalysis:
    """Analyze file header."""
    header_bytes = data[:256]

    # Magic bytes
    magic = header_bytes[:4].hex()
    magic_ascii = "".join(chr(b) if 32 <= b < 127 else "." for b in header_bytes[:4])

    # Parse as integers and floats
    int32_le = list(struct.unpack("<64I", header_bytes[:256]))
    float32_le = list(struct.unpack("<64f", header_bytes[:256]))

    # Clean up float values (replace inf/nan)
    float32_le = [f if -1e10 < f < 1e10 else None for f in float32_le]

    # Try to identify version
    # Look for version-like patterns in first few int32 values
    likely_version = None
    if int32_le[1] < 100 and int32_le[2] < 1000:
        likely_version = f"{int32_le[1]}.{int32_le[2]}"

    # Section count is often in positions 4-8
    likely_section_count = None
    for i in range(4, 12):
        if 0 < int32_le[i] < 100:
            likely_section_count = int32_le[i]
            break

    return HeaderAnalysis(
        magic=magic,
        magic_ascii=magic_ascii,
        header_int32_le=int32_le[:16],  # First 16 int32 values
        header_float32_le=[f for f in float32_le[:16] if f is not None],
        likely_version=likely_version,
        likely_section_count=likely_section_count,
    )


def analyze_file(filepath: Path, output_dir: Path) -> SectionMap:
    """Perform full binary reconnaissance on a file."""
    data = filepath.read_bytes()
    file_type = "pds" if filepath.suffix.upper() == ".PDS" else "mrk"

    # Header analysis
    header = analyze_header(data)

    # Find embedded content
    embedded = []
    notes = []

    # XML sections
    xml_sections = find_xml_sections(data)
    for start, end, preview in xml_sections:
        embedded.append(
            EmbeddedContent(
                type="xml",
                start_offset=start,
                end_offset=end,
                size=end - start,
                preview=preview,
                signature=data[start : start + 20].hex(),
            )
        )
        notes.append(f"Found XML at offset {start}-{end} ({end - start} bytes)")

    # JPEG sections
    jpeg_sections = find_jpeg_sections(data)
    for start, end in jpeg_sections:
        embedded.append(
            EmbeddedContent(
                type="jpeg",
                start_offset=start,
                end_offset=end,
                size=end - start,
                preview=f"JPEG image ({end - start} bytes)",
                signature=data[start : start + 20].hex(),
            )
        )
        notes.append(f"Found JPEG at offset {start}-{end} ({end - start} bytes)")

    # String candidates
    strings = extract_strings(data)

    # Create output directory for this file
    file_output_dir = output_dir / filepath.stem
    file_output_dir.mkdir(parents=True, exist_ok=True)

    # Extract embedded content to files
    for i, emb in enumerate(embedded):
        if emb.type == "xml":
            xml_data = data[emb.start_offset : emb.end_offset]
            out_file = file_output_dir / f"embedded_{i:02d}.xml"
            out_file.write_bytes(xml_data)
            notes.append(f"Extracted XML to {out_file.name}")
        elif emb.type == "jpeg":
            jpeg_data = data[emb.start_offset : emb.end_offset]
            out_file = file_output_dir / f"embedded_{i:02d}.jpg"
            out_file.write_bytes(jpeg_data)
            notes.append(f"Extracted JPEG to {out_file.name}")

    section_map = SectionMap(
        filename=filepath.name,
        filesize=len(data),
        sha256=sha256_file(filepath),
        file_type=file_type,
        header=header,
        embedded_content=embedded,
        string_table_candidates=strings,
        notes=notes,
    )

    # Save section map
    map_file = file_output_dir / "section_map.json"
    with open(map_file, "w", encoding="utf-8") as f:
        json.dump(asdict(section_map), f, indent=2, default=str)

    return section_map


def main():
    if len(sys.argv) < 3:
        print("Usage: python binary_recon.py <input_dir> <output_dir>")
        print("  Analyzes all .PDS and .MRK files in input_dir")
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    files = list(input_dir.rglob("*.PDS")) + list(input_dir.rglob("*.MRK"))
    print(f"Found {len(files)} files to analyze")

    results = []
    for filepath in files:
        print(f"\nAnalyzing: {filepath.name}")
        section_map = analyze_file(filepath, output_dir)
        results.append(asdict(section_map))

        print(f"  Size: {section_map.filesize:,} bytes")
        print(f"  Magic: {section_map.header.magic} ({section_map.header.magic_ascii})")
        print(f"  Embedded content: {len(section_map.embedded_content)} items")
        for emb in section_map.embedded_content:
            print(f"    - {emb.type}: offset {emb.start_offset}, size {emb.size}")

    # Save combined results
    combined_file = output_dir / "all_files_analysis.json"
    with open(combined_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n\nResults saved to: {output_dir}")
    print(f"Combined analysis: {combined_file}")


if __name__ == "__main__":
    main()
