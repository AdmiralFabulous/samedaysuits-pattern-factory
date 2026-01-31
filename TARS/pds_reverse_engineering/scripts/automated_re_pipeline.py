#!/usr/bin/env python3
"""
Automated Reverse Engineering Pipeline for Optitex PDS
Uses Optitex as an oracle for differential testing
"""
import subprocess
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import hashlib


class AutomatedREPipeline:
    """
    End-to-end automated pipeline for PDS reverse engineering.
    Uses Optitex to generate test cases and validate parser accuracy.
    """
    
    def __init__(self, optitex_exe: str, output_dir: str):
        self.optitex_exe = Path(optitex_exe)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Subdirectories
        self.batch_dir = self.output_dir / 'batch_scripts'
        self.test_output_dir = self.output_dir / 'test_outputs'
        self.parse_dir = self.output_dir / 'parse_results'
        self.report_dir = self.output_dir / 'reports'
        
        for d in [self.batch_dir, self.test_output_dir, self.parse_dir, self.report_dir]:
            d.mkdir(exist_ok=True)
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'optitex': str(self.optitex_exe),
            'phases': {}
        }
        
    def run_full_pipeline(self):
        """Execute complete reverse engineering pipeline"""
        print("="*70)
        print("  OPTITEX PDS - AUTOMATED REVERSE ENGINEERING PIPELINE")
        print("="*70)
        print(f"\nOutput Directory: {self.output_dir}")
        print(f"Optitex: {self.optitex_exe}")
        
        # Phase 1: Generate test cases
        self._phase1_generate_tests()
        
        # Phase 2: Execute in Optitex
        self._phase2_execute()
        
        # Phase 3: Parse outputs
        self._phase3_parse()
        
        # Phase 4: Differential analysis
        self._phase4_analyze()
        
        # Phase 5: Generate reports
        self._phase5_report()
        
        # Save final results
        results_file = self.report_dir / 'pipeline_results.json'
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print("\n" + "="*70)
        print(f"  PIPELINE COMPLETE")
        print(f"  Results: {results_file}")
        print(f"  HTML Report: {self.report_dir / 'report.html'}")
        print("="*70)
        
        return self.results
    
    def _phase1_generate_tests(self):
        """Generate batch scripts for systematic test cases"""
        print("\n[PHASE 1] Generating Test Cases...")
        start = time.time()
        
        test_cases = self._create_test_matrix()
        
        for category, tests in test_cases.items():
            for test_name, params in tests:
                batch_content = self._generate_batch_script(category, test_name, params)
                batch_file = self.batch_dir / f"{category}_{test_name}.txt"
                batch_file.write_text(batch_content)
        
        # Create master batch
        master = self.batch_dir / 'RUN_ALL.txt'
        master_lines = [f'@RUN "{f}"' for f in sorted(self.batch_dir.glob('*.txt')) if f.name != 'RUN_ALL.txt']
        master_lines.append('@EXIT')
        master.write_text('\n'.join(master_lines))
        
        duration = time.time() - start
        count = len(list(self.batch_dir.glob('*.txt'))) - 1  # Exclude RUN_ALL
        
        self.results['phases']['generate'] = {
            'status': 'success',
            'duration': duration,
            'test_cases': count
        }
        print(f"  ✓ Generated {count} test cases in {duration:.1f}s")
    
    def _phase2_execute(self):
        """Execute batch scripts in Optitex"""
        print("\n[PHASE 2] Executing Tests in Optitex...")
        start = time.time()
        
        batch_files = sorted([f for f in self.batch_dir.glob('*.txt') if f.name != 'RUN_ALL.txt'])
        executed = 0
        failed = 0
        
        for i, batch_file in enumerate(batch_files, 1):
            print(f"  [{i}/{len(batch_files)}] {batch_file.stem}...", end=' ', flush=True)
            
            try:
                cmd = [str(self.optitex_exe), '/BATCH', str(batch_file), '/FORCE']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    executed += 1
                    print("OK")
                else:
                    failed += 1
                    print(f"FAIL (code {result.returncode})")
                    
            except subprocess.TimeoutExpired:
                failed += 1
                print("TIMEOUT")
            except Exception as e:
                failed += 1
                print(f"ERROR: {e}")
        
        duration = time.time() - start
        
        self.results['phases']['execute'] = {
            'status': 'success' if failed == 0 else 'partial',
            'duration': duration,
            'executed': executed,
            'failed': failed
        }
        print(f"  ✓ Executed: {executed}, Failed: {failed} in {duration:.1f}s")
    
    def _phase3_parse(self):
        """Parse generated PDS files with custom parser"""
        print("\n[PHASE 3] Parsing with Custom Parser...")
        start = time.time()
        
        # Import our parser
        try:
            from pds_parser import PDSParser
        except ImportError:
            print("  ✗ pds_parser.py not found in Python path")
            self.results['phases']['parse'] = {'status': 'error', 'error': 'Parser not found'}
            return
        
        pds_files = list(self.test_output_dir.glob('*.pds'))
        parsed = 0
        errors = []
        
        for pds_file in pds_files:
            try:
                parser = PDSParser(str(pds_file))
                parser.parse()
                parser.export_to_json(str(self.parse_dir / f"{pds_file.stem}.json"))
                parsed += 1
            except Exception as e:
                errors.append(f"{pds_file.name}: {e}")
        
        duration = time.time() - start
        
        self.results['phases']['parse'] = {
            'status': 'success' if len(errors) == 0 else 'partial',
            'duration': duration,
            'parsed': parsed,
            'errors': errors
        }
        print(f"  ✓ Parsed {parsed}/{len(pds_files)} files in {duration:.1f}s")
        if errors:
            print(f"  ⚠ {len(errors)} errors (see report)")
    
    def _phase4_analyze(self):
        """Differential analysis: compare parser vs PDML"""
        print("\n[PHASE 4] Differential Analysis...")
        start = time.time()
        
        try:
            from differential_analyzer import DifferentialAnalyzer
        except ImportError:
            print("  ✗ differential_analyzer.py not found")
            self.results['phases']['analyze'] = {'status': 'error', 'error': 'Analyzer not found'}
            return
        
        analyzer = DifferentialAnalyzer(tolerance=0.01)
        
        pds_files = list(self.test_output_dir.glob('*.pds'))
        analyzed = 0
        
        for pds_file in pds_files:
            pdml_file = self.test_output_dir / f"{pds_file.stem}.pdml"
            parse_file = self.parse_dir / f"{pds_file.stem}.json"
            
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
                    print(f"  ⚠ Failed to analyze {pds_file.name}: {e}")
        
        # Generate report
        report_path = self.report_dir / 'differential_report.json'
        report = analyzer.generate_report(str(report_path))
        
        duration = time.time() - start
        
        self.results['phases']['analyze'] = {
            'status': 'success',
            'duration': duration,
            'analyzed': analyzed,
            'accuracy': report['summary']['success_rate']
        }
        print(f"  ✓ Analyzed {analyzed} files in {duration:.1f}s")
        print(f"  ✓ Parser accuracy: {report['summary']['success_rate']*100:.1f}%")
    
    def _phase5_report(self):
        """Generate final reports"""
        print("\n[PHASE 5] Generating Reports...")
        start = time.time()
        
        # HTML report
        self._generate_html_report()
        
        # Markdown report
        self._generate_markdown_report()
        
        duration = time.time() - start
        
        self.results['phases']['report'] = {
            'status': 'success',
            'duration': duration
        }
        print(f"  ✓ Reports generated in {duration:.1f}s")
    
    def _create_test_matrix(self):
        """Define systematic test cases"""
        return {
            'geometry': [
                ('square_100', {'shape': 'rect', 'w': 100, 'h': 100}),
                ('square_200', {'shape': 'rect', 'w': 200, 'h': 200}),
                ('rect_200x100', {'shape': 'rect', 'w': 200, 'h': 100}),
            ],
            'pieces': [
                ('1piece', {'pieces': 1}),
                ('2pieces', {'pieces': 2}),
                ('5pieces', {'pieces': 5}),
            ],
            'grading': [
                ('1size', {'sizes': 1}),
                ('2sizes', {'sizes': 2, 'grade': 10}),
                ('5sizes', {'sizes': 5, 'grade': 10}),
            ],
            'notches': [
                ('0notches', {'notches': 0}),
                ('1notch', {'notches': 1, 'type': 'V'}),
                ('3notches', {'notches': 3, 'type': 'V'}),
            ],
        }
    
    def _generate_batch_script(self, category: str, test_name: str, params: dict) -> str:
        """Generate Optitex batch script for a test case"""
        lines = []
        
        pds_path = self.test_output_dir / f"{category}_{test_name}.pds"
        pdml_path = self.test_output_dir / f"{category}_{test_name}.pdml"
        
        lines.append("@NEW")
        lines.append(f"@UNIT CM")
        
        # Create pieces
        num_pieces = params.get('pieces', 1)
        for i in range(num_pieces):
            lines.append(f"@NEWPIECE \"Piece{i+1}\"")
            
            # Add geometry
            if params.get('shape') == 'rect':
                w = params.get('w', 100)
                h = params.get('h', 100)
                lines.append(f"@ADDPOINT /X=0 /Y=0")
                lines.append(f"@ADDPOINT /X={w} /Y=0")
                lines.append(f"@ADDPOINT /X={w} /Y={h}")
                lines.append(f"@ADDPOINT /X=0 /Y={h}")
                lines.append("@CLOSECONTOUR")
            
            # Add notches
            for n in range(params.get('notches', 0)):
                lines.append(f"@ADDNOTCH /TYPE={params.get('type', 'V')}")
        
        # Add grading
        if 'sizes' in params:
            lines.append(f"@SETSIZECOUNT {params['sizes']}")
            if params['sizes'] > 1:
                grade = params.get('grade', 10)
                for s in range(1, params['sizes']):
                    lines.append(f"@ADDRULE /SIZE={s} /DX={grade*s} /DY={grade*s}")
        
        lines.append(f"@SAVE \"{pds_path}\" /FORMAT=PDS /XML=YES")
        lines.append(f"@SAVE \"{pdml_path}\" /FORMAT=PDML /XML=YES")
        lines.append("@CLOSE")
        
        return '\n'.join(lines)
    
    def _generate_html_report(self):
        """Generate interactive HTML report"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>PDS Reverse Engineering Results</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .phase {{ margin: 20px 0; padding: 15px; border-radius: 5px; }}
        .success {{ background: #d4edda; border-left: 4px solid #28a745; }}
        .partial {{ background: #fff3cd; border-left: 4px solid #ffc107; }}
        .error {{ background: #f8d7da; border-left: 4px solid #dc3545; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; font-weight: bold; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; padding: 15px; background: #f8f9fa; border-radius: 5px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
        .metric-label {{ font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>PDS Reverse Engineering Pipeline Results</h1>
        <p><strong>Generated:</strong> {self.results['timestamp']}</p>
        <p><strong>Optitex:</strong> {self.results['optitex']}</p>
        
        <h2>Summary</h2>
        <div>
"""
        
        # Add metrics
        if 'generate' in self.results['phases']:
            gen = self.results['phases']['generate']
            html += f"""
            <div class="metric">
                <div class="metric-value">{gen.get('test_cases', 0)}</div>
                <div class="metric-label">Test Cases</div>
            </div>
"""
        
        if 'execute' in self.results['phases']:
            exe = self.results['phases']['execute']
            html += f"""
            <div class="metric">
                <div class="metric-value">{exe.get('executed', 0)}</div>
                <div class="metric-label">Executed</div>
            </div>
"""
        
        if 'analyze' in self.results['phases']:
            ana = self.results['phases']['analyze']
            accuracy = ana.get('accuracy', 0) * 100
            html += f"""
            <div class="metric">
                <div class="metric-value">{accuracy:.1f}%</div>
                <div class="metric-label">Parser Accuracy</div>
            </div>
"""
        
        html += """
        </div>
        
        <h2>Phase Details</h2>
        <table>
            <tr><th>Phase</th><th>Status</th><th>Duration</th><th>Details</th></tr>
"""
        
        for phase_name, phase_data in self.results['phases'].items():
            status = phase_data.get('status', 'unknown')
            duration = f"{phase_data.get('duration', 0):.1f}s"
            details = ''
            
            if phase_name == 'generate':
                details = f"{phase_data.get('test_cases', 0)} tests"
            elif phase_name == 'execute':
                details = f"{phase_data.get('executed', 0)} OK, {phase_data.get('failed', 0)} failed"
            elif phase_name == 'parse':
                details = f"{phase_data.get('parsed', 0)} parsed"
            elif phase_name == 'analyze':
                details = f"{phase_data.get('analyzed', 0)} compared"
            
            html += f"<tr><td>{phase_name.title()}</td><td>{status}</td><td>{duration}</td><td>{details}</td></tr>"
        
        html += """
        </table>
        
        <h2>Next Steps</h2>
        <ol>
            <li>Review <code>reports/differential_report.json</code> for parsing errors</li>
            <li>Update parser based on failed comparisons</li>
            <li>Re-run pipeline to verify fixes</li>
            <li>Document discovered structure in Kaitai spec</li>
        </ol>
    </div>
</body>
</html>
"""
        
        report_path = self.report_dir / 'report.html'
        report_path.write_text(html)
    
    def _generate_markdown_report(self):
        """Generate markdown summary"""
        md = f"""# PDS Reverse Engineering Results

**Generated:** {self.results['timestamp']}
**Optitex:** {self.results['optitex']}

## Summary

"""
        
        for phase_name, phase_data in self.results['phases'].items():
            status = phase_data.get('status', 'unknown')
            md += f"- **{phase_name.title()}:** {status}"
            
            if phase_name == 'generate':
                md += f" ({phase_data.get('test_cases', 0)} tests)"
            elif phase_name == 'execute':
                md += f" ({phase_data.get('executed', 0)} OK, {phase_data.get('failed', 0)} failed)"
            elif phase_name == 'parse':
                md += f" ({phase_data.get('parsed', 0)} parsed)"
            elif phase_name == 'analyze':
                accuracy = phase_data.get('accuracy', 0) * 100
                md += f" ({phase_data.get('analyzed', 0)} compared, {accuracy:.1f}% accuracy)"
            
            md += "\n"
        
        md += """
## File Locations

- Batch Scripts: `batch_scripts/`
- Test Outputs: `test_outputs/` (.pds, .pdml, .dxf)
- Parse Results: `parse_results/` (.json)
- Reports: `reports/` (.json, .html, .md)

## Next Steps

1. Review `reports/differential_report.json` for detailed error analysis
2. Identify patterns in failed comparisons
3. Update `pds_parser.py` to fix identified issues
4. Re-run pipeline: `python automated_re_pipeline.py <optitex> <output>`
5. Iterate until parser accuracy > 99%
"""
        
        report_path = self.report_dir / 'report.md'
        report_path.write_text(md)


def main():
    if len(sys.argv) < 3:
        print("Usage: python automated_re_pipeline.py <optitex_exe> <output_dir>")
        print("\nExample:")
        print('  python automated_re_pipeline.py "C:/Program Files/Optitex/Optitex 21/PDS.exe" ./re_results')
        sys.exit(1)
    
    optitex_exe = sys.argv[1]
    output_dir = sys.argv[2]
    
    pipeline = AutomatedREPipeline(optitex_exe, output_dir)
    pipeline.run_full_pipeline()


if __name__ == "__main__":
    main()
