#!/usr/bin/env python3
"""
HPGL/2 exporter for DS-speciale.
Exports canonical marker models to PLT (HPGL/2) format for plotters/cutters.
"""

import json
import math
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class HPGLPoint:
    x: float
    y: float


class HPGL2Writer:
    """
    HPGL/2 writer for plotter output.

    HPGL/2 Commands used:
    - IN; Initialize
    - SP; Select Pen
    - PU; Pen Up
    - PD; Pen Down
    - PA; Plot Absolute
    - PM; Polygon Mode
    - EP; Edge Polygon
    - CI; Circle
    - LB; Label (text)
    """

    def __init__(self, units: str = "cm", scale: float = 1.0):
        """
        Initialize HPGL writer.

        Args:
            units: Input units ("mm", "cm", "in")
            scale: Scale factor to apply
        """
        self.units = units
        self.scale = scale
        self.commands = []

        # HPGL uses plotter units (typically 40 units/mm or 1016 units/inch)
        # We'll use 40 units/mm as standard
        self.units_per_mm = 40

        # Convert input units to mm
        self.input_to_mm = {"mm": 1.0, "cm": 10.0, "in": 25.4}.get(
            units, 10.0
        )  # Default to cm

    def _to_hpgl_units(self, value: float) -> int:
        """Convert input units to HPGL plotter units."""
        mm = value * self.input_to_mm * self.scale
        return int(mm * self.units_per_mm)

    def _point_to_hpgl(self, p: HPGLPoint) -> Tuple[int, int]:
        """Convert point to HPGL coordinates."""
        return (self._to_hpgl_units(p.x), self._to_hpgl_units(p.y))

    def initialize(self):
        """Initialize plotter."""
        self.commands.append("IN;")

    def select_pen(self, pen: int):
        """Select pen (1-8 typically)."""
        self.commands.append(f"SP{pen};")

    def pen_up(self):
        """Lift pen."""
        self.commands.append("PU;")

    def pen_down(self):
        """Lower pen."""
        self.commands.append("PD;")

    def move_to(self, p: HPGLPoint):
        """Move to position with pen up."""
        x, y = self._point_to_hpgl(p)
        self.commands.append(f"PU{x},{y};")

    def line_to(self, p: HPGLPoint):
        """Draw line to position (pen down)."""
        x, y = self._point_to_hpgl(p)
        self.commands.append(f"PD{x},{y};")

    def draw_polyline(self, points: List[HPGLPoint], closed: bool = False):
        """Draw a polyline (series of connected lines)."""
        if not points:
            return

        # Move to first point
        self.move_to(points[0])

        # Draw to remaining points
        for p in points[1:]:
            self.line_to(p)

        # Close if requested
        if closed and len(points) > 2:
            self.line_to(points[0])

        self.pen_up()

    def draw_rectangle(
        self, center: HPGLPoint, width: float, height: float, angle: float = 0.0
    ):
        """Draw a rectangle centered at center, with optional rotation."""
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
            rotated.append(HPGLPoint(rx, ry))

        self.draw_polyline(rotated, closed=True)

    def draw_circle(self, center: HPGLPoint, radius: float):
        """Draw a circle."""
        x, y = self._point_to_hpgl(center)
        r = self._to_hpgl_units(radius)
        # Move to center, then draw circle
        self.commands.append(f"PU{x},{y};")
        self.commands.append(f"CI{r};")

    def draw_notch(
        self,
        position: HPGLPoint,
        depth: float = 0.5,
        notch_type: str = "t",
        angle: float = 0.0,
    ):
        """
        Draw a notch mark.

        Args:
            position: Notch position
            depth: Notch depth in input units
            notch_type: "t" for T-notch, "v" for V-notch, "slit" for slit
            angle: Orientation angle in degrees
        """
        rad = math.radians(angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        if notch_type == "t":
            # T-notch: horizontal bar
            half_width = depth * 0.5
            p1 = HPGLPoint(
                position.x - half_width * cos_a, position.y - half_width * sin_a
            )
            p2 = HPGLPoint(
                position.x + half_width * cos_a, position.y + half_width * sin_a
            )
            self.draw_polyline([p1, p2])

        elif notch_type == "v":
            # V-notch: two lines forming V
            half_width = depth * 0.3
            tip = HPGLPoint(position.x + depth * sin_a, position.y - depth * cos_a)
            p1 = HPGLPoint(
                position.x - half_width * cos_a, position.y - half_width * sin_a
            )
            p2 = HPGLPoint(
                position.x + half_width * cos_a, position.y + half_width * sin_a
            )
            self.draw_polyline([p1, tip, p2])

        else:  # slit
            # Simple perpendicular line
            p1 = HPGLPoint(position.x, position.y)
            p2 = HPGLPoint(position.x + depth * sin_a, position.y - depth * cos_a)
            self.draw_polyline([p1, p2])

    def add_label(self, text: str, position: HPGLPoint, height: float = 3.0):
        """Add a text label."""
        x, y = self._point_to_hpgl(position)
        # Set character size (width, height in mm)
        h = self._to_hpgl_units(height)
        self.commands.append(f"PU{x},{y};")
        self.commands.append(f"SI{height * 0.6},{height};")  # Character size
        self.commands.append(f"LB{text}\x03")  # ETX terminates label

    def write(self, filepath: str):
        """Write HPGL file."""
        with open(filepath, "w") as f:
            for cmd in self.commands:
                f.write(cmd + "\n")


def export_marker_to_hpgl(
    marker_json: Dict,
    output_path: str,
    pen_cut: int = 1,
    pen_mark: int = 2,
    pen_label: int = 3,
    include_labels: bool = True,
    include_fabric_boundary: bool = True,
) -> str:
    """
    Export a marker (canonical JSON) to HPGL/2 PLT format.

    Args:
        marker_json: Canonical marker JSON
        output_path: Output file path
        pen_cut: Pen number for cut lines (piece outlines)
        pen_mark: Pen number for mark lines (internals, notches)
        pen_label: Pen number for labels
        include_labels: Whether to include piece labels
        include_fabric_boundary: Whether to include fabric boundary
    """
    # Get units from marker
    units = marker_json.get("units", {}).get("linear", "cm")

    hpgl = HPGL2Writer(units=units)
    hpgl.initialize()

    # Fabric boundary (mark layer)
    if include_fabric_boundary:
        fabric = marker_json.get("fabric", {})
        length = fabric.get("length", 0)
        width = fabric.get("width", 0)

        if length > 0 and width > 0:
            hpgl.select_pen(pen_mark)
            corners = [
                HPGLPoint(0, 0),
                HPGLPoint(length, 0),
                HPGLPoint(length, width),
                HPGLPoint(0, width),
            ]
            hpgl.draw_polyline(corners, closed=True)

    # Place pieces (cut layer)
    hpgl.select_pen(pen_cut)

    for style in marker_json.get("styles", []):
        for size_name, placements in style.get("sizes", {}).items():
            for placement in placements:
                pos = placement.get("position", {})
                geom = placement.get("geometry", {})

                x_center = pos.get("x_center", 0)
                y_center = pos.get("y_center", 0)
                angle = pos.get("angle", 0)

                size_x = geom.get("size_x", 10)
                size_y = geom.get("size_y", 10)

                # Draw piece rectangle
                center = HPGLPoint(x_center, y_center)
                hpgl.draw_rectangle(center, size_x, size_y, angle)

    # Labels (label layer)
    if include_labels:
        hpgl.select_pen(pen_label)

        for style in marker_json.get("styles", []):
            for size_name, placements in style.get("sizes", {}).items():
                for placement in placements:
                    piece_name = placement.get("piece_name", "")
                    pos = placement.get("position", {})
                    geom = placement.get("geometry", {})

                    x_center = pos.get("x_center", 0)
                    y_center = pos.get("y_center", 0)
                    size_y = geom.get("size_y", 10)

                    # Add label at center
                    label_pos = HPGLPoint(x_center, y_center)
                    hpgl.add_label(
                        piece_name[:15], label_pos, height=min(3.0, size_y / 8)
                    )

    # End with pen up
    hpgl.pen_up()
    hpgl.select_pen(0)  # Return pen

    # Write file
    hpgl.write(output_path)

    return output_path


def main():
    if len(sys.argv) < 3:
        print("Usage: python hpgl_exporter.py <canonical_json> <output.plt>")
        print("  Exports canonical marker JSON to HPGL/2 PLT format")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = sys.argv[2]

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    model_type = data.get("type", "")

    if model_type != "marker":
        print(f"ERROR: HPGL export only supports marker models (got '{model_type}')")
        sys.exit(1)

    print(f"Exporting MARKER to HPGL/2: {input_path.name}")
    export_marker_to_hpgl(data, output_path)

    fabric = data.get("fabric", {})
    print(
        f"  Fabric: {fabric.get('length', 0)} x {fabric.get('width', 0)} {data['units']['linear']}"
    )
    print(f"  Placements: {data['summary']['placed_count']}")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    main()
