# Problems File Clarification

## Question: Do problems need changes for YAML DSL?

**Answer: The problems in `Pic_set.txt` are fine as-is. They describe the circuit requirements, and the LLM will generate YAML DSL based on these descriptions.**

## Current Status

The `Pic_set.txt` file contains 36 problems with:
- Clear circuit descriptions
- Component requirements
- Parameter specifications
- Complexity levels

## What Happens

1. **Problem Description**: The LLM receives the problem text (e.g., "Create a Mach-Zehnder interferometer...")
2. **YAML DSL Generation**: The LLM generates YAML DSL netlist based on the problem description
3. **Framework Validation**: The framework validates the YAML DSL using:
   - YAML pilot validator (syntax, components, ports, routing, spacing)
   - Component builder (`gf.read.from_yaml()`)
   - DRC validator (generic_tech PDK)
   - LVS validator (optional)
   - Optimizers (device + circuit level)

## No Changes Needed

The problems are **descriptive** and don't need to be in YAML format themselves. The LLM converts the problem description into YAML DSL output.

## Example Flow

**Input (Problem):**
```
Problem 1 (MZI - Mach-Zehnder Interferometer) [Complexity 1]:
Create a Mach-Zehnder interferometer with a single optical input and output. Use:
• Two MMI1x2 (id: mmi1, mmi2)
• One phase shifter (id: phase_shifter)
```

**LLM Output (YAML DSL):**
```yaml
instances:
  mmi1:
    component: mmi1x2
  mmi2:
    component: mmi1x2
  phase_shifter:
    component: straight_heater_metal
placements:
  mmi1:
    x: 0.0
    y: 0.0
  mmi2:
    x: 250.0
    y: 0.0
  phase_shifter:
    x: 100.0
    y: 0.0
routes:
  optical:
    links:
      mmi1,o2: phase_shifter,o1
      phase_shifter,o2: mmi2,o1
ports:
  in: mmi1,o1
  out: mmi2,o2
```

## Summary

✅ **Problems file is ready - no changes needed**
- Problems are descriptive (not YAML)
- LLM converts descriptions to YAML DSL
- Framework validates and processes YAML DSL

