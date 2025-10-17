# Python Installation Instructions

## Problem

The Windows Store Python shortcut isn't working. You need a proper Python installation.

## Solution: Install Python Properly

### Step 1: Download Python

1. Go to: https://www.python.org/downloads/
2. Click "Download Python 3.11" (or latest version)
3. **IMPORTANT:** During installation:
   - ✅ Check "Add Python to PATH"
   - ✅ Check "Install for all users"
   - Click "Install Now"

### Step 2: Verify Installation

Open Command Prompt and run:
```cmd
python --version
```

Should show: `Python 3.11.x`

### Step 3: Install Required Packages

```cmd
pip install openai gdsfactory pandas tqdm
```

### Step 4: Run the Test

```cmd
cd C:\Users\deepa\OneDrive\Desktop\picasso\PICasso\hf_inference_workflow
python test_openai_connection.py
```

---

## Alternative: Use Conda/Anaconda

If you prefer Conda:

### Step 1: Install Miniconda

1. Download from: https://docs.conda.io/en/latest/miniconda.html
2. Install (follow prompts)

### Step 2: Create Environment

```cmd
conda create -n picasso python=3.11
conda activate picasso
```

### Step 3: Install Packages

```cmd
pip install openai gdsfactory pandas tqdm
```

### Step 4: Run Test

```cmd
cd C:\Users\deepa\OneDrive\Desktop\picasso\PICasso\hf_inference_workflow
python test_openai_connection.py
```

---

## Quick Alternative: Use Python from Microsoft Store

If you want the quickest solution:

1. Open Microsoft Store
2. Search for "Python 3.11"
3. Click "Get" to install
4. Open Command Prompt (NEW window)
5. Run: `python --version`
6. Should work now

But then disable the redirect:
- Settings → Apps → Advanced app options → App execution aliases
- Turn OFF both "python.exe" aliases

---

## After Python is Installed

Run the batch file:
```cmd
cd C:\Users\deepa\OneDrive\Desktop\picasso\PICasso\hf_inference_workflow
RUN_ME.bat
```

Or run manually:
```cmd
python test_openai_connection.py
python gen_data_openai_validated.py --problems test_20_problems.txt --output validation_report.csv
```
