# Testing Protocol: 9-Problem Validation

This document describes the testing protocol for validating the PICasso framework before running the full 36-problem benchmark.

## Overview

The 9-problem test is a **quick validation run** covering all complexity levels to ensure:
- The framework is working correctly
- Pilot validator catches common errors
- Auto-correction fallbacks are functional
- Two-phase tracking (Raw LLM vs Framework) is accurate

**Expected Runtime**: 15-30 minutes with Pass@3 (27 total samples)

## Test Coverage

The 9 problems span all complexity levels:

### Complexity 1 (Simple) - 3 problems
- **Problem 1**: MZI (Mach-Zehnder Interferometer) - 4 components
- **Problem 2**: MZM (Mach-Zehnder Modulator) - 4 components
- **Problem 10**: 2x2 Optical Switch - Single MZI

### Complexity 2 (Moderate) - 3 problems
- **Problem 4**: QPSK Modulator - Dual MZM with I/Q paths
- **Problem 7**: WDM Multiplexer - Multi-input combining
- **Problem 23**: Ring Resonator Add-Drop Filter - Curved waveguides + couplers

### Complexity 3 (Complex) - 3 problems
- **Problem 5**: 8-QAM Modulator - 7 components, dense layout, vertical stacking
- **Problem 11**: 4x4 Crossbar Switch - 16 switch nodes
- **Problem 20**: Clements 4x4 Interferometer - MZI mesh with 12 elements

## Step 1: Run 9-Problem Test

```bash
python run_9_problem_test.py
```

This script:
1. Loads `test_problems.txt` (9 problems)
2. Generates 3 samples per problem (Pass@3)
3. Runs Phase 1 (Raw LLM baseline) on first attempt
4. Runs Phase 2 (Framework with retries + validation) on subsequent attempts
5. Tracks pilot catches and auto-corrections
6. Saves results to:
   - `hf_inference_workflow/output/results/raw_llm_results.csv`
   - `hf_inference_workflow/output/results/framework_results.csv`

## Step 2: Monitor Progress (Real-Time)

While the test runs, monitor progress in a separate terminal/notebook:

1. Open `benchmark_monitoring.ipynb` in Jupyter
2. Run the setup cell (imports + file paths)
3. Start monitoring:

```python
monitor_progress(refresh_interval=10)
```

The dashboard will update every 10 seconds with:
- Phase 1 (Raw LLM) success rate
- Phase 2 (Framework) success rate
- Pilot error catches
- Auto-correction attempts
- Stage-wise validation metrics (PNR, DRC, SAX, Functional, Loss Target)

**To stop monitoring**: Kernel → Interrupt

## Step 3: Expected Results

### Phase 1 (Raw LLM Baseline)
Expected success rate: **20-40%** (structural correctness only)

Common failures:
- Mirror errors (calling `.mirror()` on Cell instead of ComponentReference)
- Spacing violations (components too close, < 100µm)
- Port name errors (e.g., using 'e1' instead of 'o1')
- Routing collisions

### Phase 2 (PICasso Framework)
Expected success rate: **60-80%** (structural + validation)

Improvements from:
- **Pilot catches**: ~30% of errors prevented upfront
- **LLM retries with feedback**: ~40% of failures recovered
- **Auto-corrections**: ~10% of exhausted failures rescued

### Stage-Wise Pass Rates (Phase 2)
- **PNR Pass**: 70-85%
- **DRC Pass**: 60-75%
- **SAX Pass**: 50-70%
- **Functional Pass**: 40-60% (testbench-level validation)
- **Loss Target Met**: 30-50% (optimized performance)

## Step 4: Analyze Results

After the test completes, visualize results:

```python
# In benchmark_monitoring.ipynb
plot_comparison()
```

This generates:
1. **Overall success rate**: Phase 1 vs Phase 2 bar chart
2. **Stage-wise pass rates**: Framework validation stages (PNR, DRC, SAX, etc.)
3. **Retry distribution**: Histogram of retry attempts
4. **Error handling mechanisms**: Pilot catches, LLM fixes, Auto-corrections

### Summary Statistics

The plot also prints:
- Total samples per phase
- Success rates
- Improvement (percentage point gain from Phase 1 to Phase 2)
- Pilot errors caught
- Auto-corrections applied

## Step 5: Interpret Results

### ✅ SUCCESS - Proceed to Full Benchmark

If the test shows:
- Phase 2 success rate > 60%
- Pilot catches > 20% of errors
- Auto-corrections rescue some failures
- Clear improvement over Phase 1

**Action**: Run the full 36-problem benchmark:
```bash
# Update config to use full problem set
python hf_inference_workflow/gen_data_validated.py
```

### ⚠️ INVESTIGATE - Results Below Expected

If the test shows:
- Phase 2 success rate < 50%
- Many failures at DRC or SAX stages
- Auto-corrections not triggering

**Action**: Check logs for patterns:
```bash
cat hf_inference_workflow/output/test_9_problems.log
```

Common issues:
- **KLayout not found**: DRC validation disabled (check `drc_validator.py`)
- **SAX timeout**: Increase `SAX_TIMEOUT` in `config.py`
- **API rate limits**: Increase `REQUEST_DELAY` in `config.py`

### ❌ FAILURE - Debug Required

If the test crashes or produces no results:

**Action**: Check for:
1. **API token issues**: Verify `HF_API_TOKEN` in `config.py`
2. **Missing dependencies**: Run `pip install -r hf_inference_workflow/requirements.txt`
3. **Python version**: Ensure Python 3.8+
4. **File paths**: Verify `test_problems.txt` exists

## Step 6: Advanced Analysis

### Pass@k Metrics

Compute Pass@k for different k values:

```python
import pandas as pd
from hf_inference_workflow.metrics import estimate_pass_at_k

fw_df = pd.read_csv("hf_inference_workflow/output/results/framework_results.csv")

# Group by problem
for problem_idx in fw_df['problem_idx'].unique():
    problem_df = fw_df[fw_df['problem_idx'] == problem_idx]
    n = len(problem_df)
    c = problem_df['success'].sum()
    
    pass_at_1 = estimate_pass_at_k(n, c, 1)
    pass_at_3 = estimate_pass_at_k(n, c, 3)
    
    print(f"Problem {problem_idx}: Pass@1={pass_at_1:.2%}, Pass@3={pass_at_3:.2%}")
```

### Spec@k (Functional Correctness)

Track Spec@k for functional validation:

```python
# Same as Pass@k but use 'spec_passed' column
for problem_idx in fw_df['problem_idx'].unique():
    problem_df = fw_df[fw_df['problem_idx'] == problem_idx]
    n = len(problem_df)
    c = problem_df['spec_passed'].sum()
    
    spec_at_1 = estimate_pass_at_k(n, c, 1)
    spec_at_3 = estimate_pass_at_k(n, c, 3)
    
    print(f"Problem {problem_idx}: Spec@1={spec_at_1:.2%}, Spec@3={spec_at_3:.2%}")
```

### Optimization Efficiency

Analyze circuit-level optimization improvements:

```python
opt_df = fw_df[fw_df['optimization_success'] == True]
avg_improvement = opt_df['circuit_improvement_db'].mean()
print(f"Average circuit-level IL improvement: {avg_improvement:.2f} dB")
```

## Success Criteria Summary

| Metric | Target | Interpretation |
|--------|--------|----------------|
| Phase 2 Success Rate | > 60% | Framework working correctly |
| Phase 1 vs Phase 2 Improvement | > +30pp | Pilot + retries effective |
| Pilot Catch Rate | > 20% | Pre-execution validation working |
| Auto-Correction Success | > 5% | Fallback rescues some failures |
| DRC Pass Rate | > 60% | Layout quality acceptable |
| SAX Pass Rate | > 50% | Circuit simulation feasible |
| Functional Pass Rate | > 40% | Testbench validation working |

## Troubleshooting

### Test runs very slowly (> 1 hour)

**Cause**: API rate limits or slow model inference

**Solutions**:
- Increase `REQUEST_DELAY` in `config.py` (current: 12s for 5 RPM)
- Reduce `SAMPLES_PER_PROBLEM` to 2 temporarily
- Use faster model: `DEFAULT_MODEL = "meta-llama/Llama-3.2-3B-Instruct"`

### Many pilot errors but no auto-corrections

**Cause**: Auto-correction only triggers after max retries exhausted

**Solution**: Check `ENABLE_AUTO_CORRECTION = True` in `config.py`

### No results saved to CSV

**Cause**: Crash during execution or output directory missing

**Solutions**:
- Check `hf_inference_workflow/output/test_9_problems.log` for errors
- Verify output directories exist (auto-created by `config.py`)

## Next Steps

After successful 9-problem validation:

1. **Run full 36-problem benchmark**:
   ```bash
   python hf_inference_workflow/gen_data_validated.py
   ```

2. **Compute final metrics** (Pass@k, Spec@k, Opt-Efficiency, Robustness Score):
   ```bash
   python demo_pass_at_k_benchmarking.ipynb  # Compute all metrics
   ```

3. **Compare against PIC-bench baseline**: See `PIC_BENCH_COMPARISON.md`

## References

- **Plan**: `two-phase-benchmarking-framework.plan.md` (Implementation details)
- **Metrics**: `METRICS_DEFINITION.md` (Pass@k, Spec@k, Opt-Efficiency)
- **Pilot System**: `PILOT_SYSTEM.md` (Pre-execution validation)
- **Two-Phase Benchmarking**: `TWO_PHASE_BENCHMARKING_README.md` (Methodology)


