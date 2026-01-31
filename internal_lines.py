#!/usr/bin/env python3
"""
Internal Lines Extractor - Seam Allowance, Grainlines, Notches

Extracts internal construction details from PDS files:
1. Seam allowance lines (stitching lines)
2. Grainlines (fabric direction)
3. Notches (alignment marks)
4. Internal construction lines

These are stored in <g> groups within the SVG, separate from the
cutting contours (which are direct <polygon> children of <svg>).

Layer Types:
- CUTTING:  Piece outlines for the cutter
- SEAM:     Seam allowance / stitching lines
- GRAIN:    Grainlines showing fabric direction
- NOTCH:    Notch marks for alignment
- INTERNAL: Other internal construction lines

Author: Claude
Date: 2026-01-30
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional, NamedTuple
from dataclasses import dataclass, field
from enum import Enum
import xml.etree.ElementTree as ET

from production_pipeline import (
    extract_xml_from_pds,
    parse_svg_path,
    Point,
    Contour,
    CUTTER_WIDTH_CM,
    HPGL_UNITS_PER_MM,
)


class LineType(Enum):
    """Types of lines in a pattern."""

    CUTTING = "cutting"  # Piece outline (for cutter)
    SEAM = "seam"  # Seam allowance / stitching line
    GRAIN = "grain"  # Grainline
    NOTCH = "notch"  # Notch mark
    INTERNAL = "internal"  # Other internal lines
    UNKNOWN = "unknown"


@dataclass
class PatternLine:
    """A line element from the pattern."""

    points: List[Point]
    line_type: LineType
    closed: bool = False
    piece_index: int = -1  # Which piece this belongs to (by proximity)
    attributes: Dict = field(default_factory=dict)


@dataclass
class ExtractedLayers:
    """All layers extracted from a pattern."""

    cutting_contours: List[Contour]
    seam_lines: List[PatternLine]
    grain_lines: List[PatternLine]
    notches: List[PatternLine]
    internal_lines: List[PatternLine]
    metadata: Dict = field(default_factory=dict)

    @property
    def total_internal_count(self) -> int:
        return (
            len(self.seam_lines)
            + len(self.grain_lines)
            + len(self.notches)
            + len(self.internal_lines)
        )


def classify_line(points: List[Point], d_attr: str = "") -> LineType:
    """
    Classify a line based on its geometry and path data.

    Heuristics:
    - Very short lines (2-3 points, short length) -> NOTCH
    - Simple vertical/horizontal lines -> GRAIN
    - Lines that closely follow a contour (seam allowance) -> SEAM
    - Other -> INTERNAL
    """
    if len(points) < 2:
        return LineType.UNKNOWN

    # Calculate total length
    total_length = 0
    for i in range(len(points) - 1):
        dx = points[i + 1].x - points[i].x
        dy = points[i + 1].y - points[i].y
        total_length += (dx * dx + dy * dy) ** 0.5

    # Very short lines are likely notches
    if len(points) <= 3 and total_length < 100:  # In SVG units
        return LineType.NOTCH

    # Simple 2-point lines - check if mostly vertical or horizontal
    if len(points) == 2:
        dx = abs(points[1].x - points[0].x)
        dy = abs(points[1].y - points[0].y)

        # Mostly vertical line - likely grainline
        if dy > 3 * dx and total_length > 500:
            return LineType.GRAIN

    # Longer complex lines are either seam lines or internal construction
    if "Z" in d_attr.upper():  # Closed path
        return LineType.SEAM

    # Default to seam line for longer paths
    if total_length > 100:
        return LineType.SEAM

    return LineType.INTERNAL


def extract_all_layers(pds_path: str) -> ExtractedLayers:
    """
    Extract all layers from a PDS file - both cutting contours and internal lines.

    Args:
        pds_path: Path to PDS file

    Returns:
        ExtractedLayers with all extracted geometry
    """
    xml_content = extract_xml_from_pds(pds_path)
    root = ET.fromstring(xml_content)

    cutting_contours: List[Contour] = []
    seam_lines: List[PatternLine] = []
    grain_lines: List[PatternLine] = []
    notches: List[PatternLine] = []
    internal_lines: List[PatternLine] = []
    metadata: Dict = {}

    BACKGROUND_COLORS = {"#C0C0C0", "#c0c0c0", "gray", "grey", "#808080"}

    for view in root.iter():
        if view.tag == "VIEW":
            factor = float(view.get("FACTOR", "0.1"))
            metadata["view_factor"] = factor

            for svg in view.iter():
                if "svg" in str(svg.tag).lower():
                    viewbox = svg.get("viewBox", "0 0 1000 1000")
                    vb_parts = viewbox.split()
                    if len(vb_parts) == 4:
                        metadata["viewbox"] = {
                            "min_x": float(vb_parts[0]),
                            "min_y": float(vb_parts[1]),
                            "width": float(vb_parts[2]),
                            "height": float(vb_parts[3]),
                        }

                    piece_index = 0

                    for elem in svg:
                        tag = str(elem.tag).lower()
                        if "}" in tag:
                            tag = tag.split("}")[-1]

                        # Direct polygon children = cutting contours
                        if tag == "polygon":
                            fill_color = elem.get("fill", "")

                            if fill_color.lower() in BACKGROUND_COLORS:
                                continue

                            points_str = elem.get("points", "")
                            if points_str:
                                points = parse_svg_polygon(points_str)
                                if points:
                                    cutting_contours.append(
                                        Contour(
                                            points=points,
                                            closed=True,
                                            fill_color=fill_color,
                                            stroke_color=elem.get("stroke", ""),
                                        )
                                    )
                                    piece_index += 1

                        # <g> groups contain internal lines
                        elif tag == "g":
                            for child in elem:
                                child_tag = str(child.tag).lower()
                                if "}" in child_tag:
                                    child_tag = child_tag.split("}")[-1]

                                if child_tag == "path":
                                    d = child.get("d", "")
                                    if d:
                                        points = parse_svg_path(d)
                                        if points:
                                            line_type = classify_line(points, d)
                                            closed = "z" in d.lower()

                                            pattern_line = PatternLine(
                                                points=points,
                                                line_type=line_type,
                                                closed=closed,
                                                piece_index=piece_index
                                                - 1,  # Associate with previous piece
                                                attributes={
                                                    "stroke": child.get("stroke", ""),
                                                    "fill": child.get("fill", ""),
                                                    "stroke-width": child.get(
                                                        "stroke-width", ""
                                                    ),
                                                },
                                            )

                                            if line_type == LineType.SEAM:
                                                seam_lines.append(pattern_line)
                                            elif line_type == LineType.GRAIN:
                                                grain_lines.append(pattern_line)
                                            elif line_type == LineType.NOTCH:
                                                notches.append(pattern_line)
                                            else:
                                                internal_lines.append(pattern_line)

    return ExtractedLayers(
        cutting_contours=cutting_contours,
        seam_lines=seam_lines,
        grain_lines=grain_lines,
        notches=notches,
        internal_lines=internal_lines,
        metadata=metadata,
    )


def parse_svg_polygon(points_str: str) -> List[Point]:
    """Parse SVG polygon points attribute."""
    points = []
    parts = points_str.strip().split()
    for part in parts:
        if "," in part:
            x, y = part.split(",")
            points.append(Point(float(x), float(y)))
    return points


def generate_layered_hpgl(
    layers: ExtractedLayers,
    output_path: str,
    fabric_width_cm: float = CUTTER_WIDTH_CM,
    include_seam: bool = True,
    include_grain: bool = False,
    include_notches: bool = True,
    include_internal: bool = False,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> Dict:
    """
    Generate HPGL with multiple layers (pen colors).

    HPGL pen assignments:
    - Pen 1 (Black): Cutting contours
    - Pen 2 (Red): Seam lines
    - Pen 3 (Green): Grainlines
    - Pen 4 (Blue): Notches
    - Pen 5 (Cyan): Internal lines

    Args:
        layers: Extracted layers
        output_path: Output PLT file path
        fabric_width_cm: Fabric width for coordinate transformation
        include_seam: Include seam allowance lines
        include_grain: Include grainlines
        include_notches: Include notch marks
        include_internal: Include other internal lines
        scale_x: X scale factor
        scale_y: Y scale factor

    Returns:
        Statistics dictionary
    """
    vb = layers.metadata.get("viewbox", {"width": 1000, "height": 1000})
    vb_width = vb.get("width", 1000)
    vb_height = vb.get("height", 1000)

    # Calculate scale to real-world mm
    # Note: This is approximate - proper scaling would use GEOM_INFO
    view_factor = layers.metadata.get("view_factor", 0.1)
    base_scale = view_factor / 100.0  # cm per SVG unit

    def svg_to_hpgl(p: Point) -> Tuple[int, int]:
        """Convert SVG point to HPGL coordinates."""
        x_cm = p.x * base_scale * scale_x
        y_cm = p.y * base_scale * scale_y
        # HPGL: 40 units per mm
        x_hpgl = int(x_cm * 10 * HPGL_UNITS_PER_MM)
        y_hpgl = int(y_cm * 10 * HPGL_UNITS_PER_MM)
        return x_hpgl, y_hpgl

    commands = ["IN;"]  # Initialize
    stats = {
        "cutting_contours": 0,
        "seam_lines": 0,
        "grain_lines": 0,
        "notches": 0,
        "internal_lines": 0,
    }

    # Pen 1: Cutting contours (always included)
    commands.append("SP1;")  # Select pen 1
    for contour in layers.cutting_contours:
        if contour.points:
            x, y = svg_to_hpgl(contour.points[0])
            commands.append(f"PU{x},{y};")

            for p in contour.points[1:]:
                x, y = svg_to_hpgl(p)
                commands.append(f"PD{x},{y};")

            if contour.closed and contour.points[0] != contour.points[-1]:
                x, y = svg_to_hpgl(contour.points[0])
                commands.append(f"PD{x},{y};")

            commands.append("PU;")
            stats["cutting_contours"] += 1

    # Pen 2: Seam lines
    if include_seam and layers.seam_lines:
        commands.append("SP2;")
        for line in layers.seam_lines:
            if line.points:
                x, y = svg_to_hpgl(line.points[0])
                commands.append(f"PU{x},{y};")

                for p in line.points[1:]:
                    x, y = svg_to_hpgl(p)
                    commands.append(f"PD{x},{y};")

                commands.append("PU;")
                stats["seam_lines"] += 1

    # Pen 3: Grainlines
    if include_grain and layers.grain_lines:
        commands.append("SP3;")
        for line in layers.grain_lines:
            if line.points:
                x, y = svg_to_hpgl(line.points[0])
                commands.append(f"PU{x},{y};")

                for p in line.points[1:]:
                    x, y = svg_to_hpgl(p)
                    commands.append(f"PD{x},{y};")

                commands.append("PU;")
                stats["grain_lines"] += 1

    # Pen 4: Notches
    if include_notches and layers.notches:
        commands.append("SP4;")
        for line in layers.notches:
            if line.points:
                x, y = svg_to_hpgl(line.points[0])
                commands.append(f"PU{x},{y};")

                for p in line.points[1:]:
                    x, y = svg_to_hpgl(p)
                    commands.append(f"PD{x},{y};")

                commands.append("PU;")
                stats["notches"] += 1

    # Pen 5: Internal lines
    if include_internal and layers.internal_lines:
        commands.append("SP5;")
        for line in layers.internal_lines:
            if line.points:
                x, y = svg_to_hpgl(line.points[0])
                commands.append(f"PU{x},{y};")

                for p in line.points[1:]:
                    x, y = svg_to_hpgl(p)
                    commands.append(f"PD{x},{y};")

                commands.append("PU;")
                stats["internal_lines"] += 1

    # End
    commands.append("SP0;")  # Deselect pen
    commands.append("IN;")  # Reset

    # Write file
    with open(output_path, "w") as f:
        f.write("\n".join(commands))

    return stats


def print_layer_summary(layers: ExtractedLayers, pattern_name: str = ""):
    """Print a summary of extracted layers."""
    print("\n" + "=" * 60)
    print(f"PATTERN LAYERS: {pattern_name}")
    print("=" * 60)
    print(f"Cutting contours:  {len(layers.cutting_contours)}")
    print(f"Seam lines:        {len(layers.seam_lines)}")
    print(f"Grainlines:        {len(layers.grain_lines)}")
    print(f"Notches:           {len(layers.notches)}")
    print(f"Internal lines:    {len(layers.internal_lines)}")
    print("-" * 60)
    print(f"Total internal:    {layers.total_internal_count}")
    print("=" * 60)


def main():
    """CLI for internal lines extraction."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract internal lines from PDS patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze layers in a PDS file
  python internal_lines.py analyze "DS-speciale/inputs/pds/Basic Tee_2D.PDS"
  
  # Generate layered HPGL with seam lines
  python internal_lines.py export "DS-speciale/inputs/pds/Basic Tee_2D.PDS" -o output.plt --seam
  
  # Export all layers
  python internal_lines.py export input.PDS -o output.plt --all
        """,
    )

    subparsers = parser.add_subparsers(dest="command")

    # Analyze command
    analyze = subparsers.add_parser("analyze", help="Analyze layers in PDS file")
    analyze.add_argument("pds_file", help="PDS file to analyze")

    # Export command
    export = subparsers.add_parser("export", help="Export layered HPGL")
    export.add_argument("pds_file", help="PDS file to export")
    export.add_argument("-o", "--output", required=True, help="Output PLT file")
    export.add_argument("--seam", action="store_true", help="Include seam lines")
    export.add_argument("--grain", action="store_true", help="Include grainlines")
    export.add_argument("--notches", action="store_true", help="Include notches")
    export.add_argument(
        "--internal", action="store_true", help="Include internal lines"
    )
    export.add_argument("--all", action="store_true", help="Include all layers")

    args = parser.parse_args()

    if args.command == "analyze":
        layers = extract_all_layers(args.pds_file)
        print_layer_summary(layers, Path(args.pds_file).stem)

    elif args.command == "export":
        layers = extract_all_layers(args.pds_file)
        print_layer_summary(layers, Path(args.pds_file).stem)

        include_seam = args.seam or args.all
        include_grain = args.grain or args.all
        include_notches = args.notches or args.all
        include_internal = args.internal or args.all

        stats = generate_layered_hpgl(
            layers,
            args.output,
            include_seam=include_seam,
            include_grain=include_grain,
            include_notches=include_notches,
            include_internal=include_internal,
        )

        print(f"\nExported to: {args.output}")
        print(f"Statistics: {stats}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
