# PICasso – Photonic Circuit Design Automation

**AI-powered Photonic Integrated Circuit generation with validation and optimization.**

PICasso is a framework for automated photonic integrated circuit (PIC) design using LLMs. It uses a YAML DSL where models produce YAML netlists compatible with GDSFactory's `generic_tech` PDK.

## Install

**From repo (recommended for development):**

```bash
# With uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

**Optional:** install with full extras (KLayout, SAX plugins, JAX, etc.):

```bash
uv pip install -e ".[full]"
# or
pip install -e ".[full]"
```

**Requirements:** Python 3.9+. API keys are **not** bundled; set them via environment variables (see below).

## API keys (environment only)

Do **not** commit keys. Set these in your shell or a local `.env` (and add `.env` to `.gitignore`):

```bash
# For Claude
export ANTHROPIC_API_KEY="your-anthropic-key"

# For GPT / OpenRouter (OpenRouter preferred for rate limits)
export OPENROUTER_API="your-openrouter-key"
# or
export OPENAI_API_KEY="your-key"

# For Hugging Face models
export HF_TOKEN="your-hf-token"
# or
export HF_API_TOKEN="your-hf-token"

# For DeepSeek
export DEEPSEEK_API_KEY="your-deepseek-key"

# For Gemini
export GEMINI_API_KEY="your-gemini-key"
```

Get tokens: [OpenAI](https://platform.openai.com/api-keys) · [Anthropic](https://console.anthropic.com/) · [OpenRouter](https://openrouter.ai/keys) · [Hugging Face](https://huggingface.co/settings/tokens)

## Overview

**Primary framework:** `gd_picasso/`. See [gd_picasso/README.md](gd_picasso/README.md) for full documentation.

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
- **Multi-Agent Critic** *(new)*: Two-layer critic agent (static checks + GPT-4o LLM review) catches design errors before formal validation, improving Spec@k_full from 0% → 100% on C1/C2 circuits

## 🤖 Multi-Agent Critic (New)

A `CriticAgent` and `MultiAgentOrchestrator` have been added to the framework. The Critic intercepts generated YAML netlists between generation and formal validation, providing targeted feedback to the generator before expensive SAX simulation is invoked.

**What was added:**

- `gd_picasso/agents/critic_agent.py` — Two-layer critic:
  - **Layer 1 – Static checks** (no API cost, instant): detects banned components (e.g. `mzi` compound), spacing violations, missing YAML sections, and known bad patterns
  - **Layer 2 – LLM review** (GPT-4o, only runs if static passes): catches wrong port names, missing routes, bad topology, and mirror configuration errors
- `gd_picasso/agents/orchestrator.py` — `MultiAgentOrchestrator` wraps a generator + critic in a generate→critique→revise loop (max 2 rounds); drop-in replacement for a single agent
- `gd_picasso/run_c3.sh` — Script to benchmark all four Complexity 3 problems (Tasks 6, 11, 20, 25) with 3 samples each across all three phases

**Design decisions:**

- Static checks run first with zero API cost; LLM review is only invoked when a design passes static checks, avoiding wasted cost on obviously invalid circuits
- The critic system prompt explicitly overrides the problem description on the MZI rule — if the spec says "use mzi components," the critic still enforces the primitive expansion — preventing oscillation across revision rounds

## 🚀 Quick Start

### Run framework tests

```bash
cd gd_picasso

# Run full test suite (all three phases including multi-agent critic)
python test_with_llm.py \
    --model gpt-4o-mini \
    --problems problems_parsed.txt \
    --num-problems 36 \
    --samples 3 \
    --compare \
    --multi-agent

# Run full test suite (vanilla + picasso only, no critic)
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

### Run Complexity 3 benchmark (all 4 C3 problems)

```bash
cd gd_picasso
bash run_c3.sh
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
│   │   ├── critic_agent.py        → Two-layer critic (static + GPT-4o review)
│   │   └── orchestrator.py        → MultiAgentOrchestrator (generator + critic loop)
│   ├── validators/                → Validation modules (YAML, DRC, LVS, SAX, P&R)
│   ├── optimizers/                → Device and circuit optimizers
│   ├── pilot/                     → Error prevention system
│   ├── injection/                 → Component specification injection
│   ├── utils/                     → Utility functions
│   ├── tests/                     → Test suite
│   ├── config.py                  → Configuration and prompts
│   ├── metrics.py                 → Metrics calculation
│   ├── test_with_llm.py           → Main test runner
│   ├── problems_parsed.txt        → 36 benchmark problems
│   └── run_c3.sh                  → Script to run all 4 Complexity 3 problems
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

## 📊 Testing Phases

The framework supports three-phase testing:

- **Phase 1 (Vanilla)**: System prompt + problem only — baseline LLM performance
- **Phase 2 (PICasso)**: System prompt + injection + pilot + problem — full framework features
- **Phase 3 (Multi-Agent)**: Phase 2 + CriticAgent in generate→critique→revise loop

Results are saved separately for comparison in `gd_picasso/output/{model}_results/`.

## 📈 Benchmark Results

Evaluated on the PIC-Set benchmark (36 problems, 3 samples each) using `gpt-4o-mini` as the generator and `gpt-4o` as the critic.

| Circuit Complexity | Phase | Spec@k_structural | Spec@k_full |
|---|---|---|---|
| C1/C2 (1–8 components) | Vanilla | 1.000 | 0.000 |
| C1/C2 (1–8 components) | PICasso | 1.000 | 0.000 |
| C1/C2 (1–8 components) | **Multi-Agent** | **1.000** | **1.000** |
| C3 (8+ components) | Vanilla | 1.000 | 0.000 |
| C3 (8+ components) | PICasso | 1.000 | 0.000 |
| C3 (8+ components) | Multi-Agent | 1.000 | 0.000 |

**Key finding:** The multi-agent critic improves Spec@k_full from **0% → 100%** on C1/C2 circuits by catching unsupported component usage (`mzi` compound) and spacing/port errors before SAX simulation. C3 failures are due to a routing geometry constraint (port overlaps after primitive expansion) that is upstream of the critic and unrelated to generation errors.

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

See [LICENSE](LICENSE) for details.

---

## Pushing this repo to GitHub (public)

From the **PICasso** directory (or repo root if the repo root is PICasso):

```bash
# 1. Initialize git (if not already)
git init

# 2. Add remote (replace with your repo URL)
git remote add origin https://github.com/YOUR_USERNAME/PICasso.git

# 3. Stage and commit
git add .
git commit -m "Public PICasso release: YAML DSL framework, no keys or logs"

# 4. Push (create main branch and set upstream)
git branch -M main
git push -u origin main
```
