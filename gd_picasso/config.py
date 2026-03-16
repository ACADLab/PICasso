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

# Create output directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FALSE_EXAMPLES_YAML_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# YAML DSL Prompt Template
# ============================================================================

# System prompt (embedded in injection)
SYSTEM_PROMPT = """You are a photonic circuit synthesis engine.

Your job is to generate valid YAML photonic circuits compatible with gdsfactory's generic_tech PDK.

You must strictly follow these three items:

1. YAML DSL SPECIFICATION
2. CANONICAL YAML TEMPLATE
3. STRICT OUTPUT RULES"""

YAML_DSL_PROMPT_TEMPLATE = """
{system_prompt}

===================================================
### YAML DSL SPECIFICATION
===================================================

Top-level keys (all required):
- instances
- placements
- routes (for connections - NOT 'connections')
- ports

------------------------------------------
INSTANCES
------------------------------------------
instances:
  <id>:
    component: <component_name>
    settings:
      <parameter>: <value>

Rules:
- <id> must be unique.
- component must be from ALLOWED_COMPONENTS.
- settings may be {{}} if empty.
- Numeric values must be raw numbers.

------------------------------------------
PLACEMENTS
------------------------------------------
placements:
  <instance_id>:
    x: <float>
    y: <float>
    rotation: <0|90|180|270>
    mirror: <true|false>

Rules:
- Each instance appears exactly once as a key.
- rotation ∈ {{0,90,180,270}}.
- placements is a DICTIONARY (not a list).

------------------------------------------
ROUTES (for connections)
------------------------------------------
routes:
  optical:
    settings:
      cross_section: strip
      radius: 20.0
    links:
      <instance1>,<port1>: <instance2>,<port2>

Rules:
- Use 'routes' section (NOT 'connections').
- routes.optical.links is a DICTIONARY (not a list).
- Format: "source_instance,port: target_instance,port"

------------------------------------------
PORTS
------------------------------------------
ports:
  <exported_port_name>: <instance_id>,<port>

Rules:
- ports is a DICTIONARY (not a list).
- Format: "port_name: instance,port"

------------------------------------------
ALLOWED COMPONENTS (generic_tech PDK)
------------------------------------------
⚠️ CRITICAL: Use ONLY these components. Others do NOT exist in generic_tech PDK!

✅ Available components:
- straight (NOT 'waveguide')
- bend_euler
- mmi1x2 (use with mirror: true for 2x1 combiner - mmi2x1 does NOT exist)
- mmi2x2
- coupler (NOT 'dc_2x2')
- mzi
- ring_single
- straight_heater_metal (NOT 'phase_shifter' or 'heater')
- taper
- spiral
- grating_coupler_elliptical
- crossing
- bend_s
- bend_circular

❌ Components that DO NOT exist (use alternatives):
- mmi2x1 → Use mmi1x2 with mirror: true
- phase_shifter → Use straight_heater_metal
- heater → Use straight_heater_metal
- y_splitter → Use coupler or mmi1x2
- y_junction → Use coupler or mmi1x2
- dc_2x2 → Use coupler
- waveguide → Use straight
- star_coupler → Use coupler or mmi2x2
- photodiode → Not available in generic_tech PDK

------------------------------------------
VALID PORT NAMES (gdsfactory standard)
------------------------------------------
straight: o1, o2
bend_euler: o1, o2
mmi1x2: o1, o2, o3 (o1=input, o2/o3=outputs)
mmi2x2: o1, o2, o3, o4
mzi: o1, o2
coupler: o1, o2, o3, o4
ring_single: o1, o2
straight_heater_metal: o1, o2

===================================================
### CANONICAL YAML TEMPLATE (REFERENCE)
===================================================

instances:
  splitter:
    component: mmi1x2
    settings: {{}}
  phase:
    component: straight_heater_metal
    settings: {{length: 20}}
  combiner:
    component: mmi1x2
    settings: {{}}

placements:
  splitter:
    x: 0
    y: 0
    rotation: 0
    mirror: false
  phase:
    x: 40
    y: 0
    rotation: 0
    mirror: false
  combiner:
    x: 80
    y: 0
    rotation: 0
    mirror: true

routes:
  optical:
    settings:
      cross_section: strip
      radius: 20.0
    links:
      splitter,o2: phase,o1
      phase,o2: combiner,o1

ports:
  in: splitter,o1
  out: combiner,o2

===================================================
### STRICT OUTPUT RULES
===================================================

- Output **YAML only** (no text or commentary).
- No comments (# ...).
- No invented components or ports.
- All components must be from ALLOWED_COMPONENTS.
- All ports must be valid.
- Must follow DSL structure exactly.
- Must be loadable by gf.read.from_yaml().
- Do NOT perform optimization; only layout topology.

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
  phase_arm:
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
  phase_arm:
    x: 100.0
    y: 0.0
routes:
  optical:
    settings:
      cross_section: strip
      radius: 20.0
    links:
      mmi_splitter,o2: phase_arm,o1
      phase_arm,o2: mmi_combiner,o1
ports:
  in: mmi_splitter,o1
  out: mmi_combiner,o2
```

CRITICAL RULES (READ CAREFULLY):

1. Spacing Rules:
   - Keep components compact: 50-100um spacing is fine.
   - Vertical offset between parallel arms: 50um is sufficient.
   - Route radius: >= 20um
   - Route separation: >= 20um
   - DO NOT over-space (200-300um gaps make routing much harder).

2. Routing Rules:
   - ALL components MUST be connected via routes.
   - Routes section is REQUIRED if you have multiple components.
   - Route format: 'source_instance,port: target_instance,port'
   - Use 'routes.optical.links' for optical connections.
   - For MZI combiners with mirror: true, the INPUT port is o1.
     Route TO combiner,o2 and combiner,o3 (NOT combiner,o1).

3. Component Rules:
   - Use valid GDSFactory component names (e.g., 'mmi1x2', 'bend_euler', 'straight_heater_metal')
   - Component names must match exactly (case-sensitive).
   - WARNING: mmi2x1 does NOT exist! Use mmi1x2 and set mirror: true.

4. Port Name Rules:
   - Port names are LITERAL STRINGS: o1, o2, o3, o4 etc.
   - NEVER use arithmetic in port names. WRONG: o4-1, o3+1, o2*1.
     CORRECT: o3, o4, o2.  Compute the number yourself and write the result.
   - All numeric values must be literal numbers. WRONG: 4-1, 3+1. CORRECT: 3, 4.

5. Placements Rules:
   - Placements ONLY contain: x, y, rotation, mirror.
   - NEVER put 'component' or 'settings' inside placements.
     Those belong ONLY in 'instances'.
   - WRONG:
       placements:
         ps1:
           component: straight_heater_metal   # FORBIDDEN here
           settings: {{length: 50}}              # FORBIDDEN here
           x: 100
   - CORRECT:
       instances:
         ps1:
           component: straight_heater_metal
           settings: {{length: 50}}
       placements:
         ps1:
           x: 100
           y: 0

6. Syntax Rules:
   - Valid YAML syntax: proper indentation, no tabs (use spaces).
   - No Unicode characters (see above).
   - All numeric values must be valid floats (e.g., 10.0, not '10 microns').

===================================================
### MULTI-COMPONENT ROUTING EXAMPLE (generic pattern)
===================================================

This example shows how to route a design with TWO parallel arms
(splitter -> arm components -> combiner).  Adapt the number of
arms and components to the problem.

instances:
  sp:
    component: mmi1x2
    settings: {{}}
  arm_upper:
    component: straight_heater_metal
    settings: {{length: 80}}
  arm_lower:
    component: straight
    settings: {{length: 80}}
  cb:
    component: mmi1x2
    settings: {{}}

placements:
  sp:
    x: 0
    y: 0
  arm_upper:
    x: 80
    y: 30
  arm_lower:
    x: 80
    y: -30
  cb:
    x: 200
    y: 0
    mirror: true

routes:
  optical:
    settings:
      cross_section: strip
      radius: 20.0
    links:
      sp,o2: arm_upper,o1
      sp,o3: arm_lower,o1
      arm_upper,o2: cb,o2
      arm_lower,o2: cb,o3

ports:
  in: sp,o1
  out: cb,o1

KEY PATTERNS TO FOLLOW:
  - Splitter outputs (o2, o3) fan out to arm inputs (o1).
  - Arm outputs (o2) converge on combiner inputs (o2, o3).
  - Combiner has mirror: true so its o2/o3 face the arms.
  - Combiner output is o1 (faces away from the arms).
  - For NESTED sub-circuits (e.g. MZMs inside a larger design),
    repeat the splitter-arms-combiner pattern for each sub-block,
    then connect sub-block outputs to the next stage.

{component_injection}

{pilot_prompt}

Your response MUST be ONLY the YAML DSL netlist (no explanations, no markdown code blocks, just the YAML).
"""

# Vanilla prompt (Phase 1 - no injection, no pilot)
VANILLA_PROMPT_TEMPLATE = """
{system_prompt}

===================================================
### YAML DSL SPECIFICATION
===================================================

Top-level keys (all required):
- instances
- placements
- routes (for connections - NOT 'connections')
- ports

See CANONICAL YAML TEMPLATE below for structure.

===================================================
### CANONICAL YAML TEMPLATE (REFERENCE)
===================================================

instances:
  splitter:
    component: mmi1x2
    settings: {{}}
  phase:
    component: straight_heater_metal
    settings: {{length: 20}}
  combiner:
    component: mmi1x2
    settings: {{}}

placements:
  splitter:
    x: 0
    y: 0
    rotation: 0
    mirror: false
  phase:
    x: 40
    y: 0
    rotation: 0
    mirror: false
  combiner:
    x: 80
    y: 0
    rotation: 0
    mirror: true

routes:
  optical:
    settings:
      cross_section: strip
      radius: 20.0
    links:
      splitter,o2: phase,o1
      phase,o2: combiner,o1

ports:
  in: splitter,o1
  out: combiner,o2

===================================================
### STRICT OUTPUT RULES
===================================================

- Output **YAML only** (no text or commentary).
- No comments (# ...).
- No invented components or ports.
- Must follow DSL structure exactly.
- Must be loadable by gf.read.from_yaml().
- Do NOT perform optimization; only layout topology.

CRITICAL: ASCII ONLY - NO UNICODE! Use 'um' NOT 'µm', 'x' NOT '×', '->' NOT '→', 'DeltaL' NOT 'ΔL'.

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
ENABLE_SAX_CHECK = True  # Functional validation using SAX
SAX_TIMEOUT = 30  # Maximum time for SAX compilation (seconds)
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

