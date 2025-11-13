# PICasso Framework - Enhanced Photonic Circuit Design with LLMs

## Overview

PICasso is an enhanced framework for generating photonic integrated circuit (PIC) designs using Large Language Models (LLMs). The framework includes comprehensive validation, automatic error correction, and optimization capabilities.

## Key Features

### 1. **Two-Phase Benchmarking**
- **Phase 1**: Raw LLM output (baseline)
- **Phase 2**: Framework-enhanced output (with validation, feedback, auto-correction)

### 2. **YAML Netlist Integration** (NEW)
- Extracts netlist from Python-generated components
- Validates and fixes spacing/routing issues in YAML format
- Uses GDSFactory native `gf.read.from_yaml()` for automatic routing
- PhIDO-inspired netlist-based validation approach

### 3. **Comprehensive Validation**
- **Pilot Validation**: Pre-execution code checks (syntax, spacing, port errors)
- **P&R Validation**: Place & Route checks (component overlap, spacing)
- **DRC Validation**: Design Rule Checks (manufacturability)
- **SAX Validation**: Functional validation using SAX simulation
- **Port Declaration**: Verifies port exposure matches specification
- **Silicon Efficiency**: Detects unused or excessive silicon

### 4. **Automatic Error Correction**
- **Immediate auto-correction** for routing collisions (YAML-based)
- **Code-based auto-correction** for spacing, mirror errors, port names
- **Pilot prompt updates** after each failure (dynamic learning)

### 5. **Component Injection & Pilot System**
- **Component Injection**: Provides LLM with component specs, ports, SAX info
- **Pilot Prompt**: Dynamic rules that update based on error patterns
- **Pydoc-based specs**: Comprehensive component information extraction

### 6. **Optimization**
- **Device-level**: Optimizes component geometries for target losses
- **Circuit-level**: Optimizes phase shifters and couplings for minimum insertion loss

## Workflow

```
Problem Description
    ↓
LLM generates Python code
    ↓
Pilot Validation (pre-execution checks)
    ↓
Execute Python → Get component
    ↓
YAML Netlist Validation (NEW)
    ├─ Extract netlist: component.get_netlist()
    ├─ Convert to YAML
    ├─ Validate spacing/routing
    └─ Fix if needed → Rebuild using gf.read.from_yaml()
    ↓
P&R Validation
    ↓
DRC Validation
    ↓
SAX Validation (functional)
    ↓
Optimization (device & circuit level)
    ↓
Final validated design
```

## Installation

```bash
# Activate conda environment
conda activate picasso

# Install dependencies
pip install -r requirements_full.txt
```

## Usage

### Run with GPT Model

```bash
cd fin_picasso_framework
python test_with_model.py --model gpt4o_mini --problems 1 --samples 3
```

### Run with HuggingFace Models

```bash
# Kimi2
python test_with_model.py --model kimi2 --problems 1 --samples 3

# DeepSeek-R1
python test_with_model.py --model deepseek_r1 --problems 1 --samples 3
```

## Configuration

Key configuration files:
- `fin_picasso_framework/config.py` - Main configuration
- `hf_inference_workflow/config.py` - Prompt templates

Key settings:
- `ENABLE_EARLY_NETLIST_VALIDATION = True` - YAML validation after Python execution
- `ENABLE_AUTO_CORRECTION = True` - Automatic error correction
- `ENABLE_DYNAMIC_PILOT_UPDATES = True` - Dynamic pilot prompt updates
- `SAMPLES_PER_PROBLEM = 3` - Number of samples per problem

## Output

Results are saved to:
- `fin_picasso_framework/output/results/` - CSV results
- `fin_picasso_framework/output/benchmark_results/raw_llm/` - Raw LLM outputs
- `fin_picasso_framework/output/benchmark_results/checkpoints/` - Debug checkpoints

## Documentation

- `PICASSO_WORKFLOW_DOCUMENTATION.md` - Complete workflow documentation
- `YAML_INTEGRATION_SUMMARY.md` - YAML netlist integration details
- `VERSION_COMPATIBILITY_CHECK.md` - Version compatibility information

## Version Requirements

- **GDSFactory**: >= 7.0.0 (tested with 8.32.2)
- **gplugins**: >= 1.2.4 (for SAX support)
- **Python**: 3.10+

## Key Modules

- `gen_data_validated.py` - Main generation pipeline
- `utils/yaml_netlist_helper.py` - YAML netlist utilities
- `early_validation/netlist_validator.py` - Netlist validation
- `pilot/pilot_validator_enhanced.py` - Pre-execution validation
- `pilot/pilot_prompt_updater.py` - Dynamic pilot prompt updates
- `error_handling/` - Error extraction and feedback generation
- `validators/` - P&R, DRC, SAX validators
- `optimizers/` - Device and circuit optimization

## Recent Updates

- ✅ YAML netlist integration for routing collision fixes
- ✅ Immediate auto-correction for routing collisions
- ✅ Dynamic pilot prompt updates after each failure
- ✅ Pydoc-based component spec extraction
- ✅ Enhanced SAX model information injection
- ✅ Incomplete method call detection and fixing
