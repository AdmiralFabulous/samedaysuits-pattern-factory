#!/usr/bin/env python3
"""
Generate Optitex batch scripts for oracle baseline capture.
These scripts can be run with PDS.exe /BATCH or Mark.exe /BATCH.
"""

import os
import sys
from pathlib import Path
from datetime import datetime


# Optitex executables
PDS_EXE = r"C:\Program Files\Optitex\Optitex 25\App\PDS.exe"
MARK_EXE = r"C:\Program Files\Optitex\Optitex 25\App\Mark.exe"


def generate_pds_export_script(pds_file: Path, output_dir: Path) -> str:
    """
    Generate a batch script to export PDML and DXF from a PDS file.

    Optitex batch commands (typical):
    @OPEN "filename.pds"
    @SAVE "output.pdml" /FORMAT=PDML
    @EXPORT "output.dxf" /FORMAT=DXF
    @EXIT
    """
    base_name = pds_file.stem

    pdml_path = output_dir / f"{base_name}.pdml"
    dxf_path = output_dir / f"{base_name}.dxf"

    script = f'''REM Optitex PDS Batch Export Script
REM Generated: {datetime.now().isoformat()}
REM Source: {pds_file}

@OPEN "{pds_file}"
@SAVE "{pdml_path}" /FORMAT=PDML
@EXPORT "{dxf_path}" /FORMAT=DXF
@EXIT
'''
    return script


def generate_mrk_export_script(mrk_file: Path, output_dir: Path) -> str:
    """
    Generate a batch script to export XML, DXF, and HPGL/2 from a MRK file.

    Optitex batch commands for Mark.exe (typical):
    @OPEN "filename.mrk"
    @EXPORT "output.dxf" /FORMAT=DXF
    @EXPORT "output.plt" /FORMAT=HPGL2
    @EXIT
    """
    base_name = mrk_file.stem

    dxf_path = output_dir / f"{base_name}.dxf"
    plt_path = output_dir / f"{base_name}.plt"

    script = f'''REM Optitex Mark Batch Export Script
REM Generated: {datetime.now().isoformat()}
REM Source: {mrk_file}

@OPEN "{mrk_file}"
@EXPORT "{dxf_path}" /FORMAT=DXF
@EXPORT "{plt_path}" /FORMAT=HPGL /NAME=HPGL2
@EXIT
'''
    return script


def generate_batch_scripts(input_dir: Path, output_dir: Path, batch_dir: Path):
    """
    Generate batch scripts for all PDS and MRK files.
    """
    batch_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    pds_files = list(input_dir.rglob("*.PDS"))
    mrk_files = list(input_dir.rglob("*.MRK"))

    print(f"Found {len(pds_files)} PDS files, {len(mrk_files)} MRK files")

    # PDS batch scripts
    pds_output = output_dir / "pds"
    pds_output.mkdir(exist_ok=True)

    for pds_file in pds_files:
        script = generate_pds_export_script(pds_file, pds_output)
        script_path = batch_dir / f"export_{pds_file.stem}.txt"
        script_path.write_text(script)
        print(f"  Created: {script_path.name}")

    # MRK batch scripts
    mrk_output = output_dir / "mrk"
    mrk_output.mkdir(exist_ok=True)

    for mrk_file in mrk_files:
        script = generate_mrk_export_script(mrk_file, mrk_output)
        script_path = batch_dir / f"export_{mrk_file.stem}.txt"
        script_path.write_text(script)
        print(f"  Created: {script_path.name}")

    # Master run script (Windows batch file)
    master_script = batch_dir / "run_all_exports.bat"

    lines = [
        "@echo off",
        f"REM Optitex Oracle Export Master Script",
        f"REM Generated: {datetime.now().isoformat()}",
        "",
        "echo Running Optitex exports...",
        "",
    ]

    for pds_file in pds_files:
        script_name = f"export_{pds_file.stem}.txt"
        lines.append(f"echo Exporting {pds_file.name}...")
        lines.append(f'"{PDS_EXE}" /BATCH "{batch_dir / script_name}"')
        lines.append("")

    for mrk_file in mrk_files:
        script_name = f"export_{mrk_file.stem}.txt"
        lines.append(f"echo Exporting {mrk_file.name}...")
        lines.append(f'"{MARK_EXE}" /BATCH "{batch_dir / script_name}"')
        lines.append("")

    lines.append("echo Done!")
    lines.append("pause")

    master_script.write_text("\n".join(lines))
    print(f"\nMaster script: {master_script}")
    print(f"\nTo run all exports:")
    print(f"  1. Open a command prompt as Administrator")
    print(f'  2. Run: "{master_script}"')
    print(f"\nOr run individual scripts with:")
    print(f'  "{PDS_EXE}" /BATCH "script.txt"')
    print(f'  "{MARK_EXE}" /BATCH "script.txt"')


def main():
    if len(sys.argv) < 4:
        print("Usage: python optitex_batch.py <input_dir> <output_dir> <batch_dir>")
        print("\nGenerates Optitex batch scripts for oracle baseline capture.")
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    batch_dir = Path(sys.argv[3])

    generate_batch_scripts(input_dir, output_dir, batch_dir)


if __name__ == "__main__":
    main()
