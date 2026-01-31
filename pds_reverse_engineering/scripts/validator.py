#!/usr/bin/env python3
"""
Validation Framework for PDS Parser
Compares parser output against Optitex PDML export
"""
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import json
from typing import Dict, List
from pds_parser import PDSParser


class PDSValidator:
    """Validate parser output against Optitex reference"""
    
    def __init__(self, optitex_path: str):
        self.optitex_path = optitex_path
        self.results = []
        
    def validate_file(self, pds_path: str, parser_class=PDSParser) -> Dict:
        """Validate parser output against Optitex PDML export"""
        pds_path = Path(pds_path)
        
        # Parse with our parser
        parser = parser_class(str(pds_path))
        try:
            parsed = parser.parse()
            parser_success = True
        except Exception as e:
            return {
                'file': str(pds_path),
                'success': False,
                'error': f"Parser failed: {e}",
                'coverage': 0
            }
        
        # Export to PDML with Optitex
        pdml_path = self._export_pdml_optitex(pds_path)
        if not pdml_path.exists():
            return {
                'file': str(pds_path),
                'success': False,
                'error': "Optitex PDML export failed",
                'coverage': 0
            }
        
        # Compare outputs
        comparison = self._compare_outputs(parsed, pdml_path)
        
        return {
            'file': str(pds_path),
            'success': comparison['match'],
            'differences': comparison['differences'],
            'coverage': comparison['coverage'],
            'details': comparison['details']
        }
    
    def _export_pdml_optitex(self, pds_path: Path) -> Path:
        """Use Optitex batch mode to export PDML"""
        pdml_path = pds_path.with_suffix('.pdml')
        
        # Create batch script
        batch_content = f"""@OPEN "{pds_path}"
@SAVE "{pdml_path}" /FORMAT=PDML
@EXIT
"""
        batch_path = pds_path.parent / 'temp_batch.txt'
        batch_path.write_text(batch_content)
        
        # Execute
        cmd = [self.optitex_path, '/BATCH', str(batch_path)]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
        except:
            pass
        
        # Cleanup
        if batch_path.exists():
            batch_path.unlink()
        
        return pdml_path
    
    def _compare_outputs(self, parsed, pdml_path: Path) -> Dict:
        """Compare parser output with Optitex PDML"""
        differences = []
        details = {}
        
        try:
            tree = ET.parse(pdml_path)
            root = tree.getroot()
        except Exception as e:
            return {
                'match': False,
                'differences': [{'error': f'Failed to parse PDML: {e}'}],
                'coverage': 0,
                'details': {}
            }
        
        # Compare piece counts
        xml_pieces = root.findall('.//Piece')
        if len(xml_pieces) != len(parsed.pieces):
            differences.append({
                'field': 'num_pieces',
                'parser': len(parsed.pieces),
                'optitex': len(xml_pieces)
            })
        details['piece_count_parser'] = len(parsed.pieces)
        details['piece_count_optitex'] = len(xml_pieces)
        
        # Compare size counts
        xml_sizes = root.findall('.//Size')
        if len(xml_sizes) != len(parsed.sizes):
            differences.append({
                'field': 'num_sizes',
                'parser': len(parsed.sizes),
                'optitex': len(xml_sizes)
            })
        
        # Compare piece names
        xml_piece_names = [p.get('name') for p in xml_pieces]
        parser_piece_names = [p.name for p in parsed.pieces]
        
        name_matches = sum(1 for name in parser_piece_names if name in xml_piece_names)
        details['piece_name_matches'] = name_matches
        details['piece_name_total'] = max(len(xml_piece_names), len(parser_piece_names))
        
        if set(xml_piece_names) != set(parser_piece_names):
            differences.append({
                'field': 'piece_names',
                'parser_only': list(set(parser_piece_names) - set(xml_piece_names)),
                'optitex_only': list(set(xml_piece_names) - set(parser_piece_names))
            })
        
        # Compare contour point counts (first piece only for now)
        if parsed.pieces and xml_pieces:
            xml_points = xml_pieces[0].findall('.//Contour/Point')
            parser_points = parsed.pieces[0].contour.points
            
            if len(xml_points) != len(parser_points):
                differences.append({
                    'field': 'contour_points',
                    'parser': len(parser_points),
                    'optitex': len(xml_points)
                })
            
            # Check coordinate accuracy
            if len(xml_points) == len(parser_points):
                coord_errors = []
                for i, (xml_pt, parser_pt) in enumerate(zip(xml_points, parser_points)):
                    xml_x = float(xml_pt.get('x', 0))
                    xml_y = float(xml_pt.get('y', 0))
                    
                    x_error = abs(xml_x - parser_pt.x)
                    y_error = abs(xml_y - parser_pt.y)
                    
                    if x_error > 0.1 or y_error > 0.1:  # 0.1mm tolerance
                        coord_errors.append({
                            'point': i,
                            'x_error': x_error,
                            'y_error': y_error
                        })
                
                details['coordinate_errors'] = coord_errors[:10]
                if coord_errors:
                    differences.append({
                        'field': 'coordinate_accuracy',
                        'errors': len(coord_errors)
                    })
        
        # Calculate coverage
        total_checks = 4  # pieces, sizes, names, coordinates
        passed_checks = total_checks - len(differences)
        coverage = passed_checks / total_checks
        
        return {
            'match': len(differences) == 0,
            'differences': differences,
            'coverage': coverage,
            'details': details
        }
    
    def run_validation_suite(self, samples_dir: str, pattern="*.pds") -> List[Dict]:
        """Run validation on all sample files"""
        samples = list(Path(samples_dir).glob(pattern))
        
        print(f"Validating {len(samples)} files...")
        
        for i, sample in enumerate(samples):
            print(f"[{i+1}/{len(samples)}] {sample.name}")
            result = self.validate_file(str(sample))
            self.results.append(result)
            
            status = "PASS" if result['success'] else "FAIL"
            coverage = result.get('coverage', 0) * 100
            print(f"    Status: {status}, Coverage: {coverage:.1f}%")
        
        return self.results
    
    def generate_report(self, output_path: str):
        """Generate validation report"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r['success'])
        
        report = {
            'summary': {
                'total_files': total,
                'passed': passed,
                'failed': total - passed,
                'success_rate': passed / total if total > 0 else 0,
                'avg_coverage': sum(r.get('coverage', 0) for r in self.results) / total if total > 0 else 0
            },
            'detailed_results': self.results
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print(f"\n{'='*60}")
        print("Validation Summary")
        print(f"{'='*60}")
        print(f"Total files: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success rate: {report['summary']['success_rate']*100:.1f}%")
        print(f"Average coverage: {report['summary']['avg_coverage']*100:.1f}%")
        
        return report


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python validator.py <optitex_path> <samples_dir> <output_json>")
        print("   or: python validator.py <optitex_path> <pds_file> <output_json> --single")
        sys.exit(1)
    
    optitex_path = sys.argv[1]
    input_path = sys.argv[2]
    output_path = sys.argv[3]
    
    validator = PDSValidator(optitex_path)
    
    if '--single' in sys.argv:
        result = validator.validate_file(input_path)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Validation result saved to {output_path}")
    else:
        validator.run_validation_suite(input_path)
        validator.generate_report(output_path)
        print(f"\nReport saved to {output_path}")
