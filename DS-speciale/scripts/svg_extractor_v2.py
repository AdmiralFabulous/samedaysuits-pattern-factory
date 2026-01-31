#!/usr/bin/env python3
"""
Extract SVG geometry from PDS/MRK XML files - v2.
Uses raw text parsing to handle namespace issues.
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
    """Parse SVG path 'd' attribute - extract vertices."""
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
            # Cubic bezier - just take endpoint
            i += 1
            if i < len(tokens):
                coords = tokens[i].strip().split()
                # Take every 6th value pair (endpoint of bezier)
                j = 4  # Skip to endpoint coords
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


def compute_metrics(points: List[Tuple[float, float]]) -> Dict:
    """Compute polygon metrics."""
    if len(points) < 3:
        return {"area": 0, "perimeter": 0, "bbox": None, "point_count": len(points)}

    # Close polygon if needed
    pts = list(points)
    if pts[0] != pts[-1]:
        pts.append(pts[0])

    # Perimeter
    perimeter = sum(
        math.sqrt((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2)
        for i in range(len(pts) - 1)
    )

    # Area (shoelace)
    area = (
        abs(
            sum(
                pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]
                for i in range(len(pts) - 1)
            )
        )
        / 2
    )

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    return {
        "area": area,
        "perimeter": perimeter,
        "bbox": {
            "min_x": min(xs),
            "min_y": min(ys),
            "max_x": max(xs),
            "max_y": max(ys),
            "width": max(xs) - min(xs),
            "height": max(ys) - min(ys),
        },
        "point_count": len(points),
    }


def extract_svg_from_xml(xml_text: str) -> Dict:
    """Extract SVG data from XML text using regex."""
    result = {
        "view_factor": None,
        "viewbox": None,
        "svg_width": None,
        "svg_height": None,
        "polygons": [],
        "paths": [],
        "rects": [],
    }

    # Find VIEW element and factor
    view_match = re.search(r'<VIEW[^>]*FACTOR="([^"]+)"', xml_text)
    if view_match:
        result["view_factor"] = float(view_match.group(1))

    # Find SVG element
    svg_match = re.search(r"<svg[^>]*>(.*?)</svg>", xml_text, re.DOTALL | re.IGNORECASE)
    if not svg_match:
        return result

    svg_tag_match = re.search(r"<svg([^>]*)>", xml_text, re.IGNORECASE)
    if svg_tag_match:
        svg_attrs = svg_tag_match.group(1)

        vb = re.search(r'viewBox="([^"]+)"', svg_attrs)
        if vb:
            result["viewbox"] = vb.group(1)

        w = re.search(r'width="([^"]+)"', svg_attrs)
        if w:
            result["svg_width"] = w.group(1)

        h = re.search(r'height="([^"]+)"', svg_attrs)
        if h:
            result["svg_height"] = h.group(1)

    svg_content = svg_match.group(0)

    # Extract polygons
    for poly in re.finditer(r'<polygon[^>]*points="([^"]+)"[^/]*/>', svg_content):
        points = parse_svg_points(poly.group(1))
        if points:
            result["polygons"].append(
                {"points": points, "metrics": compute_metrics(points)}
            )

    # Extract paths
    for path in re.finditer(r'<path[^>]*d="([^"]+)"[^/]*/>', svg_content):
        points = parse_svg_path(path.group(1))
        if len(points) >= 3:
            result["paths"].append(
                {
                    "d_preview": path.group(1)[:80] + "..."
                    if len(path.group(1)) > 80
                    else path.group(1),
                    "points": points,
                    "metrics": compute_metrics(points),
                }
            )

    # Extract rects (often used for background)
    for rect in re.finditer(
        r'<rect[^>]*x="([^"]+)"[^>]*y="([^"]+)"[^>]*width="([^"]+)"[^>]*height="([^"]+)"',
        svg_content,
    ):
        result["rects"].append(
            {
                "x": float(rect.group(1)),
                "y": float(rect.group(2)),
                "width": float(rect.group(3)),
                "height": float(rect.group(4)),
            }
        )

    # Also try reversed attribute order
    for rect in re.finditer(
        r'<rect[^>]*width="([^"]+)"[^>]*height="([^"]+)"', svg_content
    ):
        pass  # Already captured above

    return result


def match_to_pieces(svg_data: Dict, canonical: Dict, scale: float = 0.01) -> List[Dict]:
    """Match SVG shapes to known piece dimensions."""
    matches = []

    # Get piece info from canonical
    pieces_info = []
    if canonical.get("type") == "pattern":
        for piece in canonical.get("pieces", []):
            for si in piece.get("size_info", []):
                pieces_info.append(
                    {
                        "piece": piece["name"],
                        "size": si["name"],
                        "size_x": si["size_x"],
                        "size_y": si["size_y"],
                        "area": si["area"],
                        "perimeter": si["perimeter"],
                    }
                )
    elif canonical.get("type") == "marker":
        for style in canonical.get("styles", []):
            for size_name, placements in style.get("sizes", {}).items():
                for p in placements:
                    geom = p.get("geometry", {})
                    if geom.get("size_x"):
                        pieces_info.append(
                            {
                                "piece": p.get("piece_name", "unknown"),
                                "size": size_name,
                                "size_x": geom["size_x"],
                                "size_y": geom["size_y"],
                                "area": geom.get("area", 0),
                                "perimeter": geom.get("perimeter", 0),
                            }
                        )

    # Check each polygon and path
    for shape_type, shapes in [
        ("polygon", svg_data["polygons"]),
        ("path", svg_data["paths"]),
    ]:
        for shape in shapes:
            bbox = shape["metrics"].get("bbox")
            if not bbox:
                continue

            w = bbox["width"] * scale
            h = bbox["height"] * scale

            for pi in pieces_info:
                tw, th = pi["size_x"], pi["size_y"]
                if tw == 0 or th == 0:
                    continue

                # Check match (5% tolerance, either orientation)
                if (abs(w - tw) / tw < 0.05 and abs(h - th) / th < 0.05) or (
                    abs(h - tw) / tw < 0.05 and abs(w - th) / th < 0.05
                ):
                    matches.append(
                        {
                            "shape_type": shape_type,
                            "piece": pi["piece"],
                            "size": pi["size"],
                            "found_width_cm": w,
                            "found_height_cm": h,
                            "expected_width_cm": tw,
                            "expected_height_cm": th,
                            "point_count": shape["metrics"]["point_count"],
                        }
                    )

    return matches


def main():
    if len(sys.argv) < 2:
        print("Usage: python svg_extractor_v2.py <xml_file> [canonical_json]")
        sys.exit(1)

    xml_path = Path(sys.argv[1])
    canonical_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"Extracting SVG from: {xml_path.name}")
    print("=" * 60)

    xml_text = xml_path.read_text(encoding="utf-8", errors="replace")
    svg_data = extract_svg_from_xml(xml_text)

    print(f"View factor: {svg_data['view_factor']}")
    print(f"ViewBox: {svg_data['viewbox']}")
    print(f"SVG size: {svg_data['svg_width']} x {svg_data['svg_height']}")
    print(f"Polygons: {len(svg_data['polygons'])}")
    print(f"Paths: {len(svg_data['paths'])}")
    print(f"Rects: {len(svg_data['rects'])}")

    # Compute scale from viewBox
    if svg_data["viewbox"]:
        vb_parts = svg_data["viewbox"].split()
        if len(vb_parts) == 4:
            vb_w = float(vb_parts[2])
            vb_h = float(vb_parts[3])

            # Parse SVG dimensions (e.g., "24.10cm")
            if svg_data["svg_width"]:
                w_match = re.match(r"([\d.]+)(\w+)?", svg_data["svg_width"])
                if w_match:
                    phys_w = float(w_match.group(1))
                    scale = phys_w / vb_w  # cm per SVG unit
                    print(
                        f"\nComputed scale: {scale:.6f} cm/unit (1 unit = {scale * 10:.4f} mm)"
                    )

    # Show polygon info
    print("\n=== Polygons ===")
    for i, poly in enumerate(svg_data["polygons"][:10]):
        m = poly["metrics"]
        if m["bbox"]:
            print(
                f"  {i}: {m['point_count']} pts, bbox {m['bbox']['width']:.0f} x {m['bbox']['height']:.0f} units"
            )

    # Show path info
    print("\n=== Paths ===")
    for i, path in enumerate(svg_data["paths"][:10]):
        m = path["metrics"]
        if m["bbox"]:
            print(
                f"  {i}: {m['point_count']} pts, bbox {m['bbox']['width']:.0f} x {m['bbox']['height']:.0f} units"
            )

    # Match to pieces if canonical provided
    if canonical_path and canonical_path.exists():
        with open(canonical_path) as f:
            canonical = json.load(f)

        print("\n=== Matching to pieces (scale=0.01) ===")
        matches = match_to_pieces(svg_data, canonical, scale=0.01)
        for m in matches[:20]:
            print(
                f"  {m['shape_type']}: {m['piece']}/{m['size']} - {m['found_width_cm']:.2f}x{m['found_height_cm']:.2f} cm ({m['point_count']} pts)"
            )

    # Save results
    output_path = (
        xml_path.parent.parent / "binary_analysis" / f"{xml_path.stem}_svg_v2.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Make JSON serializable
    for poly in svg_data["polygons"]:
        poly["points"] = [(round(p[0], 2), round(p[1], 2)) for p in poly["points"]]
    for path in svg_data["paths"]:
        path["points"] = [(round(p[0], 2), round(p[1], 2)) for p in path["points"]]

    with open(output_path, "w") as f:
        json.dump(svg_data, f, indent=2)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
