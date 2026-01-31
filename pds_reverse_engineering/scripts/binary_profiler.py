#!/usr/bin/env python3
"""
Binary Profiler for PDS Files
Initial analysis: entropy, strings, magic bytes, structure detection
"""
import struct
import hashlib
import json
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np


class BinaryProfiler:
    """Comprehensive binary file analysis for PDS format"""
    
    def __init__(self, samples_dir, output_dir):
        self.samples_dir = Path(samples_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.profiles = {}
        
    def analyze_file(self, filepath):
        """Comprehensive single file analysis"""
        profile = {
            'filename': filepath.name,
            'size': filepath.stat().st_size,
            'hashes': {},
            'header': {},
            'entropy': {},
            'strings': {},
            'structures': {}
        }
        
        data = filepath.read_bytes()
        
        # Cryptographic hashes
        profile['hashes']['md5'] = hashlib.md5(data).hexdigest()
        profile['hashes']['sha256'] = hashlib.sha256(data).hexdigest()
        
        # Header analysis (first 256 bytes)
        header = data[:256]
        profile['header']['hex'] = header.hex()
        profile['header']['ascii'] = self._bytes_to_ascii(header)
        profile['header']['int32_le'] = list(struct.unpack('<64I', header[:256]))
        profile['header']['int32_be'] = list(struct.unpack('>64I', header[:256]))
        profile['header']['float32_le'] = list(struct.unpack('<64f', header[:256]))
        
        # Entropy analysis
        profile['entropy']['global'] = self._calculate_entropy(data)
        profile['entropy']['by_chunk'] = self._chunk_entropy(data, chunk_size=1024)
        
        # String extraction
        profile['strings']['ascii'] = self._extract_strings(data, min_len=4)
        profile['strings']['unicode'] = self._extract_unicode_strings(data, min_len=4)
        
        # Magic bytes detection
        profile['structures']['magic'] = self._detect_magic(data)
        
        # Look for float patterns (likely coordinates)
        profile['structures']['float_candidates'] = self._find_float_patterns(data)
        
        return profile
    
    def _bytes_to_ascii(self, data):
        """Convert bytes to printable ASCII representation"""
        return ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    
    def _calculate_entropy(self, data):
        """Calculate Shannon entropy of data"""
        if not data:
            return 0
        entropy = 0
        for x in range(256):
            p_x = float(data.count(x)) / len(data)
            if p_x > 0:
                entropy += -p_x * np.log2(p_x)
        return entropy
    
    def _chunk_entropy(self, data, chunk_size=1024):
        """Calculate entropy per chunk for entropy mapping"""
        entropies = []
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            entropies.append(self._calculate_entropy(chunk))
        return entropies
    
    def _extract_strings(self, data, min_len=4):
        """Extract ASCII strings from binary"""
        strings = []
        current = []
        for byte in data:
            if 32 <= byte < 127:
                current.append(chr(byte))
            else:
                if len(current) >= min_len:
                    strings.append(''.join(current))
                current = []
        return strings[:100]  # Limit output
    
    def _extract_unicode_strings(self, data, min_len=4):
        """Extract UTF-16LE strings (common in Windows)"""
        strings = []
        try:
            decoded = data.decode('utf-16le', errors='ignore')
            parts = decoded.split('\x00')
            strings = [p for p in parts if len(p) >= min_len][:50]
        except:
            pass
        return strings
    
    def _detect_magic(self, data):
        """Detect known magic byte signatures"""
        magic_signatures = {
            b'\x50\x4B\x03\x04': 'ZIP',
            b'\x1F\x8B\x08': 'GZIP',
            b'\x78\x9C': 'ZLIB',
            b'\x89PNG': 'PNG',
            b'\xFF\xD8\xFF': 'JPEG',
            b'\x25PDF': 'PDF',
            b'\x3C\x3F\x78\x6D\x6C': 'XML',
        }
        detected = []
        for magic, ftype in magic_signatures.items():
            if data.startswith(magic) or magic in data[:100]:
                detected.append(ftype)
        return detected
    
    def _find_float_patterns(self, data):
        """Find likely float32 values (coordinate candidates)"""
        candidates = []
        for i in range(0, len(data) - 4, 4):
            try:
                val = struct.unpack('<f', data[i:i+4])[0]
                # Reasonable coordinate range for garment patterns
                if -10000 < val < 10000 and abs(val) > 0.001:
                    candidates.append({'offset': i, 'value': val})
            except:
                pass
        return candidates[:20]  # Top 20 candidates
    
    def analyze_all(self):
        """Analyze all PDS files in samples directory"""
        for filepath in self.samples_dir.glob('**/*.pds'):
            print(f"Analyzing: {filepath.name}")
            self.profiles[filepath.name] = self.analyze_file(filepath)
        
        # Save JSON results
        output_file = self.output_dir / 'binary_profiles.json'
        with open(output_file, 'w') as f:
            json.dump(self.profiles, f, indent=2)
        
        # Generate visualizations
        self._visualize_entropy()
        self._visualize_header_comparison()
        
        return self.profiles
    
    def _visualize_entropy(self):
        """Create entropy heatmap for all files"""
        fig, axes = plt.subplots(len(self.profiles), 1, figsize=(15, 3*len(self.profiles)))
        if len(self.profiles) == 1:
            axes = [axes]
        
        for idx, (name, profile) in enumerate(self.profiles.items()):
            entropies = profile['entropy']['by_chunk']
            axes[idx].plot(entropies, linewidth=0.5)
            axes[idx].set_title(f"{name} - Entropy Profile")
            axes[idx].set_ylabel("Entropy")
            axes[idx].set_ylim(0, 8)
            axes[idx].grid(True, alpha=0.3)
        
        plt.xlabel("Chunk Index")
        plt.tight_layout()
        plt.savefig(self.output_dir / 'entropy_profiles.png', dpi=150)
        plt.close()
        print(f"Saved entropy visualization to {self.output_dir / 'entropy_profiles.png'}")
    
    def _visualize_header_comparison(self):
        """Compare headers across files to find common structure"""
        if len(self.profiles) < 2:
            return
        
        # Compare first 64 bytes
        fig, ax = plt.subplots(figsize=(15, 8))
        
        for name, profile in self.profiles.items():
            header_bytes = bytes.fromhex(profile['header']['hex'])[:64]
            ax.scatter(range(len(header_bytes)), header_bytes, 
                      label=name[:20], alpha=0.6, s=10)
        
        ax.set_xlabel("Byte Offset")
        ax.set_ylabel("Byte Value")
        ax.set_title("Header Byte Comparison Across Files")
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plt.savefig(self.output_dir / 'header_comparison.png', dpi=150)
        plt.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python binary_profiler.py <samples_dir> <output_dir>")
        sys.exit(1)
    
    profiler = BinaryProfiler(sys.argv[1], sys.argv[2])
    profiles = profiler.analyze_all()
    print(f"\nAnalyzed {len(profiles)} files")
    print(f"Results saved to {sys.argv[2]}")
