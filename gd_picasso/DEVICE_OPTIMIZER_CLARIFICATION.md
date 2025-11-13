# Device Optimizer Clarification

## Question: Does device optimizer minimize loss or match target values?

**Answer: The device optimizer tries to MATCH target losses from literature (loss_ppt.pdf), NOT minimize loss arbitrarily.**

## How It Works

1. **Target Losses from PDF**: The optimizer uses target insertion losses from literature (see `DEVICE_LOSS_TARGETS` in `device_optimizer.py`):
   - `mmi1x2`: 0.3 dB
   - `y_branch`: 0.28 dB
   - `bend_euler`: 0.086 dB
   - `straight_heater_metal`: 0.23 dB
   - etc.

2. **Optimization Objective**: The optimizer minimizes `|actual_loss - target_loss|`, meaning:
   - It tries to get as **close as possible** to the target value
   - If actual loss is 0.35 dB and target is 0.3 dB, it tries to reduce to 0.3 dB
   - If actual loss is 0.25 dB and target is 0.3 dB, it tries to increase to 0.3 dB (if possible)

3. **Why Match Targets, Not Minimize?**
   - Literature values represent **realistic, achievable** losses for well-designed components
   - Arbitrary minimization might lead to unrealistic geometries or fabrication issues
   - Matching targets ensures components are optimized to **industry-standard performance**

## Example

For an MMI1x2 splitter:
- **Target from PDF**: 0.3 dB
- **Optimizer goal**: Achieve 0.3 dB (not 0.0 dB)
- **Method**: Adjust width, length, etc. to get as close to 0.3 dB as possible

## Summary

✅ **Device optimizer matches target losses from loss_ppt.pdf**
❌ **Device optimizer does NOT minimize loss arbitrarily**

This ensures components are optimized to realistic, achievable performance levels based on literature values.

