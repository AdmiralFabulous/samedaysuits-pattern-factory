meta:
  id: optitex_pds
  title: Optitex Pattern Design System File
  file-extension: pds
  endian: le
  encoding: ascii

doc: |
  Optitex PDS file format for garment pattern design.
  This is a working specification based on reverse engineering analysis.
  Fields marked with TODO need verification with actual files.

seq:
  - id: header
    type: pds_header
    
  - id: metadata
    type: pds_metadata
    size: header.metadata_size
    
  - id: size_table
    type: pds_size_table
    repeat: expr
    repeat-expr: header.num_sizes
    
  - id: pieces
    type: pds_piece
    repeat: expr
    repeat-expr: header.num_pieces

types:
  pds_header:
    seq:
      - id: magic
        size: 4
        doc: TODO - Verify actual magic bytes
        
      - id: version_major
        type: u2
        
      - id: version_minor
        type: u2
        
      - id: file_flags
        type: u4
        doc: Bit flags for file properties
        
      - id: header_size
        type: u4
        doc: Total header size in bytes
        
      - id: num_pieces
        type: u4
        doc: Number of pattern pieces
        
      - id: num_sizes
        type: u4
        doc: Number of sizes/grades
        
      - id: num_notches
        type: u4
        doc: Total number of notches across all pieces
        
      - id: metadata_size
        type: u4
        doc: Size of metadata section following header
        
      - id: units_length
        type: u1
        enum: length_units
        
      - id: units_area
        type: u1
        enum: area_units
        
      - id: reserved
        size: 16
        doc: Padding/reserved for future use
        
  pds_metadata:
    seq:
      - id: style_name_len
        type: u1
        
      - id: style_name
        type: str
        size: style_name_len
        
      - id: file_path_len
        type: u1
        
      - id: file_path
        type: str
        size: file_path_len
        
      - id: creation_date
        type: u8
        doc: Unix timestamp
        
      - id: modification_date
        type: u8
        doc: Unix timestamp
        
      - id: xml_header_len
        type: u4
        
      - id: xml_header
        type: str
        size: xml_header_len
        doc: XML metadata for tech pack generation
        
  pds_size_table:
    seq:
      - id: size_name_len
        type: u1
        
      - id: size_name
        type: str
        size: size_name_len
        
      - id: num_measurements
        type: u4
        
      - id: measurements
        type: pds_measurement
        repeat: expr
        repeat-expr: num_measurements
        
      - id: num_grading_rules
        type: u4
        
      - id: grading_rules
        type: pds_grading_rule
        repeat: expr
        repeat-expr: num_grading_rules
        
  pds_measurement:
    seq:
      - id: name_len
        type: u1
        
      - id: name
        type: str
        size: name_len
        
      - id: value
        type: f4
        
  pds_grading_rule:
    seq:
      - id: point_id
        type: u4
        
      - id: delta_x
        type: f4
        doc: X offset for this size
        
      - id: delta_y
        type: f4
        doc: Y offset for this size
        
      - id: flags
        type: u2
        
  pds_piece:
    seq:
      - id: piece_header
        type: pds_piece_header
        
      - id: contour
        type: pds_contour
        
      - id: internals
        type: pds_internal_line
        repeat: expr
        repeat-expr: piece_header.num_internals
        
      - id: notches
        type: pds_notch
        repeat: expr
        repeat-expr: piece_header.num_notches
        
      - id: drill_holes
        type: pds_drill_hole
        repeat: expr
        repeat-expr: piece_header.num_drill_holes
        
  pds_piece_header:
    seq:
      - id: code_len
        type: u1
        
      - id: code
        type: str
        size: code_len
        
      - id: name_len
        type: u1
        
      - id: name
        type: str
        size: name_len
        
      - id: description_len
        type: u2
        
      - id: description
        type: str
        size: description_len
        
      - id: num_contour_points
        type: u4
        
      - id: num_internals
        type: u4
        
      - id: num_notches
        type: u4
        
      - id: num_drill_holes
        type: u4
        
      - id: seam_allowance
        type: f4
        
      - id: buffer_type
        type: u1
        
      - id: flags
        type: u2
        
  pds_contour:
    seq:
      - id: points
        type: pds_point
        repeat: expr
        repeat-expr: _parent.piece_header.num_contour_points
        
  pds_point:
    seq:
      - id: x
        type: f4
        
      - id: y
        type: f4
        
      - id: point_type
        type: u1
        enum: point_types
        doc: Corner, curve, symmetric, etc.
        
      - id: flags
        type: u1
        
  pds_internal_line:
    seq:
      - id: num_points
        type: u4
        
      - id: points
        type: pds_point
        repeat: expr
        repeat-expr: num_points
        
      - id: line_type
        type: u1
        
  pds_notch:
    seq:
      - id: position
        type: pds_point
        
      - id: notch_type
        type: u1
        enum: notch_types
        
      - id: depth
        type: f4
        
      - id: width
        type: f4
        
      - id: angle
        type: f4
        
  pds_drill_hole:
    seq:
      - id: position
        type: pds_point
        
      - id: diameter
        type: f4
        
      - id: hole_type
        type: u1

enums:
  length_units:
    0: millimeters
    1: centimeters
    2: inches
    3: points
    
  area_units:
    0: square_millimeters
    1: square_centimeters
    2: square_inches
    
  point_types:
    0: corner
    1: curve
    2: symmetric
    3: control_point
    
  notch_types:
    0: v_notch
    1: t_notch
    2: slit
    3: hole
