# PICasso - Photonic Circuit Design Automation

**AI-Powered Photonic Integrated Circuit Generation with Validation + Optimization**

## Overview

PICasso is a framework for automated photonic integrated circuit (PIC) design using Large Language Models (LLMs). The framework uses a YAML DSL approach where LLMs generate YAML netlists directly compatible with GDSFactory's `generic_tech` PDK.

**Primary Framework**: The main development work is in the `gd_picasso/` directory. See [gd_picasso/README.md](gd_picasso/README.md) for complete documentation.

## 🎯 Key Features

- **YAML DSL Generation**: LLMs generate YAML netlists directly (no Python code)
- **Two-Phase Testing**: Vanilla (baseline) and PICasso (with framework features) comparison
- **Pre-execution Validation**: Pilot validator catches errors before component building
- **Retry Logic with Feedback**: LLM learns from errors and fixes them iteratively
- **DRC Validation**: Real design rule checking using `generic_tech` PDK and KLayout
- **LVS Validation**: Layout vs Schematic verification
- **Two-Level Optimization**: Device-level (component geometries) and circuit-level (phase/coupling parameters)
- **Comprehensive Metrics**: Spec@k, Opt-Efficiency, RobustPass, Overall Robustness Score
- **Optimization Analysis**: Before/after comparison of circuit performance

## 🚀 Quick Start

### Prerequisites

```bash
# Install dependencies
pip install gdsfactory sax pydantic pyyaml

# Set API keys (for LLM access)
export OPENAI_API_KEY="your-key-here"  # For GPT models
export ANTHROPIC_API_KEY="your-key-here"  # For Claude models
export HF_TOKEN="your-token-here"  # For HuggingFace models
```

### Run Framework Tests

```bash
cd gd_picasso

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

### Run Optimization Analysis

```bash
cd gd_picasso

# Quick analysis (Problem 1, 20 samples)
python quick_optimization_analysis.py

# Full analysis (All problems, all models)
python analyze_all_optimizations.py --max-samples 5
```

## 📁 Project Structure

```
PICasso/
├── gd_picasso/                    # Main framework (primary development)
│   ├── README.md                  → Complete framework documentation
│   ├── FRAMEWORK.md               → Detailed architecture and workflow
│   ├── USAGE.md                   → Usage guide and examples
│   ├── OPTIMIZATION_ANALYSIS_README.md → Optimization analysis guide
│   ├── agents/                    → LLM agent implementations
│   ├── validators/                → Validation modules (YAML, DRC, LVS, SAX, P&R)
│   ├── optimizers/                → Device and circuit optimizers
│   ├── pilot/                     → Error prevention system
│   ├── injection/                 → Component specification injection
│   ├── utils/                     → Utility functions
│   ├── tests/                     → Test suite
│   ├── config.py                  → Configuration and prompts
│   ├── metrics.py                 → Metrics calculation
│   ├── test_with_llm.py           → Main test runner
│   └── problems_parsed.txt        → 36 benchmark problems
│
├── picasso_flow_package/          # Legacy: Original JSON netlist workflow
├── hf_inference_workflow/         # Legacy: HuggingFace inference workflow
├── fin_picasso_framework/         # Legacy: Previous framework iteration
└── openAI_llms/                   # Legacy: OpenAI workflow
```

## 📚 Documentation

### Primary Documentation (gd_picasso)

- **[gd_picasso/README.md](gd_picasso/README.md)** - Framework overview and quick start
- **[gd_picasso/FRAMEWORK.md](gd_picasso/FRAMEWORK.md)** - Complete architecture and workflow documentation
- **[gd_picasso/USAGE.md](gd_picasso/USAGE.md)** - Detailed usage guide with examples
- **[gd_picasso/OPTIMIZATION_ANALYSIS_README.md](gd_picasso/OPTIMIZATION_ANALYSIS_README.md)** - Optimization analysis guide

## 🔧 Framework Workflow

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
Auto-Fix Routing Collisions (iterative spacing + rotation)
    ↓
DRC Check (generic_tech PDK - real, not toy)
    ↓
LVS Check (layout vs schematic)
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

## 📊 Two-Phase Testing

The framework supports two-phase testing to compare baseline LLM performance with framework-enhanced performance:

- **Phase 1 (Vanilla)**: System prompt + problem only (baseline)
- **Phase 2 (PICasso)**: System prompt + injection + pilot + problem (with full framework features)

Results are saved separately for comparison in `gd_picasso/output/{model}_results/vanilla/` and `picasso/`.

## 🎯 Metrics

The framework calculates comprehensive metrics:

- **Spec@k**: Functional correctness at k samples
- **Opt-Efficiency**: Normalized optimization efficiency
- **RobustPass**: Perturbation-based robustness score
- **Overall Robustness Score**: Combined metric gated by correctness

See [gd_picasso/metrics.py](gd_picasso/metrics.py) for detailed formulas.

## 🤝 Contributing

Improvements welcome! This is an active research project.

## 📄 License

See LICENSE file for details.
