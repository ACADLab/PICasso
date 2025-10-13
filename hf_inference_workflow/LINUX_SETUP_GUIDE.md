# PICasso HuggingFace Inference Workflow - Linux Setup Guide

## ✅ Linux Compatibility Status

**Great news!** The codebase is **fully compatible with Linux**. All necessary changes have been implemented.

---

## 🔧 What Was Fixed for Linux

### 1. **Shell Scripts Created** ✅
- Created `run_demo.sh` (Linux equivalent of `run_demo.bat`)
- Created `run_validation_test.sh` (Linux equivalent of `RUN_VALIDATION_TEST.bat`)
- Both scripts made executable with proper permissions

### 2. **GDSFactory Version Compatibility** ✅
- Updated validators to handle GDSFactory 9.11+ API changes
- Fixed `component.references` → `component.insts` compatibility layer
- Fixed KLayout DRC basic checks for newer API

### 3. **Path Handling** ✅
- Already using `pathlib.Path` throughout (cross-platform by design)
- No Windows-specific path separators found

### 4. **Environment Variables** ✅
- Already platform-agnostic environment variable handling
- Works with both `export` (Linux) and `set` (Windows)

---

## 📦 Installation on Linux

### Step 1: Install Python Dependencies

```bash
cd /home/asus/Desktop/gits/PICasso/hf_inference_workflow

# Install required packages
pip install -r requirements.txt

# Or if you prefer pip3
pip3 install -r requirements.txt
```

### Step 2: Install Optional Dependencies

#### For SAX Circuit Simulation (Recommended):
```bash
pip install sax jax jaxlib
```

#### For DRC Validation with KLayout (Optional):
```bash
# Option 1: Install from package manager (Ubuntu/Debian)
sudo apt-get install klayout

# Option 2: Install from snap
sudo snap install klayout

# Option 3: Download from https://www.klayout.de/build.html
# Then add to PATH
```

If you don't want to install KLayout, you can disable DRC checks in `config.py`:
```python
ENABLE_DRC_CHECK = False
```

### Step 3: Configure HuggingFace API Token

Get your token from: https://huggingface.co/settings/tokens

**Option A: Environment Variable (Recommended)**
```bash
export HF_API_TOKEN=your_token_here

# To make it permanent, add to ~/.bashrc or ~/.bash_profile:
echo 'export HF_API_TOKEN=your_token_here' >> ~/.bashrc
source ~/.bashrc
```

**Option B: Edit config.py**
```bash
nano config.py
# Edit line 11:
# HF_API_TOKEN = "your_token_here"
```

---

## 🚀 Running on Linux

### Quick Demo (No API Token Required)

Run the validation demo to see the workflow in action:

```bash
# Using the shell script
./run_demo.sh

# Or directly with Python
python3 demo_validation_flow.py
```

**Expected output:**
- Shows messy design creation and validation failure
- Demonstrates correction workflow
- Shows clean design passing all validations
- Takes ~30 seconds to complete

### Full Validation Workflow (API Token Required)

#### Test with Challenging Problems:
```bash
# Using the shell script
./run_validation_test.sh

# Or directly with Python
python3 gen_data_validated.py --problems test_challenging_problems.txt --output test_results_challenging.csv --samples 2
```

#### Generate All Problems:
```bash
python3 gen_data_validated.py --problems ../problems.txt --output full_results.csv --samples 3
```

### Command-Line Options

```bash
# Specify custom problems file
python3 gen_data_validated.py --problems my_problems.txt

# Change output CSV name
python3 gen_data_validated.py --output my_results.csv

# Use different model
python3 gen_data_validated.py --model "Qwen/Qwen2.5-Coder-7B-Instruct"

# Generate JSON netlists instead of Python
python3 gen_data_validated.py --format json

# Change samples per problem
python3 gen_data_validated.py --samples 5
```

---

## 📊 Output Locations

All outputs are saved in the `output/` directory:

```
hf_inference_workflow/output/
├── gds_files/              # Generated GDS layouts
│   └── problem_*_sample_*_attempt_*.gds
└── results/                # CSV results
    └── *.csv               # Validation status and metrics
```

**Note:** Output directories are created automatically if they don't exist.

---

## 🔍 Verification Tests

### Test 1: Check Dependencies
```bash
python3 -c "import gdsfactory, pandas, tqdm, pathlib; print('✓ All core dependencies available')"
```

### Test 2: Test Configuration
```bash
cd /home/asus/Desktop/gits/PICasso
python3 -c "from hf_inference_workflow.config import *; print('✓ Config loaded successfully')"
```

### Test 3: Test Validators
```bash
python3 -c "import gdsfactory as gf; from hf_inference_workflow.validators import PNRValidator; pnr = PNRValidator(); c = gf.components.mzi(); passed, report = pnr.validate(c); print(f'✓ P&R Validator: {passed}')"
```

### Test 4: Run Demo
```bash
python3 demo_validation_flow.py
```

---

## 🐛 Troubleshooting Linux Issues

### Issue: "ModuleNotFoundError: No module named 'gdsfactory'"

**Solution:**
```bash
pip install gdsfactory>=9.9.4
# Or
pip3 install gdsfactory>=9.9.4
```

### Issue: "Permission denied: ./run_demo.sh"

**Solution:**
```bash
chmod +x run_demo.sh run_validation_test.sh
```

### Issue: "python3: command not found"

**Solution:**
Try using `python` instead of `python3`, or install Python 3:
```bash
# Ubuntu/Debian
sudo apt-get install python3 python3-pip

# Fedora/RHEL
sudo dnf install python3 python3-pip
```

### Issue: "SAX import error"

**Solution:**
```bash
pip install sax jax jaxlib

# If jax/jaxlib fail, try:
pip install sax jax==0.4.13 jaxlib==0.4.13
```

### Issue: "KLayout not found"

**Solutions:**
```bash
# Option 1: Install KLayout
sudo apt-get install klayout

# Option 2: Disable DRC in config.py
nano config.py
# Set: ENABLE_DRC_CHECK = False
```

### Issue: "HF_API_TOKEN not set"

**Solution:**
```bash
# Set environment variable
export HF_API_TOKEN=your_token_here

# Or edit config.py
nano config.py
# Change line 11: HF_API_TOKEN = "your_token_here"
```

### Issue: "All designs failing P&R"

**Solution:**
This may indicate GDSFactory version compatibility. Check version:
```bash
python3 -c "import gdsfactory as gf; print(gf.__version__)"
```

If you see errors, the validators have been updated to handle versions 9.9.4 through 9.11+.

---

## 🔄 Differences from Windows

| Aspect | Windows | Linux |
|--------|---------|-------|
| **Shell Scripts** | `.bat` files | `.sh` files ✅ |
| **Python Command** | `python` | `python3` |
| **Path Separators** | `\` or `\\` | `/` (handled by pathlib ✅) |
| **Environment Variables** | `set VAR=value` | `export VAR=value` |
| **Line Endings** | CRLF (`\r\n`) | LF (`\n`) ✅ |
| **KLayout** | `.exe` installer | apt/snap package |
| **Executable Permissions** | Not needed | `chmod +x` required |

All these differences are **already handled** in the codebase!

---

## 🎯 Quick Start Summary

```bash
# 1. Navigate to directory
cd /home/asus/Desktop/gits/PICasso/hf_inference_workflow

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Run demo (no API token needed)
python3 demo_validation_flow.py

# 4. Set API token
export HF_API_TOKEN=your_token_here

# 5. Run full workflow
python3 gen_data_validated.py --problems test_challenging_problems.txt
```

---

## 📚 Additional Resources

- **Main README**: [README.md](README.md)
- **Quick Start Guide**: [START_HERE.md](START_HERE.md)
- **Implementation Details**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **How to Run**: [HOW_TO_RUN_AND_SEE_RESULTS.md](HOW_TO_RUN_AND_SEE_RESULTS.md)

---

## ✅ Compatibility Checklist

- [x] Shell scripts created for Linux
- [x] File paths use `pathlib.Path` (cross-platform)
- [x] No hardcoded Windows paths
- [x] Environment variables handled correctly
- [x] Subprocess calls are platform-agnostic
- [x] GDSFactory version compatibility fixed
- [x] KLayout API compatibility fixed
- [x] All Python code tested on Linux
- [x] Documentation updated for Linux

**Status: 100% Linux Compatible** ✅

---

## 💡 Pro Tips

1. **Use Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Monitor Progress:**
   - Watch the progress bar in terminal
   - Check `output/results/*.csv` for detailed results
   - View generated GDS files with KLayout viewer

3. **Performance:**
   - First run may be slower (API warmup)
   - Subsequent runs are faster
   - Use `--samples 1` for quick tests

4. **Debugging:**
   - Check `output/generation.log` for detailed logs
   - Use `--format python` for better error messages
   - Validators provide detailed feedback in CSV

---

## 🤝 Support

If you encounter any Linux-specific issues:

1. Check this guide's troubleshooting section
2. Verify all dependencies are installed
3. Check Python and GDSFactory versions
4. Review error messages in terminal and log files

**Working Directory:** `/home/asus/Desktop/gits/PICasso/hf_inference_workflow`

Everything is ready to run on your Linux system! 🎉
