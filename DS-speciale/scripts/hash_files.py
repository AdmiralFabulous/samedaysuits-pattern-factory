#!/usr/bin/env python3
"""
Hash all files in a directory tree and output CSV manifest.
Usage: python hash_files.py <directory> [output.csv]
"""

import hashlib
import os
import sys
import csv
from pathlib import Path
from datetime import datetime, timezone


def sha256_file(filepath: Path) -> str:
    """Calculate SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_directory(directory: Path, output_csv: Path = None):
    """Hash all files in directory and write manifest."""
    results = []

    for filepath in sorted(directory.rglob("*")):
        if filepath.is_file():
            stat = filepath.stat()
            results.append(
                {
                    "path": str(filepath.relative_to(directory)),
                    "sha256": sha256_file(filepath),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )

    # Print to stdout
    print(f"Hashed {len(results)} files in {directory}")
    for r in results:
        print(f"  {r['sha256'][:16]}...  {r['size']:>10}  {r['path']}")

    # Write CSV if requested
    if output_csv:
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["path", "sha256", "size", "modified"]
            )
            writer.writeheader()
            writer.writerows(results)
        print(f"\nManifest written to: {output_csv}")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python hash_files.py <directory> [output.csv]")
        sys.exit(1)

    directory = Path(sys.argv[1])
    output_csv = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    hash_directory(directory, output_csv)
