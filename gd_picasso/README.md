# gd_picasso: YAML DSL Framework for Photonic Circuit Design

## Overview

This framework implements a YAML DSL approach where LLMs generate YAML netlists directly (not Python code) for photonic circuit design. The framework validates, corrects, optimizes, and verifies circuits before LLM testing.

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
Auto-Fix Routing Collisions (if detected)
    ├─▶ Iterative spacing fixes (1.5x, 2.0x, 2.5x)
    └─▶ Rotation algorithm (0°, 90°, 180°, 270°)
    ↓
DRC Check (generic_tech PDK - real, not toy)
    ↓
LVS Check (if scalable - layout vs schematic)
    ↓
Silicon Efficiency Check (extra silicon detection)
    ↓
Port Connection Check (same port connections)
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

## Key Features

- **YAML DSL Generation**: LLMs generate YAML netlists directly compatible with GDSFactory
- **Two-Phase Testing**: Vanilla (baseline) and PICasso (with framework features) comparison
- **Pre-execution Validation**: Pilot validator catches errors before component building
- **Retry Logic with Feedback**: LLM learns from errors and fixes them iteratively
- **Automatic Routing Fixes**: Iterative spacing and rotation algorithms for collision resolution
- **DRC Validation**: Real design rule checking using `generic_tech` PDK and KLayout
- **LVS Validation**: Layout vs Schematic verification
- **Two-Level Optimization**: Device-level (component geometries) and circuit-level (phase/coupling parameters)
- **Comprehensive Metrics**: Spec@k, Opt-Efficiency, RobustPass, Overall Robustness Score

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install gdsfactory sax pydantic pyyaml

# Set API keys
export OPENAI_API_KEY="your-key-here"  # For GPT models
export ANTHROPIC_API_KEY="your-key-here"  # For Claude models
export HF_TOKEN="your-token-here"  # For HuggingFace models
```

### Run Framework Tests

```bash
# Run full test suite (both vanilla and picasso phases)
python test_with_llm.py \
    --model gpt-4o \
    --problems problems_parsed.txt \
    --num-problems 36 \
    --samples 5

# Run vanilla phase only (baseline)
python test_with_llm.py \
    --model gpt-4o \
    --problems problems_parsed.txt \
    --num-problems 36 \
    --samples 5 \
    --vanilla-only

# Run PICasso phase only (with framework)
python test_with_llm.py \
    --model gpt-4o \
    --problems problems_parsed.txt \
    --num-problems 36 \
    --samples 5 \
    --picasso-only
```

## Two-Phase Testing

The framework supports two-phase testing to compare baseline LLM performance with framework-enhanced performance:

- **Phase 1 (Vanilla)**: System prompt + problem only (baseline)
  - No injection, no pilot
  - Single attempt (no retry)
  - Results saved to `output/{model}_results/vanilla/`

- **Phase 2 (PICasso)**: System prompt + injection + pilot + problem (with full framework features)
  - Full framework features enabled
  - Retry logic with feedback (up to MAX_RETRY_ATTEMPTS + 1)
  - Full validation (YAML, DRC, LVS, SAX, P&R)
  - Full optimization (device-level, circuit-level)
  - Results saved to `output/{model}_results/picasso/`

## Optimization Analysis

The framework includes comprehensive optimization analysis comparing circuit performance before and after optimization at two levels:

1. **Device-level optimization**: Optimizes individual component geometries (MMI, Y-branch, etc.) to target losses
2. **Circuit-level optimization**: Optimizes tunable parameters (phase shifters, couplers) to minimize σ₁²(T)

### Running Optimization Analysis

```bash
# Quick analysis (Problem 1, 20 samples)
python quick_optimization_analysis.py

# Full analysis (All problems, all models)
python analyze_all_optimizations.py --max-samples 5
```

### Analysis Results

All optimization analysis results are saved in `output/optimization_analysis/`:
- CSV files with optimization data
- JSON files with full details
- PNG plots showing before/after comparisons
- Summary statistics

See [OPTIMIZATION_ANALYSIS_README.md](OPTIMIZATION_ANALYSIS_README.md) for detailed documentation on:
- Data format and columns
- Interpretation of results
- Running different analysis modes
- Understanding optimization efficiency metrics

## Directory Structure

```
gd_picasso/
├── __init__.py
├── config.py                    # Configuration and prompt templates
├── metrics.py                   # Metrics calculation (Spec@k, OptEff, etc.)
├── test_with_llm.py            # Main test runner
├── problems_parsed.txt          # 36 benchmark problems
├── agents/                      # LLM agent implementations
│   ├── anthropic_agent.py
│   ├── deepseek_agent.py
│   └── gemini_agent.py
├── validators/                  # Validation modules
│   ├── yaml_pilot_validator.py
│   ├── drc_validator.py
│   ├── lvs_validator.py
│   ├── sax_validator.py
│   └── pnr_validator.py
├── optimizers/                  # Optimization modules
│   ├── device_optimizer.py
│   └── optimization_integration.py
├── pilot/                       # Error prevention system
│   ├── failure_analyzer.py
│   └── base_pilot_generator.py
├── injection/                   # Component specification injection
│   └── component_spec_loader.py
├── utils/                       # Utility functions
│   ├── yaml_routing_fixer.py
│   └── yaml_netlist_helper.py
├── tests/                       # Test suite
└── output/                      # Results (ignored by git)
    ├── {model}_results/
    │   ├── vanilla/
    │   └── picasso/
    └── optimization_analysis/
```

## Metrics

The framework calculates comprehensive metrics:

- **Spec@k**: Functional correctness at k samples
- **Opt-Efficiency**: Normalized optimization efficiency `(IL_before - IL_after) / (IL_before + ε)`
- **RobustPass**: Perturbation-based robustness score
- **Overall Robustness Score R**: `Spec@k × (α + β·OptEff + γ·RobustPass)` (correctness-gated)

See `metrics.py` for detailed formulas and implementation.

## Documentation

- **[FRAMEWORK.md](FRAMEWORK.md)** - Complete architecture and workflow documentation
- **[USAGE.md](USAGE.md)** - Detailed usage guide with examples
- **[OPTIMIZATION_ANALYSIS_README.md](OPTIMIZATION_ANALYSIS_README.md)** - Optimization analysis guide

## Result Organization

Results are saved in the following structure:

```
gd_picasso/output/
├── {model}_results/
│   ├── vanilla/
│   │   ├── problem_1/
│   │   │   ├── sample_1/
│   │   │   │   ├── circuit.yaml
│   │   │   │   ├── circuit.gds
│   │   │   │   └── metrics.txt
│   │   │   └── ...
│   │   └── ...
│   ├── picasso/
│   │   └── (same structure)
│   └── metrics.csv
└── optimization_analysis/
    ├── optimization_results_*.csv
    ├── optimization_results_*.json
    ├── optimization_plots_*.png
    └── summary_statistics_*.txt
```

## Supported Models

- **OpenAI**: GPT-4o, GPT-4o-mini, GPT-5
- **Anthropic**: Claude Sonnet 4.5
- **DeepSeek**: DeepSeek-R1, DeepSeek-V3
- **Google**: Gemini 2.5 Pro
- **HuggingFace**: Llama 3.1 70B, Qwen 2.5 32B
- **Kimi**: Kimi Thinking

## Contributing

Improvements welcome! This is an active research project.
