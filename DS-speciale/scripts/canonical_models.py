#!/usr/bin/env python3
"""
Canonical data models for DS-speciale.
These models represent the "truth" that both XML parsers and binary parsers must produce.
Exporters (DXF, PLT) consume these models.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from enum import Enum
import json


class PointType(Enum):
    """Point types in pattern contours."""

    CORNER = "corner"
    CURVE = "curve"  # Bezier curve point
    SYMMETRIC = "symmetric"  # Symmetric curve
    SMOOTH = "smooth"  # G1 continuous


class NotchType(Enum):
    """Types of notches."""

    V_NOTCH = "v"
    T_NOTCH = "t"
    SLIT = "slit"
    CASTLE = "castle"
    DRILL = "drill"
    UNKNOWN = "unknown"


class FlipType(Enum):
    """Flip/mirror types for marker placements."""

    NONE = "none"
    UP_DOWN = "up_down"
    LEFT_RIGHT = "left_right"
    BOTH = "both"


@dataclass
class Point2D:
    """2D coordinate point."""

    x: float
    y: float
    point_type: str = "corner"  # corner, curve, symmetric, smooth

    def to_dict(self) -> Dict:
        return {"x": self.x, "y": self.y, "type": self.point_type}


@dataclass
class Contour:
    """A closed contour (outline) consisting of points."""

    points: List[Point2D] = field(default_factory=list)
    is_closed: bool = True

    def to_dict(self) -> Dict:
        return {
            "points": [p.to_dict() for p in self.points],
            "is_closed": self.is_closed,
            "point_count": len(self.points),
        }


@dataclass
class InternalLine:
    """An internal line (grain line, fold line, etc.)."""

    points: List[Point2D] = field(default_factory=list)
    line_type: str = "internal"  # grain, fold, dart, seam, etc.

    def to_dict(self) -> Dict:
        return {"points": [p.to_dict() for p in self.points], "type": self.line_type}


@dataclass
class Notch:
    """A notch or drill hole marker."""

    position: Point2D
    notch_type: str = "t"  # v, t, slit, castle, drill
    depth: float = 0.0  # Notch depth in units
    width: float = 0.0  # Notch width
    angle: float = 0.0  # Orientation angle

    def to_dict(self) -> Dict:
        return {
            "position": self.position.to_dict(),
            "type": self.notch_type,
            "depth": self.depth,
            "width": self.width,
            "angle": self.angle,
        }


@dataclass
class DrillHole:
    """A drill hole marker."""

    position: Point2D
    diameter: float = 0.0

    def to_dict(self) -> Dict:
        return {"position": self.position.to_dict(), "diameter": self.diameter}


@dataclass
class GradingRule:
    """A grading rule for a specific point across sizes."""

    point_index: int  # Index of point in contour
    deltas: Dict[str, Point2D]  # size_name -> (delta_x, delta_y)

    def to_dict(self) -> Dict:
        return {
            "point_index": self.point_index,
            "deltas": {k: v.to_dict() for k, v in self.deltas.items()},
        }


@dataclass
class SizeInfo:
    """Size-specific geometric information."""

    name: str
    area: float = 0.0
    perimeter: float = 0.0
    sew_area: float = 0.0
    sew_perimeter: float = 0.0
    size_x: float = 0.0
    size_y: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Piece:
    """A pattern piece."""

    name: str
    code: str = ""
    unique_id: str = ""
    description: str = ""
    material: str = ""
    quantity: int = 1

    # Geometry
    contour: Optional[Contour] = None
    internal_lines: List[InternalLine] = field(default_factory=list)
    notches: List[Notch] = field(default_factory=list)
    drill_holes: List[DrillHole] = field(default_factory=list)

    # Position in style
    position_x: float = 0.0
    position_y: float = 0.0

    # Seam allowance
    seam_allowance: float = 0.0
    buffer: float = 0.0

    # Nesting constraints
    rotation_allowed: str = "none"
    flip_allowed: str = "none"
    tilt: float = 0.0

    # Size-specific info
    size_info: List[SizeInfo] = field(default_factory=list)

    # Grading
    grading_rules: List[GradingRule] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "code": self.code,
            "unique_id": self.unique_id,
            "description": self.description,
            "material": self.material,
            "quantity": self.quantity,
            "contour": self.contour.to_dict() if self.contour else None,
            "internal_lines": [il.to_dict() for il in self.internal_lines],
            "notches": [n.to_dict() for n in self.notches],
            "drill_holes": [d.to_dict() for d in self.drill_holes],
            "position": {"x": self.position_x, "y": self.position_y},
            "seam_allowance": self.seam_allowance,
            "buffer": self.buffer,
            "nesting": {
                "rotation": self.rotation_allowed,
                "flip": self.flip_allowed,
                "tilt": self.tilt,
            },
            "size_info": [si.to_dict() for si in self.size_info],
            "grading_rules": [gr.to_dict() for gr in self.grading_rules],
        }


@dataclass
class PatternModel:
    """
    Canonical model for a pattern (from PDS/PDML).
    This is the "truth" representation that exporters consume.
    """

    # Metadata
    filename: str = ""
    name: str = ""
    optitex_version: str = ""
    date: str = ""

    # Units
    linear_units: str = "cm"  # mm, cm, in
    area_units: str = "sq.m"  # sq.mm, sq.cm, sq.m, sq.in

    # Sizes
    sizes: List[str] = field(default_factory=list)
    base_size: str = ""

    # Pieces
    pieces: List[Piece] = field(default_factory=list)

    # Summary stats
    total_area: float = 0.0
    total_perimeter: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "type": "pattern",
            "filename": self.filename,
            "name": self.name,
            "optitex_version": self.optitex_version,
            "date": self.date,
            "units": {"linear": self.linear_units, "area": self.area_units},
            "sizes": self.sizes,
            "base_size": self.base_size,
            "pieces": [p.to_dict() for p in self.pieces],
            "summary": {
                "piece_count": len(self.pieces),
                "size_count": len(self.sizes),
                "total_area": self.total_area,
                "total_perimeter": self.total_perimeter,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class Placement:
    """A single piece placement in a marker."""

    piece_name: str
    piece_code: str = ""
    size_name: str = ""

    # Position (center coordinates)
    x_center: float = 0.0
    y_center: float = 0.0

    # Rotation angle in degrees
    angle: float = 0.0

    # Flip state
    flip: str = "none"  # none, up_down, left_right, both

    # Geometry info (from marker)
    size_x: float = 0.0
    size_y: float = 0.0
    area: float = 0.0
    perimeter: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "piece_name": self.piece_name,
            "piece_code": self.piece_code,
            "size_name": self.size_name,
            "position": {
                "x_center": self.x_center,
                "y_center": self.y_center,
                "angle": self.angle,
                "flip": self.flip,
            },
            "geometry": {
                "size_x": self.size_x,
                "size_y": self.size_y,
                "area": self.area,
                "perimeter": self.perimeter,
            },
        }


@dataclass
class MarkerStyle:
    """A style (pattern) included in a marker with size-specific placements."""

    name: str
    filename: str = ""
    material: str = ""
    sizes: Dict[str, List[Placement]] = field(
        default_factory=dict
    )  # size_name -> placements

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "filename": self.filename,
            "material": self.material,
            "sizes": {
                size: [p.to_dict() for p in placements]
                for size, placements in self.sizes.items()
            },
        }


@dataclass
class MarkerModel:
    """
    Canonical model for a marker (from MRK).
    Contains fabric settings and piece placements.
    """

    # Metadata
    filename: str = ""
    name: str = ""
    optitex_version: str = ""
    date: str = ""

    # Nesting info
    nest_name: str = ""
    nest_version: str = ""

    # Units
    linear_units: str = "cm"
    area_units: str = "sq.m"

    # Fabric dimensions
    length: float = 0.0  # Marker length
    width: float = 0.0  # Fabric width

    # Layout settings
    layout_mode: str = "single"  # single, face-to-face, etc.
    folding: str = "none"
    num_plies: int = 1

    # Efficiency
    efficiency: float = 0.0  # Percentage

    # Summary stats
    total_area: float = 0.0
    total_perimeter: float = 0.0
    placed_count: int = 0

    # Notches summary
    notch_count: int = 0
    notch_cut_length: float = 0.0

    # Styles with placements
    styles: List[MarkerStyle] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "type": "marker",
            "filename": self.filename,
            "name": self.name,
            "optitex_version": self.optitex_version,
            "date": self.date,
            "nesting": {"name": self.nest_name, "version": self.nest_version},
            "units": {"linear": self.linear_units, "area": self.area_units},
            "fabric": {
                "length": self.length,
                "width": self.width,
                "layout_mode": self.layout_mode,
                "folding": self.folding,
                "num_plies": self.num_plies,
            },
            "efficiency": self.efficiency,
            "summary": {
                "total_area": self.total_area,
                "total_perimeter": self.total_perimeter,
                "placed_count": self.placed_count,
                "notch_count": self.notch_count,
                "notch_cut_length": self.notch_cut_length,
            },
            "styles": [s.to_dict() for s in self.styles],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def save_model(model, filepath: str):
    """Save a canonical model to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(model.to_json())


def load_pattern_model(filepath: str) -> Dict:
    """Load a pattern model from JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_marker_model(filepath: str) -> Dict:
    """Load a marker model from JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
