# Expected Oracle Files

## PDS Exports (oracle/pds/)

| Input File | Expected Outputs |
|------------|------------------|
| Basic Tee_2D.PDS | Basic Tee_2D.pdml, Basic Tee_2D.dxf, (optional) Basic Tee_2D.rul |
| Light  Jacket_2D.PDS | Light  Jacket_2D.pdml, Light  Jacket_2D.dxf, (optional) Light  Jacket_2D.rul |
| Skinny Cargo_2D.PDS | Skinny Cargo_2D.pdml, Skinny Cargo_2D.dxf, (optional) Skinny Cargo_2D.rul |
| Skinny Trousers_2D.PDS | Skinny Trousers_2D.pdml, Skinny Trousers_2D.dxf, (optional) Skinny Trousers_2D.rul |

**Total Required: 8 files (4 pdml + 4 dxf)**
**Total Optional: 4 files (4 rul)**

## MRK Exports (oracle/mrk/)

| Input File | Expected Outputs |
|------------|------------------|
| Basic Pants.MRK | Basic Pants.dxf, Basic Pants.plt |
| Jacket Sloper.MRK | Jacket Sloper.dxf, Jacket Sloper.plt |
| Nest++Shirt_Result2.MRK | Nest++Shirt_Result2.dxf, Nest++Shirt_Result2.plt |
| Stripe Pants.MRK | Stripe Pants.dxf, Stripe Pants.plt |
| Stripe Pants_Result4.MRK | Stripe Pants_Result4.dxf, Stripe Pants_Result4.plt |

**Total Required: 10 files (5 dxf + 5 plt)**

## Grand Total
- **Required: 18 files**
- **Optional: 4 files (rul)**

## DXF Export Settings (ORACLE SPEC)
- Version: AutoCAD 2000
- Units: cm
- Scale: 1:1
- Includes: contours, seam allowances, notches, internal lines, grainlines, labels
- Curves: splines/beziers preserved
- Blocks: enabled
- Grading: included if available

## HPGL/PLT Export Settings
- Format: HPGL/2
- Scale: 1:1
- Includes: cut lines, notches, internals
