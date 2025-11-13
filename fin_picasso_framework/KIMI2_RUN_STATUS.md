# Kimi2 Full PIC Set Run Status

## Overview
Running the full PIC set (9 problems, 3 samples each = 27 total generations) with Kimi2 model via HuggingFace API.

## Configuration
- **Model**: `moonshotai/Kimi-K2-Thinking:novita` (via HuggingFace Inference API)
- **Provider**: novita
- **Problems**: All 9 problems from `test_problems.txt`
- **Samples per problem**: 3 (for pass@3 evaluation)
- **Total generations**: 27

## Test Started
- **Start Time**: 2025-11-11 21:05:00
- **Log File**: `/tmp/kimi2_full_run.log`
- **Results Directory**: `fin_picasso_framework/output/benchmark_results/`

## Monitoring Commands

### Check Live Progress
```bash
# View live log
tail -f /tmp/kimi2_full_run.log

# Monitor checkpoint status
python fin_picasso_framework/monitor_test.py

# Live monitoring dashboard (refreshes every 5 seconds)
python fin_picasso_framework/monitor_live.py
```

### Check Process Status
```bash
# Check if process is running
ps aux | grep test_with_model | grep -v grep

# Check background jobs
jobs
```

## Expected Output Structure

Results will be saved in:
```
fin_picasso_framework/output/benchmark_results/
├── raw_llm/
│   └── code/          # Raw LLM-generated code (before framework)
├── framework_processed/
│   ├── code/          # Framework-processed code (after validation)
│   ├── gds/           # Generated GDS files
│   └── reports/       # Validation reports
└── checkpoints/
    ├── pilot/         # Pilot validation checkpoints
    ├── pnr/           # P&R validation checkpoints
    ├── drc/           # DRC validation checkpoints
    ├── sax/           # SAX validation checkpoints
    ├── functional/    # Functional validation checkpoints
    └── optimization/  # Optimization checkpoints
```

## Framework Validation Stages

For each generation, the framework will:
1. **Pilot Validation**: Pre-execution checks (syntax, mirror errors, spacing, ports)
2. **P&R Validation**: Place & Route checks (component overlap, spacing)
3. **DRC Validation**: Design Rule Checks (manufacturability)
4. **SAX Validation**: Optical simulation (compilation, routing correctness)
5. **Functional Validation**: Circuit behavior verification
6. **Optimization** (if enabled): Device-level and circuit-level optimization

## Retry Logic

- **Max retries per sample**: 4 attempts (pass@3 means 3 samples, each can retry)
- **API retry logic**: 3 retries with exponential backoff (5s, 10s, 20s) for timeouts
- **Feedback loop**: Each retry includes detailed error feedback to help LLM fix issues

## Current Status

Check the monitor output for real-time status:
```bash
python fin_picasso_framework/monitor_test.py
```

## Notes

- The Kimi2 model uses the HuggingFace Inference API with the `novita` provider
- API calls may take time - the framework includes retry logic for timeouts
- Each problem will generate 3 samples for pass@3 evaluation
- Checkpoints are saved at each validation stage for debugging

## Troubleshooting

If the test stops or errors occur:

1. **Check the log file**:
   ```bash
   tail -100 /tmp/kimi2_full_run.log
   ```

2. **Check API token**:
   ```bash
   echo $HF_API_TOKEN
   ```

3. **Restart if needed**:
   ```bash
   export HF_API_TOKEN="your_token_here"
   python fin_picasso_framework/test_with_model.py --model kimi2 --samples 3
   ```

## Completion

When complete, you'll see:
- Summary statistics in the log
- All checkpoints saved
- Raw and processed code files
- Validation reports for each sample


