#!/usr/bin/env python3
"""
Verify Oracle Exports from Optitex (RUN-002).
Checks that all expected files exist and have reasonable sizes.

Usage:
    python scripts/verify_oracle.py
    python scripts/verify_oracle.py --verbose
"""

import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime


# Expected files
EXPECTED_PDS = {
    "Basic Tee_2D": ["pdml", "dxf"],
    "Light  Jacket_2D": ["pdml", "dxf"],
    "Skinny Cargo_2D": ["pdml", "dxf"],
    "Skinny Trousers_2D": ["pdml", "dxf"],
}

EXPECTED_MRK = {
    "Basic Pants": ["dxf", "plt"],
    "Jacket Sloper": ["dxf", "plt"],
    "Nest++Shirt_Result2": ["dxf", "plt"],
    "Stripe Pants": ["dxf", "plt"],
    "Stripe Pants_Result4": ["dxf", "plt"],
}

OPTIONAL_PDS = {
    "Basic Tee_2D": ["rul"],
    "Light  Jacket_2D": ["rul"],
    "Skinny Cargo_2D": ["rul"],
    "Skinny Trousers_2D": ["rul"],
}


def sha256_file(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def check_files(base_dir: Path, expected: dict, optional: dict = None) -> dict:
    """Check expected files and return status."""
    results = {"found": [], "missing": [], "optional_found": [], "files": {}}

    for base_name, extensions in expected.items():
        for ext in extensions:
            filename = f"{base_name}.{ext}"
            filepath = base_dir / filename

            if filepath.exists():
                size = filepath.stat().st_size
                results["found"].append(filename)
                results["files"][filename] = {
                    "path": str(filepath),
                    "size": size,
                    "size_kb": round(size / 1024, 2),
                    "sha256": sha256_file(filepath),
                    "status": "OK" if size > 100 else "WARNING: very small",
                }
            else:
                results["missing"].append(filename)

    # Check optional files
    if optional:
        for base_name, extensions in optional.items():
            for ext in extensions:
                filename = f"{base_name}.{ext}"
                filepath = base_dir / filename

                if filepath.exists():
                    size = filepath.stat().st_size
                    results["optional_found"].append(filename)
                    results["files"][filename] = {
                        "path": str(filepath),
                        "size": size,
                        "size_kb": round(size / 1024, 2),
                        "sha256": sha256_file(filepath),
                        "status": "OK (optional)",
                    }

    return results


def main():
    # Determine base path
    script_dir = Path(__file__).parent
    ds_speciale = script_dir.parent
    oracle_dir = ds_speciale / "oracle"

    pds_dir = oracle_dir / "pds"
    mrk_dir = oracle_dir / "mrk"

    print("=" * 70)
    print("ORACLE BASELINE VERIFICATION (RUN-002)")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 70)
    print(f"\nOracle Directory: {oracle_dir}")

    # Check directories exist
    if not pds_dir.exists():
        print(f"WARNING: PDS directory does not exist: {pds_dir}")
        pds_dir.mkdir(parents=True, exist_ok=True)
    if not mrk_dir.exists():
        print(f"WARNING: MRK directory does not exist: {mrk_dir}")
        mrk_dir.mkdir(parents=True, exist_ok=True)

    # Check PDS exports
    print("\n[PDS EXPORTS]")
    print(f"Directory: {pds_dir}")
    pds_results = check_files(pds_dir, EXPECTED_PDS, OPTIONAL_PDS)

    print(
        f"\n  Found: {len(pds_results['found'])}/{len(EXPECTED_PDS) * 2} required files"
    )
    for f in pds_results["found"]:
        info = pds_results["files"][f]
        print(f"    OK: {f} ({info['size_kb']} KB)")

    if pds_results["missing"]:
        print(f"\n  MISSING: {len(pds_results['missing'])} files")
        for f in pds_results["missing"]:
            print(f"    MISSING: {f}")

    if pds_results["optional_found"]:
        print(f"\n  Optional found: {len(pds_results['optional_found'])} files")
        for f in pds_results["optional_found"]:
            info = pds_results["files"][f]
            print(f"    OPTIONAL: {f} ({info['size_kb']} KB)")

    # Check MRK exports
    print("\n[MRK EXPORTS]")
    print(f"Directory: {mrk_dir}")
    mrk_results = check_files(mrk_dir, EXPECTED_MRK)

    print(
        f"\n  Found: {len(mrk_results['found'])}/{len(EXPECTED_MRK) * 2} required files"
    )
    for f in mrk_results["found"]:
        info = mrk_results["files"][f]
        print(f"    OK: {f} ({info['size_kb']} KB)")

    if mrk_results["missing"]:
        print(f"\n  MISSING: {len(mrk_results['missing'])} files")
        for f in mrk_results["missing"]:
            print(f"    MISSING: {f}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_required = len(EXPECTED_PDS) * 2 + len(EXPECTED_MRK) * 2
    total_found = len(pds_results["found"]) + len(mrk_results["found"])
    total_missing = len(pds_results["missing"]) + len(mrk_results["missing"])

    print(f"Required files: {total_found}/{total_required}")
    print(f"Missing files: {total_missing}")
    print(f"Optional files: {len(pds_results['optional_found'])}")

    if total_missing == 0:
        print("\nSTATUS: ALL REQUIRED FILES PRESENT")
        status = "COMPLETE"
    else:
        print(f"\nSTATUS: INCOMPLETE - {total_missing} files missing")
        status = "INCOMPLETE"

    # Save manifest
    manifest = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "pds": pds_results,
        "mrk": mrk_results,
        "summary": {
            "required_total": total_required,
            "required_found": total_found,
            "required_missing": total_missing,
            "optional_found": len(pds_results["optional_found"]),
        },
    }

    manifest_path = oracle_dir / "oracle_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest saved to: {manifest_path}")

    # Return exit code
    sys.exit(0 if total_missing == 0 else 1)


if __name__ == "__main__":
    main()
