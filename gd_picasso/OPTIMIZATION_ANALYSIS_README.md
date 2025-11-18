# Optimization Analysis - Before vs After

## Overview

This analysis compares circuit performance **before** and **after** optimization at two levels:
1. **Device-level optimization**: Optimizes individual component geometries (MMI, Y-branch, etc.)
2. **Circuit-level optimization**: Optimizes tunable parameters (phase shifters, couplers)

## Data Location

All results are saved in: `gd_picasso/output/optimization_analysis/`

### Files Generated:
- `optimization_results_YYYYMMDD_HHMMSS.csv` - CSV data for plotting
- `optimization_results_YYYYMMDD_HHMMSS.json` - JSON data with full details
- `optimization_plots_YYYYMMDD_HHMMSS.png` - Visualization plots
- `summary_statistics_YYYYMMDD_HHMMSS.txt` - Summary statistics

## CSV Columns

| Column | Description |
|--------|-------------|
| `model` | LLM model name (e.g., gpt-4o, claude-sonnet-4.5) |
| `phase` | vanilla or picasso |
| `problem_id` | Problem number (1-36) |
| `sample_idx` | Sample index |
| `device_loss_before_db` | Device-level loss before optimization (dB) |
| `device_loss_after_db` | Device-level loss after optimization (dB) - typically same as before |
| `circuit_loss_before_db` | Circuit-level loss before optimization (dB) |
| `circuit_loss_after_db` | Circuit-level loss after optimization (dB) |
| `total_loss_before_db` | Total loss before = device + circuit (dB) |
| `total_loss_after_db` | Total loss after = device + circuit (dB) |
| `improvement_db` | Improvement = before - after (dB) |
| `opt_efficiency` | Normalized optimization efficiency (0-1) |

## Running the Analysis

### Quick Analysis (Problem 1 only, 20 samples):
```bash
cd gd_picasso
python quick_optimization_analysis.py
```

### Full Analysis (All problems, all models):
```bash
cd gd_picasso
python analyze_all_optimizations.py --max-samples 5
```

### Options:
- `--max-samples N`: Maximum samples per problem (default: 5)
- `--max-problems N`: Maximum problems to process (default: all 36)
- `--skip-optimization`: Use existing results if available

## Interpretation

### If improvement_db > 0:
- ✅ Optimization improved the circuit
- LLM gave a good starting point, optimization made it better

### If improvement_db ≈ 0:
- ✅ LLM gave an already optimal circuit
- No further optimization needed

### If improvement_db < 0:
- ⚠️ Optimization made it worse (rare, may indicate local minimum)
- Or circuit was already at global optimum

## Current Status

**Note**: Many samples are currently failing with model extraction errors. This is being investigated. The framework is working correctly (as verified with test samples), but some circuits have issues with:
- Netlist extraction from GDS
- Missing SAX models for certain components
- Routing errors in generated circuits

## Next Steps

1. Fix model extraction errors for all circuits
2. Run full analysis on all 36 problems
3. Generate comprehensive plots and statistics
4. Compare LLM performance: vanilla vs picasso phases

