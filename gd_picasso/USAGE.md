# PICasso Framework - Usage Guide

## Quick Start

### Run Full Test Suite (Both Phases)

```bash
python gd_picasso/test_with_llm.py \
    --model gpt-4o \
    --problems gd_picasso/problems_parsed.txt \
    --num-problems 36 \
    --samples 5
```

This will:
1. Run **Phase 1 (Vanilla)**: System prompt + problem only (baseline)
2. Run **Phase 2 (PICasso)**: System prompt + injection + pilot + problem (framework)
3. Save results to `gd_picasso/output/{model}_results/vanilla/` and `picasso/`
4. Generate aggregated `metrics.csv`

### Run Vanilla Only (Phase 1)

```bash
python gd_picasso/test_with_llm.py \
    --model gpt-4o \
    --problems gd_picasso/problems_parsed.txt \
    --num-problems 36 \
    --samples 5 \
    --vanilla-only
```

### Run PICasso Only (Phase 2)

```bash
python gd_picasso/test_with_llm.py \
    --model gpt-4o \
    --problems gd_picasso/problems_parsed.txt \
    --num-problems 36 \
    --samples 5 \
    --picasso-only
```

## Model Options

### GPT Models (OpenAI)

```bash
# GPT-4o
python gd_picasso/test_with_llm.py --model gpt-4o --problems gd_picasso/problems_parsed.txt --num-problems 1 --samples 1

# GPT-4o-mini
python gd_picasso/test_with_llm.py --model gpt-4o-mini --problems gd_picasso/problems_parsed.txt --num-problems 1 --samples 1
```

**Requirements**: Set `OPENAI_API_KEY` environment variable

### DeepSeek Models

```bash
python gd_picasso/test_with_llm.py --model deepseek-r1 --problems gd_picasso/problems_parsed.txt --num-problems 1 --samples 1
```

### Kimi2 Models

```bash
python gd_picasso/test_with_llm.py --model kimi2 --problems gd_picasso/problems_parsed.txt --num-problems 1 --samples 1
```

## Result Organization

Results are saved in the following structure:

```
gd_picasso/output/
├── {model}_results/
│   ├── vanilla/
│   │   ├── problem_1/
│   │   │   ├── sample_1/
│   │   │   │   ├── circuit.yaml
│   │   │   │   ├── circuit.gds
│   │   │   │   └── metrics.txt
│   │   │   ├── sample_2/
│   │   │   └── ...
│   │   ├── problem_2/
│   │   └── ...
│   ├── picasso/
│   │   └── (same structure)
│   └── metrics.csv
```

## Metrics Files

### Per-Sample Metrics (`metrics.txt`)

```
Sample 1 Metrics:
  Structural Pass: True
  Functional Pass: False
  DRC Pass: True
  LVS Pass: True
  Optimization Done: True
```

### Aggregated Metrics (`metrics.csv`)

CSV file with columns:
- `problem_id`: Problem number (1-36)
- `phase`: 'vanilla' or 'picasso'
- `model`: Model name
- `sample_idx`: Sample index (1-based)
- `structural_pass`: Boolean
- `functional_pass`: Boolean
- `drc_passed`: Boolean
- `lvs_passed`: Boolean
- `opt_done`: Boolean
- `pass_at_k`: Pass@k score
- `spec_at_k`: Spec@k score
- `opt_eff`: Optimization efficiency
- `robust_pass`: RobustPass score
- `robustness_score`: Overall robustness score

## Testing Different Models

### Test Single Problem (Quick Test)

```bash
python gd_picasso/test_with_llm.py \
    --model gpt-4o \
    --problems gd_picasso/problems_parsed.txt \
    --num-problems 1 \
    --samples 1
```

### Test All 36 Problems

```bash
python gd_picasso/test_with_llm.py \
    --model gpt-4o \
    --problems gd_picasso/problems_parsed.txt \
    --num-problems 36 \
    --samples 5
```

## Environment Setup

1. **Activate conda environment**:
   ```bash
   conda activate picasso
   ```

2. **Set API keys**:
   ```bash
   export OPENAI_API_KEY="your-key-here"
   export HF_TOKEN="your-token-here"  # For HuggingFace models
   ```

3. **Verify gdsfactory**:
   ```bash
   python -c "import gdsfactory as gf; print(gf.__version__)"
   ```

## Troubleshooting

### Issue: "gdsfactory not available"
**Solution**: Activate the `picasso` conda environment or install gdsfactory

### Issue: "OPENAI_API_KEY not set"
**Solution**: Set the environment variable:
```bash
export OPENAI_API_KEY="your-key-here"
```

### Issue: "KLayout not found - DRC check skipped"
**Solution**: Install KLayout and ensure it's in PATH, or DRC will be skipped (results still saved)

### Issue: "Component build failed"
**Solution**: Check the YAML output in `circuit.yaml` - may need to fix YAML syntax or component names

## Next Steps

1. Run tests with your preferred model
2. Review results in `gd_picasso/output/{model}_results/`
3. Analyze `metrics.csv` for aggregated statistics
4. Compare vanilla vs. picasso performance


