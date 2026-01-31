#!/usr/bin/env python3
"""
UI-TARS Controller for PDS Reverse Engineering
Integrates ByteDance's UI-TARS with Optitex for automated test generation
"""
import subprocess
import json
import time
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import requests


@dataclass
class UITarsTask:
    """Represents a task for UI-TARS to execute"""
    name: str
    description: str
    expected_outputs: List[str]  # File extensions expected
    verification_steps: List[str]  # Steps to verify success


@dataclass
class UITarsResult:
    """Result of a UI-TARS task execution"""
    task_name: str
    success: bool
    outputs: Dict[str, str]
    screenshots: List[str]
    verification: Dict[str, Any]
    error: Optional[str] = None
    duration: float = 0.0


class UITarsOptitexController:
    """
    Controller for using UI-TARS to automate Optitex PDS operations
    
    This class provides a high-level interface for:
    - Generating test PDS files via natural language instructions
    - Capturing screenshots for visual verification
    - Extracting data from the Optitex UI
    - Validating created files
    """
    
    def __init__(
        self,
        ui_tars_api_url: str = "http://localhost:8080",  # UI-TARS API endpoint
        optitex_exe: str = "C:/Program Files/Optitex/Optitex 21/PDS.exe",
        output_dir: str = "./ui_tars_output",
        screenshot_interval: float = 2.0  # Seconds between screenshots
    ):
        self.ui_tars_api_url = ui_tars_api_url
        self.optitex_exe = Path(optitex_exe)
        self.output_dir = Path(output_dir)
        self.screenshot_interval = screenshot_interval
        
        # Create output directories
        self.pds_dir = self.output_dir / 'pds'
        self.pdml_dir = self.output_dir / 'pdml'
        self.screenshot_dir = self.output_dir / 'screenshots'
        self.metadata_dir = self.output_dir / 'metadata'
        
        for d in [self.pds_dir, self.pdml_dir, self.screenshot_dir, self.metadata_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    # ========================================================================
    # CORE EXECUTION METHODS
    # ========================================================================
    
    def execute_task(self, task: UITarsTask) -> UITarsResult:
        """
        Execute a task using UI-TARS
        
        Args:
            task: UITarsTask with description and expected outputs
            
        Returns:
            UITarsResult with execution details
        """
        start_time = time.time()
        
        # Build the complete instruction for UI-TARS
        instruction = self._build_instruction(task)
        
        try:
            # Send task to UI-TARS
            ui_tars_response = self._send_to_ui_tars(instruction)
            
            # Wait for and collect outputs
            outputs = self._collect_outputs(task)
            
            # Verify the results
            verification = self._verify_outputs(task, outputs)
            
            duration = time.time() - start_time
            
            result = UITarsResult(
                task_name=task.name,
                success=verification.get('all_verified', False),
                outputs=outputs,
                screenshots=self._collect_screenshots(task.name),
                verification=verification,
                duration=duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            result = UITarsResult(
                task_name=task.name,
                success=False,
                outputs={},
                screenshots=[],
                verification={},
                error=str(e),
                duration=duration
            )
        
        # Save metadata
        self._save_metadata(result)
        
        return result
    
    def _build_instruction(self, task: UITarsTask) -> str:
        """Build complete instruction for UI-TARS"""
        return f"""
You are an expert at using Optitex PDS (Pattern Design Software) for garment pattern making.
Your task is to create test files for software development purposes.

TASK NAME: {task.name}
TASK DESCRIPTION:
{task.description}

IMPORTANT INSTRUCTIONS:
1. Ensure Optitex PDS is running. If not, launch it from: {self.optitex_exe}
2. Execute the task step by step
3. Take screenshots at key moments (before/after major operations)
4. Save files to these specific locations:
   - PDS files: {self.pds_dir}/
   - PDML files: {self.pdml_dir}/
5. Use exact filenames as specified in the task
6. Verify outputs exist before completing
7. If errors occur, capture screenshots and describe the issue

VERIFICATION STEPS:
{chr(10).join(f"- {step}" for step in task.verification_steps)}

OUTPUT REQUIREMENTS:
{chr(10).join(f"- Must create: *.{ext}" for ext in task.expected_outputs)}

Execute the task carefully and report success or failure with details.
"""
    
    def _send_to_ui_tars(self, instruction: str) -> Dict:
        """Send instruction to UI-TARS API"""
        # This assumes UI-TARS exposes a REST API
        # Adjust based on actual UI-TARS interface
        
        payload = {
            "instruction": instruction,
            "mode": "computer",  # Control computer (not just browser)
            "screenshot_interval": self.screenshot_interval,
            "timeout": 300  # 5 minutes
        }
        
        try:
            response = requests.post(
                f"{self.ui_tars_api_url}/execute",
                json=payload,
                timeout=600
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            # Fallback: UI-TARS not running as service
            return self._run_ui_tars_cli(instruction)
    
    def _run_ui_tars_cli(self, instruction: str) -> Dict:
        """Run UI-TARS via command line interface"""
        # Write instruction to temp file
        instruction_file = self.output_dir / 'temp_instruction.txt'
        instruction_file.write_text(instruction)
        
        # Execute UI-TARS (adjust command based on actual CLI)
        cmd = [
            "ui-tars",
            "--instruction-file", str(instruction_file),
            "--output-dir", str(self.output_dir),
            "--mode", "computer"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    
    def _collect_outputs(self, task: UITarsTask) -> Dict[str, str]:
        """Collect generated output files"""
        outputs = {}
        
        # Check for expected files
        for ext in task.expected_outputs:
            # Search in output directories
            for search_dir in [self.pds_dir, self.pdml_dir, self.output_dir]:
                pattern = f"{task.name}*.{ext}"
                matches = list(search_dir.glob(pattern))
                if matches:
                    outputs[ext] = str(matches[0])  # Take first match
                    break
        
        return outputs
    
    def _collect_screenshots(self, task_name: str) -> List[str]:
        """Collect screenshots for a task"""
        pattern = f"{task_name}*.png"
        screenshots = list(self.screenshot_dir.glob(pattern))
        return [str(s) for s in screenshots]
    
    def _verify_outputs(self, task: UITarsTask, outputs: Dict[str, str]) -> Dict:
        """Verify that all expected outputs were created"""
        verification = {
            'all_verified': True,
            'files': {},
            'missing': []
        }
        
        for ext in task.expected_outputs:
            if ext in outputs:
                file_path = Path(outputs[ext])
                verification['files'][ext] = {
                    'exists': file_path.exists(),
                    'size': file_path.stat().st_size if file_path.exists() else 0
                }
            else:
                verification['missing'].append(ext)
                verification['all_verified'] = False
        
        return verification
    
    def _save_metadata(self, result: UITarsResult):
        """Save task metadata to file"""
        metadata_path = self.metadata_dir / f"{result.task_name}.json"
        with open(metadata_path, 'w') as f:
            json.dump(asdict(result), f, indent=2)
    
    # ========================================================================
    # PRE-DEFINED TEST CASES
    # ========================================================================
    
    def create_simple_square(self, size_mm: float = 100) -> UITarsResult:
        """
        Create a simple square piece for coordinate encoding analysis
        
        This test helps identify:
        - How coordinates are stored in binary
        - Unit scaling (mm vs cm)
        - Point ordering in contour
        """
        task = UITarsTask(
            name=f"geometry_square_{int(size_mm)}",
            description=f"""
Create a new pattern file with a single square piece:

1. In Optitex PDS, create a new file (File > New)
2. Create a new piece named "Square{int(size_mm)}"
3. Draw a perfect square with these exact dimensions:
   - Width: {size_mm} mm
   - Height: {size_mm} mm
   - Bottom-left corner at origin (0, 0)
   - So corners are at: (0,0), ({size_mm},0), ({size_mm},{size_mm}), (0,{size_mm})
4. Verify dimensions in the Properties panel
5. Save as "geometry_square_{int(size_mm)}.pds" in {self.pds_dir}
6. Export as PDML: "geometry_square_{int(size_mm)}.pdml" in {self.pdml_dir}

Take screenshots:
- After drawing the square
- Of the Properties panel showing dimensions
- After saving
""",
            expected_outputs=['pds', 'pdml'],
            verification_steps=[
                f"Square has exactly 4 corner points",
                f"Width equals {size_mm} mm",
                f"Height equals {size_mm} mm",
                f"File saved successfully"
            ]
        )
        
        return self.execute_task(task)
    
    def create_graded_pattern(self, num_sizes: int = 3, grade_step: float = 10) -> UITarsResult:
        """
        Create a graded pattern for grading table analysis
        
        Helps identify:
        - Grading table structure
        - Delta value encoding
        - Size name storage
        """
        sizes_str = "_".join([f"S{i+1}" for i in range(num_sizes)])
        
        task = UITarsTask(
            name=f"grading_{num_sizes}sizes_{int(grade_step)}step",
            description=f"""
Create a graded rectangular pattern:

1. Create new file in Optitex PDS
2. Create piece named "GradedPiece"
3. Draw a rectangle: 100mm wide x 150mm tall
4. Set up grading:
   - Open Grading Table (Window > Grading Table)
   - Create {num_sizes} sizes: {sizes_str}
   - Set base size as first size
   - Apply uniform grading: +{grade_step}mm per size in both X and Y directions
   - Apply grading to all corner points
5. Verify grading by switching between sizes
6. Save as "grading_{num_sizes}sizes_{int(grade_step)}step.pds"
7. Export as PDML

Take screenshots:
- Grading table showing all sizes and values
- Piece in base size
- Piece in largest size
""",
            expected_outputs=['pds', 'pdml'],
            verification_steps=[
                f"Grading table shows {num_sizes} sizes",
                f"Grading increment is {grade_step}mm",
                "Grading applied to all points",
                "Piece grows correctly in graded sizes"
            ]
        )
        
        return self.execute_task(task)
    
    def create_notched_piece(self, notch_count: int = 3, notch_type: str = "V") -> UITarsResult:
        """
        Create piece with notches for internal object analysis
        
        Helps identify:
        - Notch data structure
        - Position encoding (absolute vs ratio)
        - Notch type storage
        """
        task = UITarsTask(
            name=f"notches_{notch_count}{notch_type.lower()}",
            description=f"""
Create a piece with {notch_count} {notch_type}-notches:

1. Create new file
2. Create rectangular piece: 200mm x 100mm
3. Add {notch_count} {notch_type}-notches along the top edge:
   - Space them evenly
   - Use Notch tool from toolbox
   - Set notch properties: Type={notch_type}, Depth=3mm
4. Verify notches are visible and correctly positioned
5. Save as "notches_{notch_count}{notch_type.lower()}.pds"
6. Export as PDML

Take screenshots:
- Piece with notches visible
- Notch properties panel
- Close-up of individual notches
""",
            expected_outputs=['pds', 'pdml'],
            verification_steps=[
                f"Exactly {notch_count} notches present",
                f"All notches are type {notch_type}",
                "Notches evenly spaced along edge",
                "Notch depth is 3mm"
            ]
        )
        
        return self.execute_task(task)
    
    def create_complex_garment(self, garment_type: str = "shirt") -> UITarsResult:
        """
        Create a complete garment pattern for comprehensive analysis
        
        Tests:
        - Multiple pieces
        - Complex curves (Bezier)
        - Internal lines (darts)
        - Complete grading
        """
        task = UITarsTask(
            name=f"complex_{garment_type}",
            description=f"""
Create a complete {garment_type} pattern with all features:

1. Create new file for {garment_type}
2. Create pieces:
   - Front bodice with curved neckline and armhole (use Bezier curves)
   - Back bodice (mirror of front)
   - Left sleeve with sleeve head curve
   - Right sleeve (mirror of left)
   - Collar piece
3. Add features:
   - Seam allowances: 1cm on sides, 2cm on hem
   - Matching notches at armholes (V-type)
   - Dart on front bodice (if applicable)
4. Set up grading for sizes: S, M, L, XL
   - Apply appropriate grading rules
5. Verify all pieces are correctly named and proportioned
6. Save as "complex_{garment_type}.pds"
7. Export as PDML

Take screenshots:
- Full pattern layout (all pieces)
- Individual piece details
- Grading table
- 3D view if available
""",
            expected_outputs=['pds', 'pdml'],
            verification_steps=[
                f"All {garment_type} pieces created",
                "Curved elements use Bezier curves",
                "Seam allowances applied correctly",
                "Grading set up for 4 sizes",
                "All pieces have unique names"
            ]
        )
        
        return self.execute_task(task)
    
    def create_3d_enabled_pattern(self) -> UITarsResult:
        """
        Create pattern with 3D simulation data
        
        Tests:
        - 3D physics parameters
        - Texture embedding
        - Simulation cache
        """
        task = UITarsTask(
            name="with_3d_content",
            description="""
Create a pattern with 3D simulation enabled:

1. Create simple rectangular piece (100mm x 150mm)
2. Enable 3D view (Window > 3D)
3. Assign fabric:
   - Select a fabric from library (e.g., "Cotton")
   - Apply to the piece
4. Set 3D properties:
   - Open Piece 3D Properties
   - Note physics values (stretch, shear, bending)
5. Run simulation to drape on avatar
6. Save WITH 3D content (File > Save As, check "Save with 3D Content")
7. Export as PDML

Take screenshots:
- 2D pattern view
- 3D draped view
- Fabric properties panel
- 3D piece properties panel
""",
            expected_outputs=['pds', 'pdml'],
            verification_steps=[
                "3D view shows draped fabric",
                "Fabric assigned to piece",
                "Physics properties visible",
                "File saved with 3D content option"
            ]
        )
        
        return self.execute_task(task)
    
    # ========================================================================
    # BATCH TEST EXECUTION
    # ========================================================================
    
    def run_comprehensive_test_suite(self) -> List[UITarsResult]:
        """
        Execute a comprehensive test suite covering all PDS features
        
        Returns:
            List of UITarsResult for all tests
        """
        results = []
        
        print("="*70)
        print("UI-TARS COMPREHENSIVE TEST SUITE")
        print("="*70)
        
        # Geometry tests
        print("\n[1/5] Geometry Tests...")
        for size in [50, 100, 200]:
            result = self.create_simple_square(size)
            results.append(result)
            print(f"  Square {size}mm: {'✓' if result.success else '✗'}")
        
        # Grading tests
        print("\n[2/5] Grading Tests...")
        for num_sizes in [1, 2, 5]:
            result = self.create_graded_pattern(num_sizes)
            results.append(result)
            print(f"  {num_sizes} sizes: {'✓' if result.success else '✗'}")
        
        # Notch tests
        print("\n[3/5] Notch Tests...")
        for count in [0, 1, 3]:
            for ntype in ['V', 'T']:
                result = self.create_notched_piece(count, ntype)
                results.append(result)
                print(f"  {count} {ntype}-notches: {'✓' if result.success else '✗'}")
        
        # Complex garment
        print("\n[4/5] Complex Garment Tests...")
        for garment in ['shirt', 'pants', 'dress']:
            result = self.create_complex_garment(garment)
            results.append(result)
            print(f"  {garment}: {'✓' if result.success else '✗'}")
        
        # 3D content
        print("\n[5/5] 3D Content Test...")
        result = self.create_3d_enabled_pattern()
        results.append(result)
        print(f"  3D enabled: {'✓' if result.success else '✗'}")
        
        # Summary
        passed = sum(1 for r in results if r.success)
        print("\n" + "="*70)
        print(f"SUMMARY: {passed}/{len(results)} tests passed")
        print("="*70)
        
        return results
    
    def generate_report(self, results: List[UITarsResult], output_path: str):
        """Generate HTML report of test results"""
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>UI-TARS Test Results</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .test {{ margin: 20px 0; padding: 15px; border-radius: 5px; }}
        .success {{ background: #d4edda; border-left: 4px solid #28a745; }}
        .failure {{ background: #f8d7da; border-left: 4px solid #dc3545; }}
        .screenshot {{ max-width: 300px; margin: 10px; border: 1px solid #ddd; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; border: 1px solid #ddd; text-align: left; }}
        th {{ background: #f8f9fa; }}
    </style>
</head>
<body>
    <h1>UI-TARS Test Results</h1>
    <p>Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <h2>Summary</h2>
    <p>Total: {len(results)} | Passed: {sum(1 for r in results if r.success)} | Failed: {sum(1 for r in results if not r.success)}</p>
    
    <h2>Test Details</h2>
"""
        
        for result in results:
            status_class = 'success' if result.success else 'failure'
            html += f"""
    <div class="test {status_class}">
        <h3>{result.task_name}</h3>
        <p>Status: {'✓ PASS' if result.success else '✗ FAIL'}</p>
        <p>Duration: {result.duration:.1f}s</p>
        
        <h4>Outputs:</h4>
        <ul>
"""
            for ext, path in result.outputs.items():
                html += f"<li>{ext.upper()}: {path}</li>"
            
            html += "</ul>"
            
            if result.screenshots:
                html += "<h4>Screenshots:</h4>"
                for ss in result.screenshots[:3]:  # Show first 3
                    html += f'<img class="screenshot" src="{ss}" alt="Screenshot">'
            
            if result.error:
                html += f"<p><strong>Error:</strong> {result.error}</p>"
            
            html += "</div>"
        
        html += """
</body>
</html>
"""
        
        Path(output_path).write_text(html)
        print(f"\nReport saved to: {output_path}")


# ========================================================================
# MAIN ENTRY POINT
# ========================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python ui_tars_controller.py <command> [args]")
        print("\nCommands:")
        print("  square <size>      - Create square of given size (mm)")
        print("  grading <n> <step> - Create graded pattern with n sizes")
        print("  notches <n> <type> - Create piece with n notches")
        print("  garment <type>     - Create complex garment")
        print("  3d                 - Create pattern with 3D content")
        print("  full               - Run complete test suite")
        sys.exit(1)
    
    # Initialize controller
    controller = UITarsOptitexController(
        ui_tars_api_url="http://localhost:8080",
        optitex_exe="C:/Program Files/Optitex/Optitex 21/PDS.exe",
        output_dir="./ui_tars_tests"
    )
    
    command = sys.argv[1]
    
    if command == "square":
        size = float(sys.argv[2]) if len(sys.argv) > 2 else 100
        result = controller.create_simple_square(size)
        print(f"\nResult: {'Success' if result.success else 'Failed'}")
        print(f"Outputs: {result.outputs}")
        
    elif command == "grading":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        step = float(sys.argv[3]) if len(sys.argv) > 3 else 10
        result = controller.create_graded_pattern(n, step)
        print(f"\nResult: {'Success' if result.success else 'Failed'}")
        
    elif command == "notches":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        ntype = sys.argv[3] if len(sys.argv) > 3 else "V"
        result = controller.create_notched_piece(n, ntype)
        print(f"\nResult: {'Success' if result.success else 'Failed'}")
        
    elif command == "garment":
        gtype = sys.argv[2] if len(sys.argv) > 2 else "shirt"
        result = controller.create_complex_garment(gtype)
        print(f"\nResult: {'Success' if result.success else 'Failed'}")
        
    elif command == "3d":
        result = controller.create_3d_enabled_pattern()
        print(f"\nResult: {'Success' if result.success else 'Failed'}")
        
    elif command == "full":
        results = controller.run_comprehensive_test_suite()
        controller.generate_report(results, "./ui_tars_report.html")
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
