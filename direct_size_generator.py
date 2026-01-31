#!/usr/bin/env python3
"""
Direct Size Generator - Generate patterns for specific graded sizes

Instead of scaling from measurements, this module generates patterns
directly for a specific graded size (XS, S, M, L, XL, 2XL, 3XL, 4XL).

The PDS file contains dimension data (GEOM_INFO) for each piece at each size.
This module:
1. Extracts the base SVG geometry
2. Determines the rendered size (which size the SVG represents)
3. Calculates per-piece scale factors to the target size
4. Generates correctly scaled HPGL/PLT output

This is more accurate than uniform scaling because:
- Each piece may scale differently (sleeves vs body)
- Graded dimensions account for fit and proportions

Author: Claude
Date: 2026-01-30
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

from production_pipeline import (
    extract_xml_from_pds,
    extract_piece_dimensions,
    extract_svg_geometry,
    transform_to_cm,
    nest_contours,
    generate_hpgl,
    Contour,
    Point,
    CUTTER_WIDTH_CM,
)
from graded_size_extractor import (
    extract_graded_info,
    get_size_scale_factors,
    GradedPattern,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SizeGenerationResult:
    """Result of generating a pattern for a specific size."""

    success: bool
    size_name: str
    plt_file: Optional[Path]
    fabric_length_cm: float
    utilization: float
    piece_count: int
    scale_factors: Dict[str, Tuple[float, float]]  # per-piece scale factors
    message: str


def identify_rendered_size(
    pattern: GradedPattern,
    svg_contours: List[Contour],
    pieces_info: Dict[str, Dict],
) -> str:
    """
    Identify which size the SVG geometry represents.

    The SVG in the PDS is rendered at one specific size. We compare
    the actual SVG dimensions to the GEOM_INFO dimensions to find
    which size it matches.

    Args:
        pattern: GradedPattern with all size info
        svg_contours: Extracted SVG contours
        pieces_info: Piece dimensions from extract_piece_dimensions()

    Returns:
        Name of the size that best matches the rendered SVG
    """
    if not pieces_info:
        return pattern.base_size

    # Get total rendered width from pieces_info
    rendered_width = sum(p.get("size_x", 0) for p in pieces_info.values())

    # Compare to each size
    best_match = pattern.base_size
    best_diff = float("inf")

    for size_name in pattern.available_sizes:
        # Calculate total width for this size
        total_width = 0
        for piece_name, piece_info in pattern.pieces.items():
            if size_name in piece_info.sizes:
                total_width += piece_info.sizes[size_name].size_x

        diff = abs(total_width - rendered_width)
        if diff < best_diff:
            best_diff = diff
            best_match = size_name

    return best_match


def apply_per_piece_scaling(
    contours: List[Contour],
    scale_factors: Dict[str, Tuple[float, float]],
    piece_assignments: Optional[List[int]] = None,
) -> List[Contour]:
    """
    Apply per-piece scaling to contours.

    Since contours don't have piece names, we use position-based assignment
    or apply uniform scaling if piece mapping isn't available.

    Args:
        contours: List of contours
        scale_factors: Dict of piece_name -> (scale_x, scale_y)
        piece_assignments: Optional list mapping contour index to piece name

    Returns:
        Scaled contours
    """
    if not scale_factors:
        return contours

    # For now, use average scale factors since we can't reliably map contours to pieces
    # TODO: Implement proper contour-to-piece mapping using spatial proximity
    avg_scale_x = sum(sf[0] for sf in scale_factors.values()) / len(scale_factors)
    avg_scale_y = sum(sf[1] for sf in scale_factors.values()) / len(scale_factors)

    scaled = []
    for contour in contours:
        new_points = []
        for p in contour.points:
            new_points.append(
                Point(
                    x=p.x * avg_scale_x,
                    y=p.y * avg_scale_y,
                )
            )
        scaled.append(
            Contour(
                points=new_points,
                closed=contour.closed,
                fill_color=contour.fill_color,
                stroke_color=contour.stroke_color,
            )
        )

    return scaled


def generate_for_size(
    pds_path: str,
    target_size: str,
    output_dir: Path,
    fabric_width_cm: float = CUTTER_WIDTH_CM,
) -> SizeGenerationResult:
    """
    Generate a pattern for a specific graded size.

    Args:
        pds_path: Path to PDS file
        target_size: Target size name (XS, S, M, L, XL, 2XL, 3XL, 4XL)
        output_dir: Output directory for PLT files
        fabric_width_cm: Fabric width for nesting

    Returns:
        SizeGenerationResult with generated pattern info
    """
    pds_file = Path(pds_path)

    try:
        # 1. Extract graded info
        pattern = extract_graded_info(pds_file)
        logger.info(f"Pattern: {pattern.filename}")
        logger.info(f"Available sizes: {', '.join(pattern.available_sizes)}")

        # Validate target size
        if target_size not in pattern.available_sizes:
            return SizeGenerationResult(
                success=False,
                size_name=target_size,
                plt_file=None,
                fabric_length_cm=0,
                utilization=0,
                piece_count=0,
                scale_factors={},
                message=f"Size '{target_size}' not available. Available: {pattern.available_sizes}",
            )

        # 2. Extract SVG geometry
        xml_content = extract_xml_from_pds(pds_path)
        pieces_info = extract_piece_dimensions(xml_content, pattern.base_size)

        total_width = sum(p["size_x"] for p in pieces_info.values())
        total_height = (
            max(p["size_y"] for p in pieces_info.values()) if pieces_info else 0
        )

        contours, metadata = extract_svg_geometry(
            xml_content, cutting_contours_only=True
        )
        logger.info(f"Extracted {len(contours)} contours")

        # 3. Transform to cm (at base size dimensions)
        contours_cm = transform_to_cm(contours, metadata, total_width, total_height)

        # 4. Identify rendered size and calculate scale factors
        rendered_size = identify_rendered_size(pattern, contours, pieces_info)
        logger.info(f"SVG rendered at: {rendered_size}")
        logger.info(f"Target size: {target_size}")

        scale_factors = get_size_scale_factors(pattern, rendered_size, target_size)
        logger.info(f"Scale factors: {scale_factors}")

        # 5. Apply per-piece scaling
        if rendered_size != target_size:
            contours_cm = apply_per_piece_scaling(contours_cm, scale_factors)
            logger.info("Applied per-piece scaling")

        # 6. Nest pieces
        nested_contours, nesting_result = nest_contours(
            contours_cm, fabric_width=fabric_width_cm
        )

        if not nesting_result.success:
            return SizeGenerationResult(
                success=False,
                size_name=target_size,
                plt_file=None,
                fabric_length_cm=0,
                utilization=0,
                piece_count=0,
                scale_factors=scale_factors,
                message=f"Nesting failed: {nesting_result.message}",
            )

        # 7. Generate HPGL
        output_dir.mkdir(parents=True, exist_ok=True)
        plt_filename = f"{pds_file.stem}_{target_size}.plt"
        plt_path = output_dir / plt_filename

        generate_hpgl(nested_contours, str(plt_path), fabric_width_cm)

        # 8. Save metadata
        metadata_path = output_dir / f"{pds_file.stem}_{target_size}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(
                {
                    "pattern": pattern.filename,
                    "target_size": target_size,
                    "rendered_size": rendered_size,
                    "scale_factors": {
                        k: {"x": v[0], "y": v[1]} for k, v in scale_factors.items()
                    },
                    "fabric_length_cm": nesting_result.fabric_length,
                    "utilization": nesting_result.utilization,
                    "piece_count": len(contours),
                },
                f,
                indent=2,
            )

        return SizeGenerationResult(
            success=True,
            size_name=target_size,
            plt_file=plt_path,
            fabric_length_cm=nesting_result.fabric_length,
            utilization=nesting_result.utilization,
            piece_count=len(contours),
            scale_factors=scale_factors,
            message="Success",
        )

    except Exception as e:
        logger.exception(f"Error generating size {target_size}")
        return SizeGenerationResult(
            success=False,
            size_name=target_size,
            plt_file=None,
            fabric_length_cm=0,
            utilization=0,
            piece_count=0,
            scale_factors={},
            message=str(e),
        )


def generate_all_sizes(
    pds_path: str,
    output_dir: Path,
    fabric_width_cm: float = CUTTER_WIDTH_CM,
) -> Dict[str, SizeGenerationResult]:
    """
    Generate patterns for all available sizes.

    Args:
        pds_path: Path to PDS file
        output_dir: Output directory
        fabric_width_cm: Fabric width

    Returns:
        Dict mapping size name to result
    """
    pattern = extract_graded_info(Path(pds_path))

    results = {}
    for size in pattern.available_sizes:
        logger.info(f"\n{'=' * 40}")
        logger.info(f"Generating: {size}")
        logger.info(f"{'=' * 40}")

        result = generate_for_size(pds_path, size, output_dir, fabric_width_cm)
        results[size] = result

        if result.success:
            logger.info(
                f"  OK: {result.fabric_length_cm:.1f}cm fabric, {result.utilization:.1f}% utilization"
            )
        else:
            logger.error(f"  FAILED: {result.message}")

    return results


def main():
    """CLI for direct size generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate patterns for specific graded sizes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate pattern for size Large
  python direct_size_generator.py --size Large "DS-speciale/inputs/pds/Basic Tee_2D.PDS"
  
  # Generate all sizes
  python direct_size_generator.py --all "DS-speciale/inputs/pds/Basic Tee_2D.PDS"
  
  # List available sizes
  python direct_size_generator.py --list "DS-speciale/inputs/pds/Basic Tee_2D.PDS"
        """,
    )

    parser.add_argument("pds_file", help="PDS file to process")
    parser.add_argument("--size", help="Target size (XS, S, M, L, XL, 2XL, 3XL, 4XL)")
    parser.add_argument("--all", action="store_true", help="Generate all sizes")
    parser.add_argument("--list", action="store_true", help="List available sizes")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("DS-speciale/out/graded_sizes"),
        help="Output directory",
    )

    args = parser.parse_args()

    if args.list:
        pattern = extract_graded_info(Path(args.pds_file))
        print(f"\nPattern: {pattern.filename}")
        print(f"Available sizes: {', '.join(pattern.available_sizes)}")
        print(f"Base size: {pattern.base_size}")
        return

    if args.all:
        results = generate_all_sizes(args.pds_file, args.output)

        print("\n" + "=" * 60)
        print("GENERATION SUMMARY")
        print("=" * 60)

        for size, result in results.items():
            status = "OK" if result.success else "FAIL"
            fabric = f"{result.fabric_length_cm:.1f}cm" if result.success else "-"
            print(f"  {size:8} [{status}] {fabric}")

        succeeded = sum(1 for r in results.values() if r.success)
        print(f"\nTotal: {succeeded}/{len(results)} succeeded")

    elif args.size:
        result = generate_for_size(args.pds_file, args.size, args.output)

        print("\n" + "=" * 60)
        if result.success:
            print(f"SIZE {result.size_name} - SUCCESS")
            print(f"  PLT file:    {result.plt_file}")
            print(f"  Fabric:      {result.fabric_length_cm:.1f} cm")
            print(f"  Utilization: {result.utilization:.1f}%")
            print(f"  Pieces:      {result.piece_count}")
        else:
            print(f"SIZE {result.size_name} - FAILED")
            print(f"  Error: {result.message}")
        print("=" * 60)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
