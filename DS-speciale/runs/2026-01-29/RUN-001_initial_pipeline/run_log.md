# Run Log: RUN-001 Initial Pipeline Build

## Run Metadata
- **Run ID**: RUN-001
- **Date/Time (Local)**: 2026-01-29 ~19:30
- **Date/Time (UTC)**: 2026-01-29T19:30:00Z (approx)
- **Operator**: OpenCode Agent
- **Machine**:
  - Platform: Windows
  - Working Directory: `D:\SameDaySuits\_SameDaySuits\PILLARS_SAMEDAYSUITS\XX-EXPERIMENTS\REVERSE-ENGINEER-PDS`

## Optitex Environment
- **PDS.exe**: `C:\Program Files\Optitex\Optitex 25\App\PDS.exe`
  - Version (from About): Not accessed in this run
- **Mark.exe**: `C:\Program Files\Optitex\Optitex 25\App\Mark.exe`
  - Version (from About): 25.0.1.176 (64-bit) (2025-05-20)
- **License state**: Not verified in this run

## Inputs

| File | Type | Size | SHA256 (first 16) |
|------|------|------|-------------------|
| Basic Pants.MRK | MRK | 313,596 | d155e4f2947c864a |
| Jacket Sloper.MRK | MRK | 238,787 | abf33a5d5f370aeb |
| Nest++Shirt_Result2.MRK | MRK | 221,593 | 057d79025660b6f2 |
| Stripe Pants.MRK | MRK | 155,308 | 40964d23c4bc33cc |
| Stripe Pants_Result4.MRK | MRK | 154,934 | ac6e3a8748821d69 |
| Basic Tee_2D.PDS | PDS | 287,395 | fbe616d6764d87cf |
| Light  Jacket_2D.PDS | PDS | 166,659 | 435635b73ced1967 |
| Skinny Cargo_2D.PDS | PDS | 413,842 | 42f4e5334e010351 |
| Skinny Trousers_2D.PDS | PDS | 376,372 | 1c5e525f372d1c19 |

## Objective
Build and test the complete DS-speciale pipeline: extract embedded XML from PDS/MRK binaries, parse to canonical JSON, export DXF and HPGL/2 PLT files.

---

## Actions Taken (Chronological)

### 1. Workspace Setup
- Created `DS-speciale/` directory structure:
  - `inputs/pds/`, `inputs/mrk/` - immutable source files
  - `oracle/pds/`, `oracle/mrk/` - for Optitex exports (future)
  - `samples/pds/`, `samples/mrk/` - for controlled test corpus (future)
  - `out/` - pipeline outputs
  - `runs/` - test diary runs
  - `reports/` - validation reports
  - `scripts/` - Python tooling
  - `docs/` - documentation

### 2. Copied Input Files
- Copied 4 PDS files from `ExampleFiles\pds\` to `inputs\pds\`
- Copied 5 MRK files from `ExampleFiles\mrk\` to `inputs\mrk\`
- Generated `inputs_manifest.csv` with SHA256 hashes

### 3. Binary Reconnaissance
- Analyzed all 9 files for:
  - Magic bytes (all have `dc54ef12`)
  - Embedded XML locations and sizes
  - Embedded JPEG locations and sizes
- Results: All files contain embedded XML with `<STYLE>` (PDS) or `<MARKER>` (MRK) root elements

### 4. Built Extract Script
- `scripts/extract_embedded.py` - properly extracts complete XML documents and JPEG images
- Tested on all 9 files, successfully extracted:
  - 9 XML documents (1 per file)
  - 8 JPEG images (some PDS files have embedded thumbnails)

### 5. Built Canonical Models
- `scripts/canonical_models.py` - defines PatternModel and MarkerModel dataclasses
- Fields include: pieces, sizes, placements, geometry info, notches, etc.

### 6. Built XML Parser
- `scripts/xml_parser.py` - parses `<STYLE>` (pattern) and `<MARKER>` (marker) XML
- Successfully parsed all 9 XML documents to canonical JSON

### 7. Built DXF Exporter
- `scripts/dxf_exporter.py` - exports canonical models to DXF format
- Supports both patterns (piece layout) and markers (placement layout)
- Uses bounding box rectangles (actual contour geometry requires binary parsing)

### 8. Built HPGL/2 Exporter
- `scripts/hpgl_exporter.py` - exports markers to PLT format for plotters/cutters
- Supports pen selection, polylines, circles, labels
- Uses 40 units/mm scaling (standard HPGL)

### 9. Built End-to-End Pipeline
- `scripts/pipeline.py` - orchestrates the full workflow:
  1. Extract embedded content
  2. Parse XML to canonical JSON
  3. Export DXF
  4. Export HPGL/2 (markers only)

### 10. Ran Full Pipeline
- Input: 9 files (4 PDS, 5 MRK)
- Output: 9 successful, 0 errors
- Artifacts: 9 DXF files, 5 PLT files

---

## Outputs Produced

### Extracted Content (in `out/run_001/extracted/`)
| Source | XML Documents | JPEG Images |
|--------|---------------|-------------|
| Basic Pants.MRK | 1 (MARKER) | 1 |
| Jacket Sloper.MRK | 1 (MARKER) | 1 |
| Nest++Shirt_Result2.MRK | 1 (MARKER) | 1 |
| Stripe Pants.MRK | 1 (MARKER) | 1 |
| Stripe Pants_Result4.MRK | 1 (MARKER) | 1 |
| Basic Tee_2D.PDS | 1 (STYLE) | 1 |
| Light  Jacket_2D.PDS | 1 (STYLE) | 0 |
| Skinny Cargo_2D.PDS | 1 (STYLE) | 1 |
| Skinny Trousers_2D.PDS | 1 (STYLE) | 1 |

### Canonical JSON (in `out/run_001/canonical/`)
| File | Type | Key Metrics |
|------|------|-------------|
| Basic Pants_MARKER_canonical.json | MARKER | 1 style, 24 placements |
| Jacket Sloper_MARKER_canonical.json | MARKER | 1 style, 72 placements |
| Nest++Shirt_Result2_MARKER_canonical.json | MARKER | 2 styles, 82 placements |
| Stripe Pants_MARKER_canonical.json | MARKER | 1 style, 50 placements |
| Stripe Pants_Result4_MARKER_canonical.json | MARKER | 1 style, 50 placements |
| Basic Tee_2D_STYLE_canonical.json | PATTERN | 4 pieces, 8 sizes |
| Light  Jacket_2D_STYLE_canonical.json | PATTERN | 11 pieces, 3 sizes |
| Skinny Cargo_2D_STYLE_canonical.json | PATTERN | 20 pieces, 11 sizes |
| Skinny Trousers_2D_STYLE_canonical.json | PATTERN | 19 pieces, 5 sizes |

### Exports (in `out/run_001/exports/`)
| File | Size | Notes |
|------|------|-------|
| Basic Pants.dxf | 7,073 | Marker layout |
| Basic Pants.plt | 3,610 | HPGL/2 plotter output |
| Jacket Sloper.dxf | 19,362 | Marker layout |
| Jacket Sloper.plt | 10,271 | HPGL/2 plotter output |
| Nest++Shirt_Result2.dxf | 22,258 | Marker layout |
| Nest++Shirt_Result2.plt | 11,961 | HPGL/2 plotter output |
| Stripe Pants.dxf | 12,974 | Marker layout |
| Stripe Pants.plt | 7,104 | HPGL/2 plotter output |
| Stripe Pants_Result4.dxf | 12,390 | Marker layout |
| Stripe Pants_Result4.plt | 6,946 | HPGL/2 plotter output |
| Basic Tee_2D.dxf | 1,296 | Pattern layout |
| Light  Jacket_2D.dxf | 2,909 | Pattern layout |
| Skinny Cargo_2D.dxf | 5,218 | Pattern layout |
| Skinny Trousers_2D.dxf | 4,948 | Pattern layout |

---

## Validation Performed

### Pipeline Execution
- **Method**: Ran `pipeline.py` on all 9 input files
- **Result**: 9/9 successful, 0 errors

### XML Extraction Validation
- **Method**: Compared extracted XML document sizes against expected
- **Result**: All XML documents extracted completely (proper closing tags found)

### Canonical JSON Validation
- **Method**: Verified JSON structure and field presence
- **Result**: All required fields present for patterns and markers

### DXF/PLT Generation
- **Method**: Verified file creation and non-zero sizes
- **Result**: All expected files generated

### NOT YET VALIDATED (Requires Optitex Oracle Exports)
- Geometry accuracy (our DXF vs Optitex DXF)
- Coordinate precision
- Actual contour shapes (currently using bounding boxes)
- Notch/drill positions
- HPGL rendering accuracy

---

## Findings

### What Works
1. Binary file magic detection: All files share `dc54ef12` prefix
2. XML extraction: Reliable detection of `<?xml ... ?>` declaration and root element matching
3. STYLE (PDS) and MARKER (MRK) XML parsing: All required fields extracted
4. Canonical model generation: Clean JSON structure for downstream processing
5. DXF generation: Valid DXF files with polylines and text
6. HPGL/2 generation: Valid PLT files with proper pen commands

### Known Limitations
1. **No actual contour geometry**: The embedded XML only contains summary info (size_x, size_y, area, perimeter), not actual point coordinates. Actual contours are in the binary sections.
2. **Bounding boxes only**: Current DXF/PLT exports use rectangular bounding boxes, not actual piece shapes.
3. **No curves/beziers**: Even when we decode contours, curve handling needs special attention for HPGL/2 (which supports arcs but not arbitrary beziers).
4. **No oracle validation yet**: We haven't compared against Optitex-exported DXF/PLT files.

### Hypotheses for Next Steps
1. Actual contour geometry is likely stored after the embedded XML in binary form (little-endian float32 arrays)
2. The header before XML contains section offsets/counts
3. Grading rules and notch coordinates are in binary, referenced by indices in XML

---

## Next Run Plan

### RUN-002: Oracle Baseline Capture
1. Run the generated batch scripts:
   - `batch_scripts\run_all_exports.bat` (or individual scripts)
   - This will export PDML/DXF from PDS files via PDS.exe
   - This will export DXF/PLT from MRK files via Mark.exe
2. Document any manual export dialog settings with screenshots
3. Store oracle exports in `oracle/pds/` and `oracle/mrk/`
4. Verify exported files and compute hashes

### Batch Scripts Generated
| Script | Source | Target Exports |
|--------|--------|----------------|
| export_Basic Tee_2D.txt | Basic Tee_2D.PDS | PDML, DXF |
| export_Light  Jacket_2D.txt | Light  Jacket_2D.PDS | PDML, DXF |
| export_Skinny Cargo_2D.txt | Skinny Cargo_2D.PDS | PDML, DXF |
| export_Skinny Trousers_2D.txt | Skinny Trousers_2D.PDS | PDML, DXF |
| export_Basic Pants.txt | Basic Pants.MRK | DXF, PLT |
| export_Jacket Sloper.txt | Jacket Sloper.MRK | DXF, PLT |
| export_Nest++Shirt_Result2.txt | Nest++Shirt_Result2.MRK | DXF, PLT |
| export_Stripe Pants.txt | Stripe Pants.MRK | DXF, PLT |
| export_Stripe Pants_Result4.txt | Stripe Pants_Result4.MRK | DXF, PLT |

### RUN-003: Binary Geometry Parsing
1. Use PDML coordinates as "known plaintext" to locate binary offsets
2. Decode contour point arrays from binary
3. Update DXF/PLT exports to use actual geometry

### RUN-004: Validation
1. Compare our DXF vs Optitex DXF (overlay + metrics)
2. Compare our PLT vs Optitex PLT (if available)
3. Document any discrepancies

---

## Appendix

### Scripts Created
| Script | Purpose |
|--------|---------|
| `hash_files.py` | Generate SHA256 manifest |
| `binary_recon.py` | Initial binary analysis |
| `extract_embedded.py` | Extract XML/JPEG from binaries |
| `canonical_models.py` | Define PatternModel/MarkerModel |
| `xml_parser.py` | Parse STYLE/MARKER XML |
| `dxf_exporter.py` | Export to DXF |
| `hpgl_exporter.py` | Export to HPGL/2 PLT |
| `batch_export.py` | Batch export canonical JSON |
| `pipeline.py` | End-to-end orchestration |

### Key Observations from Binary Analysis
1. All files start with magic `dc 54 ef 12`
2. Header appears to be 44-62 bytes before embedded content starts
3. PDS files: XML typically at offset 44-2600, JPEG (if present) before XML
4. MRK files: XML typically at offset 48-51, JPEG after XML
5. XML sizes range from 14KB to 115KB
6. JPEG sizes range from 2.5KB to 6.3KB (thumbnails)
