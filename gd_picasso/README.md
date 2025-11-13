# gd_picasso: PhIDO-Inspired YAML DSL Framework

## Overview

This framework implements a PhIDO-inspired approach where LLMs generate YAML DSL directly (not Python code) for photonic circuit design. The framework validates, corrects, optimizes, and verifies circuits before LLM testing.

## Workflow

```
LLM generates YAML DSL
    ↓
[Injection: Rich component examples in YAML format]
[Pilot: Error prevention rules]
    ↓
YAML Pilot Validation (syntax, structure, component names, ports, spacing)
    ↓
Auto-Corrector (multi-turn tries if validation fails)
    ↓
Parse YAML → Component (gf.read.from_yaml())
    ↓
Auto-Route (handled by gf.read.from_yaml())
    ↓
DRC Check (generic_tech PDK - real, not toy)
    ↓
LVS Check (if scalable - layout vs schematic)
    ↓
Device-Level Optimization (component geometries → target losses)
    ↓
Circuit-Level Optimization (phase/coupling → minimize σ₁²(T))
    ↓
SAX Validation (functional correctness)
    ↓
P&R Validation (placement & routing)
    ↓
Metrics Calculation (pass@k, spec@k, opt-efficiency, robust score)
```

## Implementation Status

See `IMPLEMENTATION_STATUS.md` for detailed status.

### Completed ✅
- Metrics with new formulas (OptEff, RobustPass, Overall Robustness Score R)
- False examples extraction (Python and PhIDO)
- Python to YAML converter (basic)
- Failure analyzer
- Base pilot generator
- Test file skeletons

### In Progress 🔄
- Component spec loader (YAML DSL format)
- Config with YAML DSL prompt template
- Validators implementation

### Pending ⏳
- Full validator implementations
- Optimizer verification
- Integration testing

## Directory Structure

```
gd_picasso/
├── __init__.py
├── metrics.py                    # Updated metrics with new formulas
├── validation/
│   ├── false_examples_extractor.py
│   ├── python_to_yaml_converter.py
│   └── phido_examples_extractor.py
├── pilot/
│   ├── failure_analyzer.py
│   └── base_pilot_generator.py
├── tests/
│   ├── test_yaml_pilot_validator.py
│   ├── test_yaml_parser.py
│   ├── test_drc_validator.py
│   └── test_lvs_validator.py
└── injection/
    └── (component_spec_loader.py - to be updated)
```

## Next Steps

1. Complete component spec loader update for YAML DSL
2. Create config.py with YAML DSL prompt template
3. Implement YAML pilot validator
4. Implement DRC validator with generic_tech PDK
5. Complete test implementations
6. Run integration tests with false examples
7. Generate framework validation report

## Usage

Once complete, the framework will:
1. Extract and convert false examples to YAML
2. Analyze errors to generate base pilot prompt
3. Test all framework components individually
4. Run end-to-end integration tests
5. Generate validation report showing readiness for LLM testing

