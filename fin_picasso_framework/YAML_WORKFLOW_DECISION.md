# YAML Workflow Decision - Python → YAML Conversion

## Decision: Keep Python as LLM Output, Convert to YAML for Validation/Fixing

### Why This Approach?

1. **No Prompt Changes Needed** ✅
   - LLM still outputs Python code (natural, easier)
   - Injection examples stay Python-based
   - Pilot validation stays Python syntax-based
   - No need to teach LLM YAML syntax

2. **Best of Both Worlds** ✅
   - Python: Natural for LLM, easy to generate
   - YAML: Better for validation, fixing, routing

3. **Workflow**:
   ```
   LLM generates Python code
       ↓
   Execute Python → Get component
       ↓
   Extract netlist: component.get_netlist()
       ↓
   Convert to YAML: yaml.dump(netlist)
       ↓
   Validate YAML netlist (spacing, routing feasibility)
       ↓
   If issues → Fix YAML (adjust placements, routes)
       ↓
   Rebuild: component = gf.read.from_yaml(fixed_yaml)
   ```

## What Changes Are Needed?

### 1. Injection (Component Specs) - NO CHANGES ✅
- Still Python examples
- Still Python API documentation
- Still Python code snippets
- **Reason**: LLM outputs Python, so examples should be Python

### 2. Pilot Prompt - NO CHANGES ✅
- Still Python syntax validation
- Still Python code checks
- Still Python error patterns
- **Reason**: We validate Python code before execution

### 3. Routing Fixing - ADD YAML-BASED FIX ✅
- After Python execution succeeds → Extract netlist
- Convert to YAML
- Validate YAML netlist
- Fix spacing/routing in YAML
- Rebuild component from fixed YAML

### 4. New Module: Python → YAML → Fix → Rebuild
- Extract netlist from Python-generated component
- Convert to YAML
- Validate and fix
- Rebuild using `gf.read.from_yaml()`

## Implementation Plan

### Step 1: Add Netlist Extraction After Python Execution
```python
# In parse_and_execute_code() or after successful execution
component, error = parse_and_execute_code(code)
if component is not None:
    # Extract netlist
    netlist = component.get_netlist()
    # Convert to YAML
    yaml_str = yaml.dump(netlist, sort_keys=False)
    # Validate YAML
    # Fix if needed
    # Rebuild if fixed
```

### Step 2: Add YAML Validation
- Use existing `NetlistValidator`
- Check spacing in placements
- Check routing feasibility
- Check port connections

### Step 3: Add YAML Fixing
- Fix spacing in placements
- Fix routing issues
- Adjust port angles if needed

### Step 4: Rebuild from Fixed YAML
- Use `gf.read.from_yaml(fixed_yaml)`
- This handles routing automatically

## Benefits

1. **No Prompt Changes** - Keep existing Python prompts
2. **Better Validation** - YAML format easier to validate
3. **Better Fixing** - Can fix spacing/routing in YAML
4. **Automatic Routing** - `gf.read.from_yaml()` handles routing
5. **PhIDO-Inspired** - Netlist-based validation/fixing

## Files to Modify

1. ✅ `yaml_netlist_helper.py` - Already created
2. ⚠️ `gen_data_validated.py` - Add netlist extraction after Python execution
3. ⚠️ `gen_data_validated.py` - Add YAML validation/fixing step
4. ✅ `netlist_validator.py` - Already exists
5. ✅ `yaml_netlist_helper.py` - Already has fixing functions

## No Changes Needed

- ❌ `config.py` - Python prompts stay the same
- ❌ `component_spec_loader.py` - Still Python examples
- ❌ `pilot_validator.py` - Still Python syntax checks
- ❌ `pilot_prompt_updater.py` - Still Python error patterns


