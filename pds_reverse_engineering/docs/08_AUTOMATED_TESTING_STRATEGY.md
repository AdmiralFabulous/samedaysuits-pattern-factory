# Automated Testing Strategy for PDS Reverse Engineering
## Using Optitex as an Oracle for Differential Analysis

### Overview

With access to Optitex, we can treat it as a **ground truth oracle**:
- Generate test files with **known, controlled properties**
- Export to both binary (.pds) and XML (.pdml) formats
- Parse binary with our parser
- Compare against PDML "truth"
- Use discrepancies to identify parser errors or unknown structure fields

This is **property-based reverse engineering**—the gold standard for format analysis.

---

## Phase 1: Automated Test Case Generation

### 1.1 Systematic File Generation Matrix

Create files that isolate specific features:

```python
# test_matrix.py - Defines all test cases
TEST_MATRIX = {
    # Geometry Tests - Vary piece shape
    'geometry': [
        {'name': 'square_100', 'shape': 'rect', 'w': 100, 'h': 100, 'points': 4},
        {'name': 'square_200', 'shape': 'rect', 'w': 200, 'h': 200, 'points': 4},
        {'name': 'rect_200x100', 'shape': 'rect', 'w': 200, 'h': 100, 'points': 4},
        {'name': 'circle_approx', 'shape': 'circle', 'radius': 100, 'segments': 32},
        {'name': 'poly_8', 'shape': 'polygon', 'sides': 8, 'radius': 100},
        {'name': 'poly_100', 'shape': 'polygon', 'sides': 100, 'radius': 100},
    ],
    
    # Piece Count Tests
    'piece_count': [
        {'name': '1piece', 'pieces': 1},
        {'name': '2pieces', 'pieces': 2},
        {'name': '5pieces', 'pieces': 5},
        {'name': '10pieces', 'pieces': 10},
        {'name': '50pieces', 'pieces': 50},
    ],
    
    # Size/Grading Tests
    'grading': [
        {'name': '1size', 'sizes': 1},
        {'name': '2sizes', 'sizes': 2, 'grade': 10},
        {'name': '5sizes', 'sizes': 5, 'grade': 10},
        {'name': '10sizes', 'sizes': 10, 'grade': 5},
        {'name': 'variation_grade', 'sizes': [34,36,38], 'inseams': [30,32,34]},  # Matrix sizing
    ],
    
    # Notch Tests
    'notches': [
        {'name': '0notches', 'notches': 0},
        {'name': '1notch', 'notches': 1, 'type': 'V'},
        {'name': '5notches', 'notches': 5, 'type': 'V'},
        {'name': 'mixed_notches', 'notches': [V, T, Slit]},
        {'name': 'ratio_notches', 'notches': 3, 'connection': 'ratio', 'value': 0.5},
    ],
    
    # Internal Lines Tests
    'internals': [
        {'name': '0internals', 'internals': 0},
        {'name': '1internal', 'internals': 1},
        {'name': '5internals', 'internals': 5},
        {'name': 'curved_internal', 'internals': 1, 'type': 'curve'},
        {'name': 'dart', 'internals': 1, 'type': 'dart'},
    ],
    
    # Drill Hole Tests
    'drills': [
        {'name': '0drills', 'drills': 0},
        {'name': '1drill', 'drills': 1, 'diameter': 5},
        {'name': '5drills', 'drills': 5, 'diameter': 3},
    ],
    
    # Metadata Tests
    'metadata': [
        {'name': 'short_name', 'style_name': 'A'},
        {'name': 'long_name', 'style_name': 'A' * 100},
        {'name': 'unicode_name', 'style_name': '样式_日本語_한국어'},
        {'name': 'special_chars', 'style_name': 'Test@#$%^&*()'},
    ],
    
    # Unit Tests
    'units': [
        {'name': 'mm', 'units': 'mm'},
        {'name': 'cm', 'units': 'cm'},
        {'name': 'inch', 'units': 'inch'},
    ],
    
    # Seam Allowance Tests
    'seams': [
        {'name': 'no_seam', 'seam': 0},
        {'name': '1mm_seam', 'seam': 1},
        {'name': '10mm_seam', 'seam': 10},
        {'name': 'variable_seam', 'seam': [1, 2, 4, 1]},  # Different per segment
    ],
    
    # 3D Content Tests
    '3d': [
        {'name': 'no_3d', '3d': False},
        {'name': 'with_physics', '3d': True, 'physics': 'cotton'},
        {'name': 'with_texture', '3d': True, 'texture': 'embedded'},
    ],
}
```

### 1.2 Optitex Batch Command Generator

```python
#!/usr/bin/env python3
"""
Generate Optitex batch scripts for automated test file creation
"""
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional
import json


@dataclass
class TestCase:
    category: str
    name: str
    params: Dict
    expected_results: Optional[Dict] = None


class OptitexBatchGenerator:
    """Generate batch commands to create test files in Optitex"""
    
    def __init__(self, output_dir: str, optitex_exe: str):
        self.output_dir = Path(output_dir)
        self.optitex_exe = optitex_exe
        self.test_cases = []
        
    def add_test_case(self, category: str, name: str, params: Dict):
        """Add a test case to the suite"""
        self.test_cases.append(TestCase(category, name, params))
        
    def generate_batch_script(self, test_case: TestCase) -> str:
        """Generate batch commands for a single test case"""
        lines = []
        p = test_case.params
        
        # File naming
        pds_name = f"{test_case.category}_{test_case.name}.pds"
        pdml_name = f"{test_case.category}_{test_case.name}.pdml"
        pds_path = self.output_dir / pds_name
        pdml_path = self.output_dir / pdml_name
        
        # Start with new file
        lines.append("@NEW")
        
        # Set units
        if 'units' in p:
            lines.append(f"@UNIT {p['units'].upper()}")
            
        # Set style name
        if 'style_name' in p:
            lines.append(f"@SETSTYLENAME \"{p['style_name']}\"")
            
        # Create pieces
        num_pieces = p.get('pieces', 1)
        for i in range(num_pieces):
            piece_name = p.get('piece_name', f"Piece{i+1}")
            lines.extend(self._generate_piece_commands(p, i, piece_name))
            
        # Add grading if specified
        if 'sizes' in p:
            lines.extend(self._generate_grading_commands(p))
            
        # Save as PDS
        lines.append(f"@SAVE \"{pds_path}\" /FORMAT=PDS /XML=YES")
        
        # Save as PDML (our ground truth)
        lines.append(f"@SAVE \"{pdml_path}\" /FORMAT=PDML /XML=YES")
        
        # Export to DXF for additional analysis
        dxf_path = self.output_dir / f"{test_case.category}_{test_case.name}.dxf"
        lines.append(f"@EXPORT \"{dxf_path}\" /FORMAT=DXF /SEP /CGRUL=YES")
        
        lines.append("@CLOSE")
        
        return '\n'.join(lines)
        
    def _generate_piece_commands(self, params: Dict, index: int, name: str) -> List[str]:
        """Generate commands to create a piece with specific geometry"""
        lines = []
        shape = params.get('shape', 'rect')
        
        # Create new piece
        lines.append(f"@NEWPIECE \"{name}\"")
        
        if shape == 'rect':
            w = params.get('w', 100)
            h = params.get('h', 100)
            # Draw rectangle contour
            lines.append(f"@DRAWRECT /W={w} /H={h} /CENTER=0,0")
            
        elif shape == 'circle':
            r = params.get('radius', 100)
            segments = params.get('segments', 32)
            lines.append(f"@DRAWCIRCLE /R={r} /SEGMENTS={segments}")
            
        elif shape == 'polygon':
            sides = params.get('sides', 6)
            r = params.get('radius', 100)
            lines.append(f"@DRAWPOLYGON /SIDES={sides} /R={r}")
            
        # Add notches
        num_notches = params.get('notches', 0)
        if num_notches > 0:
            notch_type = params.get('notch_type', 'V')
            for n in range(num_notches):
                position = (n + 1) / (num_notches + 1)  # Evenly spaced
                lines.append(f"@ADDNOTCH /POSITION={position} /TYPE={notch_type}")
                
        # Add drill holes
        num_drills = params.get('drills', 0)
        if num_drills > 0:
            diameter = params.get('diameter', 5)
            for d in range(num_drills):
                x = (d - num_drills/2) * 20
                lines.append(f"@ADDDRILL /X={x} /Y=0 /D={diameter}")
                
        # Add internals
        num_internals = params.get('internals', 0)
        if num_internals > 0:
            internal_type = params.get('internal_type', 'line')
            for i in range(num_internals):
                y = (i - num_internals/2) * 10
                lines.append(f"@ADDINTERNAL /Y={y} /TYPE={internal_type}")
                
        # Set seam allowance
        if 'seam' in params:
            seam = params['seam']
            if isinstance(seam, list):
                # Variable seam per segment
                for seg, val in enumerate(seam):
                    lines.append(f"@SETSEAM /SEG={seg} /VAL={val}")
            else:
                lines.append(f"@SETSEAM /VAL={seam}")
                
        return lines
        
    def _generate_grading_commands(self, params: Dict) -> List[str]:
        """Generate grading setup commands"""
        lines = []
        sizes = params['sizes']
        
        if isinstance(sizes, int):
            # Simple grading - N sizes
            lines.append(f"@SETSIZECOUNT {sizes}")
            lines.append("@SETBASESIZE 0")  # First size is base
            
            # Add grading rules (simple uniform growth)
            grade = params.get('grade', 10)
            for i in range(1, sizes):
                lines.append(f"@ADDRULE /SIZE={i} /DX={grade*i} /DY={grade*i}")
                
        elif isinstance(sizes, list):
            # Variation grading (matrix sizing)
            lines.append("@ENABLEVARIATIONGRADING")
            for size in sizes:
                lines.append(f"@ADDVARIATION /TYPE=WAIST /VAL={size}")
                
        return lines
        
    def generate_all_batches(self) -> Dict[str, str]:
        """Generate batch scripts for all test cases"""
        scripts = {}
        for tc in self.test_cases:
            key = f"{tc.category}_{tc.name}"
            scripts[key] = self.generate_batch_script(tc)
        return scripts
        
    def save_batch_files(self):
        """Save all batch scripts to files"""
        batch_dir = self.output_dir / 'batch_scripts'
        batch_dir.mkdir(exist_ok=True)
        
        for tc in self.test_cases:
            filename = f"{tc.category}_{tc.name}.txt"
            script = self.generate_batch_script(tc)
            (batch_dir / filename).write_text(script)
            
        # Create master batch file
        master = batch_dir / 'RUN_ALL.txt'
        master_lines = []
        for tc in self.test_cases:
            master_lines.append(f"@RUN \"{batch_dir / f'{tc.category}_{tc.name}.txt'}\"")
        master_lines.append("@EXIT")
        master.write_text('\n'.join(master_lines))
        
        return batch_dir


# Predefined test suites
GEOMETRY_TESTS = [
    ('square_100', {'shape': 'rect', 'w': 100, 'h': 100}),
    ('square_200', {'shape': 'rect', 'w': 200, 'h': 200}),
    ('rect_200x100', {'shape': 'rect', 'w': 200, 'h': 100}),
    ('rect_50x150', {'shape': 'rect', 'w': 50, 'h': 150}),
]

PIECE_COUNT_TESTS = [
    ('1piece', {'pieces': 1}),
    ('2pieces', {'pieces': 2}),
    ('5pieces', {'pieces': 5}),
]

GRADING_TESTS = [
    ('1size', {'sizes': 1}),
    ('2sizes', {'sizes': 2, 'grade': 10}),
    ('5sizes', {'sizes': 5, 'grade': 10}),
]

NOTCH_TESTS = [
    ('0notches', {'notches': 0}),
    ('1notch_v', {'notches': 1, 'notch_type': 'V'}),
    ('3notches_v', {'notches': 3, 'notch_type': 'V'}),
    ('3notches_t', {'notches': 3, 'notch_type': 'T'}),
]


def create_comprehensive_test_suite(output_dir: str, optitex_exe: str):
    """Create a full test suite covering all features"""
    gen = OptitexBatchGenerator(output_dir, optitex_exe)
    
    # Add all geometry tests
    for name, params in GEOMETRY_TESTS:
        gen.add_test_case('geometry', name, params)
        
    # Add piece count tests
    for name, params in PIECE_COUNT_TESTS:
        gen.add_test_case('pieces', name, params)
        
    # Add grading tests
    for name, params in GRADING_TESTS:
        gen.add_test_case('grading', name, params)
        
    # Add notch tests
    for name, params in NOTCH_TESTS:
        gen.add_test_case('notches', name, params)
        
    return gen


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python test_generator.py <output_dir> <optitex_exe_path>")
        sys.exit(1)
        
    gen = create_comprehensive_test_suite(sys.argv[1], sys.argv[2])
    batch_dir = gen.save_batch_files()
    print(f"Generated {len(gen.test_cases)} test cases in {batch_dir}")
```

---

## Phase 2: Automated Execution Pipeline

```python
#!/usr/bin/env python3
"""
Automated test execution pipeline
Runs Optitex batch scripts and collects outputs
"""
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import hashlib


class TestExecutor:
    """Execute test cases and collect results"""
    
    def __init__(self, optitex_exe: str, batch_dir: str, output_dir: str):
        self.optitex_exe = Path(optitex_exe)
        self.batch_dir = Path(batch_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = []
        
    def run_batch(self, batch_file: Path, timeout: int = 60) -> Dict:
        """Execute a single batch script in Optitex"""
        result = {
            'batch_file': str(batch_file),
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'outputs': {},
            'errors': [],
            'duration': 0
        }
        
        start_time = time.time()
        
        try:
            # Run Optitex with batch file
            cmd = [
                str(self.optitex_exe),
                '/BATCH', str(batch_file),
                '/NOUI',  # Run without UI if supported
                '/FORCE'  # Overwrite existing files
            ]
            
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            result['duration'] = time.time() - start_time
            result['returncode'] = proc.returncode
            result['stdout'] = proc.stdout
            result['stderr'] = proc.stderr
            
            if proc.returncode == 0:
                result['success'] = True
                result['outputs'] = self._collect_outputs(batch_file)
            else:
                result['errors'].append(f"Non-zero exit code: {proc.returncode}")
                
        except subprocess.TimeoutExpired:
            result['errors'].append(f"Timeout after {timeout}s")
        except Exception as e:
            result['errors'].append(str(e))
            
        return result
        
    def _collect_outputs(self, batch_file: Path) -> Dict:
        """Collect all output files generated by batch"""
        outputs = {}
        base_name = batch_file.stem
        
        # Look for expected output files
        expected_extensions = ['.pds', '.pdml', '.dxf', '.rul']
        
        for ext in expected_extensions:
            file_path = self.output_dir / f"{base_name}{ext}"
            if file_path.exists():
                file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
                outputs[ext.lstrip('.')] = {
                    'path': str(file_path),
                    'size': file_path.stat().st_size,
                    'md5': file_hash
                }
                
        return outputs
        
    def run_all_tests(self) -> List[Dict]:
        """Execute all batch scripts in directory"""
        batch_files = sorted(self.batch_dir.glob('*.txt'))
        batch_files = [f for f in batch_files if f.name != 'RUN_ALL.txt']
        
        print(f"Running {len(batch_files)} test cases...")
        
        for i, batch_file in enumerate(batch_files, 1):
            print(f"[{i}/{len(batch_files)}] {batch_file.stem}...", end=' ')
            
            result = self.run_batch(batch_file)
            self.results.append(result)
            
            status = "PASS" if result['success'] else "FAIL"
            print(f"{status} ({result['duration']:.1f}s)")
            
        return self.results
        
    def save_report(self, report_path: str):
        """Save execution report"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r['success'])
        
        report = {
            'summary': {
                'total': total,
                'passed': passed,
                'failed': total - passed,
                'success_rate': passed / total if total > 0 else 0,
                'timestamp': datetime.now().isoformat()
            },
            'results': self.results
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\nReport saved to: {report_path}")
        print(f"Summary: {passed}/{total} tests passed ({report['summary']['success_rate']*100:.1f}%)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python test_executor.py <optitex_exe> <batch_dir> <output_dir>")
        sys.exit(1)
        
    executor = TestExecutor(sys.argv[1], sys.argv[2], sys.argv[3])
    executor.run_all_tests()
    executor.save_report(Path(sys.argv[3]) / 'execution_report.json')
```

---

## Phase 3: Differential Analysis Engine

```python
#!/usr/bin/env python3
"""
Differential analysis - compare our parser output against PDML ground truth
"""
import xml.etree.ElementTree as ET
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import math


@dataclass
class ComparisonResult:
    test_name: str
    field: str
    expected: any
    actual: any
    match: bool
    error_margin: Optional[float] = None


class DifferentialAnalyzer:
    """Compare parser output against PDML ground truth"""
    
    def __init__(self, tolerance: float = 0.01):
        self.tolerance = tolerance  # For floating point comparison
        self.results = []
        
    def analyze_test_case(self, test_name: str, pds_path: str, pdml_path: str, 
                         parser_output: Dict) -> List[ComparisonResult]:
        """Compare parser output against PDML for a single test"""
        results = []
        
        # Parse PDML (ground truth)
        pdml_data = self._parse_pdml(pdml_path)
        
        # Compare header info
        results.extend(self._compare_header(test_name, pdml_data, parser_output))
        
        # Compare piece counts
        results.extend(self._compare_piece_counts(test_name, pdml_data, parser_output))
        
        # Compare geometry (if pieces exist)
        if pdml_data.get('pieces') and parser_output.get('pieces'):
            results.extend(self._compare_geometry(test_name, pdml_data, parser_output))
            
        # Compare grading
        results.extend(self._compare_grading(test_name, pdml_data, parser_output))
        
        self.results.extend(results)
        return results
        
    def _parse_pdml(self, pdml_path: str) -> Dict:
        """Extract key data from PDML file"""
        tree = ET.parse(pdml_path)
        root = tree.getroot()
        
        data = {
            'style_name': self._get_attr(root, 'Name'),
            'units': self._get_text(root, './/Units/Length'),
            'num_sizes': int(self._get_attr(root, './/Sizes', 'count') or 0),
            'num_pieces': int(self._get_attr(root, './/Pieces', 'count') or 0),
            'pieces': [],
            'sizes': []
        }
        
        # Extract pieces
        for piece_elem in root.findall('.//Piece'):
            piece = {
                'code': piece_elem.get('Code', ''),
                'name': piece_elem.get('Name', ''),
                'description': piece_elem.get('Description', ''),
                'contour_points': []
            }
            
            for point in piece_elem.findall('.//Contour/Point'):
                piece['contour_points'].append({
                    'x': float(point.get('x', 0)),
                    'y': float(point.get('y', 0))
                })
                
            data['pieces'].append(piece)
            
        # Extract sizes
        for size_elem in root.findall('.//Size'):
            size = {
                'name': size_elem.get('Name', ''),
                'grading_rules': []
            }
            
            for rule in size_elem.findall('.//GradingRule'):
                size['grading_rules'].append({
                    'point_id': rule.get('PointID'),
                    'dx': float(rule.get('dX', 0)),
                    'dy': float(rule.get('dY', 0))
                })
                
            data['sizes'].append(size)
            
        return data
        
    def _get_attr(self, elem, xpath, attr, default=None):
        """Safely get attribute from XML"""
        found = elem.find(xpath)
        return found.get(attr) if found is not None else default
        
    def _get_text(self, elem, xpath, default=None):
        """Safely get text from XML"""
        found = elem.find(xpath)
        return found.text if found is not None else default
        
    def _compare_header(self, test_name: str, pdml: Dict, parser: Dict) -> List[ComparisonResult]:
        """Compare header metadata"""
        results = []
        
        # Style name
        results.append(ComparisonResult(
            test_name=test_name,
            field='style_name',
            expected=pdml.get('style_name'),
            actual=parser.get('header', {}).get('style_name'),
            match=pdml.get('style_name') == parser.get('header', {}).get('style_name')
        ))
        
        # Units
        results.append(ComparisonResult(
            test_name=test_name,
            field='units',
            expected=pdml.get('units'),
            actual=parser.get('header', {}).get('units_length'),
            match=pdml.get('units') == parser.get('header', {}).get('units_length')
        ))
        
        return results
        
    def _compare_piece_counts(self, test_name: str, pdml: Dict, parser: Dict) -> List[ComparisonResult]:
        """Compare piece and size counts"""
        results = []
        
        results.append(ComparisonResult(
            test_name=test_name,
            field='num_pieces',
            expected=pdml.get('num_pieces'),
            actual=parser.get('header', {}).get('num_pieces'),
            match=pdml.get('num_pieces') == parser.get('header', {}).get('num_pieces')
        ))
        
        results.append(ComparisonResult(
            test_name=test_name,
            field='num_sizes',
            expected=pdml.get('num_sizes'),
            actual=parser.get('header', {}).get('num_sizes'),
            match=pdml.get('num_sizes') == parser.get('header', {}).get('num_sizes')
        ))
        
        return results
        
    def _compare_geometry(self, test_name: str, pdml: Dict, parser: Dict) -> List[ComparisonResult]:
        """Compare piece geometry with tolerance"""
        results = []
        
        for i, (pdml_piece, parser_piece) in enumerate(zip(pdml['pieces'], parser.get('pieces', []))):
            # Compare point counts
            pdml_points = len(pdml_piece['contour_points'])
            parser_points = len(parser_piece.get('contour', {}).get('points', []))
            
            results.append(ComparisonResult(
                test_name=test_name,
                field=f'piece_{i}_point_count',
                expected=pdml_points,
                actual=parser_points,
                match=pdml_points == parser_points
            ))
            
            # Compare individual points
            for j, (pdml_pt, parser_pt) in enumerate(zip(
                pdml_piece['contour_points'],
                parser_piece.get('contour', {}).get('points', [])
            )):
                x_error = abs(pdml_pt['x'] - parser_pt.get('x', 0))
                y_error = abs(pdml_pt['y'] - parser_pt.get('y', 0))
                
                results.append(ComparisonResult(
                    test_name=test_name,
                    field=f'piece_{i}_point_{j}_x',
                    expected=pdml_pt['x'],
                    actual=parser_pt.get('x'),
                    match=x_error <= self.tolerance,
                    error_margin=x_error
                ))
                
                results.append(ComparisonResult(
                    test_name=test_name,
                    field=f'piece_{i}_point_{j}_y',
                    expected=pdml_pt['y'],
                    actual=parser_pt.get('y'),
                    match=y_error <= self.tolerance,
                    error_margin=y_error
                ))
                
        return results
        
    def _compare_grading(self, test_name: str, pdml: Dict, parser: Dict) -> List[ComparisonResult]:
        """Compare grading rules"""
        results = []
        
        pdml_sizes = pdml.get('sizes', [])
        parser_sizes = parser.get('sizes', [])
        
        for i, (pdml_size, parser_size) in enumerate(zip(pdml_sizes, parser_sizes)):
            pdml_rules = pdml_size.get('grading_rules', [])
            parser_rules = parser_size.get('grading_rules', [])
            
            results.append(ComparisonResult(
                test_name=test_name,
                field=f'size_{i}_rule_count',
                expected=len(pdml_rules),
                actual=len(parser_rules),
                match=len(pdml_rules) == len(parser_rules)
            ))
            
        return results
        
    def generate_report(self, output_path: str):
        """Generate comprehensive differential analysis report"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.match)
        
        # Group by test
        by_test = {}
        for r in self.results:
            if r.test_name not in by_test:
                by_test[r.test_name] = []
            by_test[r.test_name].append(r)
        
        # Calculate per-test statistics
        test_stats = {}
        for test_name, results in by_test.items():
            test_passed = sum(1 for r in results if r.match)
            test_stats[test_name] = {
                'total_checks': len(results),
                'passed': test_passed,
                'failed': len(results) - test_passed,
                'success_rate': test_passed / len(results) if results else 0
            }
        
        report = {
            'summary': {
                'total_checks': total,
                'passed': passed,
                'failed': total - passed,
                'success_rate': passed / total if total > 0 else 0,
                'tolerance': self.tolerance
            },
            'test_statistics': test_stats,
            'failures': [
                {
                    'test': r.test_name,
                    'field': r.field,
                    'expected': r.expected,
                    'actual': r.actual,
                    'error': r.error_margin
                }
                for r in self.results if not r.match
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\nDifferential Analysis Report: {output_path}")
        print(f"Overall: {passed}/{total} checks passed ({report['summary']['success_rate']*100:.1f}%)")
        print(f"Failed checks: {total - passed}")
        
        return report


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 5:
        print("Usage: python differential_analyzer.py <test_name> <pds_file> <pdml_file> <parser_output_json>")
        sys.exit(1)
        
    analyzer = DifferentialAnalyzer(tolerance=0.01)
    
    parser_output = json.loads(Path(sys.argv[4]).read_text())
    
    results = analyzer.analyze_test_case(
        sys.argv[1], sys.argv[2], sys.argv[3], parser_output
    )
    
    analyzer.generate_report('differential_report.json')
```

---

## Phase 4: Complete Automated Pipeline

```python
#!/usr/bin/env python3
"""
Complete automated reverse engineering pipeline
Orchestrates test generation → execution → analysis → reporting
"""
import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime


class ReverseEngineeringPipeline:
    """End-to-end automated PDS reverse engineering"""
    
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self.config = json.load(f)
            
        self.optitex_exe = self.config['optitex_exe']
        self.output_dir = Path(self.config['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'phases': {}
        }
        
    def run(self):
        """Execute complete pipeline"""
        print("="*60)
        print("PDS REVERSE ENGINEERING PIPELINE")
        print("="*60)
        
        # Phase 1: Generate test cases
        print("\n[PHASE 1] Generating test cases...")
        self._run_phase('generate', self._generate_tests)
        
        # Phase 2: Execute in Optitex
        print("\n[PHASE 2] Executing tests in Optitex...")
        self._run_phase('execute', self._execute_tests)
        
        # Phase 3: Parse with our parser
        print("\n[PHASE 3] Parsing with custom parser...")
        self._run_phase('parse', self._parse_outputs)
        
        # Phase 4: Differential analysis
        print("\n[PHASE 4] Running differential analysis...")
        self._run_phase('analyze', self._analyze_differences)
        
        # Phase 5: Generate reports
        print("\n[PHASE 5] Generating reports...")
        self._run_phase('report', self._generate_reports)
        
        # Save final results
        results_path = self.output_dir / 'pipeline_results.json'
        with open(results_path, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        print(f"\n{'='*60}")
        print(f"Pipeline complete! Results: {results_path}")
        print(f"{'='*60}")
        
        return self.results
        
    def _run_phase(self, name: str, func):
        """Run a pipeline phase with error handling"""
        try:
            start = datetime.now()
            result = func()
            duration = (datetime.now() - start).total_seconds()
            
            self.results['phases'][name] = {
                'status': 'success',
                'duration': duration,
                'result': result
            }
            print(f"  ✓ Completed in {duration:.1f}s")
            
        except Exception as e:
            self.results['phases'][name] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"  ✗ Failed: {e}")
            
    def _generate_tests(self):
        """Generate all test case batch scripts"""
        from test_generator import create_comprehensive_test_suite
        
        gen = create_comprehensive_test_suite(
            str(self.output_dir / 'test_cases'),
            self.optitex_exe
        )
        batch_dir = gen.save_batch_files()
        
        return {'batch_dir': str(batch_dir), 'test_count': len(gen.test_cases)}
        
    def _execute_tests(self):
        """Run all batch scripts in Optitex"""
        from test_executor import TestExecutor
        
        batch_dir = self.output_dir / 'test_cases' / 'batch_scripts'
        test_output = self.output_dir / 'test_outputs'
        
        executor = TestExecutor(self.optitex_exe, batch_dir, test_output)
        executor.run_all_tests()
        executor.save_report(test_output / 'execution_report.json')
        
        return {'output_dir': str(test_output), 'test_count': len(executor.results)}
        
    def _parse_outputs(self):
        """Parse all generated PDS files with our parser"""
        from pds_parser import PDSParser
        
        test_output = self.output_dir / 'test_outputs'
        parse_output = self.output_dir / 'parse_results'
        parse_output.mkdir(exist_ok=True)
        
        parsed_count = 0
        for pds_file in test_output.glob('*.pds'):
            try:
                parser = PDSParser(str(pds_file))
                parser.parse()
                parser.export_to_json(str(parse_output / f"{pds_file.stem}.json"))
                parsed_count += 1
            except Exception as e:
                print(f"    Warning: Failed to parse {pds_file.name}: {e}")
                
        return {'parse_dir': str(parse_output), 'parsed_count': parsed_count}
        
    def _analyze_differences(self):
        """Compare parser output against PDML ground truth"""
        from differential_analyzer import DifferentialAnalyzer
        
        test_output = self.output_dir / 'test_outputs'
        parse_output = self.output_dir / 'parse_results'
        
        analyzer = DifferentialAnalyzer(tolerance=self.config.get('tolerance', 0.01))
        
        analyzed = 0
        for pds_file in test_output.glob('*.pds'):
            pdml_file = test_output / f"{pds_file.stem}.pdml"
            parse_file = parse_output / f"{pds_file.stem}.json"
            
            if pdml_file.exists() and parse_file.exists():
                try:
                    parser_output = json.loads(parse_file.read_text())
                    analyzer.analyze_test_case(
                        pds_file.stem,
                        str(pds_file),
                        str(pdml_file),
                        parser_output
                    )
                    analyzed += 1
                except Exception as e:
                    print(f"    Warning: Failed to analyze {pds_file.name}: {e}")
                    
        report_path = self.output_dir / 'differential_report.json'
        analyzer.generate_report(str(report_path))
        
        return {'analyzed_count': analyzed, 'report': str(report_path)}
        
    def _generate_reports(self):
        """Generate final summary reports"""
        reports = {}
        
        # HTML report
        html_report = self._generate_html_report()
        reports['html'] = html_report
        
        # Markdown report
        md_report = self._generate_markdown_report()
        reports['markdown'] = md_report
        
        return reports
        
    def _generate_html_report(self) -> str:
        """Generate interactive HTML report"""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>PDS Reverse Engineering Results</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .phase { border: 1px solid #ccc; margin: 10px 0; padding: 10px; }
        .success { background: #d4edda; }
        .error { background: #f8d7da; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f2f2f2; }
    </style>
</head>
<body>
    <h1>PDS Reverse Engineering Pipeline Results</h1>
    <p>Generated: """ + datetime.now().isoformat() + """</p>
"""
        
        # Add phase summaries
        for phase_name, phase_data in self.results['phases'].items():
            status = phase_data.get('status', 'unknown')
            css_class = 'success' if status == 'success' else 'error'
            
            html += f"""
    <div class="phase {css_class}">
        <h2>Phase: {phase_name.title()}</h2>
        <p>Status: {status}</p>
        <p>Duration: {phase_data.get('duration', 'N/A')}s</p>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        report_path = self.output_dir / 'report.html'
        report_path.write_text(html)
        return str(report_path)
        
    def _generate_markdown_report(self) -> str:
        """Generate markdown summary"""
        md = f"""# PDS Reverse Engineering Results

**Generated:** {datetime.now().isoformat()}

## Pipeline Summary

| Phase | Status | Duration |
|-------|--------|----------|
"""
        
        for phase_name, phase_data in self.results['phases'].items():
            status = phase_data.get('status', 'unknown')
            duration = phase_data.get('duration', 'N/A')
            md += f"| {phase_name.title()} | {status} | {duration}s |\n"
            
        md += """
## Next Steps

1. Review differential report for parsing errors
2. Update parser based on failed comparisons
3. Re-run pipeline to verify fixes
4. Document discovered structure
"""
        
        report_path = self.output_dir / 'report.md'
        report_path.write_text(md)
        return str(report_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <config.json>")
        print("\nConfig format:")
        print(json.dumps({
            "optitex_exe": "C:/Program Files/Optitex/Optitex 21/PDS.exe",
            "output_dir": "./re_results",
            "tolerance": 0.01
        }, indent=2))
        sys.exit(1)
        
    pipeline = ReverseEngineeringPipeline(sys.argv[1])
    pipeline.run()
```

---

## Configuration File

```json
{
  "optitex_exe": "C:/Program Files/Optitex/Optitex 21/PDS.exe",
  "output_dir": "./reverse_engineering_output",
  "tolerance": 0.01,
  "test_suites": {
    "geometry": true,
    "pieces": true,
    "grading": true,
    "notches": true,
    "internals": true,
    "drills": true,
    "metadata": true,
    "units": true,
    "seams": true,
    "3d": false
  },
  "execution": {
    "timeout": 60,
    "parallel": false,
    "overwrite": true
  }
}
```

---

## Workflow Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AUTOMATED REVERSE ENGINEERING PIPELINE                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: TEST GENERATION                                                    │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ Define Test     │───▶│ Generate Batch  │───▶│ Save .txt Files │         │
│  │ Matrix          │    │ Scripts         │    │                 │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                                                              │
│  PHASE 2: EXECUTION (Optitex as Oracle)                                      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ Run Batch in    │───▶│ Generate        │───▶│ Collect         │         │
│  │ Optitex         │    │ .pds + .pdml    │    │ Outputs         │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                                                              │
│  PHASE 3: PARSING (Our Implementation)                                       │
│  ┌─────────────────┐    ┌─────────────────┐                                 │
│  │ Parse .pds with │───▶│ Export JSON     │                                 │
│  │ Custom Parser   │    │ Results         │                                 │
│  └─────────────────┘    └─────────────────┘                                 │
│                                                                              │
│  PHASE 4: DIFFERENTIAL ANALYSIS                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ Parse PDML      │───▶│ Compare with    │───▶│ Identify        │         │
│  │ (Ground Truth)  │    │ Parser Output   │    │ Discrepancies   │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                                                              │
│  PHASE 5: ITERATION                                                          │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ Update Parser   │───▶│ Re-run Tests    │───▶│ Verify Fixes    │         │
│  │ Based on Errors │    │                 │    │                 │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Advantages of This Approach

1. **Ground Truth Verification**: PDML is the authoritative source—we're not guessing
2. **Systematic Coverage**: Test matrix ensures all features are exercised
3. **Automated Regression**: Re-run pipeline after parser changes
4. **Quantified Progress**: Success metrics show parser accuracy over time
5. **Failure Isolation**: Each test isolates specific features

---

## Running the Complete Pipeline

```bash
# 1. Create config
 cat > config.json << 'EOF'
{
  "optitex_exe": "C:/Program Files/Optitex/Optitex 21/PDS.exe",
  "output_dir": "./re_results",
  "tolerance": 0.01
}
EOF

# 2. Run pipeline
python pipeline.py config.json

# 3. Review results
open re_results/report.html
 cat re_results/differential_report.json | jq '.summary'
```

This automated approach transforms reverse engineering from an art into a **measurable, iterative science**.
