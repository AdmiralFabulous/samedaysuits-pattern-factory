#!/usr/bin/env python3
"""
DXF exporter for DS-speciale.
Exports canonical pattern and marker models to DXF format.
"""

import json
import math
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DXFPoint:
    x: float
    y: float


class DXFWriter:
    """Simple DXF writer for R12/R2000 format."""

    def __init__(self):
        self.entities = []
        self.layers = {}

    def add_layer(self, name: str, color: int = 7):
        """Add a layer definition."""
        self.layers[name] = color

    def add_line(self, p1: DXFPoint, p2: DXFPoint, layer: str = "0"):
        """Add a line entity."""
        self.entities.append(
            {
                "type": "LINE",
                "layer": layer,
                "x1": p1.x,
                "y1": p1.y,
                "x2": p2.x,
                "y2": p2.y,
            }
        )

    def add_polyline(
        self, points: List[DXFPoint], layer: str = "0", closed: bool = False
    ):
        """Add a polyline entity."""
        self.entities.append(
            {"type": "LWPOLYLINE", "layer": layer, "points": points, "closed": closed}
        )

    def add_circle(self, center: DXFPoint, radius: float, layer: str = "0"):
        """Add a circle entity."""
        self.entities.append(
            {
                "type": "CIRCLE",
                "layer": layer,
                "x": center.x,
                "y": center.y,
                "radius": radius,
            }
        )

    def add_point(self, p: DXFPoint, layer: str = "0"):
        """Add a point entity."""
        self.entities.append({"type": "POINT", "layer": layer, "x": p.x, "y": p.y})

    def add_text(self, text: str, p: DXFPoint, height: float = 2.5, layer: str = "0"):
        """Add a text entity."""
        self.entities.append(
            {
                "type": "TEXT",
                "layer": layer,
                "text": text,
                "x": p.x,
                "y": p.y,
                "height": height,
            }
        )

    def add_rectangle(
        self,
        center: DXFPoint,
        width: float,
        height: float,
        angle: float = 0.0,
        layer: str = "0",
    ):
        """Add a rectangle (as polyline) centered at center, with optional rotation."""
        # Half dimensions
        hw, hh = width / 2, height / 2

        # Corner points before rotation
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]

        # Apply rotation
        rad = math.radians(angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        rotated = []
        for x, y in corners:
            rx = x * cos_a - y * sin_a + center.x
            ry = x * sin_a + y * cos_a + center.y
            rotated.append(DXFPoint(rx, ry))

        self.add_polyline(rotated, layer, closed=True)

    def write(self, filepath: str):
        """Write DXF file."""
        lines = []

        # Header section
        lines.extend(
            [
                "0",
                "SECTION",
                "2",
                "HEADER",
                "9",
                "$ACADVER",
                "1",
                "AC1015",  # AutoCAD 2000
                "9",
                "$INSUNITS",
                "70",
                "4",  # Centimeters
                "0",
                "ENDSEC",
            ]
        )

        # Tables section (layers)
        lines.extend(
            [
                "0",
                "SECTION",
                "2",
                "TABLES",
                "0",
                "TABLE",
                "2",
                "LAYER",
                "70",
                str(len(self.layers) + 1),
            ]
        )

        # Default layer
        lines.extend(["0", "LAYER", "2", "0", "70", "0", "62", "7", "6", "CONTINUOUS"])

        # Custom layers
        for layer_name, color in self.layers.items():
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

        # Entities section
        lines.extend(["0", "SECTION", "2", "ENTITIES"])

        for entity in self.entities:
            if entity["type"] == "LINE":
                lines.extend(
                    [
                        "0",
                        "LINE",
                        "8",
                        entity["layer"],
                        "10",
                        str(entity["x1"]),
                        "20",
                        str(entity["y1"]),
                        "30",
                        "0",
                        "11",
                        str(entity["x2"]),
                        "21",
                        str(entity["y2"]),
                        "31",
                        "0",
                    ]
                )

            elif entity["type"] == "LWPOLYLINE":
                pts = entity["points"]
                flags = 1 if entity["closed"] else 0
                lines.extend(
                    [
                        "0",
                        "LWPOLYLINE",
                        "8",
                        entity["layer"],
                        "90",
                        str(len(pts)),
                        "70",
                        str(flags),
                    ]
                )
                for pt in pts:
                    lines.extend(["10", str(pt.x), "20", str(pt.y)])

            elif entity["type"] == "CIRCLE":
                lines.extend(
                    [
                        "0",
                        "CIRCLE",
                        "8",
                        entity["layer"],
                        "10",
                        str(entity["x"]),
                        "20",
                        str(entity["y"]),
                        "30",
                        "0",
                        "40",
                        str(entity["radius"]),
                    ]
                )

            elif entity["type"] == "POINT":
                lines.extend(
                    [
                        "0",
                        "POINT",
                        "8",
                        entity["layer"],
                        "10",
                        str(entity["x"]),
                        "20",
                        str(entity["y"]),
                        "30",
                        "0",
                    ]
                )

            elif entity["type"] == "TEXT":
                lines.extend(
                    [
                        "0",
                        "TEXT",
                        "8",
                        entity["layer"],
                        "10",
                        str(entity["x"]),
                        "20",
                        str(entity["y"]),
                        "30",
                        "0",
                        "40",
                        str(entity["height"]),
                        "1",
                        entity["text"],
                    ]
                )

        lines.extend(["0", "ENDSEC", "0", "EOF"])

        with open(filepath, "w") as f:
            f.write("\n".join(lines))


def export_marker_to_dxf(
    marker_json: Dict,
    output_path: str,
    include_labels: bool = True,
    include_fabric_boundary: bool = True,
) -> str:
    """
    Export a marker (canonical JSON) to DXF.
    Uses bounding box rectangles for pieces (geometry not available in XML).
    """
    dxf = DXFWriter()

    # Add layers
    dxf.add_layer("FABRIC", 8)  # Gray - fabric boundary
    dxf.add_layer("PIECES", 7)  # White - piece outlines
    dxf.add_layer("LABELS", 3)  # Green - labels
    dxf.add_layer("NOTCHES", 1)  # Red - notches

    # Fabric boundary
    if include_fabric_boundary:
        fabric = marker_json.get("fabric", {})
        length = fabric.get("length", 0)
        width = fabric.get("width", 0)

        if length > 0 and width > 0:
            # Fabric rectangle at origin
            corners = [
                DXFPoint(0, 0),
                DXFPoint(length, 0),
                DXFPoint(length, width),
                DXFPoint(0, width),
            ]
            dxf.add_polyline(corners, "FABRIC", closed=True)

    # Place pieces
    placement_count = 0
    for style in marker_json.get("styles", []):
        style_name = style.get("name", "")

        for size_name, placements in style.get("sizes", {}).items():
            for placement in placements:
                piece_name = placement.get("piece_name", "")
                pos = placement.get("position", {})
                geom = placement.get("geometry", {})

                x_center = pos.get("x_center", 0)
                y_center = pos.get("y_center", 0)
                angle = pos.get("angle", 0)
                flip = pos.get("flip", "no")

                size_x = geom.get("size_x", 10)
                size_y = geom.get("size_y", 10)

                # Handle flip (affects y_center interpretation)
                # In Optitex, flip="down" typically mirrors vertically
                if flip == "down":
                    # Mirror around y_center - piece flips but center stays
                    pass  # Geometry already positioned correctly

                # Add piece rectangle
                center = DXFPoint(x_center, y_center)
                dxf.add_rectangle(center, size_x, size_y, angle, "PIECES")

                # Add label
                if include_labels:
                    label = f"{piece_name}\n{size_name}"
                    dxf.add_text(
                        piece_name[:20],
                        DXFPoint(x_center - size_x / 4, y_center),
                        height=min(2.0, size_y / 10),
                        layer="LABELS",
                    )

                placement_count += 1

    # Write file
    dxf.write(output_path)

    return output_path


def export_pattern_to_dxf(
    pattern_json: Dict, output_path: str, size_name: Optional[str] = None
) -> str:
    """
    Export a pattern (canonical JSON) to DXF.
    Note: Without actual contour geometry (only available in binary),
    this exports piece bounding boxes from size_info.
    """
    dxf = DXFWriter()

    # Add layers
    dxf.add_layer("PIECES", 7)
    dxf.add_layer("LABELS", 3)
    dxf.add_layer("INTERNALS", 4)  # Cyan
    dxf.add_layer("NOTCHES", 1)  # Red

    # Use first size if not specified
    if size_name is None:
        sizes = pattern_json.get("sizes", [])
        size_name = sizes[0] if sizes else None

    # Track piece placement (arrange in a grid for visibility)
    x_offset = 0
    y_offset = 0
    max_height = 0
    row_width = 500  # Start new row after this width

    for piece in pattern_json.get("pieces", []):
        piece_name = piece.get("name", "")

        # Find size info for requested size
        size_info = None
        for si in piece.get("size_info", []):
            if si.get("name") == size_name:
                size_info = si
                break

        if size_info is None and piece.get("size_info"):
            size_info = piece["size_info"][0]

        if size_info:
            size_x = size_info.get("size_x", 20)
            size_y = size_info.get("size_y", 20)
        else:
            size_x, size_y = 20, 20

        # Check if we need a new row
        if x_offset + size_x > row_width:
            x_offset = 0
            y_offset += max_height + 10
            max_height = 0

        # Draw piece rectangle
        center = DXFPoint(x_offset + size_x / 2, y_offset + size_y / 2)
        dxf.add_rectangle(center, size_x, size_y, 0, "PIECES")

        # Add label
        dxf.add_text(
            piece_name[:20],
            DXFPoint(x_offset + 2, y_offset + size_y / 2),
            height=min(2.0, size_y / 10),
            layer="LABELS",
        )

        # Update offsets
        x_offset += size_x + 10
        max_height = max(max_height, size_y)

    # Write file
    dxf.write(output_path)

    return output_path


def main():
    if len(sys.argv) < 3:
        print("Usage: python dxf_exporter.py <canonical_json> <output.dxf>")
        print("  Exports canonical pattern or marker JSON to DXF")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = sys.argv[2]

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    model_type = data.get("type", "")

    if model_type == "marker":
        print(f"Exporting MARKER to DXF: {input_path.name}")
        export_marker_to_dxf(data, output_path)
        print(f"  Fabric: {data['fabric']['length']} x {data['fabric']['width']} cm")
        print(f"  Placements: {data['summary']['placed_count']}")
    elif model_type == "pattern":
        print(f"Exporting PATTERN to DXF: {input_path.name}")
        export_pattern_to_dxf(data, output_path)
        print(f"  Pieces: {data['summary']['piece_count']}")
        print(f"  Sizes: {data['summary']['size_count']}")
    else:
        print(f"ERROR: Unknown model type '{model_type}'")
        sys.exit(1)

    print(f"  Output: {output_path}")


if __name__ == "__main__":
    main()
