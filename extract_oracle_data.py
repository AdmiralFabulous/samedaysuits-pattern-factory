#!/usr/bin/env python3
"""
Extract and correlate data from Optitex oracle files (PDML + DXF).

This script:
1. Extracts embedded XML from PDML files
2. Parses DXF files to extract piece geometry
3. Correlates piece metadata with actual coordinates
4. Outputs a comprehensive mapping for reverse engineering

Author: Claude
Date: 2026-01-30
"""

import os
import re
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional
import struct


@dataclass
class Point:
    """A 2D point with optional metadata."""

    x: float
    y: float
    bulge: float = 0.0  # DXF bulge for curves

    def __repr__(self):
        return f"({self.x:.4f}, {self.y:.4f})"


@dataclass
class Piece:
    """A pattern piece with metadata and geometry."""

    name: str
    code: str
    unique_id: str
    material: str
    quantity: int
    position: Tuple[float, float]
    sizes: Dict[
        str, Dict[str, float]
    ]  # size_name -> {SIZE_X, SIZE_Y, AREA, PERIMETER, ...}
    contour_points: List[Point] = field(default_factory=list)


@dataclass
class StyleData:
    """Complete style data extracted from oracle files."""

    name: str
    optitex_version: str
    units_linear: str
    units_square: str
    filename: str
    date: str
    num_sizes: int
    num_pieces: int
    size_names: List[str]
    base_size: str
    pieces: List[Piece]


def extract_xml_from_pdml(pdml_path: str) -> str:
    """Extract embedded XML content from PDML file."""
    with open(pdml_path, "rb") as f:
        data = f.read()

    # Find XML start
    xml_start = data.find(b"<?xml")
    if xml_start == -1:
        raise ValueError("No XML found in PDML file")

    # Find XML end (</STYLE>)
    xml_end = data.find(b"</STYLE>", xml_start)
    if xml_end == -1:
        raise ValueError("No </STYLE> found in PDML file")

    xml_content = data[xml_start : xml_end + len(b"</STYLE>")].decode(
        "utf-8", errors="replace"
    )
    return xml_content


def parse_pdml_xml(xml_content: str) -> StyleData:
    """Parse PDML XML content into structured data."""
    # Fix any encoding issues
    xml_content = xml_content.replace("\x00", "")

    root = ET.fromstring(xml_content)

    # Extract basic metadata
    optitex_version = (
        root.find("OPTITEX").text if root.find("OPTITEX") is not None else ""
    )
    units = root.find("UNITS")
    units_linear = units.get("LINEAR", "cm") if units is not None else "cm"
    units_square = units.get("SQUARE", "sq.m") if units is not None else "sq.m"

    name = root.find("NAME").text if root.find("NAME") is not None else ""
    filename = root.find("FILENAME").text if root.find("FILENAME") is not None else ""
    date = root.find("DATE").text if root.find("DATE") is not None else ""
    num_sizes = int(root.find("SIZES").text) if root.find("SIZES") is not None else 0
    num_pieces = int(root.find("PIECES").text) if root.find("PIECES") is not None else 0

    # Extract size names from SIZES_TABLE
    size_names = []
    base_size = ""
    sizes_table = root.find("SIZES_TABLE")
    if sizes_table is not None:
        for size_elem in sizes_table.findall("SIZE"):
            name_elem = size_elem.find("NAME")
            if name_elem is not None and name_elem.text:
                size_names.append(name_elem.text)
        base_size_elem = sizes_table.find("BASE_SIZE")
        if base_size_elem is not None:
            base_size = base_size_elem.text or ""

    # Extract pieces
    pieces = []
    for piece_elem in root.findall("PIECE"):
        piece_name = (
            piece_elem.find("NAME").text if piece_elem.find("NAME") is not None else ""
        )
        piece_code = (
            piece_elem.find("CODE").text if piece_elem.find("CODE") is not None else ""
        )
        unique_id = (
            piece_elem.find("UNIQUE").text
            if piece_elem.find("UNIQUE") is not None
            else ""
        )
        material = (
            piece_elem.find("MATERIAL").text
            if piece_elem.find("MATERIAL") is not None
            else ""
        )
        quantity_text = (
            piece_elem.find("QUANTITY").text
            if piece_elem.find("QUANTITY") is not None
            else "1"
        )
        quantity = int(quantity_text) if quantity_text else 1

        # Parse position
        position = (0.0, 0.0)
        pos_elem = piece_elem.find("POSITION")
        if pos_elem is not None and pos_elem.text:
            # Format: "X=-57.7847 Y=45.4000"
            match = re.search(r"X=([-.0-9]+)\s+Y=([-.0-9]+)", pos_elem.text)
            if match:
                position = (float(match.group(1)), float(match.group(2)))

        # Extract size-specific geometry info
        sizes = {}
        for size_elem in piece_elem.findall("SIZE"):
            size_name_elem = size_elem.find("NAME")
            size_name = size_name_elem.text if size_name_elem is not None else ""

            geom_info = size_elem.find("GEOM_INFO")
            if geom_info is not None:
                sizes[size_name] = {
                    "SIZE_X": float(geom_info.get("SIZE_X", 0)),
                    "SIZE_Y": float(geom_info.get("SIZE_Y", 0)),
                    "AREA": float(geom_info.get("AREA", 0)),
                    "PERIMETER": float(geom_info.get("PERIMETER", 0)),
                    "SEW_AREA": float(geom_info.get("SEW_AREA", 0)),
                    "SEW_PERIMETER": float(geom_info.get("SEW_PERIMETER", 0)),
                }

        pieces.append(
            Piece(
                name=piece_name,
                code=piece_code,
                unique_id=unique_id,
                material=material,
                quantity=quantity,
                position=position,
                sizes=sizes,
            )
        )

    return StyleData(
        name=name,
        optitex_version=optitex_version,
        units_linear=units_linear,
        units_square=units_square,
        filename=filename,
        date=date,
        num_sizes=num_sizes,
        num_pieces=num_pieces,
        size_names=size_names,
        base_size=base_size,
        pieces=pieces,
    )


def parse_dxf_entities(dxf_path: str) -> Dict[str, List[List[Point]]]:
    """Parse DXF file and extract piece contours.

    Returns a dict mapping piece names to lists of contour polylines.
    """
    with open(dxf_path, "r") as f:
        lines = f.readlines()

    pieces = {}
    current_piece_name = None
    current_size = None
    current_polyline = []
    in_polyline = False
    in_entities = False

    i = 0
    while i < len(lines):
        code = lines[i].strip()
        i += 1
        if i >= len(lines):
            break
        value = lines[i].strip()
        i += 1

        # Track section
        if code == "2" and value == "ENTITIES":
            in_entities = True
            continue
        if code == "0" and value == "ENDSEC":
            in_entities = False
            continue

        if not in_entities:
            continue

        # TEXT entity - may contain piece name or size
        if code == "0" and value == "TEXT":
            # Read ahead to find the text content
            while i < len(lines):
                tc = lines[i].strip()
                i += 1
                if i >= len(lines):
                    break
                tv = lines[i].strip()
                i += 1

                if tc == "1":  # Text content
                    if tv.startswith("Piece Name:"):
                        current_piece_name = tv.replace("Piece Name:", "").strip()
                        if current_piece_name not in pieces:
                            pieces[current_piece_name] = []
                    elif tv.startswith("Size:"):
                        current_size = tv.replace("Size:", "").strip()
                    break
                if tc == "0":  # Next entity
                    i -= 2  # Back up to reprocess
                    break
            continue

        # POLYLINE entity
        if code == "0" and value == "POLYLINE":
            in_polyline = True
            current_polyline = []
            continue

        # VERTEX within POLYLINE
        if code == "0" and value == "VERTEX" and in_polyline:
            x, y, bulge = 0.0, 0.0, 0.0
            while i < len(lines):
                vc = lines[i].strip()
                i += 1
                if i >= len(lines):
                    break
                vv = lines[i].strip()
                i += 1

                if vc == "10":
                    x = float(vv)
                elif vc == "20":
                    y = float(vv)
                elif vc == "42":
                    bulge = float(vv)
                elif vc == "0":  # Next entity
                    i -= 2
                    break

            current_polyline.append(Point(x, y, bulge))
            continue

        # SEQEND - end of polyline
        if code == "0" and value == "SEQEND" and in_polyline:
            in_polyline = False
            if current_piece_name and current_polyline:
                pieces[current_piece_name].append(current_polyline)
            current_polyline = []
            continue

    return pieces


def correlate_pdml_dxf(pdml_path: str, dxf_path: str, output_path: str):
    """Correlate PDML metadata with DXF geometry and output combined data."""
    print(f"\n=== Extracting Oracle Data ===")
    print(f"PDML: {pdml_path}")
    print(f"DXF:  {dxf_path}")

    # Extract and parse PDML
    print("\n1. Extracting XML from PDML...")
    xml_content = extract_xml_from_pdml(pdml_path)
    print(f"   XML extracted: {len(xml_content)} bytes")

    print("\n2. Parsing PDML metadata...")
    style_data = parse_pdml_xml(xml_content)
    print(f"   Style: {style_data.name}")
    print(f"   Optitex Version: {style_data.optitex_version}")
    print(f"   Units: {style_data.units_linear}")
    print(f"   Sizes: {style_data.num_sizes} ({', '.join(style_data.size_names)})")
    print(f"   Base Size: {style_data.base_size}")
    print(f"   Pieces: {style_data.num_pieces}")
    for p in style_data.pieces:
        print(
            f"     - {p.name} (ID: {p.unique_id}, Material: {p.material}, Qty: {p.quantity})"
        )

    # Parse DXF
    print("\n3. Parsing DXF geometry...")
    dxf_pieces = parse_dxf_entities(dxf_path)
    print(f"   Found {len(dxf_pieces)} pieces with contours:")
    for name, contours in dxf_pieces.items():
        total_points = sum(len(c) for c in contours)
        print(f"     - {name}: {len(contours)} contours, {total_points} total points")

    # Correlate - add DXF geometry to PDML pieces
    print("\n4. Correlating PDML + DXF...")
    for piece in style_data.pieces:
        if piece.name in dxf_pieces:
            # Flatten all contours into one list for simplicity
            all_points = []
            for contour in dxf_pieces[piece.name]:
                all_points.extend(contour)
            piece.contour_points = all_points
            print(f"   {piece.name}: {len(all_points)} points matched")
        else:
            print(f"   {piece.name}: No DXF geometry found (WARNING)")

    # Output combined data
    print(f"\n5. Writing output to {output_path}...")

    # Convert to serializable format
    output_data = {
        "style": {
            "name": style_data.name,
            "optitex_version": style_data.optitex_version,
            "units_linear": style_data.units_linear,
            "units_square": style_data.units_square,
            "filename": style_data.filename,
            "date": style_data.date,
            "num_sizes": style_data.num_sizes,
            "num_pieces": style_data.num_pieces,
            "size_names": style_data.size_names,
            "base_size": style_data.base_size,
        },
        "pieces": [],
    }

    for piece in style_data.pieces:
        piece_data = {
            "name": piece.name,
            "code": piece.code,
            "unique_id": piece.unique_id,
            "material": piece.material,
            "quantity": piece.quantity,
            "position": {"x": piece.position[0], "y": piece.position[1]},
            "sizes": piece.sizes,
            "contour_points": [
                {"x": p.x, "y": p.y, "bulge": p.bulge} for p in piece.contour_points
            ],
            "num_points": len(piece.contour_points),
        }
        output_data["pieces"].append(piece_data)

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"   Done! Output size: {os.path.getsize(output_path)} bytes")

    return output_data


def main():
    """Main entry point."""
    # Paths
    base_dir = Path(__file__).parent
    oracle_dir = base_dir / "DS-speciale" / "oracle" / "pds"
    output_dir = base_dir / "DS-speciale" / "oracle" / "extracted"
    output_dir.mkdir(exist_ok=True)

    # Process Basic Tee (we have both PDML + DXF)
    pdml_path = oracle_dir / "Basic Tee_2D.PDML"
    dxf_path = oracle_dir / "Basic Tee_2D.dxf"
    output_path = output_dir / "Basic Tee_2D_oracle.json"

    if pdml_path.exists() and dxf_path.exists():
        data = correlate_pdml_dxf(str(pdml_path), str(dxf_path), str(output_path))

        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY: Oracle Data Extracted")
        print("=" * 60)
        print(f"\nStyle: {data['style']['name']}")
        print(f"Pieces extracted with geometry:")
        for p in data["pieces"]:
            print(f"  - {p['name']}: {p['num_points']} contour points")
            if p["sizes"]:
                base_size = data["style"]["base_size"]
                if base_size in p["sizes"]:
                    info = p["sizes"][base_size]
                    print(
                        f"    Base size ({base_size}): {info['SIZE_X']:.2f} x {info['SIZE_Y']:.2f} cm"
                    )
                    print(
                        f"    Area: {info['AREA']:.4f} sq.m, Perimeter: {info['PERIMETER']:.2f} cm"
                    )
    else:
        print(f"ERROR: Missing oracle files")
        print(f"  PDML exists: {pdml_path.exists()}")
        print(f"  DXF exists: {dxf_path.exists()}")


if __name__ == "__main__":
    main()
