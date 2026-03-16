# PICasso Framework - Complete Documentation

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Workflow Flowchart](#workflow-flowchart)
4. [Two-Phase Testing](#two-phase-testing)
5. [System Prompt & Injection](#system-prompt--injection)
6. [Pilot Prompt & Updates](#pilot-prompt--updates)
7. [Validation Stages](#validation-stages)
8. [DRC Validation](#drc-validation)
9. [LVS Validation](#lvs-validation)
10. [Optimization](#optimization)
11. [Metrics Calculation](#metrics-calculation)
12. [Result Organization](#result-organization)
13. [Usage Commands](#usage-commands)

---

## Overview

PICasso is a framework for automated photonic integrated circuit (PIC) design using Large Language Models (LLMs). The framework uses a YAML DSL approach where the LLM directly outputs YAML netlists compatible with GDSFactory's `generic_tech` PDK.

### Key Features
- **YAML DSL Generation**: LLM generates YAML netlists directly (no Python code)
- **Pre-execution Validation**: Pilot validator catches errors before component building
- **Retry Logic with Feedback**: LLM learns from errors and fixes them iteratively
- **DRC Validation**: Real design rule checking using `generic_tech` PDK and KLayout
- **LVS Validation**: Layout vs Schematic verification
- **Two-Level Optimization**: Device-level and circuit-level optimization
- **Comprehensive Metrics**: Spec@k, OptEff, RobustPass, Overall Robustness Score

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PICasso Framework                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Phase 1    │    │   Phase 2    │    │   Metrics    │  │
│  │   Vanilla    │───▶│   PICasso    │───▶│  Collection  │  │
│  │    LLM       │    │  Framework   │    │              │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Component Pipeline                       │   │
│  │  LLM → YAML → Validation → Build → DRC → LVS → Opt  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflow Flowchart

```
START
  │
  ├─▶ Load Problem (1-36)
  │
  ├─▶ PHASE 1: Vanilla LLM
  │   │
  │   ├─▶ System Prompt + Problem → LLM
  │   ├─▶ Generate YAML DSL
  │   ├─▶ Build Component (gf.read.from_yaml)
  │   ├─▶ Save Results (vanilla/)
  │   └─▶ Calculate Metrics
  │
  ├─▶ PHASE 2: PICasso Framework
  │   │
  │   ├─▶ System Prompt + Injection + Pilot + Problem → LLM
  │   │
  │   ├─▶ YAML Pilot Validation
  │   │   ├─▶ ASCII Check
  │   │   ├─▶ YAML Syntax
  │   │   ├─▶ Component Names
  │   │   ├─▶ Component Parameters
  │   │   ├─▶ Port Names
  │   │   ├─▶ Spacing (200um min)
  │   │   └─▶ Routing Completeness
  │   │
  │   ├─▶ Retry Logic (MAX_RETRY_ATTEMPTS = 2)
  │   │   ├─▶ If validation fails → Send feedback → Retry
  │   │   └─▶ If build fails → Send error → Retry
  │   │
  │   ├─▶ Build Component (gf.read.from_yaml)
  │   │
  │   ├─▶ Auto-Fix Routing Collisions (if detected)
  │   │   ├─▶ Try iterative spacing fixes (1.5x, 2.0x, 2.5x)
  │   │   └─▶ If fails → Try rotation algorithm (0°, 90°, 180°, 270°)
  │   │
  │   ├─▶ DRC Validation
  │   │   ├─▶ Generate DRC Script (generic_tech)
  │   │   ├─▶ Run KLayout DRC
  │   │   └─▶ Parse Violations
  │   │
  │   ├─▶ LVS Validation (optional)
  │   │   ├─▶ Compare Layout vs Schematic
  │   │   └─▶ Report Mismatches
  │   │
  │   ├─▶ Silicon Efficiency Validation
  │   │   ├─▶ Detect unconnected components
  │   │   ├─▶ Detect dangling components
  │   │   └─▶ Calculate excess silicon ratio
  │   │
  │   ├─▶ Port Connection Validation
  │   │   ├─▶ Detect same port connections
  │   │   ├─▶ Detect ports connected to multiple ports
  │   │   └─▶ Validate one-to-one port connections
  │   │
  │   ├─▶ Device-Level Optimization
  │   │   ├─▶ Optimize Component Geometries
  │   │   └─▶ Target: Match Literature Losses
  │   │
  │   ├─▶ Circuit-Level Optimization
  │   │   ├─▶ Optimize Phase Shifters/Couplings
  │   │   └─▶ Target: Minimize Circuit IL (σ₁²(T))
  │   │
  │   ├─▶ Save Results (picasso/)
  │   └─▶ Calculate Metrics
  │
  └─▶ END
```

---

## Two-Phase Testing

The framework runs two phases for each problem:

### Phase 1: Vanilla LLM
- **Input**: System prompt + Problem description only
- **No injection**: No component specifications
- **No pilot**: No validation rules
- **No retry**: Single attempt
- **Purpose**: Baseline performance (what LLM can do without help)

### Phase 2: PICasso Framework
- **Input**: System prompt + Component injection + Pilot prompt + Problem description
- **Injection**: Component specifications, parameters, ports, YAML examples
- **Pilot**: Validation rules, error patterns, restrictions
- **Retry**: Up to MAX_RETRY_ATTEMPTS (default: 2) with feedback
- **Purpose**: Framework-enhanced performance

---

## System Prompt & Injection

### System Prompt

The system prompt is embedded in the injection and provides the core instructions:

```
You are a photonic circuit synthesis engine.

Your job is to generate valid YAML photonic circuits compatible with gdsfactory's generic_tech PDK.

You must strictly follow these three items:

1. YAML DSL SPECIFICATION
2. CANONICAL YAML TEMPLATE
3. STRICT OUTPUT RULES
```

**Full system prompt** (see `gd_picasso/config.py`):
- YAML DSL specification (instances, placements, connections, ports)
- Allowed components list
- Valid port names
- Canonical YAML template
- Strict output rules (YAML only, no comments, no invented components)

### Component Injection

The injection provides component-specific information to guide the LLM:

**Example Injection (excerpt)**:
```
======================================================================
COMPONENT SPECIFICATIONS (YAML DSL FORMAT)
======================================================================

⚠️ CRITICAL: Use ONLY these components. Verify component names exist before using!

Component: mmi1x2
  Ports (3 total):
    - o1 (orientation: 180.0°) (width: 500nm)
    - o2 (orientation: 0.0°) (width: 500nm)
    - o3 (orientation: 0.0°) (width: 500nm)
  Valid Parameters: width, width_taper, length_taper, length_mmi, width_mmi, gap_mmi
    - width_taper (default: 1.0) [float]
    - length_taper (default: 10.0) [float]
    - length_mmi (default: 5.5) [float]
    - width_mmi (default: 2.5) [float]
    - gap_mmi (default: 0.25) [float]
  YAML DSL Example:
    instances:
      mmi1x2:
        component: mmi1x2
        settings:
          width_taper: 1.0
          length_taper: 10.0
          length_mmi: 5.5
    placements:
      mmi1x2:
        x: 0.0
        y: 0.0
    ports:
      in: mmi1x2,o1
      out: mmi1x2,o2
  ⚠️ WARNING: mmi2x1 does NOT exist! Use mmi1x2 with mirror: true

Component: straight_heater_metal
  Ports (2 total):
    - o1 (orientation: 180.0°) (width: 500nm)
    - o2 (orientation: 0.0°) (width: 500nm)
  Valid Parameters: length, width, cross_section
    - length (default: 10.0) [float]
    - width (default: None) [float | None]
  YAML DSL Example:
    instances:
      phase_shifter:
        component: straight_heater_metal
        settings:
          length: 100.0
    placements:
      phase_shifter:
        x: 0.0
        y: 0.0
    ports:
      in: phase_shifter,o1
      out: phase_shifter,o2

======================================================================
COMMON ERROR PATTERNS TO AVOID
======================================================================

1. Missing Routes:
   ❌ WRONG: Components placed but no routes section
   ✅ CORRECT: Always include routes section with all connections

2. Spacing Violations:
   ❌ WRONG: Components too close (< 200um)
   ✅ CORRECT: Minimum 200um spacing between components

3. Invalid Parameters:
   ❌ WRONG: mmi1x2 with 'length' parameter
   ✅ CORRECT: Use 'length_mmi' instead

4. Unicode Characters:
   ❌ WRONG: 'µm', '×', '→', 'ΔL'
   ✅ CORRECT: 'um', 'x', '->', 'DeltaL'
```

**Injection Generation**:
- Loaded once at framework startup
- Generated by `ComponentSpecLoader.generate_yaml_dsl_injection()`
- Uses `inspect.signature()` to extract actual function parameters
- Includes port information (names, orientations, widths)
- Provides YAML DSL examples for each component
- Lists common error patterns to avoid

---

## Pilot Prompt & Updates

### Base Pilot Prompt

The pilot prompt contains validation rules and restrictions:

**Example Pilot Prompt (excerpt)**:
```
======================================================================
PILOT VALIDATION RULES
======================================================================

RULE #0 - MOST CRITICAL: ASCII ONLY - NO UNICODE!
⚠️⚠️⚠️ MANDATORY: Use ONLY ASCII characters! ⚠️⚠️⚠️
  - Use 'um' NOT 'µm' (micro symbol)
  - Use 'x' NOT '×' (multiplication symbol)
  - Use '->' NOT '→' (arrow symbol)
  - Use 'DeltaL' NOT 'ΔL' (Greek delta)

RULE #1 - Spacing Requirements:
  - MINIMUM 200um spacing between components (MANDATORY)
  - Simple designs (≤5 components): 200um minimum
  - Complex designs (>5 components): 250um+ spacing required
  - Vertical stacking: Use +/-100um or more vertical offset
  - Horizontal placement: 250-300um separation
  - Route radius: >= 20um
  - Route separation: >= 20um

RULE #2 - Component Parameters:
  - Use ONLY valid parameters from component function signature
  - Common mistake: mmi1x2 does NOT have 'length' parameter
  - Use 'length_mmi' instead of 'length' for MMI components
  - Check component.ports to see available ports

RULE #3 - Routing Requirements:
  - ALL components MUST be connected via routes
  - Routes section is REQUIRED if you have multiple components
  - Route format: 'source_instance,port: target_instance,port'
  - Use 'routes.optical.links' for optical connections

RULE #4 - Port Names:
  - Port names must match component port names exactly
  - Common ports: 'o1', 'o2', 'o3', 'o4'
  - Ports are labeled clockwise: o1 (left-bottom), o2 (left-top), etc.
  - All optical ports MUST be connected (no dangling ports)

RULE #5 - Syntax Requirements:
  - Valid YAML syntax: proper indentation, no tabs (use spaces)
  - No Unicode characters (see RULE #0)
  - All numeric values must be valid floats (e.g., 10.0, not '10 microns')
  - No comments (# ...) in YAML output
```

### Pilot Prompt Updates

The pilot prompt is **dynamically updated** based on observed failures:

**Update Mechanism**:
1. After each sample failure, `PilotPromptUpdater` analyzes the error
2. Extracts error patterns (syntax, component, routing, spacing, etc.)
3. Generates new rules with fix examples
4. Appends to pilot prompt for subsequent attempts

**Example Update**:
```
LEARNED RULE (from failure analysis):

ERROR: Invalid parameter 'length' for mmi1x2
FIX: Use 'length_mmi' instead of 'length'
EXAMPLE:
  ❌ WRONG:
    settings:
      length: 10.0
  ✅ CORRECT:
    settings:
      length_mmi: 10.0
```

**Pilot Prompt Storage**:
- Base rules: Hardcoded in `BasePilotGenerator.get_base_pilot_restrictions()`
- Learned rules: Saved to `pilot_rules.json`
- Rules accumulate across runs (permanent learning)

---

## Validation Stages

### Stage 1: YAML Pilot Validation (Pre-execution)

**Purpose**: Catch errors before component building

**Checks**:
1. **ASCII Only**: Detects Unicode characters (µm, ×, →, ΔL)
2. **YAML Syntax**: Valid YAML structure (indentation, brackets, quotes)
3. **Required Fields**: `instances`, `placements` sections exist
4. **Component Names**: Valid GDSFactory component names (checks `gf.components`)
5. **Component Parameters**: Valid parameters (uses `inspect.signature()`)
6. **Port Names**: Valid port names (common patterns: o1, o2, o3, etc.)
7. **Spacing**: Minimum 200um spacing between components
8. **Routing**: Routes section exists if multiple components

**Implementation**: `gd_picasso/validators/yaml_pilot_validator.py`

**Example Error Detection**:
```python
# Invalid parameter detected
Invalid parameters: mmi1.mmi1x2: invalid parameter 'length'
Valid parameters for mmi1x2: width, width_taper, length_taper, length_mmi, width_mmi, gap_mmi, taper, straight, cross_section
```

### Stage 2: Component Building

**Purpose**: Build GDSFactory component from YAML DSL

**Implementation**:
```python
component = gf.read.from_yaml(yaml_string)
```

**Error Handling**:
- If build fails → Extract error message
- Send error to LLM for retry
- Common errors: routing collisions, port angle mismatches, missing components

### Stage 2.5: Auto-Fix Routing Collisions

**Purpose**: Automatically fix routing collisions and placement issues

**Implementation**: `gd_picasso/utils/yaml_routing_fixer.py`

**Process**:
1. After component build, try to get netlist
2. If routing collision or port connection error detected:
   - **Iterative Spacing Fixes**: Try spacing multipliers (1.5x, 2.0x, 2.5x)
     - Extract netlist from component
     - Convert to YAML
     - Apply spacing multiplier to placements
     - Rebuild component from fixed YAML
     - Test if routing collision resolved
   - **Rotation Algorithm**: If spacing fails, try brute-force rotation
     - Try all 4 orientations (0°, 90°, 180°, 270°) for each component
     - Timeout: 120 seconds
     - Component limit: 8 (4^8 = 65K combinations)
3. If successful, replace component with fixed version

**Integration**: Automatically triggered after component build (Step 3.5 in `test_with_llm.py`)

### Stage 3: DRC Validation

See [DRC Validation](#drc-validation) section below.

### Stage 4: LVS Validation

See [LVS Validation](#lvs-validation) section below.

### Stage 4.5: Silicon Efficiency Validation

**Purpose**: Detect extra silicon, unconnected components, and unnecessary routing

**Implementation**: `gd_picasso/validators/silicon_efficiency_validator.py`

**Checks**:
1. **Unconnected Components**: Components not in routing graph
2. **Dangling Components**: Components with no connections
3. **Excess Silicon Ratio**: Ratio of unused silicon area

**Integration**: After LVS validation, before SAX validation (Step 5.3)

### Stage 4.6: Port Connection Validation

**Purpose**: Detect same port connections and validate port connection graph

**Implementation**: `gd_picasso/validators/port_connection_validator.py`

**Checks**:
1. **Same Port Connections**: Ports connected to themselves
2. **Multiple Connections**: Ports connected to multiple other ports
3. **One-to-One Validation**: Each port should connect to exactly one other port

**Integration**: After silicon efficiency validation, before SAX validation (Step 5.4)

---

## DRC Validation

### Overview

DRC (Design Rule Check) validates that the layout meets fabrication design rules using the `generic_tech` PDK (real, not toy).

### Implementation

**File**: `gd_picasso/validators/drc_validator.py`

**Process**:
1. **Generate DRC Script**:
   ```python
   from gdsfactory.generic_tech import LAYER
   from gplugins.klayout.drc.write_drc import write_drc_deck_macro
   
   write_drc_deck_macro(
       layers=LAYER,
       rules="all",  # Use all rules from generic_tech
       output="generic_tech_drc.lym"
   )
   ```

2. **Export Component to GDS**:
   ```python
   component.write_gds("circuit.gds")
   ```

3. **Run KLayout DRC**:
   ```bash
   klayout -b -r generic_tech_drc.lym \
           -rd input_gds=circuit.gds \
           -rd report=circuit_drc_report.lydrb
   ```

4. **Parse DRC Report**:
   - Empty report = No violations = PASS
   - Non-empty report = Violations found = FAIL
   - Count violations for detailed feedback

### generic_tech PDK

**What is generic_tech?**
- Realistic PDK (not toy) with actual design rules
- Includes layer definitions, spacing rules, width rules, etc.
- Used by GDSFactory for realistic circuit design

**How is it used?**
- `LAYER` from `gdsfactory.generic_tech` defines all layers (WG, SLAB, etc.)
- DRC rules are generated from these layers
- KLayout runs the DRC script against the GDS file

**Example DRC Rules**:
- Minimum waveguide width: 0.2 µm
- Minimum spacing: 0.2 µm
- Minimum bend radius: 5 µm
- Minimum enclosure: 0.1 µm

### DRC Report Structure

```
DRC Validation Result:
  - passed: bool
  - violations: int (0 = PASS, >0 = FAIL)
  - errors: List[str]
  - warnings: List[str]
  - drc_report_path: str (path to .lydrb file)
```

### Feedback to LLM

If DRC fails, feedback is sent:
```
DRC VIOLATIONS: 3 found

SUGGESTIONS FOR FIXING:
  - Increase spacing between components (minimum 200um)
  - Use larger bend radius (>= 20um)
  - Check that routes don't cross or overlap
  - Ensure proper clearance from waveguides
```

---

## LVS Validation

### Overview

LVS (Layout Versus Schematic) validates that the layout matches the schematic netlist.

### Implementation

**File**: `gd_picasso/validators/lvs_validator.py`

**Process**:
1. **Extract Netlists**:
   ```python
   layout_netlist = layout_component.get_netlist()
   schematic_netlist = schematic_component.get_netlist()
   ```

2. **Run LVS**:
   ```python
   from gdsfactory.utils.lvs import lvs
   
   lvs_result = lvs(layout_component, schematic_component)
   ```

3. **Check Result**:
   - `matched = True` → PASS
   - `matched = False` → FAIL (mismatches reported)

### LVS Comparison

**What is compared?**
- **Instances**: Same components in layout and schematic
- **Ports**: Same ports in layout and schematic
- **Nets**: Same connections in layout and schematic

**Mismatch Detection**:
- Missing instances in layout
- Extra instances in layout
- Port mismatches
- Net mismatches (wrong connections)

### LVS Report Structure

```
LVS Validation Result:
  - passed: bool
  - matched: bool
  - mismatches: Dict[str, List]
    - 'instances': List of missing/extra instances
    - 'ports': List of port mismatches
    - 'nets': List of net mismatches
```

### Scalability

- LVS can be slow for large circuits (>100 components)
- Can be disabled via `ENABLE_LVS_CHECK = False`
- Currently skipped for large circuits in framework

---

## Optimization

### Two-Level Optimization

The framework implements **two-level optimization**:

1. **Device-Level**: Optimize component geometries to match target losses
2. **Circuit-Level**: Optimize phase shifters/couplings to minimize circuit loss

### Device-Level Optimization

**File**: `gd_picasso/optimizers/device_optimizer.py`

**Objective**: Match target losses from literature

**Target Losses** (from `loss_ppt.pdf`):
```python
DEVICE_LOSS_TARGETS = {
    'mmi1x2': 0.3,          # dB
    'bend_euler': 0.086,    # dB
    'straight_heater_metal': 0.23,  # dB
    'y_branch': 0.28,       # dB
}
```

**Process**:
1. For each component type, define parameter ranges (width, length, gap, etc.)
2. Use SAX to simulate S-parameters for each geometry
3. Calculate insertion loss: `IL = -10*log10(|S21|^2)`
4. Minimize: `|IL - target_IL|`
5. Return optimized geometry

**Parameter Constraints** (geometry bounds):
```
MMI 1x2:    width ∈ [2.0, 6.0] µm,    length ∈ [5.0, 25.0] µm
MMI 1x4:    width ∈ [4.0, 8.0] µm,    length ∈ [10.0, 30.0] µm
Y-branch:   width ∈ [0.4, 1.0] µm,    taper_length ∈ [5.0, 20.0] µm
Bend:       radius ∈ [1.0, 50.0] µm
Phase shifter: length ∈ [5.0, 20.0] µm
Directional coupler: length ∈ [10.0, 20.0] µm, gap ∈ [0.1, 0.3] µm
```

**Formula**:
```
For component i:
  IL_i = -10 * log10(|S21_i|^2)
  Loss_i = |IL_i - target_IL_i|
  Minimize: Loss_i
  Subject to: geometry_params ∈ [bounds]
```

**Example**:
```python
# Optimize MMI 1x2
optimizer = DeviceOptimizer()
result = optimizer.optimize_component('mmi1x2', target_loss_db=0.3)

# Result:
{
    'success': True,
    'component_type': 'mmi1x2',
    'target_loss_db': 0.3,
    'achieved_loss_db': 0.32,
    'optimized_params': {
        'width': 4.0,
        'length_mmi': 10.0
    },
    'method': 'sax_simulation'
}
```

### Circuit-Level Optimization

**File**: `gd_picasso/optimizers/optimization_integration.py`

**Objective**: Minimize circuit insertion loss using σ₁²(T) approach

**Formula** (from `loss_ppt.pdf`):
```
For circuit with transfer matrix T:
  σ₁²(T) = largest singular value squared of T
  IL_circuit = -10 * log10(σ₁²(T))
  Minimize: IL_circuit
```

**Process**:
1. Extract circuit netlist
2. Build SAX circuit from netlist
3. Compute transfer matrix T (transmission submatrix from S-parameters)
4. Calculate σ₁²(T) = largest singular value squared (maximum SAX metric)
5. Optimize phase shifters/couplings to minimize insertion loss (maximize σ₁²(T))

**Parameter Constraints** (tunable bounds):
```
Phase shifters:  φ ∈ [-π, π] radians
Couplers:        κ ∈ [0.1, 0.9] (coupling ratio)
```

**Implementation**:
```python
from gplugins.sax import circuit_from_netlist

# Build SAX circuit
circ = circuit_from_netlist(netlist, models=sax_models)

# Compute S-matrix
S = circ(wavelength=1.55e-6, **phase_params)

# Calculate σ₁²(T)
sigma_1_squared = np.linalg.svd(S)[1][0] ** 2

# Minimize
loss = -10 * np.log10(sigma_1_squared)
```

**Drive Parameter**:
- `drive="svd"` uses σ₁²(T) approach
- Verified in `optimization_integration.py`

---

## Metrics Calculation

### Metrics Overview

The framework computes six metrics:

1. **Spec@k_structural**: Structural specification satisfaction @k (Phase 1 - Vanilla LLM baseline)
2. **Spec@k_full**: Full specification satisfaction @k (Phase 2 - PICasso framework)
3. **OptEff**: Optimization efficiency (normalized IL reduction)
4. **RobustPass@k**: Robustness under perturbations
5. **Overall Robustness Score (R)**: Combined correctness + performance
6. **Pass@k**: Legacy structural pass rate metric

### Spec@k_structural (Structural Specification Satisfaction @k)

**Used For**: Both Phase 1 (Vanilla LLM) and Phase 2 (PICasso Framework) - Primary comparison metric

**Formula**:
```
Spec@k_structural = 1 - C(n-c_s, k) / C(n, k)

Where:
  n = total number of samples
  c_s = number of structurally valid samples
  k = number of samples to consider (default: 3)
```

**Definition**:
- **Structural Pass Criteria**:
  - ✅ YAML builds into gdsfactory component (`component_built = True`)
  - ✅ DRC passes (`drc_passed = True`)

**Purpose**: Primary comparison metric for both phases, showing structural correctness (YAML builds + DRC passes). Allows fair comparison between vanilla LLM and PICasso framework.

**Implementation**: `gd_picasso/metrics.py::compute_spec_at_k_structural()`

---

### Spec@k_full (Full Specification Satisfaction @k)

**Used For**: Evaluated separately for both Phase 1 and Phase 2 (comprehensive validation metric)

**Formula**:
```
Spec@k_full = 1 - C(n-c_f, k) / C(n, k)

Where:
  n = total number of samples
  c_f = number of samples passing structural AND functional AND optimization validation
  k = number of samples to consider (default: 3)
```

**Definition**:
- **Full Pass Criteria**:
  - ✅ **Structural Pass**: Component builds successfully, passes DRC
  - ✅ **Functional Pass**: Circuit behavior matches specification (SAX validation)
  - ✅ **Optimization Pass**: Optimization completed successfully (if enabled)

**Purpose**: Comprehensive validation metric evaluated separately for both phases. Shows full correctness including structural, functional, and optimization validation. Allows comparison of complete framework benefits.

**Implementation**: `gd_picasso/metrics.py::compute_spec_at_k_full()`

**Example**:
```python
results = [
    {'success': True, 'validation_reports': {'functional': {'passed': True}}},  # Pass
    {'success': True, 'validation_reports': {'functional': {'passed': False}}}, # Fail (functional)
    {'success': False, 'validation_reports': {'functional': {'passed': False}}}, # Fail (structural)
]

spec_at_3 = compute_spec_at_k(results, k=3)
# Result: 0.33 (1 out of 3 passes both structural and functional)
```

### OptEff (Optimization Efficiency)

**Formula**:
```
OptEff_i = (IL_before - IL_after) / (IL_before + ε)

Then clamped to [0, 1]:
  OptEff_i* = max(0, min(1, OptEff_i))

Where:
  IL_before = insertion loss before optimization
  IL_after = insertion loss after optimization
  ε = small constant to avoid division by zero (default: 0.1 dB)
```

**Definition**:
- Normalized improvement in insertion loss
- ε stabilization prevents division by zero
- Clamped to [0, 1] range (negative efficiency = optimization made things worse)

**Implementation**: `gd_picasso/metrics.py::compute_opt_efficiency()`

**Example**:
```python
result = {
    'validation_reports': {
        'optimization': {
            'circuit_loss_before_db': 2.0,  # 2.0 dB before
            'circuit_loss_after_db': 1.5    # 1.5 dB after
        }
    }
}

opt_eff = compute_opt_efficiency(result, epsilon=0.1)
# Result: (2.0 - 1.5) / (2.0 + 0.1) = 0.5 / 2.1 = 0.238
```

### RobustPass@k (Robustness Under Perturbations)

**Formula**:
```
For each spec-satisfying sample i:
  Robust_i = (1/M) * Σ(r_{i,j} for j=1..M)

Where:
  r_{i,j} = 1 if perturbed sample j passes spec, else 0
  M = number of perturbations (default: 10)

RobustPass = (1/c) * Σ(Robust_i for all spec-satisfying samples)

Where:
  c = number of spec-satisfying samples
```

**Definition**:
- For each sample that passes spec, generate M perturbed versions
- Check if perturbed versions still pass spec
- Average robustness across all spec-satisfying samples

**Perturbations**:
- Waveguide width offsets (1% std dev)
- Coupling variations (5% std dev)
- Loss noise (0.1 dB std dev)
- Wavelength drift (0.1 nm)
- Phase error (5% std dev)

**Implementation**: `gd_picasso/metrics.py::compute_robust_pass_score()`

**Note**: Currently placeholder (returns 0.8). Full implementation requires perturbation generation.

### Overall Robustness Score (R)

**Formula**:
```
R = Spec@k × (α + β·OptEff + γ·RobustPass)

Where:
  α + β + γ = 1 (default: α=0.5, β=0.2, γ=0.3)
  Spec@k = specification satisfaction @k
  OptEff = average optimization efficiency
  RobustPass = robustness under perturbations
```

**Properties**:
- **Correctness-gated**: If Spec@k = 0, then R = 0
- **Weighted combination**: OptEff and RobustPass contribute, but only if Spec@k is high
- **Range**: R ∈ [0, 1] by construction

**Implementation**: `gd_picasso/metrics.py::compute_overall_robustness()`

**Example**:
```python
spec_at_k = 0.8
avg_opt_eff = 0.3
robust_pass = 0.7

R = compute_overall_robustness(
    spec_at_k=0.8,
    opt_efficiency=0.3,
    robust_pass=0.7,
    alpha=0.5,
    beta=0.2,
    gamma=0.3
)
# Result: 0.8 × (0.5 + 0.2×0.3 + 0.3×0.7) = 0.8 × (0.5 + 0.06 + 0.21) = 0.8 × 0.77 = 0.616
```

---

## Result Organization

### Directory Structure

Results are organized by model and phase:

```
gd_picasso/output/
├── gpt-4o_results/
│   ├── vanilla/
│   │   ├── problem_1/
│   │   │   ├── sample_1/
│   │   │   │   ├── circuit.gds
│   │   │   │   ├── circuit.yaml
│   │   │   │   └── metrics.txt
│   │   │   ├── sample_2/
│   │   │   └── ...
│   │   ├── problem_2/
│   │   └── ...
│   ├── picasso/
│   │   ├── problem_1/
│   │   │   ├── sample_1/
│   │   │   │   ├── circuit.gds
│   │   │   │   ├── circuit.yaml
│   │   │   │   ├── metrics.txt
│   │   │   │   └── optimization_report.json
│   │   │   └── ...
│   │   └── ...
│   └── metrics.csv
├── deepseek-r1_results/
│   └── (same structure)
└── kimi2_results/
    └── (same structure)
```

### Metrics Files

**metrics.txt** (per sample):
```
Sample 1 Metrics:
  Structural Pass: True
  Functional Pass: True
  DRC Pass: True
  LVS Pass: True
  Optimization Done: True
  
  Pass@k: 1.0
  Spec@k: 1.0
  OptEff: 0.238
  RobustPass: 0.8
  Overall Robustness Score: 0.616
```

**metrics.csv** (aggregated):
```csv
problem_id,phase,model,sample_idx,structural_pass,functional_pass,drc_pass,lvs_pass,opt_done,pass_at_k,spec_at_k,opt_eff,robust_pass,robustness_score
1,vanilla,gpt-4o,1,True,True,True,True,False,1.0,1.0,0.0,0.0,0.5
1,picasso,gpt-4o,1,True,True,True,True,True,1.0,1.0,0.238,0.8,0.616
```

---

## Usage Commands

### Run Full Test Suite (36 problems, 5 samples each)

**GPT-4o**:
```bash
python gd_picasso/test_with_llm.py \
    --model gpt-4o \
    --problems gd_picasso/problems_parsed.txt \
    --num-problems 36 \
    --samples 5
```

**DeepSeek-R1**:
```bash
python gd_picasso/test_with_llm.py \
    --model deepseek-r1 \
    --problems gd_picasso/problems_parsed.txt \
    --num-problems 36 \
    --samples 5
```

**Kimi2**:
```bash
python gd_picasso/test_with_llm.py \
    --model kimi2 \
    --problems gd_picasso/problems_parsed.txt \
    --num-problems 36 \
    --samples 5
```

### Run Single Problem (for testing)

```bash
python gd_picasso/test_with_llm.py \
    --model gpt-4o \
    --problems gd_picasso/problems_parsed.txt \
    --num-problems 1 \
    --samples 1
```

### Run Vanilla Only (Phase 1)

```bash
python gd_picasso/test_with_llm.py \
    --model gpt-4o \
    --problems gd_picasso/problems_parsed.txt \
    --num-problems 36 \
    --samples 5 \
    --vanilla-only
```

### Run PICasso Only (Phase 2)

```bash
python gd_picasso/test_with_llm.py \
    --model gpt-4o \
    --problems gd_picasso/problems_parsed.txt \
    --num-problems 36 \
    --samples 5 \
    --picasso-only
```

---

## Summary

The PICasso framework provides:
- **YAML DSL generation** with pre-execution validation
- **Retry logic** with detailed feedback
- **DRC validation** using `generic_tech` PDK and KLayout
- **LVS validation** for layout vs schematic verification
- **Two-level optimization** (device and circuit)
- **Comprehensive metrics** (Spec@k, OptEff, RobustPass, R)
- **Organized results** by model and phase

The framework is ready for full testing with all 36 problems across multiple LLM models.

