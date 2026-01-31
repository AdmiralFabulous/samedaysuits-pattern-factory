# Quick Start Guide - PDS Reverse Engineering

## Immediate First Steps

### 1. Set Up Your Environment (15 minutes)

```bash
# Create workspace
mkdir -p ~/pds_research/{samples,output}

# Install Python dependencies
pip install numpy matplotlib scipy scikit-learn lxml

# Optional: Install hex editor
# Linux: sudo apt-get install bless
# Windows: Download HxD or 010 Editor
# Mac: brew install hexfiend
```

### 2. Generate Your First Test Files (30 minutes)

In Optitex PDS, create these files:

**File 1: Simple Square**
- Create single piece: square 100mm x 100mm
- Save as: `A01_square100.pds`
- Export PDML: `A01_square100.pdml`

**File 2: Different Size**
- Same square, 200mm x 200mm
- Save as: `A02_square200.pds`
- Export PDML: `A02_square200.pdml`

**File 3: Rectangle**
- Rectangle: 200mm x 100mm
- Save as: `A03_rect200x100.pds`
- Export PDML: `A03_rect200x100.pdml`

Place all files in `~/pds_research/samples/`

### 3. Run First Analysis (10 minutes)

```bash
cd ~/pds_reverse_engineering

# Profile the files
python scripts/binary_profiler.py ~/pds_research/samples/ ~/pds_research/output/

# Check the output
cat ~/pds_research/output/binary_profiles.json
```

### 4. Find Coordinate Locations (15 minutes)

```bash
# For each file, correlate with PDML
python scripts/pdml_correlator.py \
    ~/pds_research/samples/A01_square100.pds \
    ~/pds_research/samples/A01_square100.pdml \
    ~/pds_research/output/A01_correlation.json

# View the results
cat ~/pds_research/output/A01_correlation.json | python -m json.tool
```

### 5. Compare File Differences (10 minutes)

```bash
python scripts/diff_analyzer.py \
    ~/pds_research/samples/A01_square100.pds \
    ~/pds_research/samples/A02_square200.pds \
    ~/pds_research/output/

# View the diff visualization
open ~/pds_research/output/diff.png
```

### 6. Try the Parser (5 minutes)

```bash
python scripts/pds_parser.py \
    ~/pds_research/samples/A01_square100.pds \
    ~/pds_research/output/parsed.json

# Check if it worked
cat ~/pds_research/output/parsed.json
```

### 7. Export to SVG (5 minutes)

```bash
python scripts/exporters.py \
    ~/pds_research/samples/A01_square100.pds \
    ~/pds_research/output/A01.svg svg

# Open in browser or SVG viewer
open ~/pds_research/output/A01.svg
```

## What to Look For

### In binary_profiler.py output:
- **Magic bytes**: First 4 bytes of file
- **Float candidates**: Values that look like coordinates
- **String locations**: Where piece names appear

### In pdml_correlator.py output:
- **Successful correlations**: Offsets where known values appear
- **Encoding**: float32_le (little-endian float) is most likely
- **Failed searches**: Values that don't appear directly (may be transformed)

### In diff_analyzer.py output:
- **Changed bytes**: Locations that differ between files
- **Value changes**: How coordinates change with piece size
- **Pattern**: Are changes at fixed offsets or variable?

## Next Steps

Once you've verified the basic structure:

1. **Create more test files** with different features:
   - Multiple pieces
   - Different numbers of points
   - Curved edges (Bezier)
   - Notches and drill holes
   - Multiple sizes (grading)

2. **Run batch analysis**:
   ```bash
   python scripts/diff_analyzer.py --campaign samples/ output/
   ```

3. **Validate your parser**:
   ```bash
   python scripts/validator.py /path/to/Optitex/PDS.exe samples/ output/validation.json
   ```

## Key Questions to Answer

1. **Header structure**: What do the first 44 bytes contain?
2. **Coordinate encoding**: float32 little-endian?
3. **String encoding**: Length-prefixed UTF-8?
4. **Array structure**: How are point arrays stored?
5. **Piece boundaries**: How do you know where one piece ends and another begins?

## Common Issues

### "No correlations found"
- Check that PDML file matches PDS file
- Try different tolerances in pdml_correlator.py
- Look for scaled values (cm vs mm)

### "Parser fails"
- Check parser's expected structure against actual file
- Use binary_profiler.py to verify assumptions
- Compare with pdml_correlator.py output

### "Coordinates don't match"
- Verify endianness (likely little-endian)
- Check for scaling factors
- Look for transform/offset values

## Tips for Success

1. **Start simple**: Single piece, simple geometry
2. **Change one thing at a time**: Isolate variables
3. **Document everything**: Keep notes on findings
4. **Cross-validate**: Use multiple analysis methods
5. **Iterate**: Update hypothesis as you learn more

## Getting Help

- Review the full documentation in `docs/`
- Check `README.md` for detailed methodology
- Examine the Kaitai spec in `ksy/optitex_pds.ksy`

## Expected Timeline

| Task | Time |
|------|------|
| Setup & first files | 1 hour |
| Initial analysis | 2-4 hours |
| Structure hypothesis | 1-2 days |
| Parser working | 3-5 days |
| Full validation | 1 week |

Good luck! Document your findings and update the specifications as you discover the actual format.
