# YAML Netlist Integration - Using GDSFactory Native Support

## Why Use GDSFactory YAML? ✅

Based on [GDSFactory YAML documentation](https://gdsfactory.github.io/gdsfactory/notebooks/10_yaml_component.html):

1. **Native Support**: `gf.read.from_yaml()` is built-in and well-tested
2. **Automatic Routing**: YAML format handles routing automatically via `routes:` section
3. **Placement Control**: Explicit `placements:` section with X, Y coordinates
4. **Port Management**: Easy port exposure via `ports:` section
5. **Netlist Extraction**: `component.get_netlist()` can extract netlist from Python-generated components

## Proposed Flow

### Option 1: LLM Generates YAML Directly (Best)
```
LLM generates YAML netlist
    ↓
Parse YAML using NetlistValidator
    ↓
Validate routing feasibility, placement spacing
    ↓
If valid → Convert to component using gf.read.from_yaml()
    ↓
If invalid → Fix YAML netlist → Convert to component
```

### Option 2: Python → YAML Conversion (Fallback)
```
LLM generates Python code
    ↓
Execute in sandbox → Get component
    ↓
Extract netlist: netlist = component.get_netlist()
    ↓
Convert netlist to YAML format
    ↓
Validate YAML using NetlistValidator
    ↓
If issues → Fix YAML → Rebuild component using gf.read.from_yaml()
```

## YAML Format (GDSFactory Native)

```yaml
instances:
  mmi_splitter:
    component: mmi1x2
    settings:
      width_mmi: 4.5
      length_mmi: 10
  mmi_combiner:
    component: mmi1x2
    settings:
      width_mmi: 4.5
      length_mmi: 10

placements:
  mmi_splitter:
    x: 0
    y: 0
  mmi_combiner:
    x: 250
    y: 0
    mirror: True

routes:
  optical:
    settings:
      cross_section: strip
      radius: 15
      separation: 15
    links:
      mmi_splitter,o2: phase_shifter1,o1
      mmi_splitter,o3: phase_shifter2,o1
      phase_shifter1,o2: mmi_combiner,o1
      phase_shifter2,o2: mmi_combiner,o2

ports:
  o1: mmi_splitter,o1
  o2: mmi_combiner,o3
```

## Benefits

1. **Automatic Routing**: GDSFactory handles routing from YAML `routes:` section
2. **Spacing Control**: Explicit placements prevent routing collisions
3. **Validation**: Can validate YAML structure before conversion
4. **Fixable**: Can modify YAML netlist to fix spacing/routing issues
5. **PhIDO-Compatible**: Similar to PhIDO's netlist-based approach

## Implementation Plan

1. **Add YAML prompt option** to LLM (ask for YAML netlist)
2. **Integrate `gf.read.from_yaml()`** for YAML → Component conversion
3. **Use `component.get_netlist()`** for Python → YAML extraction
4. **Validate YAML** using our `NetlistValidator` (check spacing, routing feasibility)
5. **Fix YAML** if validation fails (adjust placements, routes)
6. **Rebuild component** from fixed YAML using `gf.read.from_yaml()`

## Code Changes Needed

1. **Add YAML prompt template** in `config.py`
2. **Add YAML parser** in `gen_data_validated.py`
3. **Add netlist extraction** from Python components
4. **Add YAML validation** before conversion
5. **Add YAML fixer** for spacing/routing issues
6. **Use `gf.read.from_yaml()`** instead of custom converter


