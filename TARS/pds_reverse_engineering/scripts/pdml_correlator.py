#!/usr/bin/env python3
"""
PDML-Binary Correlator
Maps data from PDML (XML) export back to binary offsets
"""
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class PDSPoint:
    x: float
    y: float
    z: Optional[float] = None


@dataclass
class PDSPiece:
    code: str
    name: str
    description: str
    contour: List[PDSPoint]
    notches: List[Dict]
    drill_holes: List[PDSPoint]


@dataclass
class PDSStyle:
    filename: str
    name: str
    units_length: str
    num_sizes: int
    num_pieces: int
    pieces: List[PDSPiece]


class PDMLParser:
    """Parse PDML XML files"""
    
    def parse_file(self, filepath):
        """Parse PDML file into structured data"""
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        style = PDSStyle(
            filename=filepath.name,
            name=self._get_text(root, './/Style/Name') or "Unknown",
            units_length=self._get_text(root, './/Units/Length') or "cm",
            num_sizes=int(self._get_attr(root, './/Sizes', 'count') or 0),
            num_pieces=int(self._get_attr(root, './/Pieces', 'count') or 0),
            pieces=self._parse_pieces(root)
        )
        return style
    
    def _get_text(self, elem, xpath, default=None):
        """Safely extract text from XML element"""
        found = elem.find(xpath)
        return found.text if found is not None else default
    
    def _get_attr(self, elem, xpath, attr, default=None):
        """Safely extract attribute from XML element"""
        found = elem.find(xpath)
        return found.get(attr) if found is not None else default
    
    def _parse_pieces(self, root):
        """Extract all pieces from PDML"""
        pieces = []
        for piece_elem in root.findall('.//Piece'):
            piece = PDSPiece(
                code=piece_elem.get('code', ''),
                name=piece_elem.get('name', ''),
                description=piece_elem.get('description', ''),
                contour=self._parse_contour(piece_elem),
                notches=self._parse_notches(piece_elem),
                drill_holes=self._parse_drill_holes(piece_elem)
            )
            pieces.append(piece)
        return pieces
    
    def _parse_contour(self, piece_elem):
        """Extract contour points"""
        points = []
        contour = piece_elem.find('.//Contour')
        if contour is not None:
            for point in contour.findall('.//Point'):
                points.append(PDSPoint(
                    x=float(point.get('x', 0)),
                    y=float(point.get('y', 0)),
                    z=float(point.get('z')) if point.get('z') else None
                ))
        return points
    
    def _parse_notches(self, piece_elem):
        """Extract notch data"""
        notches = []
        for notch in piece_elem.findall('.//Notch'):
            notches.append({
                'type': notch.get('type', 'V'),
                'x': float(notch.get('x', 0)),
                'y': float(notch.get('y', 0)),
                'depth': float(notch.get('depth')) if notch.get('depth') else None
            })
        return notches
    
    def _parse_drill_holes(self, piece_elem):
        """Extract drill hole positions"""
        holes = []
        for hole in piece_elem.findall('.//DrillHole'):
            holes.append(PDSPoint(
                x=float(hole.get('x', 0)),
                y=float(hole.get('y', 0))
            ))
        return holes


class PDMLBinaryCorrelator:
    """Correlate PDML data with binary PDS file"""
    
    def __init__(self, pds_path, pdml_path):
        self.pds_data = Path(pds_path).read_bytes()
        self.pds_path = pds_path
        
        parser = PDMLParser()
        self.style = parser.parse_file(pdml_path)
        
        self.correlations = []
        self.failed_searches = []
        
    def find_coordinates(self, tolerance=0.01):
        """Find coordinate values in binary with various encodings"""
        for piece in self.style.pieces:
            for i, point in enumerate(piece.contour):
                # Search for x coordinate
                found_x = self._search_value(point.x, f"{piece.code}_pt{i}_x", tolerance)
                if not found_x:
                    self.failed_searches.append(f"{piece.code}_pt{i}_x = {point.x}")
                
                # Search for y coordinate
                found_y = self._search_value(point.y, f"{piece.code}_pt{i}_y", tolerance)
                if not found_y:
                    self.failed_searches.append(f"{piece.code}_pt{i}_y = {point.y}")
    
    def _search_value(self, value, label, tolerance=0.01):
        """Search for a numeric value in binary using multiple encodings"""
        encodings = [
            ('float32_le', struct.pack('<f', value)),
            ('float32_be', struct.pack('>f', value)),
            ('float64_le', struct.pack('<d', value)),
            ('float64_be', struct.pack('>d', value)),
            ('int32_le', struct.pack('<i', int(value * 100))),  # Scaled integer (cm->mm)
            ('int32_be', struct.pack('>i', int(value * 100))),
            ('int32_le_1000', struct.pack('<i', int(value * 1000))),  # Higher precision
        ]
        
        found_any = False
        for encoding_name, encoded in encodings:
            offset = self.pds_data.find(encoded)
            if offset != -1:
                self.correlations.append({
                    'value': value,
                    'label': label,
                    'encoding': encoding_name,
                    'offset': offset,
                    'hex': encoded.hex()
                })
                found_any = True
        
        return found_any
    
    def find_strings(self):
        """Find string values in binary"""
        strings_to_find = [self.style.name]
        
        for piece in self.style.pieces:
            strings_to_find.extend([piece.code, piece.name])
            if piece.description:
                strings_to_find.append(piece.description)
        
        for s in strings_to_find:
            if not s:
                continue
            
            encodings = [
                ('ascii', s.encode('ascii', errors='ignore')),
                ('utf8', s.encode('utf-8')),
                ('utf16_le', s.encode('utf-16-le')),
                ('utf16_be', s.encode('utf-16-be')),
            ]
            
            found_any = False
            for encoding_name, encoded in encodings:
                if not encoded:
                    continue
                offset = self.pds_data.find(encoded)
                if offset != -1:
                    self.correlations.append({
                        'value': s[:50],  # Truncate long strings
                        'label': 'string',
                        'encoding': encoding_name,
                        'offset': offset,
                        'length': len(encoded)
                    })
                    found_any = True
            
            if not found_any:
                self.failed_searches.append(f"string: {s[:30]}")
    
    def find_piece_counts(self):
        """Search for piece count values in header"""
        count = self.style.num_pieces
        
        # Try various integer encodings
        encodings = [
            ('uint32_le', struct.pack('<I', count)),
            ('uint32_be', struct.pack('>I', count)),
            ('uint16_le', struct.pack('<H', count)),
            ('uint16_be', struct.pack('>H', count)),
        ]
        
        for encoding_name, encoded in encodings:
            offset = 0
            while True:
                offset = self.pds_data.find(encoded, offset)
                if offset == -1:
                    break
                self.correlations.append({
                    'value': count,
                    'label': 'num_pieces',
                    'encoding': encoding_name,
                    'offset': offset,
                    'hex': encoded.hex()
                })
                offset += 1
    
    def generate_offset_map(self):
        """Generate visual offset map of correlations"""
        sorted_corr = sorted(self.correlations, key=lambda x: x['offset'])
        
        offset_ranges = {}
        for corr in sorted_corr:
            range_key = corr['offset'] // 512  # 512-byte ranges
            if range_key not in offset_ranges:
                offset_ranges[range_key] = []
            offset_ranges[range_key].append(corr)
        
        return offset_ranges
    
    def export_report(self, output_path):
        """Export comprehensive correlation report"""
        report = {
            'file': str(self.pds_path),
            'style_name': self.style.name,
            'num_pieces': self.style.num_pieces,
            'total_correlations': len(self.correlations),
            'failed_searches': self.failed_searches[:50],
            'offset_map': self.generate_offset_map(),
            'correlations_by_type': self._group_by_type(),
            'correlations': sorted(self.correlations, key=lambda x: x['offset'])[:200]
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def _group_by_type(self):
        """Group correlations by data type"""
        groups = {}
        for corr in self.correlations:
            enc = corr['encoding']
            if enc not in groups:
                groups[enc] = []
            groups[enc].append(corr)
        
        # Summarize
        summary = {}
        for enc, corrs in groups.items():
            summary[enc] = {
                'count': len(corrs),
                'offsets': [c['offset'] for c in corrs[:10]]  # First 10
            }
        return summary
    
    def print_summary(self):
        """Print human-readable summary"""
        print(f"\n{'='*60}")
        print(f"Correlation Summary for: {self.style.name}")
        print(f"{'='*60}")
        print(f"Total correlations found: {len(self.correlations)}")
        print(f"Failed searches: {len(self.failed_searches)}")
        
        by_type = self._group_by_type()
        print(f"\nBy encoding type:")
        for enc, info in sorted(by_type.items(), key=lambda x: -x[1]['count']):
            print(f"  {enc}: {info['count']} occurrences")
        
        if self.failed_searches:
            print(f"\nFailed searches (first 10):")
            for fail in self.failed_searches[:10]:
                print(f"  - {fail}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python pdml_correlator.py <pds_file> <pdml_file> <output_json>")
        sys.exit(1)
    
    correlator = PDMLBinaryCorrelator(sys.argv[1], sys.argv[2])
    
    print("Searching for coordinates...")
    correlator.find_coordinates()
    
    print("Searching for strings...")
    correlator.find_strings()
    
    print("Searching for piece counts...")
    correlator.find_piece_counts()
    
    correlator.print_summary()
    
    report = correlator.export_report(sys.argv[3])
    print(f"\nReport saved to: {sys.argv[3]}")
