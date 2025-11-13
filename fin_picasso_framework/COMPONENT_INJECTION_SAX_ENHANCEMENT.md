# Component Injection SAX Enhancement

## Summary

Enhanced component injection to include **SAX model information** and **instructions for creating SAX models** when they don't exist.

## Changes Made

### 1. Enhanced `ComponentSpecLoader.generate_port_reference()`

**Location**: `fin_picasso_framework/port_matching/component_spec_loader.py`

**Enhancements**:
- ✅ Integrated SAX model manager and knowledge base
- ✅ Added SAX availability check for each component
- ✅ Shows SAX model status: ✅ Available, ⚠️ Not available, ❌ Not found
- ✅ Includes SAX usage examples when available
- ✅ Added comprehensive SAX model creation instructions

**New Output Format**:
```
======================================================================
AVAILABLE GDSFACTORY COMPONENTS REFERENCE
======================================================================

⚠️ CRITICAL: Use ONLY these components. Verify component names exist before using!

Component: mmi1x2
  Ports: o1, o2, o3
  Default settings: {...}
  SAX Model: ✅ Available (mmi1x2)
  SAX Usage: MMI 1x2 Splitter SAX Model:
    - Model name: mmi1x2
    - Parameters: length, width, gap
    - Usage: gs.models.mmi1x2(length=10.0, width=3.0, gap=0.25)
    - Ports: o1 (input), o2, o3 (outputs)

Component: custom_component
  Ports: o1, o2
  SAX Model: ❌ Not found
  → Action: Create SAX model (see instructions below)

======================================================================
SAX MODEL CREATION INSTRUCTIONS
======================================================================

If a component does NOT have a SAX model, you can create one:

Method 1: Use gplugins.sax (Recommended)
[Code example]

Method 2: Use default SAX models
[Code example]

Method 3: Create custom SAX model
[Code example]

⚠️ IMPORTANT:
  - Always check if SAX model exists before using component
  - Use standard GDSFactory components that have SAX models when possible
  - If creating custom model, ensure it matches component behavior
  - Test SAX model with: circuit, _ = sax.circuit(netlist, models=models)
======================================================================
```

### 2. Added SAX Model Manager Integration

**Location**: `fin_picasso_framework/port_matching/component_spec_loader.py`

**Changes**:
- ✅ Imports `SAXModelManager` and `SAXKnowledgeBase` if available
- ✅ Initializes SAX managers in `__init__()`
- ✅ Checks SAX model availability for each component
- ✅ Provides SAX usage examples from knowledge base

### 3. Enhanced Prompt Template

**Location**: `hf_inference_workflow/config.py`

**Changes**:
- ✅ Added warnings about SAX model availability
- ✅ Added reference to SAX MODEL CREATION INSTRUCTIONS
- ✅ Fixed bad example (mmi2x1 → mmi1x2 + mirror)

### 4. Added Pilot Validation for Non-Existent Components

**Location**: `hf_inference_workflow/validators/pilot_validator.py`

**Changes**:
- ✅ Added `_check_nonexistent_components()` method
- ✅ Checks for known non-existent components (e.g., `mmi2x1`)
- ✅ Provides clear error message with fix
- ✅ Integrated into validation pipeline

## SAX Model Creation Instructions Included

The component injection now includes three methods for creating SAX models:

### Method 1: Use gplugins.sax (Recommended)
```python
import gplugins.sax as gs
import sax

# Check if model exists
if hasattr(gs.models, 'component_name'):
    model = gs.models.component_name
else:
    # Create model from component
    comp = gf.components.component_name()
    model = gs.read.model_from_gdsfactory(comp)
```

### Method 2: Use default SAX models
```python
import sax
import gplugins.sax as gs

# Common model mappings:
models = {
    'straight': gs.models.straight,
    'bend_euler': gs.models.bend,
    'mmi1x2': gs.models.mmi1x2,
    'straight_heater_metal': sax.models.phase_shifter,
}
```

### Method 3: Create custom SAX model
```python
import sax

@sax.model
def my_component_model(length: float = 10.0, width: float = 0.5):
    # Define S-parameters
    S = {...}  # S-parameter matrix
    return S
```

## Benefits

1. **Prevents SAX Errors**: LLM knows which components have SAX models
2. **Provides Solutions**: Clear instructions on how to create missing SAX models
3. **Better Code Quality**: LLM can choose components with SAX models when possible
4. **Reduces Failures**: Catches non-existent components before execution

## Integration Points

- ✅ `ComponentSpecLoader` now includes SAX information
- ✅ `core/pipeline.py` uses enhanced `generate_port_reference()` (with SAX)
- ✅ Prompt template references SAX information
- ✅ Pilot validator catches non-existent components

## Next Steps

1. **Test with actual LLM**: Verify SAX information is being used correctly
2. **Monitor SAX errors**: Check if SAX-related errors decrease
3. **Expand SAX knowledge**: Add more component-to-SAX mappings
4. **Enhance creation instructions**: Add more examples for complex components


