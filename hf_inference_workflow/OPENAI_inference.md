# OpenAI-Based Photonic Circuit Generation

Complete guide for using OpenAI API (gpt-4o-mini) to generate and validate photonic integrated circuits with GDSFactory.

---

## Table of Contents

1. [Overview](#overview)
2. [Setup Instructions](#setup-instructions)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Usage Guide](#usage-guide)
6. [Output Structure](#output-structure)
7. [Validation Pipeline](#validation-pipeline)
8. [Cost Estimates](#cost-estimates)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Usage](#advanced-usage)

---

## Overview

This workflow uses OpenAI's `gpt-4o-mini` model to automatically generate photonic circuit designs from natural language descriptions. Each design undergoes comprehensive validation (P&R, DRC, SAX) with automatic retry and correction.

### Key Features

- ✅ **Automatic Code Generation**: LLM generates GDSFactory Python code from problem descriptions
- ✅ **Comprehensive Validation**: P&R (Place & Route), DRC (Design Rule Check), SAX (Circuit Simulation)
- ✅ **Intelligent Retry**: Failed designs get specific feedback and are regenerated
- ✅ **Complete Dataset**: Saves both first attempts and final validated designs
- ✅ **Cost-Optimized**: Uses gpt-4o-mini for excellent quality at low cost
- ✅ **Functional Correctness**: Only validated, manufacturable designs in final dataset

### What Gets Saved

**For Every Problem/Sample:**
- **First Attempt GDS** → `output/gds_first_attempt/` (always saved, regardless of pass/fail)
- **Final Clean GDS** → `output/PIC_set/gds_clean/` (only if all validations pass)
- **Final Clean Code** → `output/PIC_set/code_clean/` (Python code that generated clean circuit)

**What's NOT Saved:**
- ❌ Intermediate/messy Python code (only clean code saved)
- ❌ Intermediate attempt GDS files (attempts 2-4)

---

## Setup Instructions

### 1. Install Dependencies

```bash
pip install openai
pip install gdsfactory
pip install pandas tqdm
```

**Required Packages:**
- `openai>=1.0.0` - OpenAI API client
- `gdsfactory>=9.9.4` - Photonic circuit design framework
- `pandas` - Data analysis and CSV output
- `tqdm` - Progress bars

### 2. Get OpenAI API Key

1. Go to [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key (starts with `sk-proj-...` or `sk-...`)

### 3. Configure API Key

**Option A: Edit config.py (Recommended)**

Open `hf_inference_workflow/config.py` and add your key:

```python
OPENAI_API_KEY = "sk-proj-YOUR_KEY_HERE"
```

**Option B: Environment Variable**

```bash
# Linux/Mac
export OPENAI_API_KEY="sk-proj-YOUR_KEY_HERE"

# Windows
set OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE
```

### 4. Verify Setup

Test your API connection:

```bash
cd PICasso/hf_inference_workflow
python openai_api_client.py
```

You should see:
```
✅ API connection successful!
```

---

## Quick Start

### Generate 20 Photonic Circuits

```bash
cd PICasso/hf_inference_workflow
python gen_data_openai_validated.py --problems test_20_problems.txt --output validation_report.csv
```

This will:
1. Load 20 photonic circuit problems
2. Generate 2 samples per problem (40 designs total)
3. Validate each design with P&R, DRC, SAX checks
4. Retry failed designs with LLM feedback (up to 3 retries)
5. Save first attempts and final clean designs

**Expected Runtime:** ~15-30 minutes for 40 designs
**Expected Cost:** ~$1-3 USD

---

## Configuration

### Key Parameters in `config.py`

```python
# ============================================================================
# OpenAI Configuration
# ============================================================================
OPENAI_API_KEY = "your_key_here"
OPENAI_MODEL = "gpt-4o-mini"  # Cost-optimized model

# ============================================================================
# Generation Parameters
# ============================================================================
SAMPLES_PER_PROBLEM = 2      # Samples per problem (2 = 40 designs for 20 problems)
MAX_RETRY_ATTEMPTS = 3       # Maximum retry attempts for failed validations

# Model generation parameters
MODEL_PARAMS = {
    "temperature": 0.3,       # Lower = more deterministic (0.0-1.0)
    "max_tokens": 2048,       # Max code length
    "top_p": 0.95,            # Nucleus sampling
}

# ============================================================================
# Validation Thresholds
# ============================================================================
MIN_COMPONENT_SPACING = 20.0  # Minimum spacing between components (µm)
MAX_LAYOUT_AREA = 500000.0    # Maximum layout area (µm²)
MAX_ROUTE_LENGTH = 2000.0     # Maximum individual route length (µm)

ENABLE_DRC_CHECK = True       # Enable/disable KLayout DRC
ENABLE_SAX_CHECK = True       # Enable/disable SAX compilation
```

### Model Selection

| Model | Cost (per 1M tokens) | Quality | Speed | Recommendation |
|-------|---------------------|---------|-------|----------------|
| `gpt-4o-mini` | $0.15 input / $0.60 output | ⭐⭐⭐⭐⭐ Excellent | Fast | ✅ **RECOMMENDED** |
| `gpt-3.5-turbo` | $0.50 / $1.50 | ⭐⭐⭐⭐ Good | Very Fast | Budget option |
| `gpt-4o` | $2.50 / $10.00 | ⭐⭐⭐⭐⭐ Best | Medium | Premium quality |

**For cost-optimized code generation, `gpt-4o-mini` is the best choice.**

---

## Usage Guide

### Basic Usage

```bash
# Generate from default problems file with default settings
python gen_data_openai_validated.py

# Specify custom problems file
python gen_data_openai_validated.py --problems my_problems.txt

# Custom output CSV name
python gen_data_openai_validated.py --output my_results.csv

# Change number of samples per problem
python gen_data_openai_validated.py --samples 5

# Use different OpenAI model
python gen_data_openai_validated.py --model gpt-4o

# Combine options
python gen_data_openai_validated.py --problems test_20_problems.txt --samples 3 --model gpt-4o-mini --output report.csv
```

### Command-Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--problems` | `problems.txt` | Path to problems file |
| `--output` | `openai_validated_designs.csv` | Output CSV filename |
| `--samples` | `2` | Number of samples per problem |
| `--model` | `gpt-4o-mini` | OpenAI model to use |
| `--format` | `python` | Output format (python or json) |
| `--api-key` | From config | Override API key |

### Problem File Format

Problems should follow this format:

```
Problem 1 (Title):
Description of the circuit...
- Component specifications
- Requirements
- Constraints

Problem 2 (Another Title):
Description...
```

**Example:**

```
Problem 1 (Mach-Zehnder Modulator):
Design a Mach-Zehnder Modulator with the following specifications:
- Use a 1x2 MMI splitter at the input
- Two arms with straight_heater_metal phase shifters (length=50µm)
- Use a 2x1 MMI combiner at the output
- Ensure minimum 20µm spacing between all components
- Use route_bundle for all optical connections with bend radius 10µm
- Expose input port as 'o1' and output port as 'o2'
```

---

## Output Structure

### Directory Layout

```
PICasso/hf_inference_workflow/output/
├── gds_first_attempt/              # All first attempt GDS files
│   ├── problem_1_sample_0_attempt_0.gds
│   ├── problem_1_sample_1_attempt_0.gds
│   ├── problem_2_sample_0_attempt_0.gds
│   └── ...                         # 40 files for 20 problems × 2 samples
│
├── PIC_set/                        # ✅ FINAL CLEAN DATASET
│   ├── gds_clean/                  # Validated clean GDS files
│   │   ├── problem_1_sample_0_final.gds
│   │   ├── problem_1_sample_1_final.gds
│   │   └── ...                     # Only validated designs
│   │
│   └── code_clean/                 # Python code for clean designs
│       ├── problem_1_sample_0_final.py
│       ├── problem_1_sample_1_final.py
│       └── ...                     # Corresponding Python code
│
└── results/
    └── validation_report.csv       # Complete tracking report
```

### CSV Report Columns

| Column | Description |
|--------|-------------|
| `problem_idx` | Problem number (1-20) |
| `problem_title` | Problem title/description |
| `sample` | Sample index (0, 1) |
| `first_attempt_status` | 'passed' or 'failed' |
| `first_attempt_failed_stage` | Which validation failed (PNR/DRC/SAX) |
| `first_attempt_gds_path` | Path to first attempt GDS file |
| `retry_attempts` | Number of retry attempts needed (0-3) |
| `final_success` | Whether design ultimately succeeded |
| `final_pnr_passed` | Final P&R validation status |
| `final_drc_passed` | Final DRC validation status |
| `final_sax_passed` | Final SAX validation status |
| `final_gds_path` | Path to clean GDS (in PIC_set) |
| `final_code_path` | Path to clean Python code |

### Example CSV Output

```csv
problem_idx,problem_title,sample,first_attempt_status,first_attempt_failed_stage,retry_attempts,final_success,final_gds_path
1,Mach-Zehnder Modulator,0,failed,PNR,2,True,output/PIC_set/gds_clean/problem_1_sample_0_final.gds
1,Mach-Zehnder Modulator,1,passed,None,0,True,output/PIC_set/gds_clean/problem_1_sample_1_final.gds
2,8-QAM Modulator,0,failed,DRC,1,True,output/PIC_set/gds_clean/problem_2_sample_0_final.gds
```

---

## Validation Pipeline

Each generated design goes through three validation stages:

### 1. P&R (Place & Route) Validation

**Checks:**
- ✅ Component spacing (minimum 20µm)
- ✅ Layout area within limits
- ✅ Route lengths reasonable
- ✅ No component overlaps
- ✅ Quality score threshold

**Metrics:**
- `layout_area` - Total circuit area (µm²)
- `num_components` - Number of components
- `total_route_length` - Sum of all routes (µm)
- `min_spacing` - Minimum spacing found (µm)
- `quality_score` - Overall layout quality (0-100)

**Failure Examples:**
- Components too close together (<20µm)
- Layout too large (>500,000 µm²)
- Routes excessively long (>2000µm)

### 2. DRC (Design Rule Check) Validation

**Checks:**
- ✅ Manufacturing design rules
- ✅ Minimum feature sizes
- ✅ Layer overlap rules
- ✅ Metal density rules

**Uses:** KLayout DRC engine with foundry rules

**Failure Examples:**
- Waveguides too narrow
- Metal lines too close
- Violates foundry design rules

### 3. SAX (Circuit Simulation) Validation

**Checks:**
- ✅ Circuit compiles in SAX simulator
- ✅ All ports properly connected
- ✅ Routing is electrically/optically valid
- ✅ No dangling connections

**Failure Examples:**
- Unconnected ports
- Invalid component hierarchy
- SAX compilation errors

### Retry Logic

When a design fails validation:

1. **Identify Failure Stage** - Which validation failed (P&R/DRC/SAX)
2. **Generate Feedback** - Create specific error report for LLM
3. **Retry with Feedback** - LLM generates corrected code
4. **Validate Again** - Run all validations on new design
5. **Repeat** - Up to 3 retry attempts

**Example Feedback to LLM:**
```
The previous design failed P&R validation:
- Error: Components too close (minimum spacing: 15µm, required: 20µm)
- Suggestion: Increase spacing between mmi_splitter and phase_shifter1

Please regenerate the design with:
1. Minimum 20µm spacing between all components
2. Better component positioning
3. Use route_bundle instead of route_single
```

---

## Cost Estimates

### Token Usage per Design

| Component | Tokens | Cost (gpt-4o-mini) |
|-----------|--------|-------------------|
| System Prompt | ~800 | $0.00012 |
| Problem Description | ~300 | $0.000045 |
| Generated Code | ~1200 | $0.00072 |
| Retry Feedback (if needed) | ~500 | $0.000075 |
| **Total per Design** | ~2800 | **~$0.0012** |

### Cost Breakdown for 20 Problems

| Scenario | Designs | Retries | Total Cost |
|----------|---------|---------|------------|
| **Best Case** (no retries) | 40 | 0 | **$0.05** |
| **Average Case** (1.5 retries avg) | 40 | 60 | **$1.20** |
| **Worst Case** (3 retries all) | 40 | 120 | **$2.40** |

**Expected Range:** $1-3 USD for complete 20-problem dataset

### Cost Optimization Tips

1. **Use gpt-4o-mini** - 10x cheaper than gpt-4o, nearly same quality for code
2. **Reduce samples** - Use `--samples 1` for prototyping
3. **Fix retry attempts** - Set `MAX_RETRY_ATTEMPTS = 2` to limit costs
4. **Batch processing** - Generate multiple designs in one session
5. **Cache results** - Save successful prompts for reuse

---

## Troubleshooting

### Common Issues

#### 1. API Key Error

**Error:**
```
ValueError: Please set your OpenAI API key in config.py
```

**Solution:**
- Add your API key to `config.py`: `OPENAI_API_KEY = "sk-proj-..."`
- Or set environment variable: `export OPENAI_API_KEY="sk-proj-..."`

#### 2. Module Not Found

**Error:**
```
ModuleNotFoundError: No module named 'openai'
```

**Solution:**
```bash
pip install openai>=1.0.0
```

#### 3. API Rate Limit

**Error:**
```
openai.RateLimitError: Rate limit exceeded
```

**Solution:**
- Wait a few seconds and retry
- Use `OpenAIInferenceAgentWithRetry` class (has built-in retry)
- Reduce concurrent requests

#### 4. Insufficient API Credits

**Error:**
```
openai.APIError: You exceeded your current quota
```

**Solution:**
- Add credits to your OpenAI account at [platform.openai.com/account/billing](https://platform.openai.com/account/billing)
- Minimum $5 recommended for testing

#### 5. GDSFactory Import Error

**Error:**
```
ModuleNotFoundError: No module named 'gdsfactory'
```

**Solution:**
```bash
pip install gdsfactory>=9.9.4
```

#### 6. Validation Always Fails

**Issue:** All designs fail validation even after retries

**Solution:**
- Check validation thresholds in `config.py`
- Reduce `MIN_COMPONENT_SPACING` if too strict
- Increase `MAX_LAYOUT_AREA` if designs are too large
- Review problem descriptions for conflicting requirements

#### 7. Code Generation Timeout

**Issue:** API calls take too long

**Solution:**
- Reduce `max_tokens` in `config.py` (currently 2048)
- Use simpler problem descriptions
- Check internet connection

---

## Advanced Usage

### Custom Validation Rules

Edit `config.py` to adjust validation thresholds:

```python
# Stricter validation
MIN_COMPONENT_SPACING = 30.0  # Increase spacing requirement
MAX_LAYOUT_AREA = 300000.0    # Reduce max area

# More lenient validation
MIN_COMPONENT_SPACING = 15.0  # Reduce spacing requirement
MAX_LAYOUT_AREA = 1000000.0   # Allow larger layouts
```

### Using Different Models

```bash
# Use cheaper model (lower quality)
python gen_data_openai_validated.py --model gpt-3.5-turbo

# Use premium model (higher quality, more expensive)
python gen_data_openai_validated.py --model gpt-4o

# Use legacy model
python gen_data_openai_validated.py --model gpt-4-turbo
```

### Programmatic Usage

```python
from openai_api_client import OpenAIInferenceAgent
from validators import PNRValidator, DRCValidator, SAXValidator

# Initialize agent
agent = OpenAIInferenceAgent(
    api_key="your_key",
    model="gpt-4o-mini",
    temperature=0.3
)

# Generate code
system_prompt = "You are a photonic circuit design expert..."
problem = "Design a Mach-Zehnder Modulator..."
code = agent.ASK_LLM(system_prompt, problem)

# Execute and validate
component = parse_and_execute_code(code)
pnr_passed, pnr_report = PNRValidator().validate(component)
```

### Batch Processing

Process multiple problem files:

```bash
for file in problem_set_*.txt; do
    python gen_data_openai_validated.py --problems "$file" --output "${file%.txt}_results.csv"
done
```

### Integration with CI/CD

```yaml
# .github/workflows/generate_circuits.yml
name: Generate Circuits
on: [push]
jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: pip install openai gdsfactory pandas
      - name: Generate circuits
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: python gen_data_openai_validated.py
      - name: Upload artifacts
        uses: actions/upload-artifact@v2
        with:
          name: pic-dataset
          path: output/PIC_set/
```

---

## Best Practices

### 1. Problem Description Quality

**Good Problem Description:**
```
Problem 1 (Mach-Zehnder Modulator):
Design a Mach-Zehnder Modulator with the following specifications:
- Use a 1x2 MMI splitter at the input
- Two arms with straight_heater_metal phase shifters (length=50µm)
- Use a 2x1 MMI combiner at the output
- Ensure minimum 20µm spacing between all components
- Use route_bundle with bend radius 10µm and separation 10µm
- Expose input port as 'o1' and output port as 'o2'
```

**Poor Problem Description:**
```
Problem 1:
Make a modulator
```

**Tips:**
- Be specific about components (with GDSFactory names)
- Include dimensions and spacing requirements
- Specify routing method (route_bundle vs route_single)
- Define port names
- Mention design constraints

### 2. Validation Threshold Tuning

Start with default thresholds and adjust based on results:

```python
# If too many failures:
MIN_COMPONENT_SPACING = 15.0  # Reduce from 20.0
MAX_LAYOUT_AREA = 600000.0    # Increase from 500000.0

# If designs are too loose:
MIN_COMPONENT_SPACING = 25.0  # Increase from 20.0
MAX_LAYOUT_AREA = 400000.0    # Decrease from 500000.0
```

### 3. Retry Strategy

Adjust retry attempts based on problem complexity:

```python
# Simple problems (Y-branch, single ring)
MAX_RETRY_ATTEMPTS = 2

# Medium complexity (MZM, 2x2 switch)
MAX_RETRY_ATTEMPTS = 3

# Complex problems (AWG, 16-QAM)
MAX_RETRY_ATTEMPTS = 5
```

### 4. Cost Management

Monitor costs per design:

```python
# Log token usage
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o-mini")
prompt_tokens = len(enc.encode(prompt))
response_tokens = len(enc.encode(response))

cost = (prompt_tokens * 0.15 + response_tokens * 0.60) / 1_000_000
print(f"Cost: ${cost:.4f}")
```

---

## Example Workflow

### Complete Example: Generate and Validate

```bash
# 1. Setup
cd PICasso/hf_inference_workflow
export OPENAI_API_KEY="sk-proj-YOUR_KEY"

# 2. Test API connection
python openai_api_client.py

# 3. Generate circuits (20 problems, 2 samples each)
python gen_data_openai_validated.py \
    --problems test_20_problems.txt \
    --samples 2 \
    --model gpt-4o-mini \
    --output validation_report.csv

# 4. Review results
cat output/results/validation_report.csv

# 5. Check success rate
python -c "
import pandas as pd
df = pd.read_csv('output/results/validation_report.csv')
print(f'First attempt success: {(df.first_attempt_status == \"passed\").mean()*100:.1f}%')
print(f'Final success: {df.final_success.mean()*100:.1f}%')
print(f'Avg retries: {df.retry_attempts.mean():.2f}')
"

# 6. View GDS files
ls -lh output/gds_first_attempt/
ls -lh output/PIC_set/gds_clean/
```

### Expected Output

```
Testing OpenAI API...
✅ API connection successful!

Initializing OpenAI Inference Agent...
Model: gpt-4o-mini
Loaded 20 problems from test_20_problems.txt

Generating validated designs: 100%|████████| 40/40 [15:23<00:00]

GENERATION SUMMARY
======================================================
Total designs attempted: 40
First attempt success rate: 18 (45.0%)
Final successful designs: 38 (95.0%)
Average retry attempts: 1.25
Final P&R pass rate: 38 (95.0%)
Final DRC pass rate: 38 (95.0%)
Final SAX pass rate: 38 (95.0%)

Results saved to: output/results/validation_report.csv
First attempt GDS files: output/gds_first_attempt
Clean dataset (PIC_set): output/PIC_set/gds_clean

✅ Generation complete!
```

---

## Support and Resources

### Documentation
- GDSFactory: [https://gdsfactory.github.io/gdsfactory/](https://gdsfactory.github.io/gdsfactory/)
- OpenAI API: [https://platform.openai.com/docs](https://platform.openai.com/docs)

### Related Files
- `openai_api_client.py` - OpenAI API client implementation
- `gen_data_openai_validated.py` - Main generation script
- `config.py` - Configuration and settings
- `test_20_problems.txt` - 20-problem dataset
- `validators/` - Validation modules (P&R, DRC, SAX)

### Contact
For issues or questions, refer to the project documentation or check the GDSFactory community resources.

---

## Appendix: File Structure

```
PICasso/
└── hf_inference_workflow/
    ├── openai_api_client.py          # OpenAI API client
    ├── gen_data_openai_validated.py  # Main generation script
    ├── config.py                      # Configuration
    ├── test_20_problems.txt           # Problem dataset
    ├── OPENAI_inference.md            # This documentation
    │
    ├── validators/                    # Validation modules
    │   ├── __init__.py
    │   ├── pnr_validator.py          # P&R validation
    │   ├── drc_validator.py          # DRC validation
    │   └── sax_validator.py          # SAX validation
    │
    └── output/                        # Generated outputs
        ├── gds_first_attempt/         # First attempt GDS files
        ├── PIC_set/                   # Final clean dataset
        │   ├── gds_clean/            # Validated GDS files
        │   └── code_clean/           # Python code
        └── results/                   # CSV reports
            └── validation_report.csv
```

---

**Last Updated:** 2025-01-17
**Version:** 1.0
**Model:** gpt-4o-mini
**Framework:** GDSFactory 9.9.4
