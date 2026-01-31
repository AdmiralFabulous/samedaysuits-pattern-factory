# Quick Reference: Automated PDS Reverse Engineering

## The Oracle Approach

Since you have Optitex, you can use it as a **ground truth oracle**:
1. Generate test files with **known properties**
2. Export to both binary (.pds) and XML (.pdml)
3. Parse binary with your parser
4. Compare against PDML "truth"
5. Use discrepancies to fix parser

## One-Command Pipeline

```bash
python scripts/automated_re_pipeline.py \
    "C:/Program Files/Optitex/Optitex 21/PDS.exe" \
    ./reverse_engineering_results
```

## What It Does

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: GENERATE                                              │
│  ├── Creates 20+ test cases (geometry, grading, notches, etc.)  │
│  └── Generates Optitex batch scripts                            │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 2: EXECUTE                                               │
│  ├── Runs each batch script in Optitex                          │
│  └── Outputs: .pds (binary) + .pdml (XML truth)                 │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 3: PARSE                                                 │
│  ├── Parses each .pds with your custom parser                   │
│  └── Outputs: .json (your parser's interpretation)              │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 4: ANALYZE                                               │
│  ├── Compares your JSON vs PDML XML                             │
│  └── Identifies: coordinate errors, missing fields, etc.        │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 5: REPORT                                                │
│  └── Generates: HTML report, Markdown summary, JSON data        │
└─────────────────────────────────────────────────────────────────┘
```

## Output Structure

```
reverse_engineering_results/
├── batch_scripts/          # Optitex batch files
│   ├── geometry_square_100.txt
│   ├── grading_5sizes.txt
│   └── ...
├── test_outputs/           # Files created by Optitex
│   ├── geometry_square_100.pds    ← Binary to parse
│   ├── geometry_square_100.pdml   ← Ground truth XML
│   └── geometry_square_100.dxf    ← Optional DXF export
├── parse_results/          # Your parser output
│   └── geometry_square_100.json
└── reports/
    ├── report.html         # Visual summary
    ├── report.md           # Text summary
    ├── differential_report.json  # Detailed comparisons
    └── pipeline_results.json     # Full pipeline data
```

## Interpreting Results

### HTML Report Shows:
- **Parser Accuracy %**: Target > 99%
- **Test Case Count**: How many scenarios tested
- **Phase Status**: Where failures occurred

### Differential Report Shows:
```json
{
  "failures": [
    {
      "test": "geometry_square_100",
      "field": "piece_0_point_2_x",
      "expected": 100.0,
      "actual": 0.0,
      "error": 100.0
    }
  ]
}
```
**This means**: Your parser read X=0 where PDML says X=100

## Fixing Parser Issues

### Common Problems & Solutions

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Coordinates off by 100x | Unit scaling (cm vs mm) | Apply scale factor |
| Coordinates negative | Wrong endianness | Use `<f` not `>f` |
| All points at (0,0) | Wrong offset in file | Check header size |
| Piece count wrong | Misaligned structure | Verify field order |
| Strings garbled | Wrong encoding | Use UTF-8 not ASCII |

### Iteration Workflow

```bash
# 1. Run pipeline
python scripts/automated_re_pipeline.py "$OPTITEX" ./re_results

# 2. Check accuracy
cat ./re_results/reports/differential_report.json | jq '.summary'

# 3. View failures
cat ./re_results/reports/differential_report.json | jq '.failures[:5]'

# 4. Fix parser based on failure patterns
#    Edit: scripts/pds_parser.py

# 5. Re-run to verify
python scripts/automated_re_pipeline.py "$OPTITEX" ./re_results_v2

# 6. Compare accuracy improvements
```

## Test Case Matrix

The pipeline automatically generates tests for:

| Category | Tests | Purpose |
|----------|-------|---------|
| **Geometry** | Square 100/200, Rect, Circle, Polygon | Find coordinate encoding |
| **Piece Count** | 1, 2, 5, 10, 50 pieces | Find piece array structure |
| **Grading** | 1, 2, 5, 10 sizes | Find grading table format |
| **Notches** | 0, 1, 3 notches (V, T types) | Find internal object format |
| **Drills** | 0, 1, 5 drill holes | Find point-based internals |
| **Units** | mm, cm, inch | Find unit encoding |
| **Metadata** | Short/long/unicode names | Find string encoding |

## Advanced: Custom Test Cases

Add to `automated_re_pipeline.py`:

```python
def _create_test_matrix(self):
    return {
        # ... existing tests ...
        
        'my_custom': [
            ('test1', {'shape': 'rect', 'w': 50, 'h': 75, 'notches': 2}),
            ('test2', {'shape': 'circle', 'radius': 150, 'sizes': 3}),
        ],
    }
```

## Batch Command Reference

The pipeline uses these Optitex batch commands:

| Command | Purpose |
|---------|---------|
| `@NEW` | Create new file |
| `@UNIT CM` | Set units |
| `@NEWPIECE "Name"` | Create piece |
| `@ADDPOINT /X= /Y=` | Add contour point |
| `@CLOSECONTOUR` | Close shape |
| `@ADDNOTCH /TYPE=V` | Add notch |
| `@SETSIZECOUNT N` | Set number of sizes |
| `@ADDRULE /SIZE= /DX= /DY=` | Add grading rule |
| `@SAVE "file.pds" /FORMAT=PDS` | Save binary |
| `@SAVE "file.pdml" /FORMAT=PDML` | Save XML |

## Troubleshooting

### "Optitex not found"
```bash
# Verify path
ls "C:/Program Files/Optitex/Optitex 21/PDS.exe"

# Use full path with quotes (spaces in path)
python scripts/automated_re_pipeline.py \
    "C:/Program Files/Optitex/Optitex 21/PDS.exe" \
    ./results
```

### "All tests fail"
- Check Optitex license is active
- Verify batch scripts are valid
- Run a single batch manually to debug

### "Parser not found"
```bash
# Ensure scripts are in Python path
cd /path/to/pds_reverse_engineering
python scripts/automated_re_pipeline.py ...
```

### "Accuracy stuck at 0%"
- Your parser structure is likely wrong
- Start with simpler test (1 piece, 1 size)
- Use `pdml_correlator.py` to find coordinate offsets

## Success Metrics

| Milestone | Target |
|-----------|--------|
| Header parsing | 100% accuracy |
| Piece counts | 100% accuracy |
| Coordinate reading | < 0.1mm error |
| Grading rules | 100% accuracy |
| Full file parsing | > 99% accuracy |

## Next Steps After High Accuracy

1. **Export to open formats**: SVG, DXF, JSON
2. **Build viewer**: Web-based PDS viewer
3. **Create converter**: PDS ↔ other CAD formats
4. **Document spec**: Update Kaitai .ksy file
5. **Share findings**: Contribute to community

## Key Files

| File | Purpose |
|------|---------|
| `scripts/automated_re_pipeline.py` | Main pipeline |
| `scripts/pds_parser.py` | Your parser (edit this) |
| `scripts/differential_analyzer.py` | Comparison engine |
| `ksy/optitex_pds.ksy` | Format specification |
| `reports/differential_report.json` | Error details |

## One-Liners

```bash
# Run full pipeline
python scripts/automated_re_pipeline.py "$OPTITEX" ./results

# Check accuracy
cat ./results/reports/differential_report.json | jq '.summary.success_rate'

# View top failures
cat ./results/reports/differential_report.json | jq '.failures[:10]'

# Count test outputs
ls ./results/test_outputs/*.pds | wc -l

# Compare file sizes
ls -lh ./results/test_outputs/*.{pds,pdml} | head -20
```

## Summary

This automated approach gives you:
- ✅ **Measurable progress** (accuracy %)
- ✅ **Rapid iteration** (run → fix → repeat)
- ✅ **Systematic coverage** (all features tested)
- ✅ **Ground truth validation** (PDML oracle)
- ✅ **Regression prevention** (re-run after changes)

**The goal**: Achieve > 99% parser accuracy through iterative differential testing.
