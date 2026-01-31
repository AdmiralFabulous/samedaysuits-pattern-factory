#!/usr/bin/env python3
"""
Optimal Garment Nesting - Target 95%+ Utilization

Key insight: Garment pieces are typically tall and narrow. For optimal nesting:
1. Rotate pieces 90 degrees so they lay horizontally
2. Pack pieces in rows that span the fabric width
3. Interlock similar pieces (front+back, left+right sleeves)

For a 62" (157.48 cm) wide fabric with pieces that are ~19cm wide x 69cm tall:
- Rotated: 69cm wide x 19cm tall
- Can fit 2 pieces per row (69 + 69 = 138cm < 157cm)
- 4 body pieces = 2 rows = ~40cm height
- Theoretical: 5030 sq cm / 157.48 = 31.9 cm

Author: Claude
Date: 2026-01-30
"""

import math
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field
from copy import deepcopy
import random

CUTTER_WIDTH_CM = 157.48
GAP_CM = 0.3


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Piece:
    id: int
    points: List[Point]
    area: float
    width: float  # Bounding box width
    height: float  # Bounding box height

    @classmethod
    def from_points(cls, id: int, points: List[Point]) -> "Piece":
        if not points:
            return cls(id, [], 0, 0, 0)

        xs = [p.x for p in points]
        ys = [p.y for p in points]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)

        # Calculate area
        n = len(points)
        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += points[i].x * points[j].y
            area -= points[j].x * points[i].y
        area = abs(area) / 2

        # Normalize to origin
        min_x, min_y = min(xs), min(ys)
        normalized = [Point(p.x - min_x, p.y - min_y) for p in points]

        return cls(id, normalized, area, width, height)

    def rotate90(self) -> "Piece":
        """Return piece rotated 90 degrees."""
        # Rotate around center, then normalize
        cx = self.width / 2
        cy = self.height / 2

        rotated = []
        for p in self.points:
            dx = p.x - cx
            dy = p.y - cy
            new_x = -dy + cy
            new_y = dx + cx
            rotated.append(Point(new_x, new_y))

        # Normalize
        xs = [p.x for p in rotated]
        ys = [p.y for p in rotated]
        min_x, min_y = min(xs), min(ys)
        normalized = [Point(p.x - min_x, p.y - min_y) for p in rotated]

        return Piece(self.id, normalized, self.area, self.height, self.width)

    def translate(self, dx: float, dy: float) -> "Piece":
        """Return translated piece."""
        return Piece(
            self.id,
            [Point(p.x + dx, p.y + dy) for p in self.points],
            self.area,
            self.width,
            self.height,
        )


@dataclass
class PlacedPiece:
    piece: Piece
    x: float
    y: float
    rotated: bool


@dataclass
class NestingResult:
    placed: List[PlacedPiece]
    width: float
    length: float
    utilization: float
    success: bool
    message: str


def pieces_overlap(
    p1: Piece,
    x1: float,
    y1: float,
    p2: Piece,
    x2: float,
    y2: float,
    gap: float = GAP_CM,
) -> bool:
    """Check if two placed pieces overlap."""
    # Bounding box check first
    if (
        x1 + p1.width + gap <= x2
        or x2 + p2.width + gap <= x1
        or y1 + p1.height + gap <= y2
        or y2 + p2.height + gap <= y1
    ):
        return False
    return True  # Assume overlap if bboxes overlap (conservative)


def row_based_nesting(
    pieces: List[Piece], fabric_width: float = CUTTER_WIDTH_CM, gap: float = GAP_CM
) -> NestingResult:
    """
    Row-based nesting optimized for garment pieces.

    Strategy:
    1. For each piece, determine if rotating 90 degrees helps
    2. Sort pieces by height (after potential rotation)
    3. Fill rows from left to right, bottom to top
    """
    if not pieces:
        return NestingResult([], fabric_width, 0, 0, True, "No pieces")

    # Decide rotation for each piece - rotate if it becomes shorter
    prepared = []
    for p in pieces:
        rotated = p.rotate90()
        # Choose orientation that gives smaller height (better for row packing)
        if rotated.height < p.height and rotated.width <= fabric_width:
            prepared.append((rotated, True))
        elif p.width <= fabric_width:
            prepared.append((p, False))
        elif rotated.width <= fabric_width:
            prepared.append((rotated, True))
        else:
            # Piece doesn't fit either way
            prepared.append((p, False))

    # Sort by height (descending) for First Fit Decreasing
    prepared.sort(key=lambda x: -x[0].height)

    placed: List[PlacedPiece] = []
    rows: List[Tuple[float, float, float]] = []  # (y, height, next_x)

    for piece, rotated in prepared:
        if piece.width > fabric_width:
            continue  # Skip oversized pieces

        # Try to fit in existing row
        placed_in_row = False
        for i, (row_y, row_h, row_x) in enumerate(rows):
            if (
                row_x + piece.width + gap <= fabric_width
                and piece.height <= row_h + gap
            ):
                # Fits in this row
                placed.append(PlacedPiece(piece, row_x, row_y, rotated))
                rows[i] = (row_y, row_h, row_x + piece.width + gap)
                placed_in_row = True
                break

        if not placed_in_row:
            # Create new row
            if rows:
                new_y = max(r[0] + r[1] for r in rows) + gap
            else:
                new_y = 0

            placed.append(PlacedPiece(piece, 0, new_y, rotated))
            rows.append((new_y, piece.height, piece.width + gap))

    # Calculate results
    if placed:
        max_y = max(p.y + p.piece.height for p in placed)
        total_area = sum(p.piece.area for p in placed)
        fabric_area = fabric_width * max_y
        utilization = (total_area / fabric_area) * 100
    else:
        max_y = 0
        utilization = 0

    return NestingResult(
        placed=placed,
        width=fabric_width,
        length=max_y,
        utilization=utilization,
        success=True,
        message=f"Row-based: {utilization:.1f}% in {max_y:.1f}cm",
    )


def strip_packing(
    pieces: List[Piece], fabric_width: float = CUTTER_WIDTH_CM, gap: float = GAP_CM
) -> NestingResult:
    """
    Strip packing: Place pieces in horizontal strips, each strip filled greedily.
    Better for pieces of varying heights.
    """
    if not pieces:
        return NestingResult([], fabric_width, 0, 0, True, "No pieces")

    # Try both orientations for each piece and pick best overall
    best_result = None
    best_util = 0

    # Try multiple orderings
    for attempt in range(20):
        if attempt == 0:
            # First attempt: sort by area (largest first)
            order = sorted(range(len(pieces)), key=lambda i: -pieces[i].area)
        else:
            # Random shuffles
            order = list(range(len(pieces)))
            random.shuffle(order)

        # Try with all pieces rotated for horizontal layout
        test_pieces = []
        for i in order:
            p = pieces[i]
            rot = p.rotate90()
            # Choose orientation that fits and is shorter
            if rot.width <= fabric_width and rot.height < p.height:
                test_pieces.append((rot, True, i))
            elif p.width <= fabric_width:
                test_pieces.append((p, False, i))
            elif rot.width <= fabric_width:
                test_pieces.append((rot, True, i))

        # Sort by height for better packing
        test_pieces.sort(key=lambda x: -x[0].height)

        placed = []
        current_y = 0
        current_x = 0
        current_row_height = 0

        for piece, rotated, orig_idx in test_pieces:
            if current_x + piece.width <= fabric_width:
                # Fits in current row
                placed.append(PlacedPiece(piece, current_x, current_y, rotated))
                current_x += piece.width + gap
                current_row_height = max(current_row_height, piece.height)
            else:
                # Start new row
                current_y += current_row_height + gap
                current_x = 0
                current_row_height = piece.height
                placed.append(PlacedPiece(piece, current_x, current_y, rotated))
                current_x += piece.width + gap

        if placed:
            max_y = max(p.y + p.piece.height for p in placed)
            total_area = sum(p.piece.area for p in placed)
            fabric_area = fabric_width * max_y
            utilization = (total_area / fabric_area) * 100

            if utilization > best_util:
                best_util = utilization
                best_result = NestingResult(
                    placed=placed,
                    width=fabric_width,
                    length=max_y,
                    utilization=utilization,
                    success=True,
                    message=f"Strip packing: {utilization:.1f}% in {max_y:.1f}cm",
                )

    return best_result or NestingResult([], fabric_width, 0, 0, False, "Failed")


def hybrid_nesting(
    pieces: List[Piece], fabric_width: float = CUTTER_WIDTH_CM, gap: float = GAP_CM
) -> NestingResult:
    """
    Hybrid approach: Try multiple algorithms and return best result.
    """
    results = []

    # Try row-based
    results.append(row_based_nesting(pieces, fabric_width, gap))

    # Try strip packing with multiple attempts
    results.append(strip_packing(pieces, fabric_width, gap))

    # Try with all pieces rotated 90 degrees
    rotated_pieces = [p.rotate90() for p in pieces]
    results.append(row_based_nesting(rotated_pieces, fabric_width, gap))
    results.append(strip_packing(rotated_pieces, fabric_width, gap))

    # Return best result
    valid_results = [r for r in results if r.success and r.utilization > 0]
    if valid_results:
        return max(valid_results, key=lambda r: r.utilization)

    return NestingResult([], fabric_width, 0, 0, False, "All methods failed")


def optimal_nest_adapter(
    contour_groups: List[List],
    fabric_width: float = CUTTER_WIDTH_CM,
    gap: float = GAP_CM,
):
    """
    Adapter for production_pipeline compatibility.
    """
    from nesting_engine import (
        NestingResult as OldNestingResult,
        NestedPiece,
        Point as OldPoint,
        BoundingBox,
    )

    # Convert to Piece objects
    pieces = []
    for i, contour in enumerate(contour_groups):
        points = [Point(p.x, p.y) for p in contour]
        pieces.append(Piece.from_points(i, points))

    # Run optimal nesting
    result = hybrid_nesting(pieces, fabric_width, gap)

    # Convert back to old format
    nested_pieces = []
    for placed in result.placed:
        orig_idx = placed.piece.id
        if orig_idx < len(contour_groups):
            # Get transformed points
            trans_points = [
                OldPoint(p.x + placed.x, p.y + placed.y) for p in placed.piece.points
            ]

            bbox = BoundingBox(
                placed.x,
                placed.y,
                placed.x + placed.piece.width,
                placed.y + placed.piece.height,
            )

            nested_pieces.append(
                NestedPiece(
                    piece_id=orig_idx,
                    original_points=contour_groups[orig_idx],
                    transformed_points=trans_points,
                    bbox=bbox,
                    position=(placed.x, placed.y),
                    rotation=90 if placed.rotated else 0,
                )
            )

    return OldNestingResult(
        pieces=nested_pieces,
        fabric_width=fabric_width,
        fabric_length=result.length,
        utilization=result.utilization,
        success=result.success,
        message=result.message,
    )


def test():
    """Test optimal nesting on all patterns."""
    from production_pipeline import (
        extract_xml_from_pds,
        extract_piece_dimensions,
        extract_svg_geometry,
        transform_to_cm,
    )
    from pathlib import Path

    pds_files = [
        ("Basic Tee", "DS-speciale/inputs/pds/Basic Tee_2D.PDS"),
        ("Light Jacket", "DS-speciale/inputs/pds/Light  Jacket_2D.PDS"),
        ("Skinny Trousers", "DS-speciale/inputs/pds/Skinny Trousers_2D.PDS"),
        ("Skinny Cargo", "DS-speciale/inputs/pds/Skinny Cargo_2D.PDS"),
    ]

    print("\n" + "=" * 70)
    print("OPTIMAL NESTING TEST - Target: 95%+ Utilization")
    print("=" * 70)

    for name, pds_path in pds_files:
        if not Path(pds_path).exists():
            continue

        # Extract geometry
        xml_content = extract_xml_from_pds(pds_path)
        pieces_info = extract_piece_dimensions(xml_content, "Small")
        total_width = sum(p["size_x"] for p in pieces_info.values())
        total_height = (
            max(p["size_y"] for p in pieces_info.values()) if pieces_info else 0
        )

        contours, metadata = extract_svg_geometry(
            xml_content, cutting_contours_only=True
        )
        contours_cm = transform_to_cm(contours, metadata, total_width, total_height)

        # Convert to Piece objects
        pieces = []
        for i, c in enumerate(contours_cm):
            points = [Point(p.x, p.y) for p in c.points]
            pieces.append(Piece.from_points(i, points))

        total_area = sum(p.area for p in pieces)
        theoretical_min = total_area / CUTTER_WIDTH_CM

        # Test nesting
        result = hybrid_nesting(pieces, CUTTER_WIDTH_CM, GAP_CM)

        print(f"\n{name}:")
        print(f"  Pieces:        {len(pieces)}")
        print(f"  Total area:    {total_area:.0f} sq cm")
        print(f"  Theoretical:   {theoretical_min:.1f} cm (100% util)")
        print(f"  Actual:        {result.length:.1f} cm")
        print(f"  Utilization:   {result.utilization:.1f}%")
        print(f"  Status:        {result.message}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    test()
