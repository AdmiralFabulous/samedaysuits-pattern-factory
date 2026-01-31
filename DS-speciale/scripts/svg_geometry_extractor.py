#!/usr/bin/env python3
"""
Extract geometry from embedded SVG in PDS XML.
The SVG contains the actual contour coordinates!
"""

import re
import json
import sys
import math
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import xml.etree.ElementTree as ET


def parse_svg_points(points_str: str) -> List[Tuple[float, float]]:
    """Parse SVG polygon points attribute."""
    points = []
    # Points are space-separated "x,y" pairs
    parts = points_str.strip().split()
    for part in parts:
        if "," in part:
            x, y = part.split(",")
            points.append((float(x), float(y)))
    return points


def parse_svg_path(d: str) -> List[Tuple[float, float]]:
    """Parse SVG path 'd' attribute - extract vertices only (ignoring curves for now)."""
    points = []

    # Split path into commands
    # Commands: M (move), L (line), Z (close), C (curve), etc.
    # We'll extract just the coordinate points

    # Remove commas, normalize whitespace
    d = d.replace(",", " ")
    d = re.sub(r"\s+", " ", d).strip()

    # Split by command letters
    tokens = re.split(r"([MLHVCSQTAZ])", d, flags=re.IGNORECASE)

    i = 0
    current_x, current_y = 0, 0

    while i < len(tokens):
        token = tokens[i].strip()
        if not token:
            i += 1
            continue

        if token.upper() in "MLCSQTA":
            cmd = token
            i += 1
            if i >= len(tokens):
                break

            coords_str = tokens[i].strip()
            if not coords_str:
                i += 1
                continue

            # Parse coordinate pairs
            nums = coords_str.split()
            j = 0

            while j < len(nums):
                try:
                    x = float(nums[j])
                    y = float(nums[j + 1]) if j + 1 < len(nums) else 0

                    if cmd == cmd.lower():  # Relative
                        x += current_x
                        y += current_y

                    points.append((x, y))
                    current_x, current_y = x, y
                    j += 2

                    # For curves, skip control points (take every 3rd pair for C)
                    if cmd.upper() == "C":
                        j += 4  # Skip 2 control point pairs
                    elif cmd.upper() == "Q":
                        j += 2  # Skip 1 control point pair
                except (ValueError, IndexError):
                    j += 1

            i += 1
        elif token.upper() == "Z":
            # Close path - add first point again if needed
            if points and points[0] != points[-1]:
                points.append(points[0])
            i += 1
        elif token.upper() == "H":  # Horizontal line
            i += 1
            if i < len(tokens):
                try:
                    x = float(tokens[i].strip())
                    if token == "h":
                        x += current_x
                    points.append((x, current_y))
                    current_x = x
                except:
                    pass
            i += 1
        elif token.upper() == "V":  # Vertical line
            i += 1
            if i < len(tokens):
                try:
                    y = float(tokens[i].strip())
                    if token == "v":
                        y += current_y
                    points.append((current_x, y))
                    current_y = y
                except:
                    pass
            i += 1
        else:
            i += 1

    return points


def compute_polygon_metrics(points: List[Tuple[float, float]]) -> Dict:
    """Compute area and perimeter of a polygon."""
    if len(points) < 3:
        return {"area": 0, "perimeter": 0, "bbox": None}

    # Ensure closed polygon
    if points[0] != points[-1]:
        points = points + [points[0]]

    # Perimeter
    perimeter = 0
    for i in range(len(points) - 1):
        dx = points[i + 1][0] - points[i][0]
        dy = points[i + 1][1] - points[i][1]
        perimeter += math.sqrt(dx * dx + dy * dy)

    # Area (shoelace formula)
    area = 0
    for i in range(len(points) - 1):
        area += points[i][0] * points[i + 1][1]
        area -= points[i + 1][0] * points[i][1]
    area = abs(area) / 2

    # Bounding box
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    bbox = {
        "min_x": min(xs),
        "min_y": min(ys),
        "max_x": max(xs),
        "max_y": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }

    return {
        "area": area,
        "perimeter": perimeter,
        "bbox": bbox,
        "point_count": len(points),
    }


def extract_svg_geometry(xml_path: Path) -> Dict:
    """Extract all geometry from embedded SVG in the XML."""

    tree = ET.parse(xml_path)
    root = tree.getroot()

    result = {"polygons": [], "paths": [], "view_factor": None, "viewbox": None}

    # Find VIEW element - handles both PDS (STYLE/MARKER/VIEW) and MRK (MARKER/VIEW)
    view = None

    # Check if root is MARKER (MRK file)
    if root.tag == "MARKER":
        view = root.find("VIEW")
    # Check if root is STYLE (PDS file)
    elif root.tag == "STYLE":
        marker = root.find("MARKER")
        if marker is not None:
            view = marker.find("VIEW")
    else:
        # Try various paths
        for path in [".//VIEW", ".//MARKER/VIEW"]:
            view = root.find(path)
            if view is not None:
                break

    if view is None:
        print("No VIEW element found")
        return result

    result["view_factor"] = float(view.get("FACTOR", 1.0))

    # Find SVG element
    svg = view.find(".//{http://www.w3.org/2000/svg}svg")
    if svg is None:
        # Try without namespace
        svg_text = ET.tostring(view, encoding="unicode")
        # Extract SVG manually
        svg_match = re.search(r"<svg[^>]*>(.*?)</svg>", svg_text, re.DOTALL)
        if svg_match:
            # Parse viewBox
            vb_match = re.search(r'viewBox="([^"]+)"', svg_text)
            if vb_match:
                result["viewbox"] = vb_match.group(1)

            svg_content = svg_match.group(0)

            # Extract polygons
            for poly_match in re.finditer(
                r'<polygon[^>]*points="([^"]+)"[^>]*/>', svg_content
            ):
                points_str = poly_match.group(1)
                points = parse_svg_points(points_str)
                metrics = compute_polygon_metrics(points)

                result["polygons"].append({"points": points, "metrics": metrics})

            # Extract paths
            for path_match in re.finditer(r'<path[^>]*d="([^"]+)"[^>]*/>', svg_content):
                d = path_match.group(1)
                points = parse_svg_path(d)
                metrics = compute_polygon_metrics(points)

                result["paths"].append(
                    {
                        "d": d[:100] + "..." if len(d) > 100 else d,
                        "points": points,
                        "metrics": metrics,
                    }
                )

    return result


def scale_geometry(geom: Dict, canonical_json: Dict) -> Dict:
    """
    Scale SVG geometry to match canonical piece dimensions.
    Uses the view_factor and known piece sizes to determine correct scale.
    """
    view_factor = geom.get("view_factor", 0.07)

    # The SVG is rendered at view_factor scale
    # viewBox units are likely in 0.01mm or similar

    # Try to match polygons/paths to known pieces
    pieces_info = []
    for piece in canonical_json.get("pieces", []):
        for si in piece.get("size_info", []):
            pieces_info.append(
                {
                    "piece": piece["name"],
                    "size": si["name"],
                    "area_m2": si["area"],
                    "perimeter_cm": si["perimeter"],
                    "size_x_cm": si["size_x"],
                    "size_y_cm": si["size_y"],
                }
            )

    print(f"\nView factor: {view_factor}")
    print(f"Viewbox: {geom.get('viewbox')}")
    print(f"Found {len(geom['polygons'])} polygons, {len(geom['paths'])} paths")

    # Analyze what scale the SVG units are in
    # viewBox="0 0 15694 8998" with width="10.98cm" suggests:
    # 15694 units = 10.98 cm * (1/view_factor)
    # If view_factor = 0.07, then 15694 units = 156.86 cm = 1568.6 mm
    # So 1 unit ≈ 0.1 mm = 0.01 cm

    # Let's compute actual scale from viewBox
    vb = geom.get("viewbox") or "0 0 1 1"
    vb_parts = vb.split()
    if len(vb_parts) == 4:
        vb_width = float(vb_parts[2])
        vb_height = float(vb_parts[3])

        # The actual width in cm is vb_width * view_factor * some_factor
        # Let's try to determine the factor by matching areas

        scale_factor = view_factor / 100  # Convert to cm (assuming units are 0.01mm)

        print(f"\nViewBox: {vb_width} x {vb_height}")
        print(
            f"At scale factor {scale_factor}, this is {vb_width * scale_factor:.2f} x {vb_height * scale_factor:.2f} cm"
        )

    # Analyze each polygon/path
    print("\n=== Polygons ===")
    for i, poly in enumerate(geom["polygons"][:10]):
        m = poly["metrics"]
        print(
            f"Polygon {i}: {m['point_count']} pts, bbox {m['bbox']['width']:.0f} x {m['bbox']['height']:.0f} units"
        )

        # Try different scales
        for scale in [0.01, 0.001, 0.0001]:
            w_cm = m["bbox"]["width"] * scale
            h_cm = m["bbox"]["height"] * scale
            area_m2 = m["area"] * scale * scale / 10000  # cm² to m²
            perim_cm = m["perimeter"] * scale

            # Check against known pieces
            for pi in pieces_info:
                w_match = abs(w_cm - pi["size_x_cm"]) / pi["size_x_cm"] < 0.05
                h_match = abs(h_cm - pi["size_y_cm"]) / pi["size_y_cm"] < 0.05
                w_match_swap = abs(h_cm - pi["size_x_cm"]) / pi["size_x_cm"] < 0.05
                h_match_swap = abs(w_cm - pi["size_y_cm"]) / pi["size_y_cm"] < 0.05

                if (w_match and h_match) or (w_match_swap and h_match_swap):
                    print(f"  >>> MATCH at scale {scale}: {pi['piece']}/{pi['size']}")
                    print(
                        f"      Found: {w_cm:.2f} x {h_cm:.2f} cm, area={area_m2:.4f} m², perim={perim_cm:.2f} cm"
                    )
                    print(
                        f"      Expected: {pi['size_x_cm']:.2f} x {pi['size_y_cm']:.2f} cm, area={pi['area_m2']:.4f} m², perim={pi['perimeter_cm']:.2f} cm"
                    )

    print("\n=== Paths ===")
    for i, path in enumerate(geom["paths"][:10]):
        m = path["metrics"]
        if m["bbox"]:
            print(
                f"Path {i}: {m['point_count']} pts, bbox {m['bbox']['width']:.0f} x {m['bbox']['height']:.0f} units"
            )

    return geom


def main():
    if len(sys.argv) < 2:
        print("Usage: python svg_geometry_extractor.py <xml_file> [canonical_json]")
        sys.exit(1)

    xml_path = Path(sys.argv[1])
    canonical_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"Extracting SVG geometry from: {xml_path.name}")
    print("=" * 60)

    geom = extract_svg_geometry(xml_path)

    canonical_json = {}
    if canonical_path and canonical_path.exists():
        with open(canonical_path) as f:
            canonical_json = json.load(f)

    scaled = scale_geometry(geom, canonical_json)

    # Save results
    output_path = (
        xml_path.parent.parent
        / "binary_analysis"
        / f"{xml_path.stem}_svg_geometry.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert points to serializable format
    for poly in scaled["polygons"]:
        poly["points"] = [(round(p[0], 2), round(p[1], 2)) for p in poly["points"]]
    for path in scaled["paths"]:
        path["points"] = [(round(p[0], 2), round(p[1], 2)) for p in path["points"]]

    with open(output_path, "w") as f:
        json.dump(scaled, f, indent=2)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
