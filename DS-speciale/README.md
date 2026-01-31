# DS-speciale

Optitex PDS/MRK Reverse Engineering + Plotter/Cutter Pipeline

## Goal

Transform Optitex binary files (`.PDS` patterns and `.MRK` markers) into plotter/cutter-ready outputs:
- **DXF** for geometry verification and CAD import
- **PLT/HPGL2** for direct plotter/cutter output

## Quick Start

### 1. Run the Pipeline

```bash
cd DS-speciale\scripts
python pipeline.py ..\inputs ..\out\my_run
```

This will:
1. Extract embedded XML from PDS/MRK files
2. Parse XML to canonical JSON models
3. Export DXF files (all files)
4. Export PLT/HPGL2 files (markers only)

### 2. Generate Oracle Baseline (requires Optitex)

```bash
python optitex_batch.py ..\inputs ..\oracle ..\batch_scripts
# Then run the generated batch scripts in Optitex
```

## Directory Structure

```
DS-speciale/
├── inputs/           # Source PDS/MRK files
│   ├── pds/
│   └── mrk/
├── oracle/           # Optitex exports (truth)
│   ├── pds/
│   └── mrk/
├── out/              # Pipeline outputs
│   └── run_XXX/
│       ├── extracted/    # Embedded XML/JPEG
│       ├── canonical/    # Parsed JSON models
│       └── exports/      # DXF/PLT files
├── batch_scripts/    # Optitex automation scripts
├── runs/             # Test diary documentation
├── scripts/          # Python tooling
└── docs/             # Documentation
```

## Scripts

| Script | Purpose |
|--------|---------|
| `pipeline.py` | End-to-end PDS/MRK -> DXF/PLT |
| `extract_embedded.py` | Extract XML/JPEG from binaries |
| `xml_parser.py` | Parse STYLE/MARKER XML |
| `dxf_exporter.py` | Export to DXF |
| `hpgl_exporter.py` | Export to HPGL/2 PLT |
| `batch_export.py` | Batch export canonical JSON |
| `optitex_batch.py` | Generate Optitex batch scripts |
| `binary_geometry.py` | Analyze binary structure |
| `hash_files.py` | Generate SHA256 manifest |

## Current Status

### Working
- XML extraction from PDS and MRK files
- Parsing STYLE (pattern) and MARKER (marker) XML
- DXF export with piece bounding boxes
- HPGL/2 PLT export for markers
- End-to-end pipeline automation

### In Progress
- Binary geometry parsing (actual contour points)
- Oracle baseline capture (Optitex exports)
- Parity validation vs Optitex exports

### Pending
- True contour geometry export (not just bounding boxes)
- Curve/bezier handling
- Notch/drill position extraction
- MRK-to-PDS linking for combined export

## Architecture Note

**MRK files reference PDS files for geometry.** The MRK contains placements (x, y, angle, flip) but not actual contour points. To produce a complete marker layout with true geometry:

1. Parse MRK to get placements
2. Load the referenced PDS file(s)
3. Parse PDS to get piece contours
4. Apply placement transforms
5. Export combined result

See `docs/ARCHITECTURE.md` for details.

## Test Diary

All runs are documented in `runs/YYYY-MM-DD/RUN-###_label/run_log.md` following the template in `docs/RUN_LOG_TEMPLATE.md`.

## Optitex Executables

- Pattern: `C:\Program Files\Optitex\Optitex 25\App\PDS.exe`
- Marker: `C:\Program Files\Optitex\Optitex 25\App\Mark.exe` (v25.0.1.176)
