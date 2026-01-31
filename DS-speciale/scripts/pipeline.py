#!/usr/bin/env python3
"""
DS-speciale: End-to-end pipeline.
PDS/MRK -> Extract XML -> Parse -> Export DXF/PLT

This is the main entry point for the reverse engineering pipeline.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
import hashlib

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from extract_embedded import extract_from_file
from xml_parser import parse_xml_file
from dxf_exporter import export_marker_to_dxf, export_pattern_to_dxf
from hpgl_exporter import export_marker_to_hpgl
from canonical_models import save_model


def sha256_file(filepath: Path) -> str:
    """Calculate SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def process_file(input_file: Path, output_dir: Path, verbose: bool = True) -> dict:
    """
    Process a single PDS or MRK file through the full pipeline.

    Returns a result dict with all artifacts.
    """
    file_type = "pds" if input_file.suffix.upper() == ".PDS" else "mrk"
    base_name = input_file.stem

    result = {
        "input": str(input_file),
        "type": file_type,
        "sha256": sha256_file(input_file),
        "steps": {},
        "outputs": {},
        "errors": [],
    }

    # Step 1: Extract embedded content
    if verbose:
        print(f"\n[1/4] Extracting embedded content from {input_file.name}...")

    try:
        extract_dir = output_dir / "extracted" / base_name
        extraction = extract_from_file(input_file, output_dir / "extracted")
        result["steps"]["extract"] = "success"
        result["outputs"]["extraction_manifest"] = str(
            extract_dir / "extraction_manifest.json"
        )

        if verbose:
            print(
                f"      Found {len(extraction['xml_documents'])} XML documents, {len(extraction['jpeg_images'])} images"
            )
    except Exception as e:
        result["steps"]["extract"] = "failed"
        result["errors"].append(f"Extraction failed: {e}")
        return result

    # Step 2: Parse XML to canonical model
    if verbose:
        print(f"[2/4] Parsing XML to canonical model...")

    canonical_outputs = []
    for xml_doc in extraction["xml_documents"]:
        xml_file = extract_dir / xml_doc["output_file"]
        try:
            model_type, model = parse_xml_file(str(xml_file))

            # Save canonical JSON
            canonical_file = (
                output_dir
                / "canonical"
                / f"{base_name}_{xml_doc['root_tag']}_canonical.json"
            )
            canonical_file.parent.mkdir(parents=True, exist_ok=True)
            save_model(model, str(canonical_file))

            canonical_outputs.append(
                {
                    "type": model_type,
                    "file": str(canonical_file),
                    "root_tag": xml_doc["root_tag"],
                }
            )

            if verbose:
                if model_type == "pattern":
                    print(
                        f"      Parsed PATTERN: {len(model.pieces)} pieces, {len(model.sizes)} sizes"
                    )
                else:
                    print(
                        f"      Parsed MARKER: {len(model.styles)} styles, {model.placed_count} placements"
                    )

        except Exception as e:
            result["errors"].append(f"XML parsing failed for {xml_file.name}: {e}")

    if canonical_outputs:
        result["steps"]["parse"] = "success"
        result["outputs"]["canonical"] = canonical_outputs
    else:
        result["steps"]["parse"] = "failed"
        return result

    # Step 3: Export DXF
    if verbose:
        print(f"[3/4] Exporting DXF...")

    dxf_outputs = []
    for canon in canonical_outputs:
        try:
            with open(canon["file"], "r", encoding="utf-8") as f:
                data = json.load(f)

            model_type = data.get("type", "")
            dxf_file = output_dir / "exports" / f"{base_name}.dxf"
            dxf_file.parent.mkdir(parents=True, exist_ok=True)

            if model_type == "marker":
                export_marker_to_dxf(data, str(dxf_file))
            else:
                export_pattern_to_dxf(data, str(dxf_file))

            dxf_outputs.append(str(dxf_file))
            if verbose:
                print(f"      DXF: {dxf_file.name}")

        except Exception as e:
            result["errors"].append(f"DXF export failed: {e}")

    if dxf_outputs:
        result["steps"]["dxf"] = "success"
        result["outputs"]["dxf"] = dxf_outputs

    # Step 4: Export HPGL (markers only)
    if verbose:
        print(f"[4/4] Exporting HPGL/2...")

    plt_outputs = []
    for canon in canonical_outputs:
        try:
            with open(canon["file"], "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("type") == "marker":
                plt_file = output_dir / "exports" / f"{base_name}.plt"
                export_marker_to_hpgl(data, str(plt_file))
                plt_outputs.append(str(plt_file))
                if verbose:
                    print(f"      PLT: {plt_file.name}")
            else:
                if verbose:
                    print(f"      (Skipped - patterns don't export to PLT)")

        except Exception as e:
            result["errors"].append(f"HPGL export failed: {e}")

    if plt_outputs:
        result["steps"]["hpgl"] = "success"
        result["outputs"]["plt"] = plt_outputs
    elif file_type == "mrk":
        result["steps"]["hpgl"] = "failed"
    else:
        result["steps"]["hpgl"] = "skipped"

    return result


def run_pipeline(input_dir: Path, output_dir: Path) -> dict:
    """
    Run the full pipeline on all PDS and MRK files in input_dir.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect input files
    pds_files = list(input_dir.rglob("*.PDS"))
    mrk_files = list(input_dir.rglob("*.MRK"))
    all_files = sorted(pds_files + mrk_files)

    print("=" * 70)
    print("  DS-speciale: PDS/MRK -> DXF/PLT Pipeline")
    print("=" * 70)
    print(f"\nInput directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Files found: {len(pds_files)} PDS, {len(mrk_files)} MRK")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "files": [],
    }

    for input_file in all_files:
        print(f"\n{'=' * 50}")
        print(f"Processing: {input_file.name}")
        print("=" * 50)

        result = process_file(input_file, output_dir)
        results["files"].append(result)

        if result["errors"]:
            print(f"  ERRORS: {result['errors']}")

    # Summary
    print(f"\n{'=' * 70}")
    print("  PIPELINE SUMMARY")
    print("=" * 70)

    success_count = sum(1 for f in results["files"] if not f["errors"])
    error_count = len(results["files"]) - success_count

    print(f"Total files: {len(results['files'])}")
    print(f"Successful: {success_count}")
    print(f"With errors: {error_count}")

    # Save pipeline results
    results_file = output_dir / "pipeline_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_file}")

    return results


def main():
    if len(sys.argv) < 3:
        print("Usage: python pipeline.py <input_dir> <output_dir>")
        print("\nProcesses all .PDS and .MRK files:")
        print("  1. Extracts embedded XML and images")
        print("  2. Parses XML to canonical JSON")
        print("  3. Exports DXF for patterns and markers")
        print("  4. Exports HPGL/2 PLT for markers (plotter-ready)")
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    run_pipeline(input_dir, output_dir)


if __name__ == "__main__":
    main()
