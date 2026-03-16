# 🚀 Quick Start Guide

**Get running in 5 minutes!**

---

## Step 1: Install Dependencies (2 min)

```bash
cd PICasso/hf_inference_workflow
pip install -r requirements.txt
```

---

## Step 2: Get HuggingFace API Token (2 min)

1. Visit [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Click "New token"
3. Select "Read" access
4. Copy your token

---

## Step 3: Set API Token (30 sec)

**Windows:**
```cmd
set HF_API_TOKEN=your_token_here
```

**Linux/Mac:**
```bash
export HF_API_TOKEN=your_token_here
```

---

## Step 4: Test Connection (30 sec)

```bash
python hf_api_client.py
```

You should see: `✅ API connection successful!`

---

## Step 5: Run Generation (varies)

### Quick Test (1 problem, 1 sample):

Edit [config.py](config.py) line 15:
```python
SAMPLES_PER_PROBLEM = 1
```

Then run:
```bash
python gen_data_validated.py
```

### Full Run (all problems, 3 samples each):

```bash
python gen_data_validated.py
```

---

## 📊 Check Results

Results saved to:
- **CSV**: `output/results/hf_validated_designs.csv`
- **GDS files**: `output/gds_files/`

Open CSV to see:
- Which designs passed all validations
- Retry attempts needed
- Validation stage failures

---

## 🎨 View Designs in KLayout

```bash
klayout output/gds_files/problem_1_sample_0_attempt_0.gds
```

Or double-click GDS file if KLayout is installed.

---

## ⚙️ Common Adjustments

### Use Different Model

Edit [config.py](config.py) line 16:
```python
DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
```

### Change Number of Samples

Edit [config.py](config.py) line 15:
```python
SAMPLES_PER_PROBLEM = 5  # Instead of 3
```

### Disable DRC (if KLayout not installed)

Edit [config.py](config.py) line 70:
```python
ENABLE_DRC_CHECK = False
```

### Increase Retry Attempts

Edit [config.py](config.py) line 16:
```python
MAX_RETRY_ATTEMPTS = 5  # Instead of 3
```

---

## 🐛 Troubleshooting

### ❌ "HF_API_TOKEN not found"
**Fix**: Re-run the export command in your current terminal

### ❌ "KLayout not found"
**Fix**: Set `ENABLE_DRC_CHECK = False` in config.py

### ❌ "SAX import error"
**Fix**: `pip install sax jax jaxlib`

### ❌ "All designs failing"
**Fix**: Check token usage: [huggingface.co/settings/billing](https://huggingface.co/settings/billing)

---

## 📖 Next Steps

- Read full [README.md](README.md) for detailed documentation
- Review generated CSV to understand validation results
- Examine successful vs failed designs in KLayout
- Adjust validation thresholds in [config.py](config.py) if needed

---

**You're all set! Happy generating! 🎉**
