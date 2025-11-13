# API Parameter Fixes Summary

## Issues Fixed

### 1. ✅ SAX Validator Import Error
**Problem**: `name 'get_port_items' is not defined` in SAX validator
**Fix**: Added import: `from ..utils.port_utils import get_port_items, get_port_count`
**Status**: ✅ Fixed

### 2. ✅ route_single() with separation Parameter
**Problem**: LLM using `route_single(..., separation=15)` which causes error
**Root Cause**: 
- `route_single()` does NOT accept `separation` parameter
- Only `route_bundle()` accepts `separation` parameter
- Pilot validator wasn't checking for this API mismatch

**Fixes Applied**:

#### A. Pilot Validator Check (NEW)
Added `_check_routing_errors()` enhancement to detect:
```python
route_single(..., separation=...)  # ❌ ERROR
```

**Error Message**:
```
API_PARAMETER_ERROR: route_single() does NOT accept 'separation' parameter. 
Only route_bundle() accepts 'separation'. 
Use route_single() for single connections, or route_bundle() for multiple connections with separation.
```

#### B. Prompt Template Updates
Updated `hf_inference_workflow/config.py`:

1. **Added explicit API rules**:
   ```
   - CRITICAL: route_single() does NOT accept 'separation' parameter - only route_bundle() does
   - CRITICAL: route_single() parameters: (component, port1, port2, cross_section, radius)
   - CRITICAL: route_bundle() parameters: (component, ports1, ports2, cross_section, radius, separation)
   ```

2. **Added routing API rules section**:
   ```
   5. Routing API Rules (CRITICAL - prevents API errors):
     - route_single(component, port1, port2, cross_section, radius) - for SINGLE connections
     - route_bundle(component, ports1, ports2, cross_section, radius, separation) - for MULTIPLE connections
     - ❌ NEVER use: route_single(..., separation=...) - separation is ONLY for route_bundle()
     - ✅ Use route_single() for 1-to-1 connections
     - ✅ Use route_bundle() for multiple parallel connections (with separation parameter)
   ```

3. **Updated examples with comments**:
   ```python
   # ✅ CORRECT: route_bundle() for multiple connections (accepts 'separation')
   gf.routing.route_bundle(..., separation=15)  # ✅
   
   # ❌ WRONG: route_single() does NOT accept 'separation' parameter
   # gf.routing.route_single(..., separation=15)  # ❌ ERROR!
   
   # ✅ CORRECT: route_single() for single connections (no 'separation')
   # gf.routing.route_single(..., radius=15)  # ✅
   ```

#### C. Pilot Feedback Enhancement
Added specific feedback for API parameter errors:
```python
elif "API_PARAMETER_ERROR" in error_message:
    return (
        f"{error_message}\n\n"
        "Example fix:\n"
        "```python\n"
        "# WRONG:\n"
        "gf.routing.route_single(r, port1, port2, cross_section='strip', separation=15)  # ❌\n\n"
        "# CORRECT (single connection):\n"
        "gf.routing.route_single(r, port1, port2, cross_section='strip', radius=15)  # ✅\n\n"
        "# CORRECT (multiple connections with separation):\n"
        "gf.routing.route_bundle(r, [port1, port2], [port3, port4], cross_section='strip', radius=15, separation=15)  # ✅\n"
        "```"
    )
```

## Expected Behavior After Fixes

1. **Pilot Validator**: Will catch `route_single(..., separation=...)` BEFORE code execution
2. **Prompt**: Explicitly tells LLM that `separation` is ONLY for `route_bundle()`
3. **Examples**: Show correct vs incorrect usage with clear comments
4. **Feedback**: Provides specific fix examples when error occurs

## Testing

After these fixes:
- ✅ Pilot should catch API parameter errors early
- ✅ LLM should generate correct code (no `separation` in `route_single()`)
- ✅ SAX validation should work (import fixed)
- ✅ Framework should catch and fix these errors automatically

## Next Steps

1. Re-run tests to verify fixes work
2. Monitor if LLM still generates incorrect API calls
3. If errors persist, add more explicit examples in component injection


