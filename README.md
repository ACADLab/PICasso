# PICasso - Photonic Circuit Design Automation

**AI-Powered Photonic Integrated Circuit Generation with Validation + Optimization**

## 🎯 What's New: Optimization + GPU Cluster Support

**Latest Updates (Nov 2025)**:
- ⚡ **Local GPU Models**: Run on your cluster (no API limits, 10× faster)
- 🎛️ **Phase Optimization**: Automatic tuning to minimize insertion loss
- 🎯 **Loss Target Validation**: Verify against research benchmarks
- 📊 **Comprehensive Metrics**: Track IL before/after optimization

### ✅ Complete Workflow:
1. **Generate** with local GPU LLMs (DeepSeek, Qwen, etc.)
2. **Validate** with P&R + DRC + SAX checks
3. **Optimize** phases to minimize insertion loss
4. **Verify** against target values from research literature
5. **Save** only designs that meet all criteria

### ✅ Key Features:
- **Triple Validation**: P&R + DRC + SAX checks
- **Phase Optimization**: Automatic tuning of thermal shifters, couplers
- **Loss Target Validation**: Compare against 20+ research-based targets
- **Smart Retry**: LLM gets feedback and corrects designs
- **Local GPU Support**: No rate limits, faster, unlimited generation
- **100% Quality**: Only saves validated + optimized designs

### 🚀 Quick Start: GPU Cluster (Recommended)

```bash
# 1. Setup (one-time, 15-20 min)
pip install torch transformers accelerate gdsfactory sax
# See GPU_CLUSTER_SETUP.md for detailed setup

# 2. Generate with local GPU models + optimization
cd hf_models
python hf_gen_data.py  # Uses local DeepSeek-R1-Qwen-14B

# 3. Full validated + optimized workflow
cd hf_inference_workflow
python gen_data_validated.py --problems ../problems.txt

# Results:
# - output/results/*.csv (with IL metrics)
# - output/gds_files/*.gds (validated + optimized)
```

**📖 Guides:**
- **[GPU_CLUSTER_SETUP.md](GPU_CLUSTER_SETUP.md)** - Complete GPU setup (start here!)
- **[TODO.md](TODO.md)** - Implementation tasks and testing
- **[FUTURE_WORK.md](FUTURE_WORK.md)** - Research directions

### 🚀 Quick Start: API Inference (For Testing)

```bash
cd hf_inference_workflow

# Quick test with API (no GPU needed)
python run_test_with_llm.py

# Full generation with API
python gen_data_validated.py --problems test_challenging_problems.txt
```

**See [hf_inference_workflow/START_HERE.md](hf_inference_workflow/START_HERE.md) for API setup!**

---

## 📁 Project Structure

```bash
PICasso/
├── picasso_flow_package/       # Original workflow
│   ├── schemas.py              → JSON netlist schema (Pydantic)
│   ├── placer.py              → Safe component placement
│   ├── router.py              → Deterministic routing with gdsfactory
│   ├── pipeline.py            → LLM → validated netlist → GDS
│   └── cli.py                 → Command-line interface
│
├── hf_inference_workflow/      # NEW: Validated generation
│   ├── gen_data_validated.py  → Main workflow with P&R/DRC/SAX validation
│   ├── hf_api_client.py        → HuggingFace Inference API wrapper
│   ├── validators/             → P&R, DRC, SAX validators
│   ├── retry_handler.py        → Smart retry with LLM feedback
│   ├── README.md               → Complete documentation
│   └── START_HERE.md           → Quick start guide
│
├── openAI_llms/                # OpenAI GPT-4 workflow
│   ├── gen_data.py             → Data generation
│   └── agent.py                → LLM agent
│
└── hf_models/                  # HuggingFace local models
    └── hf_agent.py             → Local model inference
```

## 🚀 How to Use

### Option 1: HF Inference Workflow (Recommended - Validated Designs)

**Complete validation with P&R/DRC/SAX checks:**

```bash
cd hf_inference_workflow

# Install dependencies
pip install -r requirements.txt

# Configure HF API token
# Get token from https://huggingface.co/settings/tokens
export HF_API_TOKEN=your_token_here  # Linux/Mac
# or
set HF_API_TOKEN=your_token_here     # Windows

# Run validation workflow
python gen_data_validated.py --problems test_challenging_problems.txt

# Results:
# - CSV: output/results/*.csv (validation status for each design)
# - GDS: output/gds_files/*.gds (only validated designs)
```

**Key Benefits:**
- ✅ Catches messy layouts (P&R validation)
- ✅ Ensures fabrication compliance (DRC validation)
- ✅ Verifies functional correctness (SAX validation)
- ✅ Auto-corrects failed designs with LLM feedback
- ✅ No more "clumsy but SAX-passing" designs!

**See [hf_inference_workflow/README.md](hf_inference_workflow/README.md) for details.**

---

### Option 2: Original Pipeline (JSON Netlist-based)

**For pre-validated netlists:**

```bash
pip install gdsfactory pydantic

# Run pipeline with sample problem + netlist
python -m picasso_flow.cli \
  --problem sample_problem.txt \
  --llm-json sample_llm_netlist.json \
  --out-gds design.gds
```

Replace `--llm-json` with actual LLM outputs (JSON).

Extend `run_pipeline()` in pipeline.py to call your LLM.

---

### Option 3: OpenAI GPT-4 Workflow

**For GPT-4 based generation:**

```bash
cd openAI_llms

# Configure API key in gen_data.py
python gen_data.py
```

**Note:** This workflow lacks validation - consider using HF Inference Workflow instead.

---

## 🎯 Comparison of Workflows

| Feature | HF Inference Workflow | Original Pipeline | OpenAI Workflow |
|---------|----------------------|-------------------|-----------------|
| **Validation** | ✅ P&R + DRC + SAX | ⚠️ Basic only | ❌ None |
| **Messy Design Detection** | ✅ Yes | ❌ No | ❌ No |
| **Auto-correction** | ✅ Smart retry | ❌ No | ❌ No |
| **Cost** | 💵 Low ($0.02/6 designs) | 💵 Free (local) | 💰 High ($3-5) |
| **Quality Guarantee** | ✅ 100% validated | ⚠️ Variable | ❌ Variable |
| **Model Downloads** | ✅ No (cloud API) | ⚠️ Depends | ✅ No (API) |

**Recommendation:** Use **HF Inference Workflow** for production designs requiring validation.

---

## 📚 Documentation

- **[hf_inference_workflow/README.md](hf_inference_workflow/README.md)** - Complete HF workflow guide
- **[hf_inference_workflow/START_HERE.md](hf_inference_workflow/START_HERE.md)** - Quick start
- **[hf_inference_workflow/HOW_TO_RUN_AND_SEE_RESULTS.md](hf_inference_workflow/HOW_TO_RUN_AND_SEE_RESULTS.md)** - Execution guide

---

## 🔧 Key Improvements (HF Workflow)

### Problem Solved: "Clumsy but SAX-passing" Designs

**Before:**
- Designs pass SAX simulation ✅
- But layouts are messy (overlaps, poor spacing) ❌
- Not fabricatable ❌

**After (with HF Workflow):**
- P&R validation catches messy layouts
- Corrector sends feedback to LLM
- LLM regenerates with proper spacing
- All designs pass P&R + DRC + SAX ✅

### Example: 8-QAM Modulator

**Attempt 1 (Messy):**
```
❌ P&R FAIL: Component spacing 12µm < 20µm minimum
```

**Corrector sends feedback:**
```
"Increase spacing to 20µm, use route_bundle instead of route_single"
```

**Attempt 2 (Clean):**
```
✅ P&R PASS: Quality score 0.91, all spacing correct
✅ DRC PASS: No fabrication violations
✅ SAX PASS: Functional correctness verified
```

---

## 🤝 Contributing

Improvements welcome! This is an active research project.

---

## 📄 License

See LICENSE file for details.
