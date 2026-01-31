#!/usr/bin/env python3
"""
PDS File Parser - Reference Implementation
Parses Optitex PDS files based on reverse-engineered specification
"""
import struct
from dataclasses import dataclass
from typing import List, Dict, Optional, BinaryIO
from pathlib import Path
import json


@dataclass
class PDSPoint:
    x: float
    y: float
    point_type: int = 0
    flags: int = 0


@dataclass
class PDSNotch:
    position: PDSPoint
    notch_type: int
    depth: float
    width: float
    angle: float


@dataclass
class PDSDrillHole:
    position: PDSPoint
    diameter: float
    hole_type: int


@dataclass
class PDSInternalLine:
    points: List[PDSPoint]
    line_type: int


@dataclass
class PDSContour:
    points: List[PDSPoint]


@dataclass
class PDSPiece:
    code: str
    name: str
    description: str
    contour: PDSContour
    internals: List[PDSInternalLine]
    notches: List[PDSNotch]
    drill_holes: List[PDSDrillHole]
    seam_allowance: float
    buffer_type: int
    flags: int


@dataclass
class PDSGradingRule:
    point_id: int
    delta_x: float
    delta_y: float
    flags: int


@dataclass
class PDSMeasurement:
    name: str
    value: float


@dataclass
class PDSSize:
    name: str
    measurements: List[PDSMeasurement]
    grading_rules: List[PDSGradingRule]


@dataclass
class PDSHeader:
    magic: bytes
    version_major: int
    version_minor: int
    file_flags: int
    header_size: int
    num_pieces: int
    num_sizes: int
    num_notches: int
    metadata_size: int
    units_length: int
    units_area: int


@dataclass
class PDSMetadata:
    style_name: str
    file_path: str
    creation_date: int
    modification_date: int
    xml_header: str


@dataclass
class PDSFile:
    header: PDSHeader
    metadata: PDSMetadata
    sizes: List[PDSSize]
    pieces: List[PDSPiece]


class PDSParser:
    """Complete PDS file parser - based on reverse-engineered spec"""
    
    # Unit mappings
    LENGTH_UNITS = {0: 'mm', 1: 'cm', 2: 'in', 3: 'pt'}
    AREA_UNITS = {0: 'mm2', 1: 'cm2', 2: 'in2'}
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.file: Optional[BinaryIO] = None
        self.pds_file: Optional[PDSFile] = None
        self.parse_errors = []
        
    def parse(self) -> PDSFile:
        """Parse the complete PDS file"""
        with open(self.file_path, 'rb') as f:
            self.file = f
            
            try:
                header = self._parse_header()
                metadata = self._parse_metadata(header.metadata_size)
                sizes = self._parse_sizes(header.num_sizes)
                pieces = self._parse_pieces(header.num_pieces)
                
                self.pds_file = PDSFile(
                    header=header,
                    metadata=metadata,
                    sizes=sizes,
                    pieces=pieces
                )
            except Exception as e:
                self.parse_errors.append(str(e))
                raise
        
        return self.pds_file
    
    def _parse_header(self) -> PDSHeader:
        """Parse file header (first ~44 bytes)"""
        return PDSHeader(
            magic=self._read_bytes(4),
            version_major=self._read_u2(),
            version_minor=self._read_u2(),
            file_flags=self._read_u4(),
            header_size=self._read_u4(),
            num_pieces=self._read_u4(),
            num_sizes=self._read_u4(),
            num_notches=self._read_u4(),
            metadata_size=self._read_u4(),
            units_length=self._read_u1(),
            units_area=self._read_u1()
        )
    
    def _parse_metadata(self, size: int) -> PDSMetadata:
        """Parse metadata section"""
        start_pos = self.file.tell()
        
        style_name = self._read_string_u1()
        file_path = self._read_string_u1()
        creation_date = self._read_u8()
        modification_date = self._read_u8()
        xml_header = self._read_string_u4()
        
        # Skip to end of metadata section
        self.file.seek(start_pos + size)
        
        return PDSMetadata(
            style_name=style_name,
            file_path=file_path,
            creation_date=creation_date,
            modification_date=modification_date,
            xml_header=xml_header
        )
    
    def _parse_sizes(self, num_sizes: int) -> List[PDSSize]:
        """Parse size/grading information"""
        sizes = []
        
        for _ in range(num_sizes):
            name = self._read_string_u1()
            
            # Read measurements
            num_measurements = self._read_u4()
            measurements = []
            for _ in range(num_measurements):
                meas_name = self._read_string_u1()
                meas_value = self._read_f4()
                measurements.append(PDSMeasurement(meas_name, meas_value))
            
            # Read grading rules
            num_rules = self._read_u4()
            rules = []
            for _ in range(num_rules):
                rules.append(PDSGradingRule(
                    point_id=self._read_u4(),
                    delta_x=self._read_f4(),
                    delta_y=self._read_f4(),
                    flags=self._read_u2()
                ))
            
            sizes.append(PDSSize(name, measurements, rules))
        
        return sizes
    
    def _parse_pieces(self, num_pieces: int) -> List[PDSPiece]:
        """Parse all pattern pieces"""
        pieces = []
        
        for _ in range(num_pieces):
            try:
                piece = self._parse_piece()
                pieces.append(piece)
            except Exception as e:
                self.parse_errors.append(f"Error parsing piece: {e}")
                # Try to continue with next piece
        
        return pieces
    
    def _parse_piece(self) -> PDSPiece:
        """Parse single piece"""
        code = self._read_string_u1()
        name = self._read_string_u1()
        description = self._read_string_u2()
        
        num_contour_points = self._read_u4()
        num_internals = self._read_u4()
        num_notches = self._read_u4()
        num_drill_holes = self._read_u4()
        
        seam_allowance = self._read_f4()
        buffer_type = self._read_u1()
        flags = self._read_u2()
        
        # Parse contour
        contour = self._parse_contour(num_contour_points)
        
        # Parse internals
        internals = []
        for _ in range(num_internals):
            internals.append(self._parse_internal_line())
        
        # Parse notches
        notches = []
        for _ in range(num_notches):
            notches.append(self._parse_notch())
        
        # Parse drill holes
        drill_holes = []
        for _ in range(num_drill_holes):
            drill_holes.append(self._parse_drill_hole())
        
        return PDSPiece(
            code=code,
            name=name,
            description=description,
            contour=contour,
            internals=internals,
            notches=notches,
            drill_holes=drill_holes,
            seam_allowance=seam_allowance,
            buffer_type=buffer_type,
            flags=flags
        )
    
    def _parse_contour(self, num_points: int) -> PDSContour:
        """Parse contour points"""
        points = []
        for _ in range(num_points):
            points.append(self._parse_point())
        return PDSContour(points=points)
    
    def _parse_internal_line(self) -> PDSInternalLine:
        """Parse internal line"""
        num_points = self._read_u4()
        points = []
        for _ in range(num_points):
            points.append(self._parse_point())
        line_type = self._read_u1()
        return PDSInternalLine(points=points, line_type=line_type)
    
    def _parse_notch(self) -> PDSNotch:
        """Parse notch"""
        return PDSNotch(
            position=self._parse_point(),
            notch_type=self._read_u1(),
            depth=self._read_f4(),
            width=self._read_f4(),
            angle=self._read_f4()
        )
    
    def _parse_drill_hole(self) -> PDSDrillHole:
        """Parse drill hole"""
        return PDSDrillHole(
            position=self._parse_point(),
            diameter=self._read_f4(),
            hole_type=self._read_u1()
        )
    
    def _parse_point(self) -> PDSPoint:
        """Parse coordinate point"""
        return PDSPoint(
            x=self._read_f4(),
            y=self._read_f4(),
            point_type=self._read_u1(),
            flags=self._read_u1()
        )
    
    # Helper methods for reading binary data
    def _read_bytes(self, n: int) -> bytes:
        return self.file.read(n)
    
    def _read_u1(self) -> int:
        return struct.unpack('B', self.file.read(1))[0]
    
    def _read_u2(self) -> int:
        return struct.unpack('<H', self.file.read(2))[0]
    
    def _read_u4(self) -> int:
        return struct.unpack('<I', self.file.read(4))[0]
    
    def _read_u8(self) -> int:
        return struct.unpack('<Q', self.file.read(8))[0]
    
    def _read_f4(self) -> float:
        return struct.unpack('<f', self.file.read(4))[0]
    
    def _read_string_u1(self) -> str:
        """Read length-prefixed string (1-byte length)"""
        length = self._read_u1()
        if length == 0:
            return ''
        return self.file.read(length).decode('utf-8', errors='ignore')
    
    def _read_string_u2(self) -> str:
        """Read length-prefixed string (2-byte length)"""
        length = self._read_u2()
        if length == 0:
            return ''
        return self.file.read(length).decode('utf-8', errors='ignore')
    
    def _read_string_u4(self) -> str:
        """Read length-prefixed string (4-byte length)"""
        length = self._read_u4()
        if length == 0:
            return ''
        return self.file.read(length).decode('utf-8', errors='ignore')
    
    def export_to_json(self, output_path: str):
        """Export parsed data to JSON"""
        if not self.pds_file:
            self.parse()
        
        data = {
            'header': {
                'magic': self.pds_file.header.magic.hex(),
                'version': f"{self.pds_file.header.version_major}.{self.pds_file.header.version_minor}",
                'num_pieces': self.pds_file.header.num_pieces,
                'num_sizes': self.pds_file.header.num_sizes,
                'units_length': self.LENGTH_UNITS.get(self.pds_file.header.units_length, 'unknown'),
                'units_area': self.AREA_UNITS.get(self.pds_file.header.units_area, 'unknown')
            },
            'metadata': {
                'style_name': self.pds_file.metadata.style_name,
                'creation_date': self.pds_file.metadata.creation_date,
                'modification_date': self.pds_file.metadata.modification_date
            },
            'sizes': [
                {
                    'name': s.name,
                    'measurements': [{'name': m.name, 'value': m.value} for m in s.measurements],
                    'grading_rules': [
                        {'point_id': r.point_id, 'delta_x': r.delta_x, 'delta_y': r.delta_y}
                        for r in s.grading_rules
                    ]
                } for s in self.pds_file.sizes
            ],
            'pieces': [
                {
                    'code': p.code,
                    'name': p.name,
                    'description': p.description,
                    'seam_allowance': p.seam_allowance,
                    'contour_points': [{'x': pt.x, 'y': pt.y} for pt in p.contour.points],
                    'num_internals': len(p.internals),
                    'num_notches': len(p.notches),
                    'num_drill_holes': len(p.drill_holes)
                } for p in self.pds_file.pieces
            ],
            'parse_errors': self.parse_errors
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python pds_parser.py <pds_file> <output_json>")
        sys.exit(1)
    
    parser = PDSParser(sys.argv[1])
    try:
        pds_data = parser.parse()
        print(f"Successfully parsed: {sys.argv[1]}")
        print(f"  Pieces: {pds_data.header.num_pieces}")
        print(f"  Sizes: {pds_data.header.num_sizes}")
        print(f"  Units: {parser.LENGTH_UNITS.get(pds_data.header.units_length, 'unknown')}")
        
        parser.export_to_json(sys.argv[2])
        print(f"Exported to: {sys.argv[2]}")
    except Exception as e:
        print(f"Parse error: {e}")
        if parser.parse_errors:
            print("Errors:")
            for err in parser.parse_errors:
                print(f"  - {err}")
