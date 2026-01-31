#!/usr/bin/env python3
"""
Batch exporter for DS-speciale.
Processes all canonical JSON files and exports DXF + HPGL.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

from dxf_exporter import export_marker_to_dxf, export_pattern_to_dxf
from hpgl_exporter import export_marker_to_hpgl


def batch_export(canonical_dir: Path, output_dir: Path) -> dict:
    """
    Export all canonical JSON files to DXF and HPGL.

    Returns summary of exports.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "canonical_dir": str(canonical_dir),
        "output_dir": str(output_dir),
        "patterns": [],
        "markers": [],
        "errors": [],
    }

    # Find all canonical JSON files
    json_files = list(canonical_dir.glob("*_canonical.json"))
    print(f"Found {len(json_files)} canonical JSON files")

    for json_file in sorted(json_files):
        print(f"\nProcessing: {json_file.name}")

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            model_type = data.get("type", "")
            base_name = json_file.stem.replace("_canonical", "")

            if model_type == "marker":
                # Export DXF
                dxf_path = output_dir / f"{base_name}.dxf"
                export_marker_to_dxf(data, str(dxf_path))
                print(f"  DXF: {dxf_path.name}")

                # Export HPGL
                plt_path = output_dir / f"{base_name}.plt"
                export_marker_to_hpgl(data, str(plt_path))
                print(f"  PLT: {plt_path.name}")

                results["markers"].append(
                    {
                        "source": json_file.name,
                        "name": data.get("name", ""),
                        "placements": data.get("summary", {}).get("placed_count", 0),
                        "dxf": dxf_path.name,
                        "plt": plt_path.name,
                    }
                )

            elif model_type == "pattern":
                # Export DXF only (patterns don't go to plotter directly)
                dxf_path = output_dir / f"{base_name}.dxf"
                export_pattern_to_dxf(data, str(dxf_path))
                print(f"  DXF: {dxf_path.name}")

                results["patterns"].append(
                    {
                        "source": json_file.name,
                        "name": data.get("name", ""),
                        "pieces": data.get("summary", {}).get("piece_count", 0),
                        "dxf": dxf_path.name,
                    }
                )
            else:
                print(f"  SKIP: Unknown model type '{model_type}'")

        except Exception as e:
            print(f"  ERROR: {e}")
            results["errors"].append({"file": json_file.name, "error": str(e)})

    # Save export manifest
    manifest_path = output_dir / "export_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n\n=== EXPORT SUMMARY ===")
    print(f"Patterns exported: {len(results['patterns'])}")
    print(f"Markers exported: {len(results['markers'])}")
    print(f"Errors: {len(results['errors'])}")
    print(f"Manifest: {manifest_path}")

    return results


def main():
    if len(sys.argv) < 3:
        print("Usage: python batch_export.py <canonical_dir> <output_dir>")
        sys.exit(1)

    canonical_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    batch_export(canonical_dir, output_dir)


if __name__ == "__main__":
    main()
