# UI-TARS Quick Start for PDS Reverse Engineering

## What You Need

1. **Optitex PDS** installed and licensed
2. **UI-TARS Desktop** from ByteDance
3. **Python 3.10+** with requests library

---

## Installation

### Step 1: Install UI-TARS Desktop

```bash
# Download from GitHub releases
curl -L -o ui-tars-desktop.exe https://github.com/bytedance/UI-TARS-desktop/releases/download/v0.2.0/UI-TARS-Desktop-Setup-0.2.0.exe

# Or download manually from:
# https://github.com/bytedance/UI-TARS-desktop/releases
```

### Step 2: Configure UI-TARS

1. Launch UI-TARS Desktop
2. Go to Settings
3. Configure Vision Model API:
   - OpenAI GPT-4V API key, OR
   - Anthropic Claude API key, OR
   - Local model endpoint
4. Set screen capture permissions
5. Test with simple task: "Open calculator and calculate 2+2"

### Step 3: Install Python Integration

```bash
# In your pds_reverse_engineering directory
pip install requests pillow

# No special SDK needed - uses HTTP API or CLI
```

---

## First Test: Create a Simple Square

### Using the Controller Script

```bash
cd /path/to/pds_reverse_engineering

python scripts/ui_tars_controller.py square 100
```

This will:
1. Launch UI-TARS (if not running)
2. Open Optitex PDS
3. Create a 100mm square piece
4. Save as `geometry_square_100.pds`
5. Export as `geometry_square_100.pdml`
6. Take screenshots
7. Save metadata

### Output Location

```
ui_tars_output/
├── pds/
│   └── geometry_square_100.pds
├── pdml/
│   └── geometry_square_100.pdml
├── screenshots/
│   ├── geometry_square_100_step1.png
│   ├── geometry_square_100_step2.png
│   └── geometry_square_100_final.png
└── metadata/
    └── geometry_square_100.json
```

---

## Running Full Test Suite

```bash
# Run comprehensive test suite (20+ test cases)
python scripts/ui_tars_controller.py full

# Generates:
# - Test PDS files for all scenarios
# - PDML ground truth files
# - Screenshots for verification
# - HTML report: ui_tars_report.html
```

---

## Integration with Existing Pipeline

### Enhanced Pipeline with UI-TARS

```python
from scripts.ui_tars_controller import UITarsOptitexController
from scripts.automated_re_pipeline import AutomatedREPipeline

# Phase 1: UI-TARS generates test files
ui_tars = UITarsOptitexController(
    optitex_exe="C:/Program Files/Optitex/Optitex 21/PDS.exe",
    output_dir="./ui_tars_tests"
)

# Generate specific test
result = ui_tars.create_simple_square(100)

# Phase 2: Parse with custom parser
from scripts.pds_parser import PDSParser

parser = PDSParser(result.outputs['pds'])
parsed = parser.parse()

# Phase 3: Compare against PDML ground truth
from scripts.differential_analyzer import DifferentialAnalyzer

analyzer = DifferentialAnalyzer()
analyzer.analyze_test_case(
    "square_100",
    result.outputs['pds'],
    result.outputs['pdml'],
    parsed
)

# Phase 4: Check accuracy
report = analyzer.generate_report("analysis.json")
print(f"Accuracy: {report['summary']['success_rate']*100:.1f}%")
```

---

## Common Tasks

### Create Graded Pattern

```bash
python scripts/ui_tars_controller.py grading 5 10
# Creates: 5 sizes, 10mm grade step
```

### Create Piece with Notches

```bash
python scripts/ui_tars_controller.py notches 3 V
# Creates: 3 V-notches
```

### Create Complex Garment

```bash
python scripts/ui_tars_controller.py garment shirt
# Creates: Complete shirt pattern
```

---

## Troubleshooting

### UI-TARS Can't Find Optitex Window

```python
# In your task, explicitly mention:
task = """
Before starting, ensure Optitex PDS is running.
If not, launch it from: C:/Program Files/Optitex/Optitex 21/PDS.exe
Wait for the application to fully load.
...
"""
```

### Screenshots Not Saving

1. Check UI-TARS has screen capture permissions
2. Verify output directory exists and is writable
3. Check UI-TARS settings for screenshot location

### Task Timeout

```python
# Increase timeout for complex tasks
controller = UITarsOptitexController(
    # ... other settings ...
    screenshot_interval=5.0  # Slower but more reliable
)
```

### API Rate Limits

If using OpenAI/Claude:
- Add delays between tasks
- Consider using local vision model
- Batch operations when possible

---

## Advanced: Custom Tasks

```python
from scripts.ui_tars_controller import UITarsController, UITarsTask

controller = UITarsOptitexController(
    optitex_exe="C:/Program Files/Optitex/Optitex 21/PDS.exe",
    output_dir="./custom_tests"
)

# Define custom task
custom_task = UITarsTask(
    name="my_custom_test",
    description="""
Create a specific pattern:
1. Create piece with irregular shape
2. Add internal dart
3. Set variable seam allowance
4. Grade for 7 sizes
5. Add 3D fabric
""",
    expected_outputs=['pds', 'pdml'],
    verification_steps=[
        "Piece has correct shape",
        "Dart is visible",
        "Seam allowance varies",
        "7 sizes in grading table"
    ]
)

# Execute
result = controller.execute_task(custom_task)
print(f"Success: {result.success}")
print(f"Outputs: {result.outputs}")
```

---

## Best Practices

### 1. Start Simple

```bash
# Test with basic shapes first
python scripts/ui_tars_controller.py square 100
python scripts/ui_tars_controller.py square 200
```

### 2. Verify Outputs

```bash
# Check files were created
ls ui_tars_output/pds/
ls ui_tars_output/pdml/

# View screenshots to verify visually
open ui_tars_output/screenshots/*.png
```

### 3. Iterate on Failures

```bash
# If a test fails, check metadata
cat ui_tars_output/metadata/geometry_square_100.json | jq '.error'

# View screenshots to see what went wrong
open ui_tars_output/screenshots/geometry_square_100_*.png
```

### 4. Combine with Parser

```bash
# After UI-TARS creates files, parse them
python scripts/pds_parser.py \
    ui_tars_output/pds/geometry_square_100.pds \
    output/parsed.json

# Compare with PDML
cat output/parsed.json | jq '.pieces[0].contour'
cat ui_tars_output/pdml/geometry_square_100.pdml | grep -A5 '<Contour>'
```

---

## Next Steps

1. **Run full test suite**: `python scripts/ui_tars_controller.py full`
2. **Integrate with parser**: Parse generated PDS files
3. **Analyze differences**: Compare parser output vs PDML
4. **Iterate**: Fix parser, re-run, improve accuracy
5. **Document**: Update Kaitai spec with findings

---

## Resources

- **UI-TARS GitHub**: https://github.com/bytedance/UI-TARS-desktop
- **UI-TARS Docs**: https://agent-tars.com/
- **Our Docs**:
  - `docs/10_UI_TARS_INTEGRATION.md` - Full integration guide
  - `docs/11_UI_TARS_VS_TRADITIONAL.md` - Comparison
  - `docs/08_AUTOMATED_TESTING_STRATEGY.md` - Pipeline strategy

---

## Summary

UI-TARS transforms PDS reverse engineering by:
- ✅ Natural language test creation
- ✅ Visual verification via screenshots
- ✅ OCR extraction of UI values
- ✅ Discovery of undocumented features
- ✅ Human-like flexibility

**Start with**: `python scripts/ui_tars_controller.py square 100`
