#!/usr/bin/env python3
"""
Pattern Recognition for PDS Binary Files
Uses ML and statistical methods to identify structure
"""
import struct
import numpy as np
from pathlib import Path
from collections import Counter
import matplotlib.pyplot as plt


class PatternRecognizer:
    """Identify patterns and structures in binary PDS files"""
    
    def __init__(self, file_path):
        self.data = Path(file_path).read_bytes()
        self.file_path = file_path
        self.patterns = {}
        
    def find_repeating_patterns(self, min_length=4, max_length=64, min_occurrences=3):
        """Find repeating byte sequences that might indicate structure"""
        patterns = {}
        
        for length in range(min_length, max_length + 1):
            for i in range(len(self.data) - length):
                pattern = self.data[i:i+length]
                pattern_hex = pattern.hex()
                
                if pattern_hex in patterns:
                    patterns[pattern_hex]['count'] += 1
                    patterns[pattern_hex]['offsets'].append(i)
                else:
                    patterns[pattern_hex] = {
                        'pattern': pattern,
                        'count': 1,
                        'offsets': [i],
                        'length': length
                    }
        
        # Filter for truly repeating patterns
        repeating = {k: v for k, v in patterns.items() 
                    if v['count'] >= min_occurrences}
        
        self.patterns['repeating'] = repeating
        return repeating
    
    def find_float_arrays(self, min_values=3):
        """Find sequences of float32 values (likely coordinates)"""
        float_arrays = []
        
        i = 0
        while i < len(self.data) - 4:
            try:
                val = struct.unpack('<f', self.data[i:i+4])[0]
                # Reasonable range for garment coordinates
                if -10000 < val < 10000 and not np.isnan(val):
                    # Look for consecutive floats
                    array_start = i
                    array_values = [val]
                    j = i + 4
                    
                    while j < len(self.data) - 4:
                        next_val = struct.unpack('<f', self.data[j:j+4])[0]
                        if -10000 < next_val < 10000 and not np.isnan(next_val):
                            array_values.append(next_val)
                            j += 4
                        else:
                            break
                    
                    if len(array_values) >= min_values:
                        float_arrays.append({
                            'offset': array_start,
                            'length': len(array_values),
                            'values': array_values[:20]  # First 20
                        })
                        i = j  # Skip past this array
                    else:
                        i += 4
                else:
                    i += 1
            except:
                i += 1
        
        self.patterns['float_arrays'] = float_arrays
        return float_arrays
    
    def find_integer_arrays(self, min_values=3):
        """Find sequences of int32 values (likely counts/indices)"""
        int_arrays = []
        
        i = 0
        while i < len(self.data) - 4:
            try:
                val = struct.unpack('<i', self.data[i:i+4])[0]
                # Reasonable range for counts
                if 0 <= val < 100000:
                    array_start = i
                    array_values = [val]
                    j = i + 4
                    
                    while j < len(self.data) - 4:
                        next_val = struct.unpack('<i', self.data[j:j+4])[0]
                        if 0 <= next_val < 100000:
                            array_values.append(next_val)
                            j += 4
                        else:
                            break
                    
                    if len(array_values) >= min_values:
                        int_arrays.append({
                            'offset': array_start,
                            'length': len(array_values),
                            'values': array_values[:20]
                        })
                        i = j
                    else:
                        i += 4
                else:
                    i += 1
            except:
                i += 1
        
        self.patterns['int_arrays'] = int_arrays
        return int_arrays
    
    def analyze_byte_distribution(self):
        """Analyze byte value distribution for structure hints"""
        byte_counts = Counter(self.data)
        total = len(self.data)
        
        distribution = {
            'zero_bytes': byte_counts[0] / total,
            'ff_bytes': byte_counts[255] / total,
            'printable_ascii': sum(byte_counts[b] for b in range(32, 127)) / total,
            'high_bytes': sum(byte_counts[b] for b in range(128, 256)) / total,
            'most_common': byte_counts.most_common(10)
        }
        
        self.patterns['byte_distribution'] = distribution
        return distribution
    
    def find_string_tables(self, min_strings=5):
        """Find regions with many consecutive strings"""
        string_regions = []
        in_region = False
        region_start = 0
        string_count = 0
        
        i = 0
        while i < len(self.data):
            # Check for length-prefixed string
            length = self.data[i]
            if 1 <= length <= 100 and i + 1 + length < len(self.data):
                # Check if following bytes are printable
                string_bytes = self.data[i+1:i+1+length]
                if all(32 <= b < 127 or b == 0 for b in string_bytes):
                    if not in_region:
                        in_region = True
                        region_start = i
                        string_count = 1
                    else:
                        string_count += 1
                    i += 1 + length
                    continue
            
            if in_region and string_count >= min_strings:
                string_regions.append({
                    'offset': region_start,
                    'length': i - region_start,
                    'string_count': string_count
                })
            
            in_region = False
            string_count = 0
            i += 1
        
        self.patterns['string_tables'] = string_regions
        return string_regions
    
    def visualize_patterns(self, output_path):
        """Create comprehensive pattern visualization"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # 1. Byte value heatmap
        byte_array = np.array(list(self.data[:10000]))  # First 10KB
        byte_matrix = byte_array[:10000].reshape(100, 100)
        im = axes[0, 0].imshow(byte_matrix, cmap='hot', aspect='auto')
        axes[0, 0].set_title('Byte Value Heatmap (First 10KB)')
        axes[0, 0].set_xlabel('Position')
        axes[0, 0].set_ylabel('Block')
        plt.colorbar(im, ax=axes[0, 0])
        
        # 2. Byte frequency
        byte_counts = Counter(self.data)
        axes[0, 1].bar(range(256), [byte_counts[i] for i in range(256)])
        axes[0, 1].set_title('Byte Frequency Distribution')
        axes[0, 1].set_xlabel('Byte Value')
        axes[0, 1].set_ylabel('Count')
        
        # 3. Float array locations
        float_arrays = self.patterns.get('float_arrays', [])
        if float_arrays:
            offsets = [a['offset'] for a in float_arrays]
            lengths = [a['length'] for a in float_arrays]
            axes[1, 0].scatter(offsets, lengths, alpha=0.5)
            axes[1, 0].set_title('Detected Float Arrays')
            axes[1, 0].set_xlabel('File Offset')
            axes[1, 0].set_ylabel('Array Length')
        else:
            axes[1, 0].text(0.5, 0.5, 'No float arrays detected', 
                          ha='center', va='center')
        
        # 4. Entropy by section
        chunk_size = 256
        entropies = []
        positions = []
        for i in range(0, len(self.data) - chunk_size, chunk_size):
            chunk = self.data[i:i+chunk_size]
            entropy = self._calculate_entropy(chunk)
            entropies.append(entropy)
            positions.append(i)
        
        axes[1, 1].plot(positions, entropies, linewidth=0.5)
        axes[1, 1].set_title('Entropy by Section')
        axes[1, 1].set_xlabel('File Offset')
        axes[1, 1].set_ylabel('Entropy')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        print(f"Saved pattern visualization to {output_path}")
    
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
    
    def generate_report(self):
        """Generate comprehensive pattern report"""
        print(f"\n{'='*60}")
        print(f"Pattern Analysis: {self.file_path}")
        print(f"{'='*60}")
        
        # Run all analyses
        self.find_repeating_patterns()
        self.find_float_arrays()
        self.find_integer_arrays()
        self.analyze_byte_distribution()
        self.find_string_tables()
        
        # Print summary
        print(f"\nFile size: {len(self.data)} bytes")
        
        dist = self.patterns.get('byte_distribution', {})
        print(f"\nByte Distribution:")
        print(f"  Zero bytes: {dist.get('zero_bytes', 0)*100:.2f}%")
        print(f"  0xFF bytes: {dist.get('ff_bytes', 0)*100:.2f}%")
        print(f"  Printable ASCII: {dist.get('printable_ascii', 0)*100:.2f}%")
        
        repeating = self.patterns.get('repeating', {})
        print(f"\nRepeating patterns: {len(repeating)}")
        top_patterns = sorted(repeating.items(), 
                             key=lambda x: -x[1]['count'])[:5]
        for pattern_hex, info in top_patterns:
            print(f"  {pattern_hex[:20]}...: {info['count']} occurrences")
        
        float_arrays = self.patterns.get('float_arrays', [])
        print(f"\nFloat arrays detected: {len(float_arrays)}")
        for arr in float_arrays[:5]:
            print(f"  Offset {arr['offset']}: {arr['length']} values")
        
        int_arrays = self.patterns.get('int_arrays', [])
        print(f"\nInteger arrays detected: {len(int_arrays)}")
        for arr in int_arrays[:5]:
            print(f"  Offset {arr['offset']}: {arr['length']} values")
        
        string_tables = self.patterns.get('string_tables', [])
        print(f"\nString table regions: {len(string_tables)}")
        for region in string_tables[:3]:
            print(f"  Offset {region['offset']}: {region['string_count']} strings")
        
        return self.patterns


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pattern_recognizer.py <pds_file> [output_png]")
        sys.exit(1)
    
    recognizer = PatternRecognizer(sys.argv[1])
    recognizer.generate_report()
    
    if len(sys.argv) >= 3:
        recognizer.visualize_patterns(sys.argv[2])
