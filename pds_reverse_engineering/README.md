# Optitex PDS Reverse Engineering Toolkit

A comprehensive toolkit for reverse engineering the proprietary Optitex PDS (Pattern Design System) file format.

## Overview

This toolkit provides a systematic approach to understanding and parsing the Optitex PDS binary file format through:

- **PDML Analysis**: Using Optitex's XML export as a "Rosetta Stone"
- **Controlled Diff Analysis**: Systematically varying files to identify structure
- **Binary Pattern Recognition**: Statistical and ML-based pattern detection
- **Formal Specification**: Kaitai Struct specification for documentation

## Directory Structure

```
pds_reverse_engineering/
├── docs/               # Documentation and methodology guides
├── scripts/            # Python analysis and parsing tools
├── ksy/               # Kaitai Struct specifications
└── samples/           # Test file series (create this)
```

## Quick Start

### 1. Environment Setup

```bash
# Install dependencies
pip install numpy matplotlib scipy scikit-learn lxml

# Optional: Install Kaitai Struct compiler
# https://kaitai.io/#download
```

### 2. Generate Test Files

Using Optitex PDS, create controlled test files:

**Series A - Geometry Variations:**
- `A01_base.pds` - Single square (100x100mm)
- `A02_rect.pds` - Rectangle (200x100mm)
- `A03_circle.pds` - Circle approximation (Bezier curves)
- `A04_poly8.pds` - 8-sided polygon
- `A05_poly100.pds` - 100-sided polygon

**Series B - Piece Count:**
- `B01_1piece.pds` - 1 piece
- `B02_2pieces.pds` - 2 pieces
- `B05_5pieces.pds` - 5 pieces
- `B10_10pieces.pds` - 10 pieces

**Series C - Size/Grading:**
- `C01_1size.pds` - Base size only
- `C02_2sizes.pds` - 2 sizes
- `C05_5sizes.pds` - 5 sizes

### 3. Export PDML

For each PDS file, export to PDML format:
```
File > Save As > Format: PDML
```

### 4. Run Analysis

```bash
# Binary profiling
python scripts/binary_profiler.py samples/ output/profiles/

# PDML correlation
python scripts/pdml_correlator.py sample.pds sample.pdml output/correlation.json

# Pattern recognition
python scripts/pattern_recognizer.py sample.pds output/patterns.png

# Diff analysis
python scripts/diff_analyzer.py --campaign samples/ output/diffs/
```

### 5. Parse PDS Files

```bash
python scripts/pds_parser.py sample.pds output/result.json
```

### 6. Export to Open Formats

```bash
# Export to SVG
python scripts/exporters.py sample.pds output.svg svg

# Export to DXF
python scripts/exporters.py sample.pds output.dxf dxf

# Export to JSON
python scripts/exporters.py sample.pds output.json json
```

### 7. Validate Parser

```bash
python scripts/validator.py /path/to/Optitex/PDS.exe samples/ output/validation.json
```

## Core Methodology

### The "Known Plaintext" Approach

Since we have access to Optitex and can export PDML:

1. **Create** a PDS file with known values (e.g., square at specific coordinates)
2. **Export** to PDML (gives us the "plaintext")
3. **Search** binary for those known values
4. **Document** the encoding (endianness, data type, offset)
5. **Repeat** with variations to confirm patterns

### Analysis Pipeline

```
PDS Files → PDML Export → Correlation Analysis → Structure Hypothesis
     ↓                                              ↓
Binary Profile → Pattern Recognition ←→ Diff Analysis
     ↓                                              ↓
              Kaitai Specification ←→ Parser Implementation
                              ↓
                    Validation & Iteration
```

## Tools Reference

### binary_profiler.py
Initial file analysis - entropy, strings, magic bytes, float detection.

```bash
python binary_profiler.py <samples_dir> <output_dir>
```

**Output:**
- `binary_profiles.json` - Comprehensive file profiles
- `entropy_profiles.png` - Entropy visualization
- `header_comparison.png` - Header byte comparison

### pdml_correlator.py
Maps PDML data to binary offsets.

```bash
python pdml_correlator.py <pds_file> <pdml_file> <output_json>
```

**Output:**
- Correlation report with offset mappings
- Failed search analysis
- Encoding type summary

### diff_analyzer.py
Compares file pairs to identify structure changes.

```bash
# Single comparison
python diff_analyzer.py <base_file> <modified_file> <output_dir>

# Batch campaign
python diff_analyzer.py --campaign <samples_dir> <output_dir>
```

**Output:**
- Diff visualizations
- Value change reports
- Insertion/deletion analysis

### pattern_recognizer.py
Statistical pattern detection.

```bash
python pattern_recognizer.py <pds_file> [output_png]
```

**Output:**
- Float array detection
- Integer array detection
- String table identification
- Pattern visualization

### pds_parser.py
Reference parser implementation.

```bash
python pds_parser.py <pds_file> <output_json>
```

**Output:**
- Parsed PDS data as JSON
- Parse error reporting

### validator.py
Validates parser against Optitex PDML export.

```bash
# Single file
python validator.py <optitex_path> <pds_file> <output_json> --single

# Batch validation
python validator.py <optitex_path> <samples_dir> <output_json>
```

**Output:**
- Validation report with coverage metrics
- Detailed difference analysis

### exporters.py
Export to open formats.

```bash
python exporters.py <pds_file> <output_file> <format>
# format: svg, dxf, json
```

## Kaitai Struct Specification

The `ksy/optitex_pds.ksy` file contains a formal specification that can be compiled to parsers in multiple languages:

```bash
# Compile to Python
kaitai-struct-compiler --target python ksy/optitex_pds.ksy

# Compile to other languages
kaitai-struct-compiler --target java ksy/optitex_pds.ksy
kaitai-struct-compiler --target csharp ksy/optitex_pds.ksy
```

## Understanding the Format

### High-Level Structure

```
┌─────────────────────────────────────┐
│            HEADER (~44 bytes)       │
├─────────────────────────────────────┤
│          METADATA (variable)        │
│  - Style name                       │
│  - File path                        │
│  - Creation/modification dates      │
│  - XML header                       │
├─────────────────────────────────────┤
│         SIZE TABLE (variable)       │
│  - Size names                       │
│  - Measurements                     │
│  - Grading rules                    │
├─────────────────────────────────────┤
│          PIECES (variable)          │
│  ┌───────────────────────────────┐  │
│  │        PIECE HEADER           │  │
│  │  - Code, name, description    │  │
│  │  - Counts (points, notches)   │  │
│  ├───────────────────────────────┤  │
│  │        CONTOUR DATA           │  │
│  │  - Array of (x,y) points      │  │
│  ├───────────────────────────────┤  │
│  │       INTERNAL LINES          │  │
│  ├───────────────────────────────┤  │
│  │          NOTCHES              │  │
│  ├───────────────────────────────┤  │
│  │        DRILL HOLES            │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

### Data Types

| Type | Size | Description |
|------|------|-------------|
| `uint8` | 1 byte | Small integers, flags |
| `uint16` | 2 bytes | Lengths, counts |
| `uint32` | 4 bytes | Large counts, offsets |
| `uint64` | 8 bytes | Timestamps |
| `float32` | 4 bytes | Coordinates (little-endian) |
| `string` | 1+n bytes | Length-prefixed UTF-8 |

### Key Findings (To Be Verified)

1. **Coordinates**: float32, little-endian
2. **String encoding**: Length-prefixed UTF-8
3. **Header size**: ~44 bytes (version dependent)
4. **Point structure**: x (4) + y (4) + type (1) + flags (1) = 10 bytes

## Troubleshooting

### Parser Fails on File

1. Check file version with `binary_profiler.py`
2. Export PDML and run `pdml_correlator.py`
3. Compare with known-good files using `diff_analyzer.py`

### Coordinates Don't Match

1. Verify endianness (likely little-endian)
2. Check for scaling factors (mm vs cm)
3. Look for offset/transform values in header

### Strings Not Found

1. Try different encodings (ASCII, UTF-8, UTF-16LE)
2. Check for length-prefix byte(s)
3. Look for null-terminated strings

## Contributing

To extend this toolkit:

1. Add new test file series for specific features
2. Implement additional analysis methods
3. Improve parser based on new findings
4. Update Kaitai specification

## Legal Notice

This toolkit is for educational and interoperability purposes. The PDS format is proprietary to Optitex. This project does not distribute any proprietary software or copyrighted material.

## Timeline Estimate

| Phase | Duration |
|-------|----------|
| Setup & Samples | 1 week |
| Initial Analysis | 2 weeks |
| Structure Identification | 3 weeks |
| Parser Development | 2 weeks |
| Validation & Refinement | 2 weeks |
| **Total** | **10 weeks** |

## Resources

- [Kaitai Struct](https://kaitai.io/) - Binary format DSL
- [010 Editor](https://www.sweetscape.com/010editor/) - Hex editor with templates
- [Binwalk](https://github.com/ReFirmLabs/binwalk) - Firmware analysis
- [Optitex Documentation](https://optitex.com/) - Official resources

## License

This toolkit is provided for educational purposes. Respect intellectual property rights when working with proprietary formats.
