"""
Configuration for gd_picasso framework.

YAML DSL prompt templates and framework settings.
"""

from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
FRAMEWORK_ROOT = Path(__file__).parent

# Output directories
OUTPUT_DIR = FRAMEWORK_ROOT / "output"
VALIDATION_OUTPUT_DIR = FRAMEWORK_ROOT / "validation"
FALSE_EXAMPLES_YAML_DIR = VALIDATION_OUTPUT_DIR / "false_examples_yaml"
PHIDO_EXAMPLES_DIR = VALIDATION_OUTPUT_DIR / "phido_failed_examples"

# Create output directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FALSE_EXAMPLES_YAML_DIR.mkdir(parents=True, exist_ok=True)
PHIDO_EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# YAML DSL Prompt Template
# ============================================================================

YAML_DSL_PROMPT_TEMPLATE = """
You are a professional photonic integrated circuit (PIC) designer. Your task is to generate a YAML DSL netlist for the requested circuit using GDSFactory components.

CRITICAL REQUIREMENT - READ THIS FIRST: ASCII ONLY - NO UNICODE!
⚠️⚠️⚠️ MANDATORY: Use ONLY ASCII characters in YAML DSL output! ⚠️⚠️⚠️
  * Use 'um' NOT 'µm' (micro symbol)
  * Use 'x' NOT '×' (multiplication symbol)
  * Use '->' NOT '→' (arrow symbol)
  * Use 'DeltaL' NOT 'ΔL' (Greek delta)
  * Unicode will cause YAML parsing errors!

YAML DSL Format (GDSFactory Native):

```yaml
instances:
  component_name:
    component: component_type
    settings:
      param1: value1
      param2: value2
placements:
  component_name:
    x: 0.0
    y: 0.0
    rotation: 0.0
    mirror: false
routes:
  optical:
    settings:
      cross_section: strip
      radius: 20.0
      separation: 20.0
    links:
      source_instance,port: target_instance,port
ports:
  in: instance_name,port
  out: instance_name,port
```

Example: MZI in YAML DSL

```yaml
instances:
  mmi_splitter:
    component: mmi1x2
    settings:
      width: 4.0
      length: 10.0
  mmi_combiner:
    component: mmi1x2
    settings:
      width: 4.0
      length: 10.0
  phase_shifter:
    component: straight_heater_metal
    settings:
      length: 100.0
placements:
  mmi_splitter:
    x: 0.0
    y: 0.0
  mmi_combiner:
    x: 250.0
    y: 0.0
    mirror: true
  phase_shifter:
    x: 100.0
    y: 0.0
routes:
  optical:
    settings:
      cross_section: strip
      radius: 20.0
    links:
      mmi_splitter,o2: phase_shifter,o1
      phase_shifter,o2: mmi_combiner,o1
ports:
  in: mmi_splitter,o1
  out: mmi_combiner,o2
```

CRITICAL RULES:

1. Spacing Rules (prevents routing collisions):
   - MINIMUM 200um spacing between components (MANDATORY)
   - Simple designs (≤5 components): 200um minimum
   - Complex designs (>5 components): 250um+ spacing required
   - Vertical stacking: Use +/-100um or more vertical offset
   - Horizontal placement: 250-300um separation
   - Route radius: >= 20um (not 15um)
   - Route separation: >= 20um

2. Routing Rules:
   - ALL components MUST be connected via routes
   - Routes section is REQUIRED if you have multiple components
   - Route format: 'source_instance,port: target_instance,port'
   - Use 'routes.optical.links' for optical connections

3. Component Rules:
   - Use valid GDSFactory component names (e.g., 'mmi1x2', 'bend_euler', 'straight_heater_metal')
   - Component names must match exactly (case-sensitive)
   - ⚠️ WARNING: mmi2x1 does NOT exist! Use mmi1x2 and set mirror: true

4. Port Rules:
   - Port names must match component port names exactly (typically 'o1', 'o2', 'o3', etc.)
   - Ports are labeled clockwise: o1 (left-bottom), o2 (left-top), o3 (right-top), etc.
   - All optical ports MUST be connected (no dangling ports)

5. Syntax Rules:
   - Valid YAML syntax: proper indentation, no tabs (use spaces)
   - No Unicode characters (see above)
   - All numeric values must be valid floats (e.g., 10.0, not '10 microns')

{component_injection}

{pilot_prompt}

Your response MUST be ONLY the YAML DSL netlist (no explanations, no markdown code blocks, just the YAML).
"""

# Component injection placeholder (will be filled by component_spec_loader)
COMPONENT_INJECTION_PLACEHOLDER = "{component_injection}"

# Pilot prompt placeholder (will be filled by base_pilot_generator)
PILOT_PROMPT_PLACEHOLDER = "{pilot_prompt}"

# ============================================================================
# Framework Settings
# ============================================================================

# Validation settings
ENABLE_YAML_PILOT_VALIDATION = True
ENABLE_DRC_CHECK = True
ENABLE_LVS_CHECK = True  # If scalable
ENABLE_AUTO_CORRECTION = True
ENABLE_DEVICE_OPTIMIZATION = True
ENABLE_CIRCUIT_OPTIMIZATION = True

# DRC settings
DRC_PDK = "generic_tech"  # Real PDK, not toy
DRC_LAYER_SOURCE = "gdsfactory.generic_tech.LAYER"

# Optimization settings
DEVICE_OPTIMIZATION_TARGETS = {
    'mmi1x2': 0.3,  # dB
    'bend_euler': 0.086,  # dB
    'straight_heater_metal': 0.23,  # dB
    'y_branch': 0.28,  # dB
}

CIRCUIT_OPTIMIZATION_DRIVE = "svd"  # Use σ₁²(T) approach

# Metrics settings
OPT_EFF_EPSILON = 0.1  # dB
ROBUST_PASS_NUM_PERTURBATIONS = 10
ROBUSTNESS_WEIGHTS = {
    'alpha': 0.5,  # Base weight
    'beta': 0.2,   # OptEff weight
    'gamma': 0.3,  # RobustPass weight
}

# Retry settings
MAX_RETRY_ATTEMPTS = 2  # Reduced to force better first attempts

