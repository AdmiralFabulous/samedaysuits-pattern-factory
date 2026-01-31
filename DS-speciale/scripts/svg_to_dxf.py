#!/usr/bin/env python3
"""
Convert embedded SVG geometry from PDS/MRK files to DXF.
Uses actual contour coordinates extracted from the embedded SVG.
"""

import re
import json
import sys
import math
from pathlib import Path
from typing import List, Dict, Tuple


def parse_svg_points(points_str: str) -> List[Tuple[float, float]]:
    """Parse SVG polygon points attribute."""
    points = []
    parts = points_str.strip().split()
    for part in parts:
        if "," in part:
            x, y = part.split(",")
            try:
                points.append((float(x), float(y)))
            except ValueError:
                pass
    return points


def parse_svg_path(d: str) -> List[Tuple[float, float]]:
    """Parse SVG path 'd' attribute."""
    points = []
    d = d.replace(",", " ")
    d = re.sub(r"\s+", " ", d).strip()

    tokens = re.split(r"([MLHVCSQTAZ])", d, flags=re.IGNORECASE)

    current_x, current_y = 0, 0
    i = 0

    while i < len(tokens):
        token = tokens[i].strip()
        if not token:
            i += 1
            continue

        cmd = token.upper()
        is_relative = token.islower()

        if cmd in "ML":
            i += 1
            if i < len(tokens):
                coords = tokens[i].strip().split()
                j = 0
                while j + 1 < len(coords):
                    try:
                        x = float(coords[j])
                        y = float(coords[j + 1])
                        if is_relative:
                            x += current_x
                            y += current_y
                        points.append((x, y))
                        current_x, current_y = x, y
                        j += 2
                    except ValueError:
                        j += 1
            i += 1
        elif cmd == "H":
            i += 1
            if i < len(tokens):
                try:
                    x = float(tokens[i].strip())
                    if is_relative:
                        x += current_x
                    points.append((x, current_y))
                    current_x = x
                except ValueError:
                    pass
            i += 1
        elif cmd == "V":
            i += 1
            if i < len(tokens):
                try:
                    y = float(tokens[i].strip())
                    if is_relative:
                        y += current_y
                    points.append((current_x, y))
                    current_y = y
                except ValueError:
                    pass
            i += 1
        elif cmd == "Z":
            if points and points[0] != points[-1]:
                points.append(points[0])
            i += 1
        elif cmd == "C":
            i += 1
            if i < len(tokens):
                coords = tokens[i].strip().split()
                j = 4
                while j + 1 < len(coords):
                    try:
                        x = float(coords[j])
                        y = float(coords[j + 1])
                        if is_relative:
                            x += current_x
                            y += current_y
                        points.append((x, y))
                        current_x, current_y = x, y
                        j += 6
                    except ValueError:
                        j += 1
            i += 1
        else:
            i += 1

    return points


def extract_svg_shapes(xml_text: str) -> Dict:
    """Extract all shapes from embedded SVG in XML."""
    result = {
        "view_factor": None,
        "viewbox": None,
        "scale": 0.01,  # Default: 1 unit = 0.01 cm
        "polygons": [],
        "paths": [],
    }

    # Find VIEW factor
    view_match = re.search(r'<VIEW[^>]*FACTOR="([^"]+)"', xml_text)
    if view_match:
        result["view_factor"] = float(view_match.group(1))

    # Find SVG viewBox and compute scale
    svg_tag_match = re.search(r"<svg([^>]*)>", xml_text, re.IGNORECASE)
    if svg_tag_match:
        svg_attrs = svg_tag_match.group(1)

        vb = re.search(r'viewBox="([^"]+)"', svg_attrs)
        if vb:
            result["viewbox"] = vb.group(1)
            vb_parts = vb.group(1).split()
            if len(vb_parts) == 4:
                vb_w = float(vb_parts[2])

        w = re.search(r'width="([\d.]+)(\w+)?"', svg_attrs)
        if w and vb:
            phys_w = float(w.group(1))
            vb_w = float(vb.group(1).split()[2])
            result["scale"] = phys_w / vb_w  # cm per SVG unit

    # Extract polygons
    svg_content = xml_text
    for poly in re.finditer(r'<polygon[^>]*points="([^"]+)"[^/]*/>', svg_content):
        points = parse_svg_points(poly.group(1))
        if len(points) >= 3:
            result["polygons"].append(points)

    # Extract paths
    for path in re.finditer(r'<path[^>]*d="([^"]+)"[^/]*/>', svg_content):
        points = parse_svg_path(path.group(1))
        if len(points) >= 3:
            result["paths"].append(points)

    return result


def write_dxf(shapes: Dict, output_path: str, scale: float = 1.0, flip_y: bool = True):
    """Write shapes to DXF file."""
    lines = []

    # Header
    lines.extend(
        [
            "0",
            "SECTION",
            "2",
            "HEADER",
            "9",
            "$ACADVER",
            "1",
            "AC1015",
            "9",
            "$INSUNITS",
            "70",
            "4",  # Centimeters
            "0",
            "ENDSEC",
        ]
    )

    # Tables (layers)
    lines.extend(["0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", "3"])

    # Layers
    for layer_name, color in [("0", 7), ("CONTOURS", 7), ("FILL", 8)]:
        lines.extend(
            [
                "0",
                "LAYER",
                "2",
                layer_name,
                "70",
                "0",
                "62",
                str(color),
                "6",
                "CONTINUOUS",
            ]
        )

    lines.extend(["0", "ENDTAB", "0", "ENDSEC"])

    # Entities
    lines.extend(["0", "SECTION", "2", "ENTITIES"])

    # Find bounding box for Y flip
    all_points = []
    for poly in shapes["polygons"]:
        all_points.extend(poly)
    for path in shapes["paths"]:
        all_points.extend(path)

    if all_points:
        max_y = max(p[1] for p in all_points)
    else:
        max_y = 0

    # Write polygons as LWPOLYLINE
    for poly in shapes["polygons"]:
        if len(poly) < 3:
            continue

        # Scale and optionally flip Y
        scaled_pts = []
        for x, y in poly:
            sx = x * scale
            sy = (max_y - y) * scale if flip_y else y * scale
            scaled_pts.append((sx, sy))

        # Check if closed
        is_closed = 1 if poly[0] == poly[-1] else 0

        lines.extend(
            [
                "0",
                "LWPOLYLINE",
                "8",
                "CONTOURS",
                "90",
                str(len(scaled_pts)),
                "70",
                str(is_closed),
            ]
        )
        for x, y in scaled_pts:
            lines.extend(["10", f"{x:.4f}", "20", f"{y:.4f}"])

    # Write paths as LWPOLYLINE
    for path in shapes["paths"]:
        if len(path) < 3:
            continue

        scaled_pts = []
        for x, y in path:
            sx = x * scale
            sy = (max_y - y) * scale if flip_y else y * scale
            scaled_pts.append((sx, sy))

        is_closed = 1 if path[0] == path[-1] else 0

        lines.extend(
            [
                "0",
                "LWPOLYLINE",
                "8",
                "CONTOURS",
                "90",
                str(len(scaled_pts)),
                "70",
                str(is_closed),
            ]
        )
        for x, y in scaled_pts:
            lines.extend(["10", f"{x:.4f}", "20", f"{y:.4f}"])

    lines.extend(["0", "ENDSEC", "0", "EOF"])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    return output_path


def main():
    if len(sys.argv) < 3:
        print("Usage: python svg_to_dxf.py <input_xml> <output.dxf>")
        print("  Extracts SVG from PDS/MRK XML and exports to DXF")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = sys.argv[2]

    print(f"Processing: {input_path.name}")

    xml_text = input_path.read_text(encoding="utf-8", errors="replace")
    shapes = extract_svg_shapes(xml_text)

    print(f"  View factor: {shapes['view_factor']}")
    print(f"  ViewBox: {shapes['viewbox']}")
    print(f"  Scale: {shapes['scale']:.6f} cm/unit")
    print(f"  Polygons: {len(shapes['polygons'])}")
    print(f"  Paths: {len(shapes['paths'])}")

    # Use 0.01 cm/unit scale (SVG units are typically 0.01 cm = 0.1 mm)
    # This is consistent with our analysis
    scale = 0.01

    write_dxf(shapes, output_path, scale=scale, flip_y=True)

    print(f"  Output: {output_path}")

    # Count total entities
    total = len(shapes["polygons"]) + len(shapes["paths"])
    print(f"  Total contours: {total}")


if __name__ == "__main__":
    main()
