# How to Run the Full Generation

## Quick Start - Full Generation (20 Problems)

### Option 1: Using the Batch Script (Easiest)

1. **Open Command Prompt**
   - Press `Windows Key + R`
   - Type `cmd` and press Enter

2. **Navigate to the folder**
   ```cmd
   cd C:\Users\deepa\OneDrive\Desktop\picasso\PICasso\hf_inference_workflow
   ```

3. **Run the script**
   ```cmd
   run_manual.cmd
   ```

4. **Follow the prompts**
   - It will test your API connection first
   - Then ask if you want full generation (option 1) or quick test (option 2)
   - Choose **1** for full generation

---

### Option 2: Direct Command (Manual)

**Run this single command:**

```cmd
cd C:\Users\deepa\OneDrive\Desktop\picasso\PICasso\hf_inference_workflow
python gen_data_openai_validated.py --problems test_20_problems.txt --output validation_report.csv --samples 2
```

**What this does:**
- Loads 20 problems from `test_20_problems.txt`
- Generates 2 samples per problem = **40 total designs**
- Saves results to `validation_report.csv`

---

## What Will Happen

### Timeline
- **Duration:** ~15-30 minutes for 40 designs
- **Cost:** ~$1-3 USD (using OpenAI gpt-4o-mini)

### Progress Display
```
Initializing OpenAI Inference Agent...
Model: gpt-4o-mini

Loaded 20 problems from test_20_problems.txt

Generating validated designs: 100%|████████████| 40/40 [15:23<00:00]

============================================================
GENERATION SUMMARY
============================================================
Total designs attempted: 40
First attempt success rate: 18 (45.0%)
Final successful designs: 38 (95.0%)
Average retry attempts: 1.25

Final P&R pass rate: 38 (95.0%)
Final DRC pass rate: 38 (95.0%)
Final SAX pass rate: 38 (95.0%)

Results saved to: output\results\validation_report.csv
First attempt GDS files: output\gds_first_attempt
Clean dataset (PIC_set): output\PIC_set\gds_clean
```

---

## Output Files

After completion, you'll have:

```
output/
├── gds_first_attempt/                  # 40 GDS files (all first attempts)
│   ├── problem_1_sample_0_attempt_0.gds
│   ├── problem_1_sample_1_attempt_0.gds
│   └── ... (40 files total)
│
├── PIC_set/                            # VALIDATED CLEAN DATASET
│   ├── gds_clean/                      # ~38 validated GDS files
│   │   ├── problem_1_sample_0_final.gds
│   │   ├── problem_1_sample_1_final.gds
│   │   └── ... (~38 files)
│   │
│   └── code_clean/                     # Python code for clean designs
│       ├── problem_1_sample_0_final.py
│       ├── problem_1_sample_1_final.py
│       └── ... (~38 files)
│
└── results/
    └── validation_report.csv           # Complete tracking CSV
```

---

## Understanding the CSV Report

Open `output/results/validation_report.csv` to see:

| Column | Meaning |
|--------|---------|
| `problem_idx` | Problem number (1-20) |
| `problem_title` | Circuit type (e.g., "Mach-Zehnder Modulator") |
| `sample` | Sample number (0 or 1) |
| `first_attempt_status` | Did first attempt pass? (passed/failed) |
| `first_attempt_failed_stage` | Which validation failed (PNR/DRC/SAX/None) |
| `first_attempt_gds_path` | Path to first attempt GDS |
| `retry_attempts` | How many retries needed (0-3) |
| `final_success` | Did it succeed after retries? |
| `final_pnr_passed` | Final P&R validation (True/False) |
| `final_drc_passed` | Final DRC validation (True/False) |
| `final_sax_passed` | Final SAX validation (True/False) |
| `final_gds_path` | Path to clean GDS (in PIC_set) |
| `final_code_path` | Path to clean Python code |

---

## Command Options

### Full Generation (Recommended)
```cmd
python gen_data_openai_validated.py --problems test_20_problems.txt --output validation_report.csv --samples 2
```
- **20 problems × 2 samples = 40 designs**
- **Cost:** ~$1-3
- **Time:** ~15-30 minutes

### Quick Test (5 Problems)
```cmd
python gen_data_openai_validated.py --problems problems.txt --output quick_test.csv --samples 1
```
- **5 problems × 1 sample = 5 designs**
- **Cost:** ~$0.15
- **Time:** ~3-5 minutes

### Single Problem Test
```cmd
python gen_data_openai_validated.py --problems problems.txt --output single_test.csv --samples 1
```
Then manually edit `problems.txt` to contain only 1 problem.

### Custom Configuration
```cmd
python gen_data_openai_validated.py \
  --problems my_problems.txt \
  --output my_results.csv \
  --samples 3 \
  --model gpt-4o
```

**Available Options:**
- `--problems` - Path to problems file (default: `problems.txt`)
- `--output` - CSV filename (default: `openai_validated_designs.csv`)
- `--samples` - Samples per problem (default: 2)
- `--model` - OpenAI model (default: `gpt-4o-mini`)
- `--format` - Output format: `python` or `json` (default: `python`)
- `--api-key` - Override API key from config

---

## Monitoring Progress

### During Generation

The script shows:
1. **Progress bar** - Current design being generated
2. **Log messages** - Detailed validation results
3. **Retry attempts** - When designs fail and are retried

### Example Log Output
```
============================================================
Problem 1: Mach-Zehnder Modulator - Sample 1/2
============================================================

Problem 1, Sample 0, Attempt 1/4
Parsing and executing generated code...
Running P&R validation...
Running DRC validation...
Running SAX validation...
[OK] All validations passed!
[OK] Design validated successfully!

[OK] First attempt GDS saved: output/gds_first_attempt/problem_1_sample_0_attempt_0.gds
[OK] Clean GDS saved: output/PIC_set/gds_clean/problem_1_sample_0_final.gds
[OK] Clean Python code saved: output/PIC_set/code_clean/problem_1_sample_0_final.py
```

---

## Pausing or Stopping

**To pause:** Press `Ctrl+C` once
- Waits for current design to finish
- Saves results up to that point

**To force stop:** Press `Ctrl+C` twice
- Immediately stops
- May lose progress on current design

**To resume:** Just run the command again with a different output filename

---

## Troubleshooting

### Installation Still Running
If `pip install` is still running in background:
```cmd
# Check if it's done
pip show gdsfactory

# If not installed, wait or install manually:
pip install pandas gdsfactory
```

### Out of Memory
If you get memory errors:
- Reduce samples: `--samples 1`
- Run fewer problems at a time
- Close other applications

### API Rate Limit
If you hit OpenAI rate limits:
- Wait 60 seconds
- Script will auto-retry with exponential backoff
- Or use `OpenAIInferenceAgentWithRetry` class

### All Designs Failing
Check:
1. Validation thresholds in `config.py` (may be too strict)
2. Problem descriptions (may be contradictory)
3. GDSFactory installation (run `python -c "import gdsfactory; print(gdsfactory.__version__)"`)

---

## After Generation

### View Results
```cmd
# Open CSV in Excel or any spreadsheet program
start output\results\validation_report.csv

# Or view in command line
type output\results\validation_report.csv
```

### View GDS Files
Use KLayout (if installed):
```cmd
klayout output\PIC_set\gds_clean\problem_1_sample_0_final.gds
```

Or any GDS viewer.

### Analyze Success Rate
```cmd
python -c "import pandas as pd; df = pd.read_csv('output/results/validation_report.csv'); print(f'Success rate: {df.final_success.mean()*100:.1f}%')"
```

---

## Expected Results

Based on testing with similar problems:

| Metric | Expected Value |
|--------|----------------|
| First attempt success | ~40-50% |
| Final success (after retries) | ~90-95% |
| Average retries per design | ~1.5 |
| P&R pass rate | >95% |
| DRC pass rate | >95% |
| SAX pass rate | >95% |

**Total Designs:**
- Attempted: 40
- Expected to succeed: 36-38
- Saved to PIC_set: 36-38 clean designs

---

## Next Steps

After generation completes:

1. **Review CSV** - Check success rates, retry patterns
2. **Inspect GDS files** - View in KLayout or GDS viewer
3. **Examine code** - Review Python code in `PIC_set/code_clean/`
4. **Compare first vs final** - See how LLM corrected failed designs
5. **Use dataset** - Train ML models, analyze designs, fabricate circuits

---

## Quick Reference

| Task | Command |
|------|---------|
| **Full generation** | `python gen_data_openai_validated.py --problems test_20_problems.txt --output validation_report.csv --samples 2` |
| **Quick test** | `python gen_data_openai_validated.py --problems problems.txt --output test.csv --samples 1` |
| **Check progress** | Watch the progress bar and log messages |
| **View results** | `start output\results\validation_report.csv` |
| **View GDS** | `klayout output\PIC_set\gds_clean\problem_1_sample_0_final.gds` |

---

**Ready to start?** Just run:
```cmd
cd C:\Users\deepa\OneDrive\Desktop\picasso\PICasso\hf_inference_workflow
python gen_data_openai_validated.py --problems test_20_problems.txt --output validation_report.csv --samples 2
```

**Questions?** See [README_OPENAI.md](README_OPENAI.md) or [OPENAI_inference.md](OPENAI_inference.md)
