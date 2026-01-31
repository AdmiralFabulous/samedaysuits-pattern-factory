# PDS Reverse Engineering - Execution Log

**Started:** 2026-01-30
**Goal:** Build automated production pipeline: Customer measurements -> Plotter-ready output (62" cutter)

---

## Phase 0: Capture Oracle Baseline

**Started:** 2026-01-30 [NOW]
**Status:** IN PROGRESS

### Objective
Run Optitex batch exports to get PDML + DXF files as ground truth for reverse engineering.

### Actions
- [ ] Check existing batch scripts
- [ ] Verify Optitex installation
- [ ] Run batch exports
- [ ] Verify output files

### Log

**2026-01-30 22:XX** - Phase 0 Started

**Findings:**
- Optitex O/25 is installed at `C:\Program Files\Optitex\Optitex 25\App\PDS.exe`
- Batch scripts exist for all 9 files (4 PDS + 5 MRK)
- Existing oracle files:
  - `Basic Tee_2D.PDML` (250 KB) - COMPLETE
  - `Basic Tee_2D.dxf` (352 KB) - COMPLETE
  - `Light Jacket_2D.PDML` (130 KB) - PARTIAL (no DXF)

**Challenge #1: Optitex Batch Mode**
- Running `PDS.exe /BATCH script.txt` returns immediately with no output
- Optitex may be launching GUI window instead of running headless
- The `/s` silent flag mentioned in documentation may not work in this version
- **Workaround:** Proceed with existing oracle files (Basic Tee has both PDML + DXF)

**Lesson Learned:**
- Optitex batch automation requires manual verification
- For production, consider GUI automation (Computer Use Agent) as fallback
- Or require user to manually export oracle files

**Decision:** Proceed to Phase 1 with existing Basic Tee oracle files

---

## Phase 1: Extract Point Names from PDML

**Started:** 2026-01-30
**Status:** COMPLETE

### Objective
Parse PDML files to extract piece definitions and point names for TheBlackbox BTF automation.

### Actions
- [x] Create extraction script `extract_oracle_data.py`
- [x] Extract XML from PDML binary file (starts at offset 2572)
- [x] Parse DXF file to get actual contour coordinates
- [x] Correlate PDML metadata with DXF geometry
- [x] Output combined JSON for reverse engineering

### Results

**MILESTONE: Successfully extracted oracle data from Basic Tee!**

| Piece | Points | Base Size (Small) | Area | Perimeter |
|-------|--------|-------------------|------|-----------|
| Front | 1,712 | 27.77 x 77.50 cm | 0.3692 sq.m | 268.39 cm |
| Back | 1,534 | 27.78 x 78.72 cm | 0.3876 sq.m | 262.99 cm |
| Right Sleeve | 772 | 25.92 x 42.23 cm | 0.0798 sq.m | 115.32 cm |
| Neck Binding | 268 | 24.04 x 3.82 cm | 0.0183 sq.m | 103.76 cm |
| **TOTAL** | **4,286** | - | - | - |

**Key Findings:**
- PDML is a hybrid binary/XML format
- Binary header + JPEG thumbnail + XML metadata + binary footer
- XML contains piece metadata but NOT actual contour coordinates
- Actual geometry is in the DXF oracle file
- DXF has 16 contours per piece (2 per size = 8 sizes x 2)

**Output Files:**
- `DS-speciale/oracle/extracted/Basic Tee_2D_oracle.json` (513 KB)
- Contains complete piece definitions with geometry

**Challenge #2: DXF Has All Sizes**
- DXF export contains all 8 sizes overlaid
- Need to separate by size for individual pattern extraction
- Current extraction captures all points together

**Lesson Learned:**
- PDML is for metadata only, not geometry
- DXF oracle is the real "ground truth" for coordinates
- Need to match DXF coordinates to binary PDS for decoding

---

## Phase 2: Decode Binary Geometry

**Started:** 2026-01-30
**Status:** IN PROGRESS

### Objective
Use DXF coordinates as "known plaintext" to find matching values in PDS binary.

### Actions
- [x] Create binary_correlator.py - search for float32/float64 matches
- [x] Create deep_binary_analysis.py - analyze zlib sections
- [x] Run full DS-speciale pipeline on all input files

### Key Discovery: SVG Geometry in Embedded XML!

**BREAKTHROUGH:** The embedded XML in PDS files DOES contain SVG geometry!
- Each piece has polygon/path elements with actual coordinates
- Coordinates are in a view-space (scaled/offset from real cm)
- SVG viewBox: "0 0 15694 8998" - need to convert to cm

**Pipeline Test Results:**
```
Total files: 9 (4 PDS + 5 MRK)
Successful: 9
Exports: 9 DXF + 5 PLT
```

**Challenge #3: Pipeline Outputs Bounding Boxes**
- Current pipeline extracts XML metadata but NOT SVG contours
- DXF output contains piece bounding boxes, not actual shapes
- Need to integrate SVG geometry extraction into pipeline

**Challenge #4: Coordinate Transformation**
- SVG coordinates are in viewBox space (integer pixels)
- Need to transform to real-world cm coordinates
- May need scale factor from GEOM_INFO or viewBox attributes

### Binary Analysis Results
- Float32 matches found for some coordinate-like values
- 7 zlib compressed sections detected in PDS binary
- Float arrays found in raw binary (many are 0-filled)
- Direct coordinate matching failed - values are likely transformed

**Lesson Learned:**
- The SVG in embedded XML IS the geometry source
- Don't need to decode binary - just parse SVG!
- Need to understand coordinate transformation

---

## Phase 3: Integrate SVG Geometry Extraction

**Started:** 2026-01-30
**Status:** COMPLETE

### Objective
Update pipeline to extract actual contour geometry from embedded SVG.

### Actions
- [x] Create `production_pipeline.py` - end-to-end PDS -> HPGL/PLT
- [x] Extract GEOM_INFO for real piece dimensions
- [x] Parse SVG polygons and paths for contour geometry
- [x] Transform SVG coordinates to real-world cm using piece dimensions
- [x] Generate HPGL for 62" cutter

### Results

**MILESTONE: Production Pipeline Working!**

| Pattern | Pieces | Layout (cm) | Fits 62"? |
|---------|--------|-------------|-----------|
| Basic Tee | 4 | 105.49 x 82.47 | YES |
| Light Jacket | 11 | 330.81 x 63.56 | Needs nesting |
| Skinny Cargo | 20 | TBD | TBD |
| Skinny Trousers | 19 | TBD | TBD |

**Key Files Created:**
- `production_pipeline.py` - Main production pipeline
- `DS-speciale/out/production_62inch/*.plt` - HPGL output files
- `DS-speciale/out/production_62inch/*_metadata.json` - Piece metadata

### How the Pipeline Works:

```
PDS File
    |
    v
[1] Extract embedded XML
    |
    v
[2] Parse GEOM_INFO for piece dimensions
    |
    v
[3] Parse SVG polygons/paths for contours
    |
    v
[4] Transform to real-world cm coordinates
    |
    v
[5] Generate HPGL/PLT for 62" cutter
```

### Coordinate Transformation

The SVG is a preview at reduced scale. We calculate:
```
scale_x = total_layout_width_cm / viewbox_width
scale_y = total_layout_height_cm / viewbox_height
```

Where `total_layout_width_cm` comes from summing GEOM_INFO `SIZE_X` values.

### Challenge #5: Nesting Required

The SVG contains pieces laid out in a single row. For production:
- Need to re-nest pieces for optimal fabric usage
- 62" cutter width = 157.48 cm
- Some patterns exceed this (e.g., Light Jacket 330 cm wide needs folding/nesting)

---

---

## Phase 4: Nesting Engine

**Started:** 2026-01-30
**Status:** COMPLETE

### Objective
Implement bin-packing algorithm to nest pattern pieces on 62" (157.48 cm) fabric width.

### Actions
- [x] Create `nesting_engine.py` with shelf-based bin packing
- [x] Implement rotation support (0, 90, 180, 270 degrees)
- [x] Add coordinate normalization for proper positioning
- [x] Integrate nesting into `production_pipeline.py`
- [x] Filter SVG to extract only cutting contours (skip background, grainlines)
- [x] Fix bug: ensure points are normalized to origin for all rotations

### Results

**MILESTONE: Nesting Engine Working!**

| Pattern | Original Layout | Nested Layout | Utilization | Status |
|---------|----------------|---------------|-------------|--------|
| Basic Tee | 104 x 77 cm | N/A (fits) | - | OK |
| Light Jacket | 328 x 63 cm | 151 x 126 cm | 34.9% | NESTED |
| Skinny Cargo | 332 x 59 cm | 115 x 144 cm | 44.0% | NESTED |
| Skinny Trousers | 325 x 103 cm | 134 x 263 cm | 60.4% | NESTED |

### Algorithm Details

**Shelf-Based Bin Packing:**
1. Sort pieces by height (largest first)
2. Place each piece on lowest available shelf
3. If piece doesn't fit on any shelf, create new shelf
4. Try 0, 90, 180, 270 degree rotations to minimize width

**Key Improvements Made:**
- Filter SVG to extract only piece outline polygons (colored fills)
- Skip background rectangles (#C0C0C0) and internal details (<g> groups)
- Fixed normalization bug: ensure all points start at origin before positioning

### Files Created
- `nesting_engine.py` - Standalone nesting engine with bin-packing algorithm

---

## Summary of Milestones

| Phase | Status | Key Achievement |
|-------|--------|-----------------|
| Phase 0 | PARTIAL | Oracle files captured (Basic Tee complete) |
| Phase 1 | COMPLETE | Extracted 4,286 contour points from oracle |
| Phase 2 | COMPLETE | Found SVG geometry in embedded XML |
| Phase 3 | COMPLETE | Production pipeline generating HPGL/PLT |
| Phase 4 | COMPLETE | Nesting engine for 62" fabric width |
| Phase 5 | COMPLETE | SameDaySuits Production API |
| Phase 6 | COMPLETE | Pattern Scaling from Measurements |
| Phase 7 | COMPLETE | Cutter Queue / Watch Folder |
| Phase 8 | COMPLETE | Graded Size Extraction from PDS |
| Phase 9 | COMPLETE | Unified CLI (sds_cli.py) |

## Lessons Learned

1. **Optitex batch mode is unreliable** - May launch GUI instead of headless
2. **PDML contains metadata, not geometry** - DXF is the real oracle
3. **SVG in embedded XML IS the geometry** - No need to decode binary!
4. **GEOM_INFO provides real dimensions** - Use for coordinate scaling
5. **DS-speciale had working scripts** - Should have checked existing code first

---

## Phase 5: SameDaySuits Production API

**Started:** 2026-01-30
**Status:** COMPLETE

### Objective
Create unified API that bridges TheBlackbox (measurements) and PDS pipeline (patterns).

### Actions
- [x] Analyze TheBlackbox architecture (pipeline.py, workflow.py)
- [x] Identify integration points (measurements -> template -> nesting -> cutter)
- [x] Create `samedaysuits_api.py` - unified production API
- [x] Implement CLI for single orders and batch processing
- [x] Test with sample orders

### Results

**MILESTONE: Production API Working!**

**Features:**
- Order processing with customer measurements
- Template selection by garment type (tee, jacket, trousers, cargo)
- Automatic nesting for 62" fabric
- HPGL/PLT output with full metadata
- Batch processing from JSON files
- CLI interface

**Test Results:**
```
Batch complete: 3/3 successful
Total fabric needed: 457.0 cm

ORD-BATCH-001 (tee):      68.9 cm fabric, 54.0% utilization
ORD-BATCH-002 (trousers): 262.6 cm fabric, 60.4% utilization
ORD-BATCH-003 (jacket):   125.6 cm fabric, 34.9% utilization
```

### CLI Usage

```bash
# List templates
python samedaysuits_api.py --list-templates

# Process single order
python samedaysuits_api.py --order ORD-001 --garment jacket \
    --chest 102 --waist 88 --hip 100

# Batch process from JSON
python samedaysuits_api.py --json orders.json
```

### API Usage

```python
from samedaysuits_api import SameDaySuitsAPI, Order, GarmentType, FitType, CustomerMeasurements

api = SameDaySuitsAPI()

order = Order(
    order_id="ORD-001",
    customer_id="CUST-123",
    garment_type=GarmentType.JACKET,
    fit_type=FitType.REGULAR,
    measurements=CustomerMeasurements(
        chest_cm=102,
        waist_cm=88,
        hip_cm=100,
    )
)

result = api.process_order(order)

if result.success:
    print(f"PLT: {result.plt_file}")
    print(f"Fabric: {result.fabric_length_cm} cm")
```

---

---

## Phase 6: Pattern Scaling from Measurements

**Started:** 2026-01-30
**Status:** COMPLETE

### Objective
Scale patterns based on customer body measurements.

### Actions
- [x] Create `pattern_scaler.py` with size charts and scaling logic
- [x] Implement size selection based on primary measurement
- [x] Calculate X/Y scale factors from measurements
- [x] Integrate scaling into production API
- [x] Test with different customer sizes

### Results

**Size Selection:**
- Maps customer measurements to standard sizes (XS-4XL)
- Uses chest for tops, hip for bottoms
- Calculates scale factors from size chart

**Test Results:**
```
Customer (small): chest=88 -> Base XS, Scale X=1.023
Customer (large): chest=120 -> Base 3XL, Scale X=1.008
```

---

## Phase 7: Cutter Queue / Watch Folder

**Started:** 2026-01-30
**Status:** COMPLETE

### Objective
Manage queue of jobs for the 62" plotter/cutter.

### Actions
- [x] Create `cutter_queue.py` with queue management
- [x] Implement priority system (Rush/High/Normal/Low)
- [x] Add watch folder monitoring for new PLT files
- [x] Add spool directory for cutter
- [x] Persist queue state to JSON

### Features

**Queue Manager:**
- Priority-based job ordering
- Status tracking (pending/queued/cutting/complete/error)
- Fabric length and time estimates
- State persistence across restarts

**CLI Commands:**
```bash
python cutter_queue.py status     # Show queue status
python cutter_queue.py list       # List all jobs
python cutter_queue.py add --order ORD-001 --plt file.plt --priority rush
python cutter_queue.py process    # Process next job
python cutter_queue.py watch      # Watch for new PLT files
```

---

---

## Phase 8: Graded Size Extraction

**Started:** 2026-01-30
**Status:** COMPLETE

### Objective
Extract graded size information (XS-4XL) directly from PDS files.

### Actions
- [x] Create `graded_size_extractor.py`
- [x] Parse PIECE/SIZE/GEOM_INFO elements from XML
- [x] Calculate per-piece scale factors between sizes
- [x] Add size selection based on measurements

### Results

**Size Information Extracted:**
- Basic Tee: 8 sizes (XS-4XL), 4 pieces
- Light Jacket: 3 sizes (S-L), 11 pieces
- Full GEOM_INFO: size_x, size_y, area, perimeter

---

## Phase 9: Unified CLI

**Started:** 2026-01-30
**Status:** COMPLETE

### Objective
Create single entry point CLI for all pipeline operations.

### Actions
- [x] Create `sds_cli.py` with subcommands
- [x] Implement: order, batch, queue, templates, sizes, test

### Usage

```bash
# Process order
python sds_cli.py order --id ORD-001 --garment tee --chest 102 --waist 88 --hip 100

# Batch process
python sds_cli.py batch orders.json

# Queue management
python sds_cli.py queue status
python sds_cli.py queue list
python sds_cli.py queue watch

# Show templates
python sds_cli.py templates

# Show graded sizes
python sds_cli.py sizes --template tee

# Run tests
python sds_cli.py test
```

---

## Session 2: Extended Pipeline (2026-01-30 Evening)

### Phase 10: Web API/Dashboard - COMPLETE

**File:** `web_api.py`

- FastAPI-based REST API
- Full HTML/CSS/JS dashboard with real-time updates
- WebSocket for live queue status
- Endpoints: `/orders`, `/queue/status`, `/queue/jobs`, `/templates`
- Run with: `python sds_cli.py serve --port 8000`

### Phase 11: Database Integration - COMPLETE

**File:** `database_integration.py`

- Supabase integration (local or cloud)
- Order polling from website database
- Automatic order sync service
- CLI: `sds db status`, `sds db sync`, `sds db watch`
- Schema SQL for creating orders table

### Phase 12: Seam Allowance & Internal Lines - COMPLETE

**File:** `internal_lines.py`

- Extracts internal construction details from PDS
- Layer types: CUTTING, SEAM, GRAIN, NOTCH, INTERNAL
- Multi-pen HPGL output (different colors per layer)
- CLI: `python internal_lines.py analyze file.PDS`

### Phase 13: Direct Graded Size Geometry - COMPLETE

**File:** `direct_size_generator.py`

- Generate patterns directly for any graded size (XS-4XL)
- Per-piece scale factors from GEOM_INFO
- CLI: `python direct_size_generator.py --size Large file.PDS`
- Batch generation: `--all` flag

### Phase 14: Improved Nesting - COMPLETE

**File:** `improved_nesting.py`

- Guillotine algorithm: 55-80% utilization
- Skyline algorithm: 60-88% utilization
- Best-of-all selector for optimal results
- **Results:**
  - Light Jacket: 34.9% -> **78.1%** (+43pp)
  - Skinny Trousers: 60.4% -> **87.7%** (+27pp)
  - Skinny Cargo: 44.0% -> **83.0%** (+39pp)

---

## What's Still Needed (Future Work)

1. ~~**Nesting for production**~~ - COMPLETE (Phase 4)
2. ~~**Integration with TheBlackbox**~~ - COMPLETE (Phase 5)
3. ~~**Pattern scaling**~~ - COMPLETE (Phase 6)
4. ~~**Cutter queue**~~ - COMPLETE (Phase 7)
5. ~~**Graded sizes**~~ - COMPLETE (Phase 8)
6. ~~**Unified CLI**~~ - COMPLETE (Phase 9)
7. ~~**Order database connection**~~ - COMPLETE (Phase 11)
8. ~~**Seam allowance handling**~~ - COMPLETE (Phase 12)
9. ~~**Web API / Dashboard**~~ - COMPLETE (Phase 10)
10. ~~**Improved nesting efficiency**~~ - COMPLETE (Phase 14)
11. **Production deployment** - Deploy to server with Supabase cloud
12. **TheBlackbox integration** - Connect measurement extraction to order API

---

## Files Created (All Sessions)

```
REVERSE-ENGINEER-PDS/
├── EXECUTION_LOG.md           # This file
├── sds_cli.py                 # Unified CLI for all operations
│
├── # Core Pipeline
├── production_pipeline.py     # PDS -> HPGL/PLT pipeline
├── nesting_engine.py          # Basic shelf-based bin-packing
├── improved_nesting.py        # Guillotine & Skyline algorithms (70%+ util)
├── samedaysuits_api.py        # Unified production API
│
├── # Scaling & Grading
├── pattern_scaler.py          # Size selection and scaling
├── graded_size_extractor.py   # Extract XS-4XL size info from PDS
├── direct_size_generator.py   # Generate patterns for specific sizes
│
├── # Internal Lines
├── internal_lines.py          # Seam allowance, grainlines, notches
│
├── # Infrastructure
├── cutter_queue.py            # Cutter job queue management
├── web_api.py                 # FastAPI REST API + Dashboard
├── database_integration.py    # Supabase integration
│
├── # Analysis (used during development)
├── extract_oracle_data.py     # PDML/DXF correlation
├── binary_correlator.py       # Float search in binary
├── deep_binary_analysis.py    # Zlib section analysis
│
├── test_orders.json           # Sample batch order file
│
└── DS-speciale/out/
    ├── production_62inch/     # Production outputs
    ├── graded_sizes/          # Per-size PLT files
    ├── orders/                # Order outputs from API
    └── cutter_spool/          # Cutter queue spool
```

## CLI Commands Summary

```bash
# Process orders
python sds_cli.py order --id ORD-001 --garment tee --chest 102 --waist 88 --hip 100
python sds_cli.py batch orders.json

# Queue management
python sds_cli.py queue status
python sds_cli.py queue list
python sds_cli.py queue watch

# Templates and sizes
python sds_cli.py templates
python sds_cli.py sizes --template tee

# Database integration
python sds_cli.py db status
python sds_cli.py db sync
python sds_cli.py db watch --interval 30

# Web server
python sds_cli.py serve --port 8000

# Tests
python sds_cli.py test

# Direct size generation
python direct_size_generator.py --size Large "file.PDS"
python direct_size_generator.py --all "file.PDS"

# Internal lines
python internal_lines.py analyze "file.PDS"
python internal_lines.py export "file.PDS" -o output.plt --seam --notches

# Nesting comparison
python improved_nesting.py --compare "file.PDS"
```

