#!/usr/bin/env python3
"""
XML parsers for Optitex PDML (pattern) and MRK (marker) embedded XML.
Produces canonical models from extracted XML.
"""

import xml.etree.ElementTree as ET
import re
import sys
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from canonical_models import (
    PatternModel,
    MarkerModel,
    Piece,
    SizeInfo,
    Notch,
    DrillHole,
    InternalLine,
    Point2D,
    Contour,
    Placement,
    MarkerStyle,
    save_model,
)


def parse_position(pos_str: str) -> Tuple[float, float]:
    """Parse position string like 'X=-178.1978 Y=78.8914'."""
    x, y = 0.0, 0.0
    if pos_str:
        match_x = re.search(r"X=(-?[\d.]+)", pos_str)
        match_y = re.search(r"Y=(-?[\d.]+)", pos_str)
        if match_x:
            x = float(match_x.group(1))
        if match_y:
            y = float(match_y.group(1))
    return x, y


def get_text(elem: Optional[ET.Element], default: str = "") -> str:
    """Get text content of element, or default if None."""
    if elem is not None and elem.text:
        return elem.text.strip()
    return default


def get_float(elem: Optional[ET.Element], default: float = 0.0) -> float:
    """Get float value from element text."""
    text = get_text(elem)
    if text:
        try:
            return float(text)
        except ValueError:
            pass
    return default


def get_int(elem: Optional[ET.Element], default: int = 0) -> int:
    """Get int value from element text."""
    text = get_text(elem)
    if text:
        try:
            return int(text)
        except ValueError:
            pass
    return default


def parse_style_xml(xml_content: str) -> PatternModel:
    """
    Parse Optitex STYLE XML (from PDS embedded XML) to PatternModel.
    This is the XML found inside .PDS files with <STYLE> root.
    """
    root = ET.fromstring(xml_content)

    if root.tag != "STYLE":
        raise ValueError(f"Expected STYLE root element, got {root.tag}")

    model = PatternModel()

    # Metadata
    model.optitex_version = get_text(root.find("OPTITEX"))
    model.filename = get_text(root.find("FILENAME"))
    model.name = get_text(root.find("NAME"))
    model.date = get_text(root.find("DATE"))

    # Units
    units_elem = root.find("UNITS")
    if units_elem is not None:
        model.linear_units = units_elem.get("LINEAR", "cm")
        model.area_units = units_elem.get("SQUARE", "sq.m")

    # Sizes table
    sizes_table = root.find("SIZES_TABLE")
    if sizes_table is not None:
        for size_elem in sizes_table.findall("SIZE"):
            size_name = get_text(size_elem.find("NAME"))
            if size_name:
                model.sizes.append(size_name)

        base_size_elem = sizes_table.find("BASE_SIZE")
        if base_size_elem is not None:
            model.base_size = get_text(base_size_elem)

    # Pieces
    for piece_elem in root.findall("PIECE"):
        piece = Piece(
            name=get_text(piece_elem.find("NAME")),
            code=get_text(piece_elem.find("CODE")),
            unique_id=get_text(piece_elem.find("UNIQUE")),
            description=get_text(piece_elem.find("DESCRIPTION")),
            material=get_text(piece_elem.find("MATERIAL")),
            quantity=get_int(piece_elem.find("QUANTITY"), 1),
        )

        # Position
        pos_str = get_text(piece_elem.find("POSITION"))
        piece.position_x, piece.position_y = parse_position(pos_str)

        # Nesting enables
        nesting = piece_elem.find("NESTING_ENABLES")
        if nesting is not None:
            piece.rotation_allowed = nesting.get("ROTATION", "None")
            piece.flip_allowed = nesting.get("OPPOSITE", "None")
            tilt_str = nesting.get("TILT", "0.0 deg.")
            tilt_match = re.search(r"([\d.]+)", tilt_str)
            if tilt_match:
                piece.tilt = float(tilt_match.group(1))

        # Size-specific geometry info
        for size_elem in piece_elem.findall("SIZE"):
            size_name = get_text(size_elem.find("NAME"))
            geom = size_elem.find("GEOM_INFO")
            if geom is not None:
                size_info = SizeInfo(
                    name=size_name,
                    size_x=float(geom.get("SIZE_X", 0)),
                    size_y=float(geom.get("SIZE_Y", 0)),
                    area=float(geom.get("AREA", 0)),
                    perimeter=float(geom.get("PERIMETER", 0)),
                    sew_area=float(geom.get("SEW_AREA", 0)),
                    sew_perimeter=float(geom.get("SEW_PERIMETER", 0)),
                )
                piece.size_info.append(size_info)

        # Internals (notches info - counts only in this XML, not coordinates)
        internals_elem = piece_elem.find("INTERNALS")
        if internals_elem is not None:
            notch_elem = internals_elem.find("NOTCH")
            if notch_elem is not None:
                # T_NOTCH, V_NOTCH, etc.
                for notch_type_elem in notch_elem:
                    if notch_type_elem.tag.endswith("_NOTCH"):
                        count = get_int(notch_type_elem.find("COUNT"), 0)
                        # Note: coordinates not in this XML format

        model.pieces.append(piece)

    return model


def parse_marker_xml(xml_content: str) -> MarkerModel:
    """
    Parse Optitex MARKER XML (from MRK embedded XML) to MarkerModel.
    This is the XML found inside .MRK files with <MARKER> root.
    """
    root = ET.fromstring(xml_content)

    if root.tag != "MARKER":
        raise ValueError(f"Expected MARKER root element, got {root.tag}")

    model = MarkerModel()

    # Metadata
    model.optitex_version = get_text(root.find("OPTITEX"))
    model.filename = get_text(root.find("FILENAME"))
    model.name = get_text(root.find("NAME"))
    model.date = get_text(root.find("DATE"))

    # Nesting info
    nest_elem = root.find("NEST")
    if nest_elem is not None:
        model.nest_name = get_text(nest_elem.find("NAME"))
        model.nest_version = get_text(nest_elem.find("VERSION"))

    # Units
    units_elem = root.find("UNITS")
    if units_elem is not None:
        model.linear_units = units_elem.get("LINEAR", "cm")
        model.area_units = units_elem.get("SQUARE", "sq.m")

    # Fabric dimensions
    model.length = get_float(root.find("LENGTH"))
    model.width = get_float(root.find("WIDTH"))

    # Layout
    model.layout_mode = get_text(root.find("LAYOUT_MODE"), "Single")
    model.folding = get_text(root.find("FOLDING"), "none")
    model.num_plies = get_int(root.find("NB_OF_PLIES"), 1)

    # Stats
    model.efficiency = get_float(root.find("EFFICIENCY"))
    model.total_area = get_float(root.find("SUM_AREA"))
    model.total_perimeter = get_float(root.find("SUM_PERIMETER"))
    model.placed_count = get_int(root.find("PLACED_ON_TABLE"))

    # Notches summary
    notches_elem = root.find("NOTCHES")
    if notches_elem is not None:
        cut_elem = notches_elem.find("CUT")
        if cut_elem is not None:
            model.notch_count = get_int(cut_elem.find("QUANTITY"))
            model.notch_cut_length = get_float(cut_elem.find("SUM_LENGTH"))

    # Styles with placements
    for style_elem in root.findall("STYLE"):
        style = MarkerStyle(
            name=get_text(style_elem.find("NAME")),
            filename=get_text(style_elem.find("FILENAME")),
            material=get_text(style_elem.find("MATERIAL")),
        )

        # Sizes
        for size_elem in style_elem.findall("SIZE"):
            size_name = get_text(size_elem.find("NAME"))
            placements = []

            # Pieces in this size
            for piece_elem in size_elem.findall("PIECE"):
                piece_name = get_text(piece_elem.find("NAME"))
                piece_code = get_text(piece_elem.find("CODE"))

                # Geometry info
                geom = piece_elem.find("GEOM_INFO")
                size_x = float(geom.get("SIZE_X", 0)) if geom is not None else 0.0
                size_y = float(geom.get("SIZE_Y", 0)) if geom is not None else 0.0
                area = float(geom.get("AREA", 0)) if geom is not None else 0.0
                perimeter = float(geom.get("PERIMETER", 0)) if geom is not None else 0.0

                # Placements
                placed_elem = piece_elem.find("PLACED")
                if placed_elem is not None:
                    for pos_elem in placed_elem.findall("POSITION"):
                        placement = Placement(
                            piece_name=piece_name,
                            piece_code=piece_code,
                            size_name=size_name,
                            x_center=float(pos_elem.get("X-CENTER", 0)),
                            y_center=float(pos_elem.get("Y-CENTER", 0)),
                            angle=float(pos_elem.get("ANGLE", 0)),
                            flip=pos_elem.get("FLIP", "no"),
                            size_x=size_x,
                            size_y=size_y,
                            area=area,
                            perimeter=perimeter,
                        )
                        placements.append(placement)

            if placements:
                style.sizes[size_name] = placements

        model.styles.append(style)

    return model


def parse_xml_file(xml_path: str) -> Tuple[str, object]:
    """
    Parse an XML file and return (type, model) where type is 'pattern' or 'marker'.
    """
    with open(xml_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Determine type by root element
    if "<STYLE>" in content[:500]:
        return "pattern", parse_style_xml(content)
    elif "<MARKER>" in content[:500]:
        return "marker", parse_marker_xml(content)
    else:
        raise ValueError(f"Unknown XML format in {xml_path}")


def main():
    """Parse extracted XML files and produce canonical JSON."""
    if len(sys.argv) < 3:
        print("Usage: python xml_parser.py <xml_file_or_dir> <output_dir>")
        print("  Parses Optitex XML files and produces canonical JSON")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect XML files
    if input_path.is_file():
        xml_files = [input_path]
    else:
        xml_files = list(input_path.rglob("*.xml"))

    print(f"Found {len(xml_files)} XML files to parse")

    results = {"patterns": [], "markers": [], "errors": []}

    for xml_file in xml_files:
        print(f"\nParsing: {xml_file.name} (from {xml_file.parent.name})")
        try:
            model_type, model = parse_xml_file(str(xml_file))

            # Save canonical JSON - include parent folder name for uniqueness
            parent_name = xml_file.parent.name
            out_name = f"{parent_name}_{xml_file.stem}_canonical.json"
            out_path = output_dir / out_name
            save_model(model, str(out_path))

            if model_type == "pattern":
                results["patterns"].append(
                    {
                        "source": str(xml_file),
                        "output": str(out_path),
                        "pieces": len(model.pieces),
                        "sizes": len(model.sizes),
                    }
                )
                print(f"  Type: PATTERN")
                print(f"  Pieces: {len(model.pieces)}, Sizes: {len(model.sizes)}")
            else:
                results["markers"].append(
                    {
                        "source": str(xml_file),
                        "output": str(out_path),
                        "styles": len(model.styles),
                        "placements": model.placed_count,
                    }
                )
                print(f"  Type: MARKER")
                print(
                    f"  Styles: {len(model.styles)}, Placements: {model.placed_count}"
                )

            print(f"  Saved: {out_path}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results["errors"].append({"file": str(xml_file), "error": str(e)})

    # Summary
    print(f"\n\n=== SUMMARY ===")
    print(f"Patterns parsed: {len(results['patterns'])}")
    print(f"Markers parsed: {len(results['markers'])}")
    print(f"Errors: {len(results['errors'])}")

    return results


if __name__ == "__main__":
    main()
