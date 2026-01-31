#!/usr/bin/env python3
"""
Improved embedded content extraction for PDS and MRK files.
Properly extracts complete XML sections and JPEG images.
"""

import re
import json
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import hashlib


def sha256_bytes(data: bytes) -> str:
    """Calculate SHA256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def find_xml_document(
    data: bytes, start_pos: int = 0
) -> Optional[Tuple[int, int, str]]:
    """
    Find a complete XML document starting from start_pos.
    Returns (start, end, root_tag) or None.
    """
    # Find XML declaration
    xml_decl = re.compile(b"<\\?xml[^?]*\\?>")
    match = xml_decl.search(data, start_pos)
    if not match:
        return None

    start = match.start()

    # After declaration, find root element
    # Skip whitespace and find the first <TAG
    pos = match.end()
    while pos < len(data) and data[pos : pos + 1] in (b" ", b"\n", b"\r", b"\t"):
        pos += 1

    if pos >= len(data) or data[pos : pos + 1] != b"<":
        return None

    # Extract root tag name
    root_match = re.match(b"<([A-Za-z_][A-Za-z0-9_]*)", data[pos : pos + 50])
    if not root_match:
        return None

    root_tag = root_match.group(1).decode("ascii")
    closing_tag = f"</{root_tag}>".encode("ascii")

    # Find the closing tag
    end = data.find(closing_tag, pos)
    if end == -1:
        return None

    end += len(closing_tag)
    return (start, end, root_tag)


def find_all_xml_documents(data: bytes) -> List[Tuple[int, int, str, bytes]]:
    """
    Find all complete XML documents in binary data.
    Returns list of (start, end, root_tag, xml_bytes).
    """
    results = []
    pos = 0

    while pos < len(data):
        result = find_xml_document(data, pos)
        if result is None:
            break

        start, end, root_tag = result
        xml_bytes = data[start:end]
        results.append((start, end, root_tag, xml_bytes))
        pos = end

    return results


def find_all_jpegs(data: bytes) -> List[Tuple[int, int, bytes]]:
    """
    Find all JPEG images in binary data.
    Returns list of (start, end, jpeg_bytes).
    """
    results = []

    # JPEG starts with FFD8FF, ends with FFD9
    jpeg_start = b"\xff\xd8\xff"
    jpeg_end = b"\xff\xd9"

    pos = 0
    while True:
        start = data.find(jpeg_start, pos)
        if start == -1:
            break

        end = data.find(jpeg_end, start + 3)
        if end == -1:
            break

        end += 2  # Include the end marker
        jpeg_bytes = data[start:end]
        results.append((start, end, jpeg_bytes))
        pos = end

    return results


def extract_from_file(filepath: Path, output_dir: Path) -> Dict:
    """
    Extract all embedded content from a PDS or MRK file.
    """
    data = filepath.read_bytes()
    file_type = "pds" if filepath.suffix.upper() == ".PDS" else "mrk"

    # Create output directory for this file
    file_output_dir = output_dir / filepath.stem
    file_output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "filename": filepath.name,
        "filesize": len(data),
        "sha256": sha256_bytes(data),
        "file_type": file_type,
        "magic": data[:4].hex(),
        "xml_documents": [],
        "jpeg_images": [],
        "notes": [],
    }

    # Extract XML documents
    xml_docs = find_all_xml_documents(data)
    for i, (start, end, root_tag, xml_bytes) in enumerate(xml_docs):
        out_file = file_output_dir / f"xml_{i:02d}_{root_tag}.xml"
        out_file.write_bytes(xml_bytes)

        result["xml_documents"].append(
            {
                "index": i,
                "root_tag": root_tag,
                "start_offset": start,
                "end_offset": end,
                "size": len(xml_bytes),
                "sha256": sha256_bytes(xml_bytes),
                "output_file": out_file.name,
            }
        )
        result["notes"].append(
            f"Extracted {root_tag} XML ({len(xml_bytes):,} bytes) to {out_file.name}"
        )

    # Extract JPEG images
    jpegs = find_all_jpegs(data)
    for i, (start, end, jpeg_bytes) in enumerate(jpegs):
        out_file = file_output_dir / f"image_{i:02d}.jpg"
        out_file.write_bytes(jpeg_bytes)

        result["jpeg_images"].append(
            {
                "index": i,
                "start_offset": start,
                "end_offset": end,
                "size": len(jpeg_bytes),
                "sha256": sha256_bytes(jpeg_bytes),
                "output_file": out_file.name,
            }
        )
        result["notes"].append(
            f"Extracted JPEG ({len(jpeg_bytes):,} bytes) to {out_file.name}"
        )

    # Save extraction manifest
    manifest_file = file_output_dir / "extraction_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_embedded.py <input_dir> <output_dir>")
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    files = list(input_dir.rglob("*.PDS")) + list(input_dir.rglob("*.MRK"))
    print(f"Found {len(files)} files to process")

    all_results = []

    for filepath in sorted(files):
        print(f"\nProcessing: {filepath.name}")
        result = extract_from_file(filepath, output_dir)
        all_results.append(result)

        print(f"  Size: {result['filesize']:,} bytes")
        print(f"  Magic: {result['magic']}")
        print(f"  XML documents: {len(result['xml_documents'])}")
        for doc in result["xml_documents"]:
            print(
                f"    - <{doc['root_tag']}> at offset {doc['start_offset']}, {doc['size']:,} bytes"
            )
        print(f"  JPEG images: {len(result['jpeg_images'])}")
        for img in result["jpeg_images"]:
            print(f"    - at offset {img['start_offset']}, {img['size']:,} bytes")

    # Save combined manifest
    combined_file = output_dir / "all_extractions.json"
    with open(combined_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n\nExtraction complete. Results saved to: {output_dir}")
    print(f"Combined manifest: {combined_file}")


if __name__ == "__main__":
    main()
