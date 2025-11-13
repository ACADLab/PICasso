# Component Injection Debug Report

## Issues Found

### ❌ **CRITICAL: Bad Example in Prompt Template**

**Location**: `hf_inference_workflow/config.py` lines 169, 366

**Problem**: The prompt template contains a **BAD EXAMPLE** that uses `mmi2x1()` which **does NOT exist** in gdsfactory!

**Before (WRONG)**:
```python
mmi_combiner = r.add_ref(gf.components.mmi2x1())  # ❌ DOES NOT EXIST!
mmi_combiner.move((200, 0))
```

**After (FIXED)**:
```python
mmi_combiner = r.add_ref(gf.components.mmi1x2())  # ✅ Use mmi1x2
mmi_combiner.mirror()  # Mirror to create 2x1 combiner
mmi_combiner.move((250, 0))
```

**Impact**: This bad example is teaching the LLM to use a non-existent component, causing `AttributeError: module 'gdsfactory.components' has no attribute 'mmi2x1'` errors.

### ⚠️ **Component Injection Not Being Used**

**Problem**: The framework's `ComponentSpecLoader` exists but is **NOT being called** in `gen_data_validated.py`.

**Current Flow**:
1. `gen_data_validated.py` uses `PYTHON_PROMPT_TEMPLATE` from `hf_inference_workflow/config.py`
2. That template references `COMPONENT_SPECS` from `components.txt` (static file)
3. The dynamic `ComponentSpecLoader` is never used

**What Should Happen**:
1. Extract component types from problem description
2. Use `ComponentSpecLoader` to get actual component specs from gdsfactory
3. Inject those specs into the prompt
4. This would prevent `mmi2x1` errors by showing only available components

### ⚠️ **Pilot Validator Missing Component Check**

**Problem**: Pilot validator doesn't check for non-existent components before execution.

**Solution**: Added `_check_nonexistent_components()` method to catch `mmi2x1` and other non-existent components.

## Fixes Applied

### ✅ **1. Fixed Bad Example in Prompt Template**
- Replaced `mmi2x1()` with `mmi1x2()` + `.mirror()`
- Added warning comment explaining why
- Updated spacing to 250µm for DRC safety

### ✅ **2. Added Component Validation to Pilot**
- Added `_check_nonexistent_components()` method
- Checks for known non-existent components (mmi2x1, etc.)
- Provides clear error message with fix

### ✅ **3. Enhanced Prompt Template**
- Added critical warnings about common mistakes
- Explicitly states `mmi2x1` does NOT exist
- Provides correct pattern: `mmi1x2()` + `.mirror()`

## Recommendations

### **Priority 1: Integrate ComponentSpecLoader**

The framework should dynamically load component specs instead of using static `components.txt`:

```python
# In gen_data_validated.py
from fin_picasso_framework.port_matching.component_spec_loader import ComponentSpecLoader

component_loader = ComponentSpecLoader()
# Extract component types from problem
component_types = extract_component_types(problem_desc)
# Get actual specs from gdsfactory
component_specs = component_loader.generate_port_reference(component_types)
# Inject into prompt
```

### **Priority 2: Enhance Component Injection**

1. **List available components** in the prompt (not just from problem)
2. **Explicitly list non-existent components** to avoid:
   - `mmi2x1` → use `mmi1x2` + mirror
   - Other common mistakes
3. **Show port names** for each component
4. **Provide usage examples** for each component

### **Priority 3: Improve Pilot Validation**

1. ✅ **DONE**: Added non-existent component check
2. **TODO**: Add actual gdsfactory component validation (try to import and check)
3. **TODO**: Add port name validation against actual component ports

## Current Status

- ✅ Bad example fixed in prompt template
- ✅ Pilot validator now checks for non-existent components
- ✅ Enhanced prompt warnings added
- ⚠️ Component injection still using static file (needs dynamic loading)
- ⚠️ ComponentSpecLoader not integrated into main pipeline

## Next Steps

1. **Integrate ComponentSpecLoader** into `gen_data_validated.py`
2. **Test with mmi2x1 error** to verify pilot catches it
3. **Verify component injection** is actually being used in prompts
4. **Monitor** if errors decrease after fixes


