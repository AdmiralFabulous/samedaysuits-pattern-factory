# Run Log Template

Copy this template for every run.

---

## Run Metadata
- **Run ID**: RUN-###
- **Date/Time (Local)**: 
- **Date/Time (UTC)**: 
- **Operator**: 
- **Machine**:
  - Hostname: 
  - OS: Windows XX build XXXXX
  - Display scaling: 
  - Locale/decimal separator: 

## Optitex Environment
- **PDS.exe**: `C:\Program Files\Optitex\Optitex 25\App\PDS.exe`
  - Version (from About): 
- **Mark.exe**: `C:\Program Files\Optitex\Optitex 25\App\Mark.exe`
  - Version (from About): 25.0.1.176 (64-bit) (2025-05-20)
- **License state**: (trial/full, any warnings)

## Inputs
| File | Path | SHA256 |
|------|------|--------|
| | | |

## Objective
(Single sentence describing what this run aims to accomplish)

---

## Export Settings Diary

### PDS -> PDML
- **Menu path**: 
- **Dialog fields**:
  - Field 1: 
  - Field 2: 
- **Screenshot**: `screenshots/pds_pdml_export.png`

### PDS -> DXF
- **Menu path**: 
- **Dialog fields**:
  - Units: 
  - Scale: 
  - Curve handling: 
  - Layers: 
  - Seam allowance: 
- **Screenshot**: `screenshots/pds_dxf_export.png`

### MRK -> XML
- **Menu path**: 
- **Dialog fields**:
- **Screenshot**: `screenshots/mrk_xml_export.png`

### MRK -> DXF
- **Menu path**: 
- **Dialog fields**:
  - Units: 
  - Scale: 
- **Screenshot**: `screenshots/mrk_dxf_export.png`

### MRK -> PLT (HPGL/2)
- **Menu path**: `File > Export to CAD/CAM files...`
- **Format dropdown**: HPGL/2
- **Dialog fields**:
  - Working Units: 
  - Scale: 
  - Output precision/resolution: 
  - Curve/arc settings: 
  - Labels on/off: 
  - Notches on/off: 
  - Drills on/off: 
  - Cut order / optimization: 
  - Origin / zero point: 
  - Pen mapping / layers: 
  - Velocity reduction for curves: 
- **Screenshot**: `screenshots/mrk_plt_export.png`

---

## Actions Taken (Chronological)
1. 
2. 
3. 

---

## Outputs Produced

| File | Path | SHA256 | Size |
|------|------|--------|------|
| | | | |

---

## Validation Performed

### Semantic Checks (XML/PDML vs parsed JSON)
- Method: 
- Result: 

### Geometry Checks (our DXF vs Optitex DXF)
- Overlay tool/viewer: 
- Tolerance: 
- Bounding box match: 
- Per-piece perimeter match: 
- Notch/drill positions: 
- Result: 

### Plot Checks (our PLT vs Optitex PLT)
- HPGL viewer used: 
- Extents match: 
- Segment count: 
- Total cut length: 
- Result: 

---

## Findings

### What Matched
- 

### What Diverged
- 

### Hypotheses
- 

---

## Next Run Plan
(What will change and why)

---

## Appendix

### Screenshot Index
| Filename | Description |
|----------|-------------|
| | |

### Hashes File
Path: `hashes.csv`
