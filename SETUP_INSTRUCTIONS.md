# PICasso Setup Instructions

## ⚠️ Installation Note
Due to conda/pip permission issues on your system, please run these commands **manually in your terminal**.

## 📦 Quick Setup (Recommended)

```bash
cd /Users/deepakvungarala/Desktop/shigoto/PICasso

# Install klayout Python API (for DRC validation)
pip install klayout

# Install other missing packages
pip install sax jax jaxlib transformers huggingface-hub

# Verify installation
python check_klayout_config.py
```

## 🔧 Full Environment Setup

If you want a clean environment:

```bash
cd /Users/deepakvungarala/Desktop/shigoto/PICasso

# Option 1: Using venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_full.txt

# Option 2: Using conda
conda create -n picasso python=3.10
conda activate picasso
pip install -r requirements_full.txt
```

## ✅ Verify Installation

After installation, run:

```bash
python check_klayout_config.py
```

You should see:
- ✅ klayout Python API is available
- ✅ DRC checking is ENABLED in config.py

## 🖼️ Visualizing Layouts in Jupyter

See `layout_visualization_demo.ipynb` for examples of:
- Loading and displaying GDS layouts
- Using `circuit.plot()` for inline visualization
- Displaying multiple designs side-by-side
- Saving high-resolution layout images

## 📊 Running HF Inference

With the environment set up:

```bash
cd hf_inference_workflow

# Test single problem
python gen_data_validated.py --problems ../problems.txt --samples 1 --output test_run.csv

# Full benchmark run
python gen_data_validated.py --problems ../problems.txt --samples 3 --output full_results.csv
```

## 🔍 Model Selection

The system currently uses **HuggingFace Inference API** (cloud-based).

Current model: `Qwen/Qwen2.5-Coder-32B-Instruct`

To change models, edit `hf_inference_workflow/config.py`:

```python
# Line 24
DEFAULT_MODEL = "your-model-name-here"
```

See the "Model Configuration" section in this repo for a list of models you can test.

## 🐛 Troubleshooting

### KLayout not found
- Run: `pip install klayout`
- Or disable DRC in config.py: `ENABLE_DRC_CHECK = False`

### SAX import errors
- Run: `pip install sax jax jaxlib`

### HuggingFace token errors
- Check token in config.py (line 20)
- Get token from: https://huggingface.co/settings/tokens

### OpenAI API key errors
- Check key in config.py (line 12)
- Get key from: https://platform.openai.com/api-keys


