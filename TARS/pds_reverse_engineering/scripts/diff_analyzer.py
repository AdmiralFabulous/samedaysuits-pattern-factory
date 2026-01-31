#!/usr/bin/env python3
"""
Binary Diff Analyzer for PDS Files
Controlled diff analysis to identify structure changes
"""
import difflib
import struct
from pathlib import Path
import json
import matplotlib.pyplot as plt
import numpy as np


class PDSBinaryDiff:
    """Comprehensive binary diff analysis"""
    
    def __init__(self, base_file, modified_file, description=""):
        self.base_data = Path(base_file).read_bytes()
        self.modified_data = Path(modified_file).read_bytes()
        self.description = description
        self.diffs = []
        
    def byte_level_diff(self):
        """Generate byte-by-byte diff"""
        diff = []
        min_len = min(len(self.base_data), len(self.modified_data))
        
        for i in range(min_len):
            if self.base_data[i] != self.modified_data[i]:
                diff.append({
                    'offset': i,
                    'base': self.base_data[i],
                    'modified': self.modified_data[i],
                    'base_hex': f'{self.base_data[i]:02X}',
                    'modified_hex': f'{self.modified_data[i]:02X}'
                })
        
        # Handle length differences
        if len(self.base_data) != len(self.modified_data):
            diff.append({
                'type': 'length_difference',
                'base_len': len(self.base_data),
                'modified_len': len(self.modified_data)
            })
        
        self.diffs = diff
        return diff
    
    def find_insertions(self):
        """Find inserted byte sequences"""
        sm = difflib.SequenceMatcher(None, self.base_data, self.modified_data)
        insertions = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'insert':
                insertions.append({
                    'offset': j1,
                    'length': j2 - j1,
                    'data_hex': self.modified_data[j1:j2].hex()[:100]
                })
        return insertions
    
    def find_deletions(self):
        """Find deleted byte sequences"""
        sm = difflib.SequenceMatcher(None, self.base_data, self.modified_data)
        deletions = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'delete':
                deletions.append({
                    'offset': i1,
                    'length': i2 - i1,
                    'data_hex': self.base_data[i1:i2].hex()[:100]
                })
        return deletions
    
    def find_replacements(self):
        """Find replaced byte sequences"""
        sm = difflib.SequenceMatcher(None, self.base_data, self.modified_data)
        replacements = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'replace':
                replacements.append({
                    'base_offset': i1,
                    'base_len': i2 - i1,
                    'base_hex': self.base_data[i1:i2].hex()[:100],
                    'modified_offset': j1,
                    'modified_len': j2 - j1,
                    'modified_hex': self.modified_data[j1:j2].hex()[:100]
                })
        return replacements
    
    def analyze_value_changes(self):
        """Try to interpret changes as numeric values"""
        changes = []
        for rep in self.find_replacements():
            if rep['base_len'] == rep['modified_len']:
                # Same size - might be value change
                if rep['base_len'] == 4:
                    try:
                        base_f = struct.unpack('<f', bytes.fromhex(rep['base_hex']))[0]
                        mod_f = struct.unpack('<f', bytes.fromhex(rep['modified_hex']))[0]
                        base_i = struct.unpack('<i', bytes.fromhex(rep['base_hex']))[0]
                        mod_i = struct.unpack('<i', bytes.fromhex(rep['modified_hex']))[0]
                        
                        changes.append({
                            'offset': rep['base_offset'],
                            'type': '4_byte_value',
                            'float32_le': {
                                'base': base_f,
                                'modified': mod_f,
                                'delta': mod_f - base_f
                            },
                            'int32_le': {
                                'base': base_i,
                                'modified': mod_i,
                                'delta': mod_i - base_i
                            }
                        })
                    except:
                        pass
                        
                elif rep['base_len'] == 8:
                    try:
                        base_d = struct.unpack('<d', bytes.fromhex(rep['base_hex']))[0]
                        mod_d = struct.unpack('<d', bytes.fromhex(rep['modified_hex']))[0]
                        changes.append({
                            'offset': rep['base_offset'],
                            'type': '8_byte_value',
                            'float64_le': {
                                'base': base_d,
                                'modified': mod_d,
                                'delta': mod_d - base_d
                            }
                        })
                    except:
                        pass
        return changes
    
    def visualize_diff(self, output_path):
        """Create comprehensive visual diff"""
        fig, axes = plt.subplots(4, 1, figsize=(15, 12))
        
        # 1. Byte difference map
        min_len = min(len(self.base_data), len(self.modified_data))
        diff_bytes = np.zeros(min_len)
        for i in range(min_len):
            diff_bytes[i] = 1 if self.base_data[i] != self.modified_data[i] else 0
        
        diff_indices = np.where(diff_bytes > 0)[0]
        if len(diff_indices) > 0:
            axes[0].scatter(diff_indices, diff_bytes[diff_indices], c='red', s=1, alpha=0.5)
        axes[0].set_title(f'Byte Differences - {self.description}')
        axes[0].set_ylabel('Difference')
        axes[0].set_xlim(0, max(len(self.base_data), len(self.modified_data)))
        
        # 2. Entropy comparison
        base_entropy = self._rolling_entropy(self.base_data)
        mod_entropy = self._rolling_entropy(self.modified_data)
        
        axes[1].plot(base_entropy, label='Base', alpha=0.7, linewidth=0.5)
        axes[1].plot(mod_entropy, label='Modified', alpha=0.7, linewidth=0.5)
        axes[1].set_title('Entropy Comparison')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        # 3. Byte value distribution
        axes[2].hist(self.base_data, bins=256, alpha=0.5, label='Base', density=True)
        axes[2].hist(self.modified_data, bins=256, alpha=0.5, label='Modified', density=True)
        axes[2].set_title('Byte Value Distribution')
        axes[2].legend()
        
        # 4. Difference magnitude (for numeric interpretations)
        value_changes = self.analyze_value_changes()
        if value_changes:
            offsets = [c['offset'] for c in value_changes if 'float32_le' in c]
            deltas = [c['float32_le']['delta'] for c in value_changes if 'float32_le' in c]
            axes[3].scatter(offsets, deltas, alpha=0.5, s=5)
            axes[3].set_title('Float Value Changes (Delta)')
            axes[3].set_xlabel('Offset')
            axes[3].set_ylabel('Delta')
            axes[3].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        print(f"Saved diff visualization to {output_path}")
    
    def _rolling_entropy(self, data, window=1024):
        """Calculate rolling entropy"""
        entropies = []
        for i in range(0, len(data) - window, window):
            window_data = data[i:i+window]
            entropy = self._calculate_entropy(window_data)
            entropies.append(entropy)
        return entropies
    
    def _calculate_entropy(self, data):
        """Calculate Shannon entropy"""
        if not data:
            return 0
        entropy = 0
        for x in range(256):
            p_x = float(data.count(x)) / len(data)
            if p_x > 0:
                entropy += -p_x * np.log2(p_x)
        return entropy
    
    def generate_report(self, output_path):
        """Generate comprehensive diff report"""
        report = {
            'description': self.description,
            'base_size': len(self.base_data),
            'modified_size': len(self.modified_data),
            'byte_differences': len(self.byte_level_diff()),
            'insertions': len(self.find_insertions()),
            'deletions': len(self.find_deletions()),
            'replacements': len(self.find_replacements()),
            'value_changes': self.analyze_value_changes()[:50]  # Limit output
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report


class DiffCampaign:
    """Run systematic diff analysis across file series"""
    
    def __init__(self, samples_dir, output_dir):
        self.samples_dir = Path(samples_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def run_series_diffs(self, series_prefix):
        """Run diffs for a file series (e.g., A01-A05)"""
        # Find base file
        base_file = self.samples_dir / f"{series_prefix}_base.pds"
        if not base_file.exists():
            print(f"Base file not found: {base_file}")
            return
        
        # Find all variants
        variants = list(self.samples_dir.glob(f"{series_prefix}_*.pds"))
        variants = [v for v in variants if v != base_file]
        
        for variant in variants:
            description = f"{base_file.stem} vs {variant.stem}"
            print(f"Analyzing: {description}")
            
            diff = PDSBinaryDiff(base_file, variant, description)
            
            # Generate outputs
            stem = variant.stem
            diff.visualize_diff(self.output_dir / f"{stem}_diff.png")
            diff.generate_report(self.output_dir / f"{stem}_report.json")
    
    def run_all_series(self):
        """Run diffs for all series (A-H)"""
        for series in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
            print(f"\n=== Series {series} ===")
            self.run_series_diffs(series)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python diff_analyzer.py <base_file> <modified_file> <output_dir>")
        print("   or: python diff_analyzer.py --campaign <samples_dir> <output_dir>")
        sys.exit(1)
    
    if sys.argv[1] == '--campaign':
        campaign = DiffCampaign(sys.argv[2], sys.argv[3])
        campaign.run_all_series()
    else:
        diff = PDSBinaryDiff(sys.argv[1], sys.argv[2], f"{sys.argv[1]} vs {sys.argv[2]}")
        diff.visualize_diff(Path(sys.argv[3]) / 'diff.png')
        diff.generate_report(Path(sys.argv[3]) / 'report.json')
