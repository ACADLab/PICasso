# GPU Cluster Setup Guide for PICasso

Complete guide to setting up local GPU models for fast, unlimited photonic circuit generation.

**Recommended for**: Batch generation of 100+ designs, iterative development

**Last Updated**: Nov 3, 2025

---

## 📋 **Prerequisites**

### Hardware Requirements

#### Minimum (Single GPU)
- **GPU**: NVIDIA GPU with 24GB+ VRAM
  - A100 (40GB/80GB) - Excellent
  - V100 (32GB) - Good
  - RTX 4090 (24GB) - Acceptable
  - RTX 3090 (24GB) - Acceptable
- **RAM**: 32GB+ system RAM
- **Storage**: 100GB+ free space (for models + outputs)

#### Recommended (Multi-GPU)
- **GPUs**: 2-8× A100 40GB or similar
- **RAM**: 64GB+ system RAM
- **Storage**: 500GB+ NVMe SSD

### Software Requirements
- **OS**: Linux (Ubuntu 20.04/22.04 recommended) or Windows with WSL2
- **CUDA**: 11.8 or 12.1+
- **Python**: 3.10 or 3.11
- **Driver**: NVIDIA driver 525.xx or newer

---

## 🚀 **Quick Start** (15-20 minutes)

### Step 1: Verify GPU and CUDA

```bash
# Check GPU
nvidia-smi

# Expected output:
# +-----------------------------------------------------------------------------+
# | NVIDIA-SMI 525.xx       Driver Version: 525.xx       CUDA Version: 12.1     |
# |-------------------------------+----------------------+----------------------+
# | GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
# |   0  NVIDIA A100-...  Off   | 00000000:00:1E.0 Off |                    0 |
# +-------------------------------+----------------------+----------------------+

# Verify CUDA
nvcc --version

# If CUDA not found, install CUDA Toolkit:
# https://developer.nvidia.com/cuda-downloads
```

### Step 2: Install Python Dependencies

```bash
# Clone repository
git clone https://github.com/your-org/PICasso.git
cd PICasso
git checkout deepak_v

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install PyTorch with CUDA support
pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu121

# Install other dependencies
pip install transformers accelerate
pip install gdsfactory sax gplugins
pip install pandas tqdm numpy scipy

# Verify PyTorch sees GPU
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}, Devices: {torch.cuda.device_count()}')"
# Expected: CUDA available: True, Devices: 1 (or more)
```

### Step 3: Download Model Weights

The model will be downloaded automatically on first run, but you can pre-download:

```bash
# Option A: Automatic download (easier)
# Model downloads on first run to ~/.cache/huggingface/

# Option B: Manual download (for offline use)
pip install huggingface-cli
huggingface-cli download deepseek-ai/DeepSeek-R1-Distill-Qwen-14B

# Model size: ~28 GB
# Download time: 10-30 minutes (depends on internet speed)
```

### Step 4: Configure for Local GPU

```bash
# hf_models/hf_gen_data.py is already configured for local GPU:
# ENGINE = 'hf'  # Local GPU
# HF_MODEL_NAME = 'deepseek-ai/DeepSeek-R1-Distill-Qwen-14B'
```

### Step 5: Test Local GPU Inference

```bash
cd hf_models

# Quick test (generates 1-2 designs)
python hf_gen_data.py

# Monitor GPU usage in another terminal:
watch -n 1 nvidia-smi
```

Expected output:
```
🚀 Using 1 GPU(s) for model inference
  GPU 0: NVIDIA A100-SXM4-40GB (40.0 GB)
Loading tokenizer: deepseek-ai/DeepSeek-R1-Distill-Qwen-14B
Loading model: deepseek-ai/DeepSeek-R1-Distill-Qwen-14B
✅ Model loaded successfully on cuda
  GPU 0 Memory: 26.34 GB allocated, 27.02 GB reserved
```

---

## ⚙️ **Configuration Options**

### Model Selection

Edit `hf_models/hf_gen_data.py`:

```python
# Current default (recommended for single A100 40GB)
HF_MODEL_NAME = 'deepseek-ai/DeepSeek-R1-Distill-Qwen-14B'

# Alternative models:

# Qwen2.5-Coder-32B (Excellent quality, needs 2×A100 or 1×A100 80GB)
HF_MODEL_NAME = 'Qwen/Qwen2.5-Coder-32B-Instruct'

# DeepSeek-Coder-V2-Lite (Memory-efficient, fits on 16GB GPU)
HF_MODEL_NAME = 'deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct'

# Llama-3.3-70B (Very good quality, needs 4×A100)
HF_MODEL_NAME = 'meta-llama/Llama-3.3-70B-Instruct'
```

### Multi-GPU Configuration

The system automatically detects and uses all available GPUs (`device_map="auto"`).

**Verify multi-GPU**:
```bash
python -c "import torch; print(f'GPUs: {torch.cuda.device_count()}')"
```

**Manual GPU selection** (if needed):
```bash
# Use only GPUs 0 and 1
export CUDA_VISIBLE_DEVICES=0,1

# Run generation
python hf_gen_data.py
```

### Generation Parameters

Edit `hf_models/hf_gen_data.py`:

```python
SAMPLES_PER_PR = 3      # Designs per problem
MAX_NEW_TOKENS = 2048   # Max code length
TEMPERATURE = 0.3       # 0.1-0.5 for code (lower = more deterministic)
TOP_P = 0.95           # Nucleus sampling
```

---

## 🏃 **Running Generation**

### Basic Usage

```bash
cd hf_models

# Generate designs from default problems
python hf_gen_data.py

# Outputs:
# - llm_responses.csv (all attempts)
# - Generated code in output/
```

### Validated Workflow (Recommended)

```bash
cd hf_inference_workflow

# With full validation (P&R + DRC + SAX) + optimization
python gen_data_validated.py --problems ../problems.txt

# Outputs:
# - output/results/*.csv (metrics with IL data)
# - output/gds_files/*.gds (validated + optimized designs)
# - output/gds_first_attempt/*.gds (all attempts)
```

### Custom Problems

```bash
# Create custom_problems.txt:
cat > custom_problems.txt << 'EOF'
Problem 1 (My Custom MZM):
Design a Mach-Zehnder Modulator with two 3dB couplers and two phase shifters.
Target insertion loss: < 5 dB.
EOF

# Run generation
python gen_data_validated.py --problems custom_problems.txt
```

---

## 📊 **Performance Benchmarks**

### Single GPU (A100 40GB)

| Model | Designs/Hour | Memory Usage | Quality |
|-------|--------------|--------------|---------|
| DeepSeek-R1-Qwen-14B | 40-60 | 26 GB | ⭐⭐⭐⭐⭐ |
| Qwen2.5-Coder-32B | 25-35 | 64 GB | ⭐⭐⭐⭐⭐ |
| DeepSeek-Coder-V2-Lite | 80-100 | 16 GB | ⭐⭐⭐⭐ |

### Multi-GPU (8×A100 40GB)

| Workflow | Designs/Hour | Notes |
|----------|--------------|-------|
| Generation only | 400-500 | Linear scaling |
| Full pipeline (validate + optimize) | 150-200 | Bottleneck: SAX |

*Benchmarks measured on Ubuntu 22.04, CUDA 12.1, 20-component MZM circuits*

---

## 🐛 **Troubleshooting**

### Issue: `CUDA out of memory`

**Solution 1**: Use smaller model
```python
HF_MODEL_NAME = 'deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct'  # 16GB
```

**Solution 2**: Enable 8-bit quantization
```python
# In hf_agent.py, modify load_model:
from transformers import BitsAndBytesConfig

quantization_config = BitsAndBytesConfig(load_in_8bit=True)
model = AutoModelForCausalLM.from_pretrained(
    ...,
    quantization_config=quantization_config
)
```

**Solution 3**: Reduce batch size / max_new_tokens
```python
MAX_NEW_TOKENS = 1024  # Instead of 2048
```

### Issue: Slow model download

**Solution**: Use mirror or offline transfer
```bash
# Use HuggingFace mirror (if available)
export HF_ENDPOINT=https://hf-mirror.com

# OR: Download on fast connection, transfer to cluster
# On fast machine:
huggingface-cli download deepseek-ai/DeepSeek-R1-Distill-Qwen-14B --local-dir ./model_weights

# Transfer to cluster:
rsync -avz ./model_weights cluster:/path/to/PICasso/.model_cache/
```

### Issue: `ImportError: cannot import name 'xxx' from 'transformers'`

**Solution**: Update transformers
```bash
pip install --upgrade transformers accelerate
```

### Issue: Model generates incorrect code

**Possible causes**:
1. Temperature too high → Lower to 0.1-0.3
2. Model not suitable for code → Try Qwen2.5-Coder or DeepSeek-Coder
3. Prompt unclear → Check problems.txt clarity

---

## 🔧 **Advanced Configuration**

### Custom Model Cache Directory

```python
# In hf_inference_workflow/config.py:
CACHE_DIR = Path("/mnt/fast_storage/.model_cache")  # Use fast NVMe
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# In hf_agent.py:
from hf_inference_workflow.config import CACHE_DIR

agent = HFAgent(
    model_name=HF_MODEL_NAME,
    cache_dir=str(CACHE_DIR)
)
```

### Mixed Precision Training/Inference

Already enabled by default (`torch_dtype=torch.float16`).

To use full precision (slower but more accurate):
```python
# In hf_agent.py:
torch_dtype=torch.float32  # Instead of float16
```

### Distributed Generation (Multiple Nodes)

For very large batches (1000+ designs), see FUTURE_WORK.md for distributed setup.

---

## 📈 **Monitoring & Logging**

### GPU Utilization

```bash
# Real-time monitoring
watch -n 1 nvidia-smi

# Log to file
nvidia-smi --query-gpu=timestamp,name,utilization.gpu,utilization.memory,memory.used --format=csv -l 5 > gpu_log.csv
```

### Generation Progress

```bash
# Logs are in hf_inference_workflow/output/generation.log
tail -f hf_inference_workflow/output/generation.log
```

### Metrics Analysis

```bash
# After generation, analyze results
cd hf_inference_workflow/output/results
python -c "
import pandas as pd
df = pd.read_csv('results_latest.csv')
print(f'Success rate: {df["sax_passed"].mean():.1%}')
print(f'Avg IL: {df["loss_achieved_db"].mean():.2f} dB')
print(f'Target compliance: {df["meets_loss_target"].mean():.1%}')
"
```

---

## ✅ **Verification Checklist**

Before running large batches, verify:

- [ ] `nvidia-smi` shows GPU(s)
- [ ] `torch.cuda.is_available()` returns `True`
- [ ] Model downloaded successfully (check `.model_cache/` or `~/.cache/huggingface/`)
- [ ] Test generation completes without errors
- [ ] GPU memory usage stable (not hitting OOM)
- [ ] Generated code is valid Python
- [ ] Validation pipeline works (P&R/DRC/SAX)
- [ ] Optimization runs successfully

---

## 🆘 **Getting Help**

### Common Resources
- **HuggingFace Docs**: https://huggingface.co/docs/transformers
- **PyTorch GPU Guide**: https://pytorch.org/docs/stable/cuda.html
- **GDSFactory Docs**: https://gdsfactory.github.io/gdsfactory/

### Project-Specific
- **Issues**: https://github.com/your-org/PICasso/issues
- **TODO**: See `TODO.md` for current tasks
- **Future Work**: See `FUTURE_WORK.md` for planned features

---

**Last updated**: Nov 3, 2025

**Next**: See `TODO.md` for next steps after setup is complete.
