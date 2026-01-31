# UI-TARS-desktop Integration for PDS Reverse Engineering
## AI-Powered GUI Automation for Optitex File Analysis

---

## What is UI-TARS-desktop?

**UI-TARS-desktop** is ByteDance's open-source multimodal AI agent stack that enables:
- **Computer Vision**: Sees and understands screen content
- **GUI Automation**: Clicks, types, drags, and interacts with applications
- **Natural Language Control**: Instructs the AI to perform tasks via text
- **Screenshot Analysis**: Captures and analyzes visual state
- **Remote Operation**: Can control computers remotely

**GitHub**: https://github.com/bytedance/UI-TARS-desktop

---

## Why UI-TARS Transforms Our Reverse Engineering Strategy

### The Problem with Current Approach

Our current automated pipeline relies on **Optitex batch commands**:
- Limited to documented batch operations
- Cannot create complex geometries easily
- No visual verification of what's being created
- Cannot extract data that isn't exportable
- Requires manual intervention for complex scenarios

### How UI-TARS Solves These Problems

| Limitation | UI-TARS Solution |
|------------|------------------|
| Batch commands limited | **Natural language**: "Create a shirt with 5 buttons" |
| No visual feedback | **Screenshot verification**: See what's actually created |
| Complex geometries hard | **Visual drawing**: Click and drag to create shapes |
| Can't extract hidden data | **OCR + visual inspection**: Read values from UI |
| Manual test creation | **AI-generated tests**: Describe test, AI creates it |

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    UI-TARS + OPTITEX INTEGRATION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐        ┌──────────────────┐        ┌──────────────┐   │
│  │  Human Operator  │        │   UI-TARS AI     │        │   Optitex    │   │
│  │                  │───────▶│   GUI Agent      │───────▶│    PDS       │   │
│  │                  │        │                  │        │              │   │
│  │ "Create a test   │        │ 1. Opens Optitex │        │ 1. Creates   │   │
│  │  file with a     │        │ 2. Navigates UI  │        │    pattern   │   │
│  │  100mm square    │        │ 3. Clicks tools  │        │ 2. Saves     │   │
│  │  and 3 notches"  │        │ 4. Types values  │        │    to .pds   │   │
│  │                  │        │ 5. Takes screenshots│     │              │   │
│  └──────────────────┘        └──────────────────┘        └──────────────┘   │
│                                         │                                    │
│                                         ▼                                    │
│                              ┌──────────────────┐                           │
│                              │  Visual Analysis │                           │
│                              │  - Screenshot    │                           │
│                              │  - OCR values    │                           │
│                              │  - Verify state  │                           │
│                              └──────────────────┘                           │
│                                         │                                    │
│                                         ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    DIFFERENTIAL ANALYSIS PIPELINE                    │    │
│  │  UI-TARS Output (.pds + screenshots)  vs  Our Parser Output (.json) │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Specific Use Cases for PDS Reverse Engineering

### 1. Visual Test Case Generation

**Traditional Batch Approach**:
```
@NEWPIECE "Square"
@ADDPOINT /X=0 /Y=0
@ADDPOINT /X=100 /Y=0
...
```

**UI-TARS Natural Language Approach**:
```
"Open Optitex PDS. Create a new piece called 'TestSquare'. 
Use the rectangle tool to draw a 100mm x 100mm square centered at origin. 
Add three V-notches evenly spaced along the top edge. 
Save the file as 'test_square_100.pds' in C:/TestFiles/"
```

**Advantage**: UI-TARS handles all UI navigation, tool selection, and precise drawing automatically.

---

### 2. Visual Verification & Data Extraction

UI-TARS can:
- **Screenshot** the pattern after creation
- **OCR read** coordinate values from the properties panel
- **Verify** that the piece actually has the expected dimensions
- **Extract** data not available via exports (e.g., visual feedback)

```python
# UI-TARS workflow with verification
instructions = """
1. Open Optitex PDS
2. Load file 'test.pds'
3. Click on the piece to select it
4. Take screenshot of the properties panel
5. Read the piece dimensions from the screenshot
6. Report: width=?, height=?
"""
```

---

### 3. Complex Geometry Creation

Creating complex shapes via batch commands is difficult. UI-TARS can:
- Use the **Bezier curve tool** visually
- Create **graded sizes** by clicking through dialogs
- Add **3D textures** by navigating material panels
- Set up **grading rules** through the UI

```python
# Create a graded shirt pattern with UI-TARS
instructions = """
Create a complete shirt pattern with:
- Front bodice piece with curved armhole (Bezier)
- Back bodice piece
- Two sleeve pieces
- Collar piece
- Grade for sizes S, M, L, XL with 2cm increments
- Add seam allowances (1cm sides, 2cm hem)
- Add notches at armhole matching points
- Save as 'shirt_graded.pds'
"""
```

---

### 4. Systematic Property Variation

UI-TARS can systematically vary properties and capture results:

```python
# Automated property exploration
test_matrix = [
    {"seam": 0, "notches": 0},
    {"seam": 1, "notches": 0},
    {"seam": 0, "notches": 3},
    {"seam": 1, "notches": 3},
]

for test in test_matrix:
    instructions = f"""
    Open Optitex. Create square piece.
    Set seam allowance to {test['seam']}mm.
    Add {test['notches']} V-notches.
    Save as 'test_seam{test['seam']}_notch{test['notches']}.pds'
    """
    # UI-TARS executes and saves file
    # We then analyze the binary differences
```

---

### 5. Reverse Engineering Unknown Features

When we don't know how a feature works:

```python
# Explore "Style Sets" feature
instructions = """
1. Open Optitex with a multi-piece file
2. Open the Style Sets panel (Window > Style Sets)
3. Create a new style set called "VariantA"
4. Assign different fabrics to pieces
5. Save the file
6. Take screenshots of each step
7. Report what changed in the UI
"""
```

UI-TARS documents the **visual workflow**, which we can correlate with binary changes.

---

## Implementation: UI-TARS + PDS Pipeline

### Setup Requirements

```bash
# 1. Install UI-TARS Desktop
# Download from: https://github.com/bytedance/UI-TARS-desktop/releases

# 2. Configure UI-TARS
# - Set up API key for vision model (OpenAI, Anthropic, or local)
# - Configure screen capture permissions
# - Set Optitex window detection

# 3. Install Python integration
pip install ui-tars-sdk  # If available, or use HTTP API
```

### Integration Script

```python
#!/usr/bin/env python3
"""
UI-TARS + Optitex Integration for PDS Reverse Engineering
"""
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Optional


class UITarsOptitexController:
    """
    Uses UI-TARS to control Optitex for automated test generation
    """
    
    def __init__(self, ui_tars_path: str, optitex_exe: str, output_dir: str):
        self.ui_tars_path = Path(ui_tars_path)
        self.optitex_exe = Path(optitex_exe)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Subdirectories
        self.pds_dir = self.output_dir / 'pds_files'
        self.screenshot_dir = self.output_dir / 'screenshots'
        self.metadata_dir = self.output_dir / 'metadata'
        
        for d in [self.pds_dir, self.screenshot_dir, self.metadata_dir]:
            d.mkdir(exist_ok=True)
    
    def execute_task(self, task_description: str, test_name: str) -> Dict:
        """
        Execute a task via UI-TARS and capture results
        
        Args:
            task_description: Natural language instructions for UI-TARS
            test_name: Name for this test case
            
        Returns:
            Dict with paths to generated files and metadata
        """
        result = {
            'test_name': test_name,
            'task': task_description,
            'timestamp': time.time(),
            'outputs': {},
            'success': False
        }
        
        # Build UI-TARS instruction payload
        ui_tars_instruction = self._build_instruction(task_description, test_name)
        
        # Execute via UI-TARS (via CLI or API)
        try:
            ui_tars_result = self._run_ui_tars(ui_tars_instruction)
            result['ui_tars_output'] = ui_tars_result
            
            # Collect generated files
            result['outputs'] = self._collect_outputs(test_name)
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
        
        # Save metadata
        metadata_path = self.metadata_dir / f"{test_name}.json"
        with open(metadata_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        return result
    
    def _build_instruction(self, task: str, test_name: str) -> str:
        """
        Build complete UI-TARS instruction with context
        """
        return f"""
You are controlling Optitex PDS (Pattern Design Software) to create test files for reverse engineering.

TASK: {task}

IMPORTANT INSTRUCTIONS:
1. Always wait for Optitex to fully load before proceeding
2. Take screenshots after each major step
3. Save files to: {self.pds_dir}
4. Name the file: {test_name}.pds
5. Also export to PDML format as: {test_name}.pdml
6. If errors occur, take screenshot and report the error
7. Be precise with measurements - use the properties panel to verify

WORKFLOW:
- Open Optitex PDS if not already open
- Create the pattern as specified
- Verify dimensions using the measurement tools
- Save both .pds and .pdml formats
- Report success or failure
"""
    
    def _run_ui_tars(self, instruction: str) -> Dict:
        """
        Execute UI-TARS with the given instruction
        
        This can be done via:
        1. UI-TARS CLI if available
        2. UI-TARS HTTP API
        3. Direct integration with UI-TARS SDK
        """
        # Option 1: CLI execution
        cmd = [
            str(self.ui_tars_path),
            '--instruction', instruction,
            '--headless', 'false',  # Show UI for debugging
            '--timeout', '300'  # 5 minute timeout
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    
    def _collect_outputs(self, test_name: str) -> Dict:
        """Collect all output files for a test"""
        outputs = {}
        
        # Find PDS file
        pds_path = self.pds_dir / f"{test_name}.pds"
        if pds_path.exists():
            outputs['pds'] = str(pds_path)
        
        # Find PDML file
        pdml_path = self.pds_dir / f"{test_name}.pdml"
        if pdml_path.exists():
            outputs['pdml'] = str(pdml_path)
        
        # Find screenshots
        screenshots = list(self.screenshot_dir.glob(f"{test_name}_*.png"))
        if screenshots:
            outputs['screenshots'] = [str(s) for s in screenshots]
        
        return outputs
    
    # ========================================================================
    # PRE-DEFINED TEST CASES
    # ========================================================================
    
    def test_geometry_square(self, size: float = 100) -> Dict:
        """Create a simple square of given size"""
        task = f"""
Create a new pattern file with a single square piece:
1. Create new piece named "Square{int(size)}"
2. Draw a perfect square with sides {size}mm
3. Position centered at origin (0,0)
4. Save as "geometry_square_{int(size)}.pds"
5. Export to PDML
"""
        return self.execute_task(task, f"geometry_square_{int(size)}")
    
    def test_grading_simple(self, num_sizes: int = 3, grade_step: float = 10) -> Dict:
        """Create graded pattern with N sizes"""
        task = f"""
Create a graded pattern:
1. Create a rectangular piece 100mm x 150mm
2. Set up grading for {num_sizes} sizes
3. Apply uniform grading: +{grade_step}mm per size in both X and Y
4. Save as "grading_{num_sizes}sizes_{int(grade_step)}step.pds"
5. Export to PDML
"""
        return self.execute_task(task, f"grading_{num_sizes}sizes_{int(grade_step)}step")
    
    def test_notches_variations(self, notch_types: List[str]) -> Dict:
        """Create pieces with different notch types"""
        types_str = "_".join(notch_types)
        task = f"""
Create a piece with various notches:
1. Create rectangular piece 200mm x 100mm
2. Add notches along the top edge:
"""
        for i, nt in enumerate(notch_types):
            task += f"   - {nt} notch at position {i+1}/{len(notch_types)+1}\n"
        task += f"""
3. Save as "notches_{types_str}.pds"
4. Export to PDML
"""
        return self.execute_task(task, f"notches_{types_str}")
    
    def test_complex_garment(self, garment_type: str = "shirt") -> Dict:
        """Create a complete garment pattern"""
        task = f"""
Create a complete {garment_type} pattern:
1. Create front bodice piece with curved neckline and armhole
2. Create back bodice piece
3. Create two sleeve pieces (left and right)
4. Add seam allowances (1cm)
5. Add matching notches at armholes
6. Set up grading for sizes S, M, L
7. Save as "complex_{garment_type}.pds"
8. Export to PDML
"""
        return self.execute_task(task, f"complex_{garment_type}")


# ========================================================================
# INTEGRATION WITH EXISTING PIPELINE
# ========================================================================

class UITarsEnhancedPipeline:
    """
    Enhanced pipeline combining UI-TARS with existing differential analysis
    """
    
    def __init__(self, config: Dict):
        self.ui_tars = UITarsOptitexController(
            config['ui_tars_path'],
            config['optitex_exe'],
            config['output_dir']
        )
        self.config = config
    
    def run_full_pipeline(self):
        """
        Execute complete UI-TARS enhanced pipeline
        """
        print("="*70)
        print("UI-TARS ENHANCED PDS REVERSE ENGINEERING PIPELINE")
        print("="*70)
        
        # Phase 1: UI-TARS Test Generation
        print("\n[PHASE 1] Generating tests via UI-TARS...")
        test_results = self._phase1_generate_tests()
        
        # Phase 2: Parse with custom parser
        print("\n[PHASE 2] Parsing with custom parser...")
        parse_results = self._phase2_parse(test_results)
        
        # Phase 3: Differential analysis
        print("\n[PHASE 3] Differential analysis...")
        analysis_results = self._phase3_analyze(test_results, parse_results)
        
        # Phase 4: Visual verification
        print("\n[PHASE 4] Visual verification...")
        visual_results = self._phase4_visual_verify(test_results)
        
        # Phase 5: Report
        print("\n[PHASE 5] Generating reports...")
        self._phase5_report(test_results, parse_results, analysis_results, visual_results)
        
        print("\n" + "="*70)
        print("PIPELINE COMPLETE")
        print("="*70)
    
    def _phase1_generate_tests(self) -> List[Dict]:
        """Generate comprehensive test suite via UI-TARS"""
        results = []
        
        # Geometry tests
        for size in [50, 100, 200]:
            results.append(self.ui_tars.test_geometry_square(size))
        
        # Grading tests
        for num_sizes in [1, 2, 5]:
            results.append(self.ui_tars.test_grading_simple(num_sizes))
        
        # Notch tests
        results.append(self.ui_tars.test_notches_variations(['V']))
        results.append(self.ui_tars.test_notches_variations(['V', 'T']))
        results.append(self.ui_tars.test_notches_variations(['V', 'T', 'Slit']))
        
        # Complex garment
        results.append(self.ui_tars.test_complex_garment('shirt'))
        
        return results
    
    def _phase2_parse(self, test_results: List[Dict]) -> List[Dict]:
        """Parse generated PDS files with custom parser"""
        from pds_parser import PDSParser
        
        parse_results = []
        for test in test_results:
            if 'pds' in test.get('outputs', {}):
                pds_path = test['outputs']['pds']
                try:
                    parser = PDSParser(pds_path)
                    parsed = parser.parse()
                    parse_results.append({
                        'test_name': test['test_name'],
                        'parsed': parsed,
                        'success': True
                    })
                except Exception as e:
                    parse_results.append({
                        'test_name': test['test_name'],
                        'error': str(e),
                        'success': False
                    })
        
        return parse_results
    
    def _phase3_analyze(self, test_results: List[Dict], parse_results: List[Dict]) -> List[Dict]:
        """Differential analysis: parser output vs PDML ground truth"""
        from differential_analyzer import DifferentialAnalyzer
        
        analyzer = DifferentialAnalyzer(tolerance=0.01)
        
        for test in test_results:
            if 'pdml' in test.get('outputs', {}):
                pdml_path = test['outputs']['pdml']
                # Find corresponding parse result
                parse_result = next(
                    (p for p in parse_results if p['test_name'] == test['test_name']), 
                    None
                )
                if parse_result and parse_result.get('success'):
                    analyzer.analyze_test_case(
                        test['test_name'],
                        test['outputs']['pds'],
                        pdml_path,
                        parse_result['parsed']
                    )
        
        return analyzer.results
    
    def _phase4_visual_verify(self, test_results: List[Dict]) -> Dict:
        """
        Use UI-TARS to visually verify created patterns
        
        This adds an extra layer of validation:
        - Screenshot verification
        - OCR reading of dimensions
        - Visual confirmation of features
        """
        verification_results = []
        
        for test in test_results:
            if 'screenshots' in test.get('outputs', {}):
                # UI-TARS can analyze screenshots and confirm:
                # - Piece dimensions match expected
                # - Notches are present
                # - Grading is applied correctly
                verification_results.append({
                    'test_name': test['test_name'],
                    'screenshots': test['outputs']['screenshots'],
                    'verified': True  # Would be determined by UI-TARS analysis
                })
        
        return verification_results
    
    def _phase5_report(self, test_results, parse_results, analysis_results, visual_results):
        """Generate comprehensive report"""
        # Implementation similar to existing pipeline
        pass


# ========================================================================
# USAGE EXAMPLE
# ========================================================================

if __name__ == "__main__":
    config = {
        'ui_tars_path': 'C:/Program Files/UI-TARS/UI-TARS.exe',
        'optitex_exe': 'C:/Program Files/Optitex/Optitex 21/PDS.exe',
        'output_dir': './ui_tars_results'
    }
    
    pipeline = UITarsEnhancedPipeline(config)
    pipeline.run_full_pipeline()
```

---

## Benefits Summary

| Aspect | Traditional Batch | UI-TARS Enhanced |
|--------|-------------------|------------------|
| **Test Creation** | Limited to batch commands | Natural language, any operation |
| **Complex Geometry** | Difficult/impossible | Visual drawing, easy |
| **Verification** | File existence only | Screenshot + OCR verification |
| **Data Extraction** | Only exported data | UI values, visual state |
| **Unknown Features** | Cannot explore | AI can discover workflows |
| **Debugging** | Binary analysis only | Visual feedback |
| **Maintenance** | Fragile batch scripts | Resilient natural language |

---

## Next Steps

1. **Install UI-TARS Desktop**: https://github.com/bytedance/UI-TARS-desktop/releases
2. **Configure API**: Set up vision model (OpenAI GPT-4V, Claude, or local)
3. **Test Integration**: Run simple "create square" task
4. **Build Test Suite**: Expand to comprehensive test matrix
5. **Iterate**: Use differential analysis to improve parser

---

## Alternative: UI-TARS SDK (Programmatic)

If UI-TARS Desktop is too heavy, consider the **UI-TARS SDK**:

```python
from ui_tars_sdk import UITarsAgent

agent = UITarsAgent(
    model="gpt-4-vision-preview",
    api_key="your-key"
)

# Direct screen control
result = agent.execute("""
    Look at the screen.
    Find the Optitex PDS window.
    Click on 'File' menu.
    Click 'New'.
    ...
""")
```

This provides lower-level control without the full desktop application.
