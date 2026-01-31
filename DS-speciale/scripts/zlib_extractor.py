#!/usr/bin/env python3
"""
Extract and analyze zlib-compressed sections from PDS files.
"""

import struct
import json
import sys
import zlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import math


def find_zlib_streams(data: bytes) -> List[Dict]:
    """Find all potential zlib streams in data."""
    streams = []
    signatures = [
        (b"\x78\x9c", "default"),
        (b"\x78\x01", "no_compression"),
        (b"\x78\xda", "best_compression"),
        (b"\x78\x5e", "low_compression"),
    ]

    for sig, level in signatures:
        offset = 0
        while True:
            pos = data.find(sig, offset)
            if pos == -1:
                break
            streams.append({"offset": pos, "signature": sig.hex(), "level": level})
            offset = pos + 1

    return sorted(streams, key=lambda x: x["offset"])


def try_decompress(
    data: bytes, offset: int, max_compressed: int = 500000
) -> Optional[Dict]:
    """Try to decompress zlib data at offset, return info about decompressed content."""
    for wbits in [15, -15, 31]:
        try:
            decompressor = zlib.decompressobj(wbits)
            chunk = data[offset : offset + max_compressed]
            decompressed = decompressor.decompress(chunk)
            unused = len(decompressor.unused_data)
            compressed_size = len(chunk) - unused

            return {
                "offset": offset,
                "wbits": wbits,
                "compressed_size": compressed_size,
                "decompressed_size": len(decompressed),
                "ratio": len(decompressed) / compressed_size
                if compressed_size > 0
                else 0,
                "data": decompressed,
            }
        except Exception as e:
            continue
    return None


def analyze_decompressed_data(data: bytes, source_offset: int) -> Dict:
    """Analyze decompressed binary data for coordinate arrays."""
    result = {
        "source_offset": source_offset,
        "size": len(data),
        "float32_arrays": [],
        "float64_arrays": [],
        "strings": [],
        "header_int32s": [],
    }

    # Check first 64 bytes as potential header
    if len(data) >= 64:
        for i in range(0, min(64, len(data) - 4), 4):
            val = struct.unpack("<I", data[i : i + 4])[0]
            result["header_int32s"].append(
                {
                    "offset": i,
                    "value": val,
                    "as_signed": struct.unpack("<i", data[i : i + 4])[0],
                }
            )

    # Look for float32 arrays
    i = 0
    while i < len(data) - 16:
        sequence = []
        j = i
        while j < len(data) - 4:
            try:
                val = struct.unpack("<f", data[j : j + 4])[0]
                if -1000 < val < 1000 and not math.isnan(val) and not math.isinf(val):
                    sequence.append(val)
                    j += 4
                else:
                    break
            except:
                break

        if len(sequence) >= 10:
            # Compute bbox if looks like XY pairs
            bbox = None
            if len(sequence) % 2 == 0 and len(sequence) >= 4:
                xs = sequence[0::2]
                ys = sequence[1::2]
                bbox = {
                    "min_x": min(xs),
                    "min_y": min(ys),
                    "max_x": max(xs),
                    "max_y": max(ys),
                    "width": max(xs) - min(xs),
                    "height": max(ys) - min(ys),
                }

            result["float32_arrays"].append(
                {
                    "offset": i,
                    "count": len(sequence),
                    "point_count": len(sequence) // 2
                    if len(sequence) % 2 == 0
                    else None,
                    "preview": [round(v, 4) for v in sequence[:20]],
                    "bbox": bbox,
                }
            )
            i = j
        else:
            i += 4

    # Look for float64 arrays
    i = 0
    while i < len(data) - 32:
        sequence = []
        j = i
        while j < len(data) - 8:
            try:
                val = struct.unpack("<d", data[j : j + 8])[0]
                if -1000 < val < 1000 and not math.isnan(val) and not math.isinf(val):
                    sequence.append(val)
                    j += 8
                else:
                    break
            except:
                break

        if len(sequence) >= 6:
            bbox = None
            if len(sequence) % 2 == 0 and len(sequence) >= 4:
                xs = sequence[0::2]
                ys = sequence[1::2]
                bbox = {
                    "min_x": min(xs),
                    "min_y": min(ys),
                    "max_x": max(xs),
                    "max_y": max(ys),
                    "width": max(xs) - min(xs),
                    "height": max(ys) - min(ys),
                }

            result["float64_arrays"].append(
                {
                    "offset": i,
                    "count": len(sequence),
                    "point_count": len(sequence) // 2
                    if len(sequence) % 2 == 0
                    else None,
                    "preview": [round(v, 4) for v in sequence[:20]],
                    "bbox": bbox,
                }
            )
            i = j
        else:
            i += 8

    return result


def compute_polygon_metrics(points: List[Tuple[float, float]]) -> Dict:
    """Compute area and perimeter of a polygon."""
    if len(points) < 3:
        return {"area": 0, "perimeter": 0}

    # Perimeter
    perimeter = 0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        perimeter += math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    # Area (shoelace formula)
    area = 0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    area = abs(area) / 2

    return {"area": area, "perimeter": perimeter}


def main():
    if len(sys.argv) < 2:
        print("Usage: python zlib_extractor.py <pds_file> [canonical_json]")
        sys.exit(1)

    pds_path = Path(sys.argv[1])
    canonical_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"Analyzing: {pds_path.name}")
    print("=" * 70)

    data = pds_path.read_bytes()
    print(f"File size: {len(data):,} bytes")

    # Load canonical for comparison
    pieces_info = []
    if canonical_path and canonical_path.exists():
        with open(canonical_path) as f:
            canonical = json.load(f)
        pieces_info = canonical.get("pieces", [])
        print(f"Loaded {len(pieces_info)} pieces from canonical")

        # Print expected dimensions
        print("\nExpected piece dimensions:")
        for piece in pieces_info:
            base_size = None
            for si in piece.get("size_info", []):
                if si.get("name") == "Small" or not base_size:
                    base_size = si
            if base_size:
                print(
                    f"  {piece['name']}: {base_size['size_x']:.2f} x {base_size['size_y']:.2f} cm, area={base_size['area']:.4f} m², perim={base_size['perimeter']:.2f} cm"
                )

    # Find zlib streams
    print("\nSearching for zlib streams...")
    streams = find_zlib_streams(data)
    print(f"Found {len(streams)} potential zlib signatures")

    # Try to decompress each
    results = []
    successful = 0

    for stream in streams:
        decomp = try_decompress(data, stream["offset"])
        if decomp:
            successful += 1
            print(f"\n--- Stream at offset {stream['offset']} ({stream['level']}) ---")
            print(f"    Compressed: {decomp['compressed_size']:,} bytes")
            print(f"    Decompressed: {decomp['decompressed_size']:,} bytes")
            print(f"    Ratio: {decomp['ratio']:.2f}x")

            # Analyze decompressed content
            analysis = analyze_decompressed_data(decomp["data"], stream["offset"])

            # Show float arrays
            if analysis["float64_arrays"]:
                print(f"    Float64 arrays: {len(analysis['float64_arrays'])}")
                for arr in analysis["float64_arrays"][:3]:
                    if arr["bbox"]:
                        print(
                            f"      @{arr['offset']}: {arr['point_count']} pts, {arr['bbox']['width']:.2f} x {arr['bbox']['height']:.2f}"
                        )

                        # Check if this matches any piece
                        for piece in pieces_info:
                            for si in piece.get("size_info", []):
                                tw, th = si["size_x"], si["size_y"]
                                aw, ah = arr["bbox"]["width"], arr["bbox"]["height"]

                                # Check both orientations
                                if (abs(aw - tw) < 1 and abs(ah - th) < 1) or (
                                    abs(ah - tw) < 1 and abs(aw - th) < 1
                                ):
                                    print(
                                        f"        >>> MATCH: {piece['name']}/{si['name']} ({tw:.2f} x {th:.2f})"
                                    )

                                    # Extract points and compute metrics
                                    decompressed = decomp["data"]
                                    points = []
                                    for k in range(arr["point_count"]):
                                        offset = arr["offset"] + k * 16
                                        x = struct.unpack(
                                            "<d", decompressed[offset : offset + 8]
                                        )[0]
                                        y = struct.unpack(
                                            "<d", decompressed[offset + 8 : offset + 16]
                                        )[0]
                                        points.append((x, y))

                                    metrics = compute_polygon_metrics(points)
                                    # Convert area from cm² to m²
                                    area_m2 = metrics["area"] / 10000
                                    print(
                                        f"        Computed: area={area_m2:.4f} m², perim={metrics['perimeter']:.2f} cm"
                                    )
                                    print(
                                        f"        Expected: area={si['area']:.4f} m², perim={si['perimeter']:.2f} cm"
                                    )

            if analysis["float32_arrays"]:
                print(f"    Float32 arrays: {len(analysis['float32_arrays'])}")
                for arr in analysis["float32_arrays"][:3]:
                    if arr["bbox"]:
                        print(
                            f"      @{arr['offset']}: {arr['point_count']} pts, {arr['bbox']['width']:.2f} x {arr['bbox']['height']:.2f}"
                        )

            results.append(
                {
                    "stream": stream,
                    "decompressed_size": decomp["decompressed_size"],
                    "compressed_size": decomp["compressed_size"],
                    "analysis": {
                        "float64_count": len(analysis["float64_arrays"]),
                        "float32_count": len(analysis["float32_arrays"]),
                        "float64_arrays": analysis["float64_arrays"][:10],
                        "float32_arrays": analysis["float32_arrays"][:10],
                    },
                }
            )

    print(f"\n{'=' * 70}")
    print(f"Successfully decompressed {successful}/{len(streams)} streams")

    # Save results
    output_path = (
        pds_path.parent.parent
        / "out"
        / "binary_analysis"
        / f"{pds_path.stem}_zlib.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
