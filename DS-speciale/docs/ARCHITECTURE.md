# DS-speciale Architecture

## File Format Relationships

### PDS (Pattern Design System)
- Contains piece definitions with full geometry
- Embedded XML (`<STYLE>`) provides metadata: piece names, sizes, size summaries (area, perimeter)
- Binary sections contain actual contour point coordinates
- May contain embedded JPEG thumbnails

### MRK (Marker/Nesting)
- Contains piece PLACEMENTS, not piece geometry
- References external PDS file(s) for actual geometry
- Embedded XML (`<MARKER>`) provides:
  - Fabric dimensions (length, width)
  - Placement coordinates (X-CENTER, Y-CENTER, ANGLE, FLIP)
  - Piece metadata (from referenced PDS)
  - Nesting efficiency statistics
- Binary sections may contain additional placement data or optimization info

### Critical Architecture Point

**MRK files do NOT contain piece contour geometry.**

The geometry is in the referenced PDS file(s). Example from Basic Pants.MRK XML:
```xml
<STYLE>
   <NAME>Basic pants-For Eva</NAME>
   <FILENAME>K:\Install\Ver10 Samples\PDS\...\Basic pants-For Eva.PDS</FILENAME>
```

To render a complete marker layout:
1. Parse MRK to get placements (x, y, angle, flip)
2. Load the referenced PDS file(s)
3. Parse PDS to get piece contours
4. Apply placement transforms to contours
5. Export to DXF/PLT

## Current Implementation Status

### Working
- Extract embedded XML from PDS and MRK
- Parse XML to canonical JSON models
- Export DXF/PLT with bounding box placeholders

### Pending
- Decode actual contour points from PDS binary
- Link MRK placements to PDS geometry
- Export true contour geometry in DXF/PLT

## Data Flow

```
PDS File                           MRK File
    |                                  |
    v                                  v
[Binary + XML]                   [Binary + XML]
    |                                  |
    v                                  v
PatternModel                     MarkerModel
    |                                  |
    +----------+    +------------------+
               |    |
               v    v
        [Placement Engine]
               |
               v
        [DXF/PLT Exporter]
               |
               v
        Plotter-Ready Output
```

## Geometry Location in PDS Files

Based on binary analysis:
- Header: first 44-62 bytes (magic, version, section info)
- JPEG thumbnail (optional): varies, ~2.5KB
- XML section: 14-54KB of `<STYLE>...</STYLE>`
- Binary geometry section: after XML, potentially 100KB+

The binary geometry section likely contains:
- Per-piece contour point arrays (float32 x, y pairs)
- Curve type flags (corner vs bezier)
- Notch/drill positions and types
- Grading rules (size-specific point offsets)

## Next Steps for Full Pipeline

1. **Oracle Capture**: Export DXF from Optitex for PDS files
   - This gives us "ground truth" geometry to compare against
   - We can extract coordinates from the DXF and search for them in binary

2. **Binary Correlation**: Use known DXF coordinates as "known plaintext"
   - Search PDS binary for float32 matches
   - Identify offset, endianness, and array structure

3. **Contour Parsing**: Implement PDS binary parser for geometry
   - Decode point arrays
   - Handle curve types
   - Extract notches/drills

4. **MRK-PDS Linking**: Match marker placements to pattern pieces
   - By piece name/code
   - Apply transforms (translate, rotate, flip)

5. **True Geometry Export**: Update DXF/PLT exporters
   - Use actual contours instead of bounding boxes
   - Preserve curves where possible
