# Routing Fix Analysis - Current State

## What We Have ✅

### 1. **Auto-Corrector Module** (PhIDO-Inspired)
- **File**: `hf_inference_workflow/auto_corrector.py`
- **Status**: ✅ Implemented
- **Routing Fixes**:
  - `_increase_spacing()`: Increases `.move()` coordinates by 1.5x
  - `_fix_routing_bend_radius()`: Fixes radius < 15µm
- **Trigger**: After MAX_RETRY_ATTEMPTS (default: 3) failures

### 2. **Routing Collision Detection**
- **File**: `fin_picasso_framework/gen_data_validated.py`
- **Status**: ✅ Implemented
- **Detection**: Catches "routing collision" errors at execution time
- **Error Type**: `ROUTING_COLLISION`

### 3. **Routing Fixer Module** (Advanced)
- **File**: `fin_picasso_framework/auto_fix/routing_fixer.py`
- **Status**: ⚠️ **NOT INTEGRATED** - Exists but not used in pipeline
- **Capabilities**: Can add missing routes, analyze component structure

## The Problem ❌

### Issue 1: Auto-Corrector Not Triggered for Routing Collisions
- Routing collisions happen at **EXECUTION time** (when code runs)
- Auto-corrector only triggers for **PILOT validation failures** or after **max retries**
- **Current flow**:
  1. Code executes → Routing collision error
  2. Error detected → Feedback sent to LLM
  3. LLM retries (up to 3 times)
  4. **Only then** auto-corrector triggers (if still failing)
  
**Problem**: We should auto-correct routing collisions **immediately** or use spacing fix!

### Issue 2: Routing Fixer Not Integrated
- `routing_fixer.py` exists but is **never called** in `gen_data_validated.py`
- Could be used to fix routing issues automatically

### Issue 3: Spacing Fix Not Applied for Routing Collisions
- `_increase_spacing()` exists in auto-corrector
- But routing collisions don't trigger it until after max retries
- Should trigger **immediately** when `ROUTING_COLLISION` detected

## What PhIDO Does (Reference)

From the code comments, PhIDO:
- **Automatic component matching** - Matches components automatically
- **Routing correction** - Automatically fixes routing issues
- **Rule-based transformations** - Applies fixes based on error patterns

## Recommended Fixes 🔧

### Fix 1: Immediate Auto-Correction for Routing Collisions
**Location**: `fin_picasso_framework/gen_data_validated.py` - `parse_and_execute_code()`

**Change**:
```python
if error_type == "ROUTING_COLLISION":
    # IMMEDIATELY try auto-correction for spacing
    if ENABLE_AUTO_CORRECTION:
        auto_corrector = AutoCorrector()
        corrected_code = auto_corrector.attempt_correction(code, "spacing_error")
        if corrected_code:
            # Try executing corrected code
            # If successful, return corrected result
```

### Fix 2: Integrate Routing Fixer
**Location**: `fin_picasso_framework/gen_data_validated.py`

**Change**:
- Import `RoutingFixer` from `fin_picasso_framework.auto_fix.routing_fixer`
- Use it when routing errors are detected
- Can fix missing routes or spacing issues

### Fix 3: Enhanced Spacing Fix
**Location**: `hf_inference_workflow/auto_corrector.py`

**Enhancement**:
- Make spacing fix more aggressive for routing collisions
- Increase spacing by 2x (not 1.5x) for routing collisions
- Add vertical spacing checks

## Current Status

- ✅ Detection: Working
- ✅ Feedback: Working (sends to LLM)
- ❌ **Auto-correction: NOT triggered immediately for routing collisions**
- ❌ **Routing Fixer: NOT integrated**

## Next Steps

1. **Immediate**: Add auto-correction trigger for `ROUTING_COLLISION` errors
2. **Short-term**: Integrate `RoutingFixer` into pipeline
3. **Long-term**: Enhance spacing fix to be more aggressive for routing collisions


