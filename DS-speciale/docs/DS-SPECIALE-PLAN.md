# DS-speciale: Optitex PDS/MRK Reverse Engineering + Plotter/Cutter Pipeline

## North Star
Given `.PDS` (pattern) + `.MRK` (marker/nest), produce cutter/plotter-ready outputs that match Optitex O/25:
- `DXF` (geometry truth + visual diff)
- `PLT/HPGL2` (plot/cut vectors)

## Oracle Executables
- Patterns: `C:\Program Files\Optitex\Optitex 25\App\PDS.exe`
- Markers: `C:\Program Files\Optitex\Optitex 25\App\Mark.exe` (v25.0.1.176, 64-bit, 2025-05-20)

## Default Export Targets
- Primary plotter/cutter: **HPGL/2** saved as `.PLT`
- Geometry truth: **DXF**
- Semantic truth: **PDML** (PDS) / **Marker XML** (MRK)

## Workspace Layout
```
DS-speciale/
├── inputs/           # Immutable source files (copied from ExampleFiles)
│   ├── pds/
│   └── mrk/
├── oracle/           # Optitex exports (truth)
│   ├── pds/<case>/   # {source.pds, truth.pdml, oracle.dxf, settings.json}
│   └── mrk/<case>/   # {source.mrk, truth.xml, oracle.dxf, oracle.plt, settings.json}
├── samples/          # Controlled test corpus (generated in Optitex)
│   ├── pds/
│   └── mrk/
├── out/              # Our parser/exporter outputs
│   ├── pds/<case>/
│   └── mrk/<case>/
├── runs/             # Test diary runs (YYYY-MM-DD/RUN-###_label/)
├── reports/          # Validation reports
├── scripts/          # Python tooling
└── docs/             # Documentation
```

## Milestones
- **A**: Oracle baseline (export PDML/DXF for PDS; XML/DXF/PLT for MRK)
- **B**: Controlled test corpus
- **C**: Truth parsers (PDML/XML → canonical JSON)
- **D**: Binary parsers (PDS + MRK → canonical JSON)
- **E**: Exporters (DXF + PLT/HPGL2)
- **F**: Validation parity checks
- **G**: End-to-end plotter-ready workflow

## Acceptance Criteria
1. Units/scale: 1:1 match within tolerance
2. Geometry: closed contours, correct notch/drill positions, correct placements
3. Curves: no silent polyline approximation (HPGL/2 + DXF splines)
4. PLT: extents match oracle, correct segment counts, renders in HPGL viewer

## Test Diary Standard
Every run is documented with:
- Run ID, timestamp, operator, machine info
- Optitex versions, export settings (every dialog field)
- Screenshots of export dialogs
- Input/output file hashes (SHA256)
- Validation results + findings
- Next run plan

See `docs/RUN_LOG_TEMPLATE.md` for the required format.
