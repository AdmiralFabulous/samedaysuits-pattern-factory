# Optitex PDS File Format - Complete Reverse Engineering Master Plan

## Document Information
- **Project**: Optitex PDS Binary Format Reverse Engineering
- **Objective**: Complete documentation and parser implementation for the proprietary .pds file format
- **Approach**: Multi-vector analysis using static, dynamic, and AI-assisted methodologies
- **Estimated Duration**: 16-20 weeks (full-time equivalent)
- **Last Updated**: 2026-01-29

---

## Executive Overview

This master plan provides a comprehensive, systematic approach to reverse engineering the proprietary Optitex PDS (Pattern Design System) file format. The plan covers every tactic and method available, from basic static analysis to advanced AI-assisted techniques.

### Why This Approach?

1. **PDML as Rosetta Stone**: Optitex provides XML export (PDML) that serves as a readable reference
2. **Controlled Variation Method**: Systematically varying file contents to isolate data structures
3. **Multi-Vector Validation**: Using multiple independent analysis methods to confirm findings
4. **AI Augmentation**: Leveraging LLMs and ML for pattern recognition and code generation

---

## Phase Summary

| Phase | Duration | Key Deliverables | Priority |
|-------|----------|------------------|----------|
| 0: Environment Setup | 3-5 days | Tools installed, workspace ready | Critical |
| 1: Sample Acquisition | 1 week | 100+ controlled test files | Critical |
| 2: PDML Analysis | 1-2 weeks | XML schema mapped | High |
| 3: Binary Profiling | 1 week | Entropy maps, string tables | High |
| 4: Controlled Diff | 2 weeks | Structure hypotheses validated | Critical |
| 5: Header Analysis | 1 week | Header format documented | Critical |
| 6: Geometry Decoding | 2 weeks | Coordinate system understood | Critical |
| 7: Kaitai Spec | 1 week | Formal .ksy specification | High |
| 8: AI/ML Analysis | 1-2 weeks | Pattern recognition models | Medium |
| 9: Dynamic Analysis | 1-2 weeks | Runtime behavior captured | Medium |
| 10: Parser Dev | 2 weeks | Working Python parser | Critical |
| 11: Validation | 1 week | Test suite passing | Critical |
| 12: Converters | 1 week | SVG/DXF/JSON export | High |
| 13: Documentation | 1 week | Complete spec published | High |

**Total: 18-22 weeks**

---

## Core Methodology: The "Known Plaintext" Approach

Since we have access to Optitex and can generate PDML exports, we use a **known-plaintext attack** methodology:

1. Create PDS file with known values (e.g., square with corners at specific coordinates)
2. Export to PDML (gives us the "plaintext")
3. Search binary for those known values
4. Document the encoding (endianness, data type, offset)
5. Repeat with variations to confirm patterns

---

## Key Tools Required

### Tier 1: Essential
- 010 Editor (with binary templates)
- Python 3.10+ with scientific stack
- Optitex PDS 15+ installed
- Hex editor (HxD, ImHex, or Bless)

### Tier 2: Important
- Kaitai Struct compiler
- Binwalk (for embedded data detection)
- Diffoscope (for binary diffing)
- Process Monitor (Windows)

### Tier 3: Advanced
- Ghidra (if code analysis needed)
- TensorFlow/PyTorch (for ML pattern detection)
- API Monitor (for runtime analysis)

---

## Success Criteria

- [ ] Can parse header from any PDS file
- [ ] Can extract all piece geometry accurately
- [ ] Can decode grading rules for all sizes
- [ ] Can convert to SVG/DXF with <1% error
- [ ] Passes validation on 50+ sample files
- [ ] Complete format specification documented

---

## File Organization

```
pds_reverse_engineering/
├── docs/
│   ├── 00_MASTER_PLAN.md (this file)
│   ├── 01_SETUP_GUIDE.md
│   ├── 02_SAMPLE_GENERATION.md
│   ├── 03_PDML_ANALYSIS.md
│   ├── 04_BINARY_ANALYSIS.md
│   ├── 05_KAITAI_SPEC.md
│   ├── 06_AI_ML_METHODS.md
│   └── 07_PARSER_IMPLEMENTATION.md
├── scripts/
│   ├── binary_profiler.py
│   ├── pdml_parser.py
│   ├── diff_analyzer.py
│   ├── pattern_recognizer.py
│   ├── pds_parser.py
│   ├── validator.py
│   └── exporters.py
├── ksy/
│   └── optitex_pds.ksy
└── samples/
    ├── series_a_geometry/
    ├── series_b_pieces/
    ├── series_c_sizes/
    └── ...
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Format changes between versions | Test with multiple Optitex versions |
| Compressed/encrypted sections | Check entropy; try standard algorithms |
| Undocumented edge cases | Extensive fuzzing and validation |
| Legal concerns | Document as interoperability research |

---

## Next Steps

1. Review the detailed phase documents in `/docs/`
2. Set up environment per `01_SETUP_GUIDE.md`
3. Generate initial sample files
4. Begin with Phase 1 (PDML export and analysis)

---

*This is a living document. Update as findings emerge.*
