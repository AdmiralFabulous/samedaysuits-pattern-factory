#!/usr/bin/env python3
"""
Geometry decoder for PDS files.
Extracts and decodes contour geometry from compressed sections.
"""

import struct
import json
import sys
import zlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import math


def decompress_at(data: bytes, offset: int) -> Optional[bytes]:
    """Decompress zlib data at offset."""
    for wbits in [15, -15, 31]:
        try:
            decompressor = zlib.decompressobj(wbits)
            return decompressor.decompress(data[offset:])
        except:
            continue
    return None


def scan_for_point_arrays(data: bytes, target_sizes: List[Dict]) -> List[Dict]:
    """
    Scan decompressed data for point arrays that match expected piece sizes.
    Try various data layouts.
    """
    matches = []

    # Strategy 1: float64 XY pairs (x, y, x, y, ...)
    print("  Strategy 1: float64 XY interleaved...")
    arrays_f64_xy = find_arrays_f64_xy(data, target_sizes)
    matches.extend(arrays_f64_xy)

    # Strategy 2: float64 separate X and Y arrays
    print("  Strategy 2: float64 separate X/Y arrays...")
    arrays_f64_sep = find_arrays_f64_separate(data, target_sizes)
    matches.extend(arrays_f64_sep)

    # Strategy 3: float32 XY pairs
    print("  Strategy 3: float32 XY interleaved...")
    arrays_f32_xy = find_arrays_f32_xy(data, target_sizes)
    matches.extend(arrays_f32_xy)

    # Strategy 4: int32 scaled coordinates
    print("  Strategy 4: int32 scaled coordinates...")
    arrays_int32 = find_arrays_int32_scaled(data, target_sizes)
    matches.extend(arrays_int32)

    # Strategy 5: Look for point count headers followed by coordinates
    print("  Strategy 5: Count-prefixed arrays...")
    arrays_counted = find_counted_arrays(data, target_sizes)
    matches.extend(arrays_counted)

    return matches


def find_arrays_f64_xy(data: bytes, target_sizes: List[Dict]) -> List[Dict]:
    """Find float64 XY interleaved point arrays."""
    matches = []

    for i in range(0, len(data) - 32, 8):
        # Try to read a sequence of float64 pairs
        points = []
        j = i
        while j < len(data) - 16:
            try:
                x = struct.unpack("<d", data[j : j + 8])[0]
                y = struct.unpack("<d", data[j + 8 : j + 16])[0]

                # Check if values are plausible coordinates (cm range for garments)
                if (
                    -500 < x < 500
                    and -500 < y < 500
                    and not math.isnan(x)
                    and not math.isnan(y)
                    and not math.isinf(x)
                    and not math.isinf(y)
                ):
                    points.append((x, y))
                    j += 16
                else:
                    break
            except:
                break

        if len(points) >= 4:  # Minimum for a polygon
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            width = max(xs) - min(xs)
            height = max(ys) - min(ys)

            # Check against target sizes
            for target in target_sizes:
                tw = target["size_x"]
                th = target["size_y"]

                # Allow 5% tolerance, check both orientations
                if (abs(width - tw) / tw < 0.05 and abs(height - th) / th < 0.05) or (
                    abs(height - tw) / tw < 0.05 and abs(width - th) / th < 0.05
                ):
                    # Compute area and perimeter
                    area = compute_area(points)
                    perim = compute_perimeter(points)

                    matches.append(
                        {
                            "strategy": "float64_xy",
                            "offset": i,
                            "point_count": len(points),
                            "width": width,
                            "height": height,
                            "area_cm2": area,
                            "perimeter_cm": perim,
                            "target": target,
                            "points": points[:10],  # Preview
                        }
                    )
                    break

    return matches


def find_arrays_f64_separate(data: bytes, target_sizes: List[Dict]) -> List[Dict]:
    """Find float64 arrays stored as separate X and Y arrays."""
    matches = []

    # Look for patterns like: [count][x0,x1,x2,...][y0,y1,y2,...]
    for i in range(0, len(data) - 16, 4):
        # Try reading a count
        try:
            count = struct.unpack("<I", data[i : i + 4])[0]
            if 3 < count < 1000:  # Reasonable point count
                # Check if followed by count*8 bytes of X coords then count*8 bytes of Y coords
                x_start = i + 4
                y_start = x_start + count * 8

                if y_start + count * 8 <= len(data):
                    xs = []
                    ys = []
                    valid = True

                    for k in range(count):
                        x = struct.unpack(
                            "<d", data[x_start + k * 8 : x_start + k * 8 + 8]
                        )[0]
                        y = struct.unpack(
                            "<d", data[y_start + k * 8 : y_start + k * 8 + 8]
                        )[0]

                        if (
                            -500 < x < 500
                            and -500 < y < 500
                            and not math.isnan(x)
                            and not math.isnan(y)
                        ):
                            xs.append(x)
                            ys.append(y)
                        else:
                            valid = False
                            break

                    if valid and len(xs) == count:
                        width = max(xs) - min(xs)
                        height = max(ys) - min(ys)

                        for target in target_sizes:
                            tw = target["size_x"]
                            th = target["size_y"]

                            if (
                                abs(width - tw) / tw < 0.05
                                and abs(height - th) / th < 0.05
                            ) or (
                                abs(height - tw) / tw < 0.05
                                and abs(width - th) / th < 0.05
                            ):
                                points = list(zip(xs, ys))
                                area = compute_area(points)
                                perim = compute_perimeter(points)

                                matches.append(
                                    {
                                        "strategy": "float64_separate",
                                        "offset": i,
                                        "count_offset": i,
                                        "x_offset": x_start,
                                        "y_offset": y_start,
                                        "point_count": count,
                                        "width": width,
                                        "height": height,
                                        "area_cm2": area,
                                        "perimeter_cm": perim,
                                        "target": target,
                                        "points": points[:10],
                                    }
                                )
                                break
        except:
            pass

    return matches


def find_arrays_f32_xy(data: bytes, target_sizes: List[Dict]) -> List[Dict]:
    """Find float32 XY interleaved point arrays."""
    matches = []

    for i in range(0, len(data) - 16, 4):
        points = []
        j = i
        while j < len(data) - 8:
            try:
                x = struct.unpack("<f", data[j : j + 4])[0]
                y = struct.unpack("<f", data[j + 4 : j + 8])[0]

                if (
                    -500 < x < 500
                    and -500 < y < 500
                    and not math.isnan(x)
                    and not math.isnan(y)
                    and not math.isinf(x)
                    and not math.isinf(y)
                ):
                    points.append((x, y))
                    j += 8
                else:
                    break
            except:
                break

        if len(points) >= 4:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            width = max(xs) - min(xs)
            height = max(ys) - min(ys)

            for target in target_sizes:
                tw = target["size_x"]
                th = target["size_y"]

                if tw > 0 and th > 0:
                    if (
                        abs(width - tw) / tw < 0.05 and abs(height - th) / th < 0.05
                    ) or (abs(height - tw) / tw < 0.05 and abs(width - th) / th < 0.05):
                        area = compute_area(points)
                        perim = compute_perimeter(points)

                        matches.append(
                            {
                                "strategy": "float32_xy",
                                "offset": i,
                                "point_count": len(points),
                                "width": width,
                                "height": height,
                                "area_cm2": area,
                                "perimeter_cm": perim,
                                "target": target,
                                "points": points[:10],
                            }
                        )
                        break

    return matches


def find_arrays_int32_scaled(
    data: bytes, target_sizes: List[Dict], scales: List[float] = [10, 100, 1000]
) -> List[Dict]:
    """Find int32 scaled coordinate arrays."""
    matches = []

    for scale in scales:
        for i in range(0, len(data) - 16, 4):
            points = []
            j = i
            while j < len(data) - 8:
                try:
                    x_raw = struct.unpack("<i", data[j : j + 4])[0]
                    y_raw = struct.unpack("<i", data[j + 4 : j + 8])[0]

                    x = x_raw / scale
                    y = y_raw / scale

                    if -500 < x < 500 and -500 < y < 500:
                        points.append((x, y))
                        j += 8
                    else:
                        break
                except:
                    break

            if len(points) >= 4:
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                width = max(xs) - min(xs)
                height = max(ys) - min(ys)

                for target in target_sizes:
                    tw = target["size_x"]
                    th = target["size_y"]

                    if tw > 0 and th > 0:
                        if (
                            abs(width - tw) / tw < 0.05 and abs(height - th) / th < 0.05
                        ) or (
                            abs(height - tw) / tw < 0.05 and abs(width - th) / th < 0.05
                        ):
                            area = compute_area(points)
                            perim = compute_perimeter(points)

                            matches.append(
                                {
                                    "strategy": f"int32_scaled_{scale}",
                                    "offset": i,
                                    "scale": scale,
                                    "point_count": len(points),
                                    "width": width,
                                    "height": height,
                                    "area_cm2": area,
                                    "perimeter_cm": perim,
                                    "target": target,
                                    "points": points[:10],
                                }
                            )
                            break

    return matches


def find_counted_arrays(data: bytes, target_sizes: List[Dict]) -> List[Dict]:
    """Find arrays prefixed with a point count."""
    matches = []

    for i in range(0, len(data) - 20, 4):
        try:
            # Try reading count as uint32
            count = struct.unpack("<I", data[i : i + 4])[0]

            # Skip unreasonable counts
            if count < 3 or count > 5000:
                continue

            # Try float64 XY pairs after count
            data_start = i + 4
            required_bytes = count * 16  # 2 doubles per point

            if data_start + required_bytes <= len(data):
                points = []
                valid = True

                for k in range(count):
                    offset = data_start + k * 16
                    x = struct.unpack("<d", data[offset : offset + 8])[0]
                    y = struct.unpack("<d", data[offset + 8 : offset + 16])[0]

                    if (
                        -500 < x < 500
                        and -500 < y < 500
                        and not math.isnan(x)
                        and not math.isnan(y)
                    ):
                        points.append((x, y))
                    else:
                        valid = False
                        break

                if valid and len(points) == count and count >= 3:
                    xs = [p[0] for p in points]
                    ys = [p[1] for p in points]
                    width = max(xs) - min(xs)
                    height = max(ys) - min(ys)

                    for target in target_sizes:
                        tw = target["size_x"]
                        th = target["size_y"]

                        if tw > 0 and th > 0:
                            if (
                                abs(width - tw) / tw < 0.05
                                and abs(height - th) / th < 0.05
                            ) or (
                                abs(height - tw) / tw < 0.05
                                and abs(width - th) / th < 0.05
                            ):
                                area = compute_area(points)
                                perim = compute_perimeter(points)

                                matches.append(
                                    {
                                        "strategy": "counted_f64_xy",
                                        "offset": i,
                                        "point_count": count,
                                        "width": width,
                                        "height": height,
                                        "area_cm2": area,
                                        "perimeter_cm": perim,
                                        "target": target,
                                        "points": points[:10],
                                    }
                                )
                                break
        except:
            pass

    return matches


def compute_area(points: List[Tuple[float, float]]) -> float:
    """Compute polygon area using shoelace formula."""
    if len(points) < 3:
        return 0
    n = len(points)
    area = 0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    return abs(area) / 2


def compute_perimeter(points: List[Tuple[float, float]]) -> float:
    """Compute polygon perimeter."""
    if len(points) < 2:
        return 0
    perim = 0
    for i in range(len(points)):
        j = (i + 1) % len(points)
        dx = points[j][0] - points[i][0]
        dy = points[j][1] - points[i][1]
        perim += math.sqrt(dx * dx + dy * dy)
    return perim


def main():
    if len(sys.argv) < 3:
        print("Usage: python geometry_decoder.py <pds_file> <canonical_json>")
        sys.exit(1)

    pds_path = Path(sys.argv[1])
    canonical_path = Path(sys.argv[2])

    print(f"Analyzing: {pds_path.name}")
    print("=" * 70)

    data = pds_path.read_bytes()
    print(f"File size: {len(data):,} bytes")

    # Load canonical
    with open(canonical_path) as f:
        canonical = json.load(f)

    # Build target sizes list
    target_sizes = []
    for piece in canonical.get("pieces", []):
        for si in piece.get("size_info", []):
            target_sizes.append(
                {
                    "piece": piece["name"],
                    "size": si["name"],
                    "size_x": si["size_x"],
                    "size_y": si["size_y"],
                    "area": si["area"],
                    "perimeter": si["perimeter"],
                }
            )

    print(f"Looking for {len(target_sizes)} piece/size combinations")

    # Find main compressed section
    print("\nFinding compressed geometry section...")
    zlib_offsets = []
    for sig in [b"\x78\xda", b"\x78\x9c"]:
        offset = 0
        while True:
            pos = data.find(sig, offset)
            if pos == -1:
                break
            zlib_offsets.append(pos)
            offset = pos + 1

    print(f"Found {len(zlib_offsets)} zlib signatures")

    all_matches = []

    for zlib_offset in zlib_offsets:
        decompressed = decompress_at(data, zlib_offset)
        if decompressed and len(decompressed) > 1000:  # Skip small chunks
            print(
                f"\nDecompressed {len(decompressed):,} bytes from offset {zlib_offset}"
            )
            print("Scanning for geometry arrays...")

            matches = scan_for_point_arrays(decompressed, target_sizes)

            if matches:
                print(f"\n*** Found {len(matches)} potential geometry matches! ***")
                for m in matches[:10]:
                    print(f"\n  {m['strategy']} at offset {m['offset']}:")
                    print(f"    Target: {m['target']['piece']}/{m['target']['size']}")
                    print(
                        f"    Expected: {m['target']['size_x']:.2f} x {m['target']['size_y']:.2f} cm"
                    )
                    print(
                        f"    Found: {m['width']:.2f} x {m['height']:.2f} cm ({m['point_count']} points)"
                    )
                    print(
                        f"    Area: {m['area_cm2'] / 10000:.4f} m² (expected {m['target']['area']:.4f} m²)"
                    )
                    print(
                        f"    Perimeter: {m['perimeter_cm']:.2f} cm (expected {m['target']['perimeter']:.2f} cm)"
                    )

                    # Add decompression info
                    m["zlib_offset"] = zlib_offset
                    m["decompressed_size"] = len(decompressed)

                all_matches.extend(matches)

    # Save results
    output_path = (
        pds_path.parent.parent
        / "out"
        / "binary_analysis"
        / f"{pds_path.stem}_geometry.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert points to serializable format
    for m in all_matches:
        m["points"] = [(round(p[0], 4), round(p[1], 4)) for p in m["points"]]

    with open(output_path, "w") as f:
        json.dump(all_matches, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"Found {len(all_matches)} total geometry matches")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
