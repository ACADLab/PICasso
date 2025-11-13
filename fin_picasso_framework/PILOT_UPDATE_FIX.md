# Pilot Prompt Update Fix

## Issue
Previously, pilot prompt was only updated **after all 3 samples failed** for a problem. This meant:
- Learning from failures was delayed
- Next problem would benefit, but not the remaining samples of the current problem
- Not optimal for iterative improvement

## Fix Applied
Now pilot prompt updates **after each sample failure** (after pass@k is exhausted for that sample):

### New Logic:
1. **After each sample fails** (with all retries exhausted):
   - Analyze the failure(s) for this problem so far
   - Update pilot rules immediately
   - Apply updated prompt for **next sample/attempt**

2. **Benefits**:
   - ✅ Immediate learning from failures
   - ✅ Next sample in same problem benefits from updated prompt
   - ✅ Faster convergence on fixes
   - ✅ Better use of pass@k attempts

### Code Changes:
```python
# OLD: Only updated after all 3 samples failed
if len(failed_cases) >= SAMPLES_PER_PROBLEM:  # All samples failed
    # Update pilot...

# NEW: Updates after each sample failure (pass@k exhausted)
if retry_attempts >= MAX_RETRY_ATTEMPTS:  # All retries exhausted for this sample
    # Analyze failures (accumulated for this problem)
    # Update pilot rules
    # Apply updated prompt for next sample
```

## Testing
Running test with:
- 1 problem
- 5 samples (to see pilot updates in action)
- DeepSeek-R1 model

Monitoring for:
- ✅ Pilot prompt updates happening after each sample failure
- ✅ Updated prompt being used for next sample
- ✅ Framework catching and fixing errors iteratively


