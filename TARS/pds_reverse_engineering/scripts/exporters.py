#!/usr/bin/env python3
"""
PDS to Open Format Exporters
Convert PDS files to SVG, DXF, and JSON
"""
import xml.etree.ElementTree as ET
from pathlib import Path
import json
from pds_parser import PDSParser


class PDSExporter:
    """Export PDS data to various open formats"""
    
    def __init__(self, pds_path: str):
        self.parser = PDSParser(pds_path)
        self.pds_data = self.parser.parse()
    
    def to_svg(self, output_path: str, scale: float = 1.0):
        """Export to SVG format"""
        # Create SVG root
        svg = ET.Element('svg')
        svg.set('xmlns', 'http://www.w3.org/2000/svg')
        svg.set('version', '1.1')
        
        # Calculate bounds
        all_points = []
        for piece in self.pds_data.pieces:
            all_points.extend(piece.contour.points)
        
        if all_points:
            min_x = min(p.x for p in all_points)
            max_x = max(p.x for p in all_points)
            min_y = min(p.y for p in all_points)
            max_y = max(p.y for p in all_points)
            
            # Add padding
            padding = 50
            width = (max_x - min_x + 2 * padding) * scale
            height = (max_y - min_y + 2 * padding) * scale
            
            svg.set('width', f"{width}mm")
            svg.set('height', f"{height}mm")
            svg.set('viewBox', f"{min_x - padding} {min_y - padding} {max_x - min_x + 2*padding} {max_y - min_y + 2*padding}")
        
        # Add pieces as groups
        for piece in self.pds_data.pieces:
            g = ET.SubElement(svg, 'g')
            g.set('id', piece.code)
            g.set('data-name', piece.name)
            
            # Create contour path
            if piece.contour.points:
                path_data = f"M {piece.contour.points[0].x} {piece.contour.points[0].y}"
                for point in piece.contour.points[1:]:
                    path_data += f" L {point.x} {point.y}"
                path_data += " Z"
                
                path = ET.SubElement(g, 'path')
                path.set('d', path_data)
                path.set('fill', 'none')
                path.set('stroke', 'black')
                path.set('stroke-width', '0.5')
                path.set('stroke-linejoin', 'round')
            
            # Add internal lines
            for internal in piece.internals:
                if internal.points:
                    path_data = f"M {internal.points[0].x} {internal.points[0].y}"
                    for point in internal.points[1:]:
                        path_data += f" L {point.x} {point.y}"
                    
                    path = ET.SubElement(g, 'path')
                    path.set('d', path_data)
                    path.set('fill', 'none')
                    path.set('stroke', 'gray')
                    path.set('stroke-width', '0.3')
                    path.set('stroke-dasharray', '2,2')
            
            # Add notches
            for notch in piece.notches:
                circle = ET.SubElement(g, 'circle')
                circle.set('cx', str(notch.position.x))
                circle.set('cy', str(notch.position.y))
                circle.set('r', '2')
                circle.set('fill', 'red')
                circle.set('stroke', 'none')
            
            # Add drill holes
            for hole in piece.drill_holes:
                circle = ET.SubElement(g, 'circle')
                circle.set('cx', str(hole.position.x))
                circle.set('cy', str(hole.position.y))
                circle.set('r', str(hole.diameter / 2))
                circle.set('fill', 'none')
                circle.set('stroke', 'blue')
                circle.set('stroke-width', '0.3')
            
            # Add piece label
            if piece.contour.points:
                centroid_x = sum(p.x for p in piece.contour.points) / len(piece.contour.points)
                centroid_y = sum(p.y for p in piece.contour.points) / len(piece.contour.points)
                
                text = ET.SubElement(g, 'text')
                text.set('x', str(centroid_x))
                text.set('y', str(centroid_y))
                text.set('font-size', '5')
                text.set('text-anchor', 'middle')
                text.text = piece.code
        
        # Write SVG
        tree = ET.ElementTree(svg)
        ET.indent(tree, space='  ')
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        
        return output_path
    
    def to_dxf(self, output_path: str):
        """Export to AutoCAD DXF format (R12 compatible)"""
        lines = [
            '0', 'SECTION',
            '2', 'HEADER',
            '9', '$ACADVER',
            '1', 'AC1009',
            '0', 'ENDSEC',
            '0', 'SECTION',
            '2', 'TABLES',
            '0', 'TABLE',
            '2', 'LAYER',
            '70', str(len(self.pds_data.pieces) + 2),
        ]
        
        # Add layer definitions
        layer_names = ['CONTOUR', 'INTERNALS', 'NOTCHES', 'DRILL_HOLES']
        for i, name in enumerate(layer_names):
            lines.extend([
                '0', 'LAYER',
                '2', name,
                '70', '0',
                '62', str(i + 1),
                '6', 'CONTINUOUS'
            ])
        
        lines.extend(['0', 'ENDTAB', '0', 'ENDSEC'])
        
        # Entities section
        lines.extend(['0', 'SECTION', '2', 'ENTITIES'])
        
        for piece in self.pds_data.pieces:
            layer = f"PIECE_{piece.code}"
            
            # Add contour as polyline
            if piece.contour.points:
                lines.extend([
                    '0', 'POLYLINE',
                    '8', layer,
                    '66', '1',
                    '70', '1'  # Closed
                ])
                
                for point in piece.contour.points:
                    lines.extend([
                        '0', 'VERTEX',
                        '8', layer,
                        '10', str(point.x),
                        '20', str(point.y),
                        '30', '0'
                    ])
                
                lines.extend(['0', 'SEQEND'])
            
            # Add internal lines
            for internal in piece.internals:
                if internal.points:
                    lines.extend([
                        '0', 'POLYLINE',
                        '8', f"{layer}_INTERNAL",
                        '66', '1',
                        '70', '0'  # Open
                    ])
                    
                    for point in internal.points:
                        lines.extend([
                            '0', 'VERTEX',
                            '8', f"{layer}_INTERNAL",
                            '10', str(point.x),
                            '20', str(point.y),
                            '30', '0'
                        ])
                    
                    lines.extend(['0', 'SEQEND'])
            
            # Add notches as points
            for notch in piece.notches:
                lines.extend([
                    '0', 'POINT',
                    '8', f"{layer}_NOTCHES",
                    '10', str(notch.position.x),
                    '20', str(notch.position.y),
                    '30', '0'
                ])
            
            # Add drill holes as circles
            for hole in piece.drill_holes:
                lines.extend([
                    '0', 'CIRCLE',
                    '8', f"{layer}_HOLES",
                    '10', str(hole.position.x),
                    '20', str(hole.position.y),
                    '30', '0',
                    '40', str(hole.diameter / 2)
                ])
        
        lines.extend(['0', 'ENDSEC', '0', 'EOF'])
        
        Path(output_path).write_text('\n'.join(lines))
        return output_path
    
    def to_json(self, output_path: str):
        """Export to comprehensive JSON"""
        data = {
            'header': {
                'version': f"{self.pds_data.header.version_major}.{self.pds_data.header.version_minor}",
                'num_pieces': self.pds_data.header.num_pieces,
                'num_sizes': self.pds_data.header.num_sizes,
                'units': {
                    'length': self.parser.LENGTH_UNITS.get(self.pds_data.header.units_length, 'unknown'),
                    'area': self.parser.AREA_UNITS.get(self.pds_data.header.units_area, 'unknown')
                }
            },
            'metadata': {
                'style_name': self.pds_data.metadata.style_name,
                'creation_date': self.pds_data.metadata.creation_date,
                'modification_date': self.pds_data.metadata.modification_date
            },
            'sizes': [
                {
                    'name': s.name,
                    'measurements': [{'name': m.name, 'value': m.value} for m in s.measurements],
                    'grading_rules': [
                        {'point_id': r.point_id, 'delta_x': r.delta_x, 'delta_y': r.delta_y}
                        for r in s.grading_rules
                    ]
                } for s in self.pds_data.sizes
            ],
            'pieces': [
                {
                    'code': p.code,
                    'name': p.name,
                    'description': p.description,
                    'seam_allowance': p.seam_allowance,
                    'contour': {
                        'points': [{'x': pt.x, 'y': pt.y, 'type': pt.point_type} for pt in p.contour.points]
                    },
                    'internals': [
                        {
                            'points': [{'x': pt.x, 'y': pt.y} for pt in il.points],
                            'type': il.line_type
                        } for il in p.internals
                    ],
                    'notches': [
                        {
                            'x': n.position.x,
                            'y': n.position.y,
                            'type': n.notch_type,
                            'depth': n.depth,
                            'width': n.width
                        } for n in p.notches
                    ],
                    'drill_holes': [
                        {
                            'x': h.position.x,
                            'y': h.position.y,
                            'diameter': h.diameter
                        } for h in p.drill_holes
                    ]
                } for p in self.pds_data.pieces
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python exporters.py <pds_file> <output_file> <format>")
        print("  format: svg, dxf, or json")
        sys.exit(1)
    
    pds_file = sys.argv[1]
    output_file = sys.argv[2]
    fmt = sys.argv[3].lower()
    
    exporter = PDSExporter(pds_file)
    
    if fmt == 'svg':
        exporter.to_svg(output_file)
    elif fmt == 'dxf':
        exporter.to_dxf(output_file)
    elif fmt == 'json':
        exporter.to_json(output_file)
    else:
        print(f"Unknown format: {fmt}")
        sys.exit(1)
    
    print(f"Exported to: {output_file}")
