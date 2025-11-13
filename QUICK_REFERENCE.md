# PICasso Quick Reference Card

## 🚀 Installation (One-Time Setup)

```bash
cd /Users/deepakvungarala/Desktop/shigoto/PICasso

# Install klayout for DRC validation
pip install klayout

# Install other dependencies if needed
pip install sax jax jaxlib transformers huggingface-hub

# Verify setup
python check_klayout_config.py
```

## 📊 Visualization

```bash
# Open visualization notebook
jupyter notebook layout_visualization_demo.ipynb
```

## 🤖 Prompting Strategy

- **First Attempt**: ONE-SHOT (1 example in system prompt)
- **Retries**: MULTI-TURN (with validation feedback)

## 🎯 Optimization Levels

- **Device-Level**: Optimize component geometries (width, length, gap, radius)
- **Circuit-Level**: Optimize control parameters (phase, voltage, coupling ratio)

## 🔧 Configuration Files

| File | Purpose | Key Settings |
|------|---------|-------------|
| `hf_inference_workflow/config.py` | Main config | `DEFAULT_MODEL`, `SAMPLES_PER_PROBLEM`, `ENABLE_DRC_CHECK` |
| `hf_inference_workflow/hf_api_client.py` | HF API client | Model inference |
| `hf_inference_workflow/gen_data_validated.py` | Main workflow | Generation + validation |

## 🌐 Model Selection (HF API)

```python
# Current model (in config.py line 24)
DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"

# To change:
# Option 1: Edit config.py
# Option 2: Command line
python gen_data_validated.py --model "your-model-name"
```

## 🏃 Running Inference

```bash
cd hf_inference_workflow

# Quick test (1 sample per problem)
python gen_data_validated.py --samples 1 --output test.csv

# Full benchmark (3 samples per problem)
python gen_data_validated.py --samples 3 --output results.csv

# Specific problems file
python gen_data_validated.py --problems test_20_problems.txt --samples 2
```

## 📁 Output Locations

```
hf_inference_workflow/output/
├── gds_files/              # All GDS files
├── results/
│   ├── framework_results.csv       # Phase 2: With retries + validation
│   ├── raw_llm_results.csv         # Phase 1: First attempts only
│   └── comparison_metrics.json     # pass@k, Spec@k, metrics
└── layout_images/          # High-res PNG exports (from notebook)
```

## 📊 Key Metrics

- **pass@k**: Probability of at least 1 success in k attempts
- **Spec@k**: Structural + functional correctness rate
- **Opt-Efficiency**: Optimization effectiveness (IL improvement / iterations)
- **Robustness Score**: Combined quality metric (Spec@k × 0.7 + Opt-Eff × 0.3)

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| KLayout not found | `pip install klayout` |
| SAX import error | `pip install sax jax jaxlib` |
| HF token error | Check `HF_API_TOKEN` in config.py |
| conda/pip permission error | Run commands manually in terminal |
| No results to visualize | Run `gen_data_validated.py` first |

## 🔍 Checking Status

```bash
# Check klayout
python check_klayout_config.py

# List result files
ls hf_inference_workflow/output/results/

# Check latest results
python -c "import pandas as pd; df = pd.read_csv('hf_inference_workflow/output/results/framework_results.csv'); print(f'Success rate: {df[\"success\"].mean()*100:.1f}%')"
```

## 📚 Documentation Files

- `ANSWERS_TO_QUESTIONS.md` - Detailed answers to your questions
- `SETUP_INSTRUCTIONS.md` - Installation guide
- `layout_visualization_demo.ipynb` - Visualization examples
- `README.md` - Project overview
- `hf_inference_workflow/README.md` - Workflow details
- `hf_inference_workflow/HOW_TO_RUN.md` - Execution guide

## 🆘 Getting Help

1. Read `ANSWERS_TO_QUESTIONS.md` for detailed explanations
2. Check `hf_inference_workflow/README.md` for workflow details
3. Run `python check_klayout_config.py` for diagnostics
4. Look at `layout_visualization_demo.ipynb` for examples

## ⚡ Quick Commands Cheatsheet

```bash
# Install dependencies
pip install klayout sax jax jaxlib

# Check configuration
python check_klayout_config.py

# Run quick test
cd hf_inference_workflow && python gen_data_validated.py --samples 1

# Open notebook
jupyter notebook layout_visualization_demo.ipynb

# View results
cat hf_inference_workflow/output/results/comparison_metrics.json | python -m json.tool
```


