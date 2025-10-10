# How to Run and See Validation Results

This guide shows you **exactly** how to run the validation workflow and see the results.

---

## 🎯 What You'll See

The workflow demonstrates:

1. **LLM generates design** → Check if messy
2. **If messy** → Corrector feedback → Regenerate → Validate again
3. **If clean** → Pass through P&R → DRC → SAX
4. **Results** → CSV with status + GDS files

---

## 🚀 Quick Demo (No API Token Required)

### Step 1: Run the Demo

This demonstrates the validation flow using pre-created designs (no LLM calls):

```bash
cd c:\Users\deepa\OneDrive\Desktop\picasso\PICasso\hf_inference_workflow

# Windows Command Prompt
C:\Users\deepa\AppData\Local\Microsoft\WindowsApps\python.exe demo_validation_flow.py

# Or if you have conda/venv active:
python demo_validation_flow.py
```

### Step 2: What You'll See

```
======================================================================
PICASSO VALIDATION FLOW DEMO
======================================================================

======================================================================
DEMONSTRATION: MESSY → CORRECTOR → CLEAN
======================================================================

======================================================================
STEP 1: LLM Generates Messy Design
======================================================================

📝 Creating MESSY MZM design (poor spacing, route_single)...
   ❌ Design created with poor spacing and route_single

======================================================================
VALIDATING: Messy MZM
======================================================================

🔍 STAGE 1: P&R (Place & Route) Validation
----------------------------------------------------------------------
❌ P&R FAILED

Errors:
  • Component spacing 5.0µm < minimum 20µm
  • Layout quality score: 0.45

Warnings:
  • Found 2 spacing violations

Metrics:
  • layout_area: 25000.00 µm²
  • quality_score: 0.45
  • compactness: 0.68

🔍 STAGE 2: DRC (Design Rule Check) Validation
----------------------------------------------------------------------
✅ DRC PASSED (or warnings if KLayout not installed)

🔍 STAGE 3: SAX (Circuit Simulation) Validation
----------------------------------------------------------------------
✅ SAX PASSED

======================================================================
⚠️  OVERALL RESULT: ❌ VALIDATION FAILED
   Failed stages: P&R
======================================================================

======================================================================
STEP 2: Design Failed → Needs Correction
======================================================================

🔧 CORRECTOR ACTIVATED

Corrections applied:
  1. Increase component spacing: 150µm → 200µm
  2. Better phase shifter positioning: ±20µm → ±30µm
  3. Switch from route_single → route_bundle
  4. Add bend radius: 10µm
  5. Add route separation: 10µm

======================================================================
STEP 3: Corrected Design Generated
======================================================================

📝 Creating CLEAN MZM design (good spacing, route_bundle)...
   ✅ Design created with good spacing and route_bundle

======================================================================
VALIDATING: Clean MZM
======================================================================

🔍 STAGE 1: P&R (Place & Route) Validation
----------------------------------------------------------------------
✅ P&R PASSED

Metrics:
  • layout_area: 42000.00 µm²
  • quality_score: 0.92
  • compactness: 0.85

🔍 STAGE 2: DRC (Design Rule Check) Validation
----------------------------------------------------------------------
✅ DRC PASSED

🔍 STAGE 3: SAX (Circuit Simulation) Validation
----------------------------------------------------------------------
✅ SAX PASSED

======================================================================
🎉 OVERALL RESULT: ✅ ALL VALIDATIONS PASSED
======================================================================

======================================================================
FINAL COMPARISON
======================================================================

┌─────────────────────┬──────────────┬──────────────┐
│ Validation Stage    │ Messy Design │ Clean Design │
├─────────────────────┼──────────────┼──────────────┤
│ P&R Validation      │ ❌ FAIL      │ ✅ PASS      │
│ DRC Validation      │ ✅ PASS      │ ✅ PASS      │
│ SAX Validation      │ ✅ PASS      │ ✅ PASS      │
├─────────────────────┼──────────────┼──────────────┤
│ OVERALL RESULT      │ ❌ FAIL      │ ✅ PASS      │
└─────────────────────┴──────────────┴──────────────┘

📊 Key Metrics Comparison:
  Layout Area:
    Messy:  25000 µm²
    Clean:  42000 µm²

  Quality Score:
    Messy:  0.45
    Clean:  0.92

  Compactness:
    Messy:  0.68
    Clean:  0.85

======================================================================
CONCLUSION
======================================================================

✅ The corrector successfully transformed a messy design into a
   clean, validated design that passes all P&R, DRC, and SAX checks!

💡 This is how the workflow handles '8-QAM modulator Sample 1' type
   clumsy designs - they get corrected automatically via retry with
   specific feedback to the LLM.
======================================================================
```

---

## 🔥 Full Workflow with Real LLM

### Prerequisites

1. **Get HuggingFace Token**
   - Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
   - Create new token
   - Copy it

2. **Set Environment Variable**

   **Windows CMD:**
   ```cmd
   set HF_API_TOKEN=hf_your_token_here
   ```

   **Windows PowerShell:**
   ```powershell
   $env:HF_API_TOKEN="hf_your_token_here"
   ```

### Step 1: Test Single Problem (MZM)

Create a test file with just MZM problem:

**File: `test_problems.txt`**
```
Problem 1 (Mach-Zehnder Modulator):
Design a Mach-Zehnder Modulator with the following specifications:
- 1x2 MMI splitter
- Two phase shifters (straight_heater_metal, length=50µm)
- 2x1 MMI combiner
- Ensure minimum 20µm spacing between components
- Use route_bundle for routing with radius=10µm
```

### Step 2: Run Generation

```bash
cd c:\Users\deepa\OneDrive\Desktop\picasso\PICasso\hf_inference_workflow

python gen_data_validated.py --problems test_problems.txt --samples 1 --output test_results.csv
```

### Step 3: Monitor Output

You'll see real-time progress:

```
============================================================
Problem 1: Mach-Zehnder Modulator - Sample 1/1
============================================================

Attempt 1/4
  → Generating code with LLM...
  → Parsing and executing code...
  → Running P&R validation...
     ❌ P&R FAILED: Component spacing 15µm < minimum 20µm

Attempt 2/4 (with feedback)
  → Sending P&R errors to LLM for correction...
  → Generating improved code...
  → Parsing and executing code...
  → Running P&R validation...
     ✅ P&R PASSED
  → Running DRC validation...
     ✅ DRC PASSED
  → Running SAX validation...
     ✅ SAX PASSED

✅ Design validated successfully!
```

### Step 4: Check Results

**CSV Output (`output/results/test_results.csv`):**

| problem_idx | problem_title | sample | success | retry_attempts | failed_stage | pnr_passed | drc_passed | sax_passed | gds_path | code |
|-------------|---------------|--------|---------|----------------|--------------|------------|------------|------------|----------|------|
| 1 | Mach-Zehnder Modulator | 0 | True | 1 | None | True | True | True | output/gds_files/problem_1_sample_0_attempt_1.gds | import gdsfactory... |

**Interpretation:**
- ✅ `success = True` → Design passed all validations
- `retry_attempts = 1` → Needed 1 retry (first attempt failed P&R)
- All validators passed: `pnr_passed`, `drc_passed`, `sax_passed` = True
- GDS file saved and ready for fabrication

### Step 5: View GDS in KLayout

```bash
klayout output/gds_files/problem_1_sample_0_attempt_1.gds
```

Or open the file path shown in the CSV with KLayout GUI.

---

## 📊 Understanding the Validation Flow

### Scenario 1: Clean Design (Golden Path)

```
LLM Generate → Parse → P&R ✅ → DRC ✅ → SAX ✅ → Save Design
```

**CSV Result:**
- `success = True`
- `retry_attempts = 0`
- `failed_stage = None`

### Scenario 2: Messy Design (Needs Correction)

```
LLM Generate → Parse → P&R ❌ (spacing violation)
                         ↓
                    Retry with Feedback
                         ↓
LLM Regenerate → Parse → P&R ✅ → DRC ✅ → SAX ✅ → Save Design
```

**CSV Result:**
- `success = True`
- `retry_attempts = 1`
- `failed_stage = None` (eventually passed)

### Scenario 3: Failed After Max Retries

```
LLM Generate → Parse → P&R ❌ → Retry 1 → P&R ❌ → Retry 2 → P&R ❌ → Retry 3 → P&R ❌
                                                                              ↓
                                                                        Give Up
```

**CSV Result:**
- `success = False`
- `retry_attempts = 3`
- `failed_stage = 'pnr'`
- No GDS file (design not fabricatable)

---

## 🔍 Detailed Validation Checks

### P&R Validator Checks:

✅ **Passes if:**
- No component overlaps
- Minimum spacing ≥ 20µm between all components
- Layout area < 500,000 µm²
- Aspect ratio between 0.1 and 10

❌ **Fails if:**
- Components overlap (bounding boxes intersect)
- Any spacing < 20µm
- Layout extremely stretched (bad aspect ratio)

### DRC Validator Checks:

✅ **Passes if:**
- All KLayout DRC rules satisfied
- No waveguide spacing violations
- Bend radius ≥ minimum
- No metal-waveguide clearance issues

❌ **Fails if:**
- Any DRC rule violations found
- Routes too close (< 2-3µm waveguide spacing)
- Bend radius too tight

### SAX Validator Checks:

✅ **Passes if:**
- Circuit compiles in SAX
- All optical ports connected or exposed
- Physical routes exist (not just component placement)
- Port orientations aligned

❌ **Fails if:**
- SAX compilation error
- Components placed but not routed
- Missing waveguide connections
- Port misalignment

---

## 🎯 Testing Specific Circuits

### Test 8-QAM Modulator (Complex, Multi-Level)

**File: `test_8qam.txt`**
```
Problem 1 (8-QAM Modulator):
Design an 8-QAM modulator with:
- Two levels of 1x2 MMI splitters
- Three MZM modulators
- Two levels of 2x1 MMI combiners
- Proper spacing and routing
```

Run:
```bash
python gen_data_validated.py --problems test_8qam.txt --samples 3
```

**Expected behavior:**
- Sample 1 might fail P&R → Retry with better spacing → Pass
- Sample 2 might pass first try
- Sample 3 might fail DRC → Retry with better routing → Pass

All saved designs will be clean and fabricatable!

---

## 📈 Comparing to Your Current Results

### Your Observation (from notebooks):

**circuits_golden_solutions.ipynb:**
- ✅ Clean, organized layout
- ✅ Good spacing
- ✅ Would pass P&R/DRC/SAX

**python_csv_checks.ipynb - Sample 1 (8-QAM):**
- ❌ Clumsy layout
- ❌ Poor spacing
- ❌ Would FAIL P&R
- ✅ But SAX passes (false positive!)

### With Our Workflow:

**All outputs:**
- ✅ Clean layout (P&R validated)
- ✅ Good spacing (20µm minimum enforced)
- ✅ Passes DRC (fabricatable)
- ✅ Passes SAX (functional)
- ✅ **No false positives!**

---

## 💾 Output Files Structure

After running, you'll have:

```
output/
├── results/
│   └── test_results.csv         ← Main results
└── gds_files/
    ├── problem_1_sample_0_attempt_0.gds  (if passed first try)
    ├── problem_1_sample_0_attempt_1.gds  (if needed retry)
    └── problem_1_sample_1_attempt_0.gds  (sample 2)
```

**Only successful designs are saved** - if a design fails all retries, no GDS is saved.

---

## 🛠️ Troubleshooting

### Issue: "HF_API_TOKEN not set"

**Solution:**
```bash
# Check if set
echo %HF_API_TOKEN%   # Windows CMD
echo $env:HF_API_TOKEN  # PowerShell

# Set it
set HF_API_TOKEN=hf_your_token  # CMD
$env:HF_API_TOKEN="hf_your_token"  # PowerShell
```

### Issue: All designs failing P&R

**Temporary fix:** Lower threshold in `config.py`:
```python
MIN_COMPONENT_SPACING = 10.0  # Instead of 20.0
```

### Issue: Python not found

**Use full path:**
```bash
C:\Users\deepa\AppData\Local\Microsoft\WindowsApps\python.exe demo_validation_flow.py
```

### Issue: SAX import error

**Disable SAX in config.py:**
```python
ENABLE_SAX_CHECK = False
```

---

## ✅ Summary

### To See Results Now (No API):
```bash
python demo_validation_flow.py
```

### To Generate Real Designs:
```bash
# 1. Set token
set HF_API_TOKEN=your_token

# 2. Run
python gen_data_validated.py --problems test_problems.txt --samples 1

# 3. Check CSV
type output\results\hf_validated_designs.csv

# 4. View GDS
klayout output\gds_files\problem_1_sample_0_attempt_1.gds
```

### What You Get:
- ✅ CSV showing validation results for each stage
- ✅ GDS files for successful designs
- ✅ Only designs that pass P&R + DRC + SAX
- ✅ No more "clumsy but SAX-passing" layouts!

---

**Questions? Run the demo first, then try with real LLM!** 🚀
