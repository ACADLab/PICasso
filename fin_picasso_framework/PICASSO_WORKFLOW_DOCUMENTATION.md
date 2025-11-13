# PICasso Framework - Complete Workflow Documentation

## Overview

PICasso is an enhanced framework for generating and validating photonic integrated circuit (PIC) designs using Large Language Models (LLMs). The framework provides comprehensive validation, error detection, feedback generation, and optimization to ensure generated designs are manufacturable and meet specifications.

## Table of Contents

1. [Complete Workflow](#complete-workflow)
2. [LLM Prompting](#llm-prompting)
3. [Validation Stages](#validation-stages)
4. [Feedback System](#feedback-system)
5. [Optimization](#optimization)
6. [DRC Validation](#drc-validation)
7. [Result Saving and Checkpoints](#result-saving-and-checkpoints)
8. [Error Handling and Robustness](#error-handling-and-robustness)

---

## Complete Workflow

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PICASSO FRAMEWORK WORKFLOW                       │
└─────────────────────────────────────────────────────────────────────┘

1. INPUT QUALITY VALIDATION
   ├─ Validate problem description
   ├─ Check for Unicode characters
   └─ Sanitize input

2. PROMPT ENHANCEMENT
   ├─ Add component reference snippets
   ├─ Inject design restrictions
   ├─ Add SAX knowledge (if enabled)
   └─ Format prompt for LLM

3. LLM INFERENCE
   ├─ First attempt: Vanilla LLM (baseline)
   ├─ Retry attempts: With framework feedback
   └─ Extract code from response

4. PILOT VALIDATION (Pre-execution)
   ├─ Syntax checking
   ├─ Pattern detection (mirror errors, spacing, etc.)
   ├─ Port name validation
   └─ Routing method checks

5. CODE EXECUTION
   ├─ Parse and clean code
   ├─ Execute in isolated namespace
   └─ Extract GDSFactory Component

6. VALIDATION PIPELINE
   ├─ P&R Validation (Place & Route)
   ├─ DRC Validation (Design Rules)
   ├─ SAX Validation (Compilation & Routing)
   └─ Functional Validation (Circuit Behavior)

7. OPTIMIZATION (if enabled)
   ├─ Device-Level: Optimize component geometries
   └─ Circuit-Level: Optimize phase shifters & couplings

8. RESULT SAVING
   ├─ Save raw LLM code
   ├─ Save framework-processed code
   ├─ Save validation reports
   └─ Create checkpoints at each stage
```

### Detailed Step-by-Step Process

#### Step 1: Input Quality Validation

**Module**: `fin_picasso_framework/input_quality/input_validator.py`

- Validates problem description for quality
- Checks for Unicode characters that could cause syntax errors
- Detects potential hallucination triggers
- Ensures input is suitable for LLM processing

**Example checks**:
- Unicode character detection (µm, ×, Δ → should be um, x, DeltaL)
- Input length validation
- Special character filtering

#### Step 2: Prompt Enhancement

**Module**: `fin_picasso_framework/input_quality/prompt_enhancer.py`

- Sanitizes inputs
- Adds component reference snippets (if component injection enabled)
- Injects design restrictions (spacing, routing, etc.)
- Formats prompt for optimal LLM response

**Component Injection**:
- Loads component specifications dynamically
- Provides port names and API signatures
- Includes SAX model availability (if enabled)

#### Step 3: LLM Inference

**First Attempt (Phase 1 - Baseline)**:
- Uses vanilla prompt (no component specs) for baseline comparison
- Generates initial code
- Saved as "raw LLM" result

**Retry Attempts (Phase 2 - Framework Enhanced)**:
- Uses enhanced prompt with component specs
- Includes detailed feedback from previous failures
- Iterates up to MAX_RETRY_ATTEMPTS (default: 3)

#### Step 4: Pilot Validation

**Module**: `fin_picasso_framework/pilot/pilot_validator_enhanced.py`

**Pre-execution checks** (before code runs):
- **Syntax errors**: Unicode characters, invalid decimal literals
- **Mirror errors**: Detects `gf.components.xxx().mirror()` pattern
- **Spacing violations**: Checks `.move()` coordinates for minimum spacing
- **Port errors**: Validates port names (e1→o1, out1→o1, etc.)
- **Routing errors**: Validates bend radius in route calls
- **Routing method**: Detects route_single overuse (>3 calls)
- **Combiner orientation**: Ensures MMI combiners have `.mirror()` call

**YAML Netlist Validation** (after Python execution):
- Extracts netlist from Python-generated component using `component.get_netlist()`
- Converts netlist to YAML format using `yaml.dump(netlist)`
- Validates netlist structure, spacing, and routing feasibility
- Fixes spacing issues in YAML if detected
- Rebuilds component using `gf.read.from_yaml()` (GDSFactory native support)
- **Benefits**: Catches routing/placement errors early, fixes spacing automatically
- Checks routing feasibility
- Validates placement constraints
- Checks port connections

#### Step 5: Code Execution

**Module**: `hf_inference_workflow/gen_data_validated.py` → `parse_and_execute_code()`

- Extracts code from `<result>` tags or markdown fences
- Cleans code (removes Unicode, fixes decimal literals)
- Executes in isolated namespace with `gdsfactory` available
- Extracts GDSFactory Component from namespace

#### Step 6: Validation Pipeline

**6.1 P&R Validation** (Place & Route)

**Module**: `fin_picasso_framework/validators/pnr_validator.py`

**Checks**:
- Component overlap detection
- Minimum spacing between components (default: 20µm)
- Layout area bounds
- Route quality metrics
- Compactness score

**Feedback**:
- Specific spacing violations with locations
- Layout metrics (area, aspect ratio, compactness)
- Suggestions for improvement

**6.2 DRC Validation** (Design Rule Check)

**Module**: `fin_picasso_framework/validators/drc_validator.py`

**How it works**:
- Uses KLayout for physical design rule checking
- Writes component to temporary GDS file
- Runs KLayout DRC script (if available) or basic checks
- Parses DRC report XML to count violations

**What is checked**:
- Waveguide spacing (minimum 2-3µm)
- Routing overlaps
- Minimum feature sizes
- Metal layer violations
- Bend radius compliance

**KLayout Integration**:
- Checks if KLayout executable is available
- Uses custom DRC script if provided (`.drc` file)
- Falls back to basic geometric checks if KLayout unavailable
- Generates XML report with violation details

**Comparison with PhIDO**:
- PICasso uses KLayout directly (industry-standard DRC tool)
- PhIDO may use different DRC approach
- Both check physical design rules, but implementation differs

**6.3 SAX Validation** (Compilation & Routing)

**Module**: `fin_picasso_framework/validators/sax_validator.py`

**Checks**:
- SAX compilation: Can circuit be compiled to S-parameter model?
- Routing correctness: Are components physically connected?
- Port alignment: Are ports properly aligned for routing?

**How it works**:
- Converts GDSFactory component to SAX netlist
- Attempts SAX compilation
- Validates that routes exist between connected components
- Checks port orientations are cardinal (0°, 90°, 180°, 270°)

**6.4 Functional Validation** (Circuit Behavior)

**Module**: `fin_picasso_framework/validators/functional_validator.py`

**Purpose**: Verify circuit performs intended function (like VHDL/SPICE testbenches)

**Methods**:
- **8-QAM Modulator**: Sweep 3 phase shifters through all 8 binary combinations → should produce 8 distinct constellation points
- **MZM**: Sweep phase shifter 0-2π → should show extinction ratio > 20dB
- **MZI**: Check interference patterns
- **Generic**: Check reciprocity and passivity

**Test Procedure** (Example: 8-QAM):
1. Identify phase shifters in circuit
2. Apply all 8 binary combinations: [0,0,0], [0,0,1], ..., [1,1,1]
3. Simulate S-parameters using SAX for each state
4. Extract output complex amplitude S21
5. Plot constellation points (Re(S21), Im(S21))
6. Verify 8 distinct points with adequate separation

**Pass Criteria**:
- 8-QAM: At least 8 distinct constellation points, minimum separation > 0.05
- MZM: Extinction ratio > 20 dB
- MZI: Proper interference pattern

#### Step 7: Optimization

**Module**: `fin_picasso_framework/optimization_integration.py`

**Two-Level Optimization**:

**Level 1: Device-Level Optimization**

**Module**: `fin_picasso_framework/optimizers/device_optimizer.py`

**What it does**:
- Optimizes individual component geometries (width, length, gap, radius)
- Targets: Match insertion losses from literature
- Method: SAX simulation or analytical models

**Example**:
- For 8-QAM with 3 Y-splitters:
  - Optimize Y-splitter geometry (width, taper_length) to achieve 0.28 dB target
  - Use SAX to simulate S-parameters for each geometry
  - Minimize: |actual_loss - target_loss|

**Target Losses** (from literature):
- mmi1x2: 0.3 dB
- y_branch: 0.28 dB
- directional_coupler: 0.27 dB
- bend_euler: 0.086 dB
- phase_shifter: 0.23 dB

**Level 2: Circuit-Level Optimization**

**Module**: `fin_picasso_framework/optimization_integration.py` → `optimize_circuit_parameters()`

**What it does**:
- Optimizes phase shifters and couplings for minimum insertion loss
- Method: Multi-start Nelder-Mead optimization with SAX S-matrix simulation

**Parameters optimized**:
- Phase shifter angles (φ ∈ [-π, π])
- Coupler ratios (κ ∈ [0.1, 0.9])

**Example** (8-QAM Modulator):
- 3 MZMs → 6 phase shifters (12 parameters: 6 φ values)
- 2 MMI splitters → 2 coupler ratios
- **Total: 14 tunable parameters**
- **Result**: Initial IL = 3.2 dB → Optimized IL = 1.4 dB (Δ = -1.8 dB improvement)

**Optimization Process**:
1. Extract tunable parameters from netlist
2. Define objective function: minimize insertion loss
3. Use SAX to simulate full circuit for each parameter set
4. Run optimizer (Nelder-Mead with random restarts)
5. Return optimized parameters and loss improvement

---

## LLM Prompting

### Initial Prompt Structure

**Location**: `hf_inference_workflow/config.py` → `PYTHON_PROMPT_TEMPLATE`

**Base Prompt**:
```
You are a professional Photonic Integrated Circuit (PIC) designer with expertise in GDSFactory.
Your task is to generate Python code based on the circuit design requirements provided.
```

**Key Sections**:

1. **Component Reference** (if `ENABLE_COMPONENT_INJECTION=True`):
   - Lists available GDSFactory components
   - Provides exact port names and API signatures
   - Indicates SAX model availability

2. **Important Restrictions**:
   - Component selection guidelines
   - Port naming and connection rules
   - Component mirroring (CRITICAL)
   - Spacing rules
   - Parameters and settings
   - Code format requirements

3. **Response Format**:
   - `<analysis>`: Step-by-step implementation plan
   - `<result>`: Complete executable Python code

4. **Reference Example**:
   - Shows complete MZM example with proper structure

### Component Injection

**Module**: `fin_picasso_framework/port_matching/component_spec_loader.py`

**What is injected**:
- Component names and paths (e.g., `gf.components.mmi1x2()`)
- Port names for each component (e.g., `o1`, `o2`, `o3`)
- API signatures and parameters
- SAX model availability (if enabled)

**Example injection**:
```
--- AVAILABLE GDSFACTORY COMPONENTS REFERENCE ---
mmi1x2:
  Ports: o1 (input), o2, o3 (outputs)
  SAX Model: Available ✓
  Usage: gf.components.mmi1x2()

mzis.mzm:
  Ports: o1, o2
  SAX Model: Available ✓
  Usage: gf.components.mzis.mzm()
--- END COMPONENTS REFERENCE ---
```

### Pilot Prompt

**Module**: `fin_picasso_framework/pilot/pilot_validator_enhanced.py`

**Current checks** (embedded in validator, not separate prompt):
- Mirror error detection
- Spacing violation detection
- Port error detection
- Routing error detection
- Syntax error detection

**Dynamic updates**: After pass@3 failures, pilot rules are updated based on error patterns.

### Retry Prompt Structure

**Module**: `fin_picasso_framework/error_handling/feedback_generator.py`

**Structure**:
```
{original_prompt}

======================================================================
RETRY ATTEMPT {attempt_number}
======================================================================

{detailed_feedback}

IMPORTANT: Please carefully address ALL the issues mentioned above.
...
```

**Feedback includes**:
- Error type and severity
- Specific error message
- Problematic code snippet
- Suggested fix with examples
- Step-by-step fix instructions
- Prevention rules

---

## Validation Stages

### Stage 1: Pilot Validation (Pre-execution)

**When**: Before code execution

**Checks**:
- Syntax errors (Unicode, invalid literals)
- Mirror errors (`gf.components.xxx().mirror()`)
- Spacing violations (coordinates < minimum)
- Port errors (wrong port names)
- Routing errors (bend radius < minimum)
- Routing method (route_single overuse)
- Combiner orientation (missing `.mirror()`)

**Feedback**: Immediate feedback with examples and fixes

### Stage 2: P&R Validation

**When**: After code execution, component created

**Checks**:
- Component overlap
- Minimum spacing (20µm default)
- Layout area bounds
- Route quality

**Feedback**: Detailed metrics and specific violations

### Stage 3: DRC Validation

**When**: After P&R passes

**Checks** (via KLayout):
- Waveguide spacing
- Routing overlaps
- Minimum feature sizes
- Metal layer violations

**Feedback**: Violation count by category, specific locations

### Stage 4: SAX Validation

**When**: After DRC passes

**Checks**:
- SAX compilation success
- Routing correctness (physical connections exist)
- Port alignment

**Feedback**: Compilation errors, routing issues, port misalignments

### Stage 5: Functional Validation

**When**: After SAX passes

**Checks**:
- Circuit behavior matches specification
- Testbench-style validation (8-QAM produces 8 states, etc.)

**Feedback**: Test results, expected vs actual behavior

---

## Feedback System

### How Feedback is Generated

**Module**: `fin_picasso_framework/error_handling/feedback_generator.py`

**Process**:
1. Error extraction: `ErrorExtractor` analyzes error
2. Categorization: Error classified (port_mismatch, missing_route, etc.)
3. Code snippet extraction: Relevant code section identified
4. Fix generation: Suggested fix with before/after examples
5. Step-by-step instructions: Detailed fix steps
6. Prevention rules: Rules to avoid error in future

### Feedback Detail Level

**Very Detailed**:
- Specific error location in code
- Before/after code examples
- Common patterns to avoid
- Step-by-step fix instructions
- Prevention rules for pilot validator

**Example Feedback**:
```
❌ ERROR TYPE: Missing Route
📍 FAILED STAGE: PNR
🔴 SEVERITY: CRITICAL

ERROR MESSAGE:
P&R validation failed: No routing structures found

PROBLEMATIC CODE:
```python
component1.move((0, 0))
component2.move((100, 0))
# No routing! ❌
```

🔧 SUGGESTED FIX:
Components are placed but not routed. Add route_single() or route_bundle() calls
to create physical waveguides.

📝 FIX EXAMPLE:
```python
component1.move((0, 0))
component2.move((100, 0))
gf.routing.route_single(r, component1.ports['o2'], component2.ports['o1'], 
                        cross_section='strip', radius=15)  # ✅
```

📋 STEP-BY-STEP FIX INSTRUCTIONS:
  1. Identify all component pairs that should be connected
  2. For each pair, add a route_single() call
  3. Use correct port names for source and destination
  4. Set appropriate radius (>= 15µm) and cross_section
  5. Verify all routes are added before add_port() calls
```

### Examples in Feedback

**Yes, feedback includes examples**:
- Before/after code snippets
- Common patterns to avoid
- Reference examples for correct usage

---

## Optimization

### Device-Level Optimization

**What**: Optimize component geometries (width, length, gap, radius)

**Why**: Match target insertion losses from literature

**How**:
1. For each component type, define parameter ranges
2. Use SAX to simulate S-parameters for each geometry
3. Calculate insertion loss: IL = -10*log10(|S21|²)
4. Minimize: |IL - target_IL|
5. Return optimized geometry

**Example**:
- Y-splitter: Optimize width and taper_length to achieve 0.28 dB target
- MMI: Optimize width and length to achieve 0.3 dB target

### Circuit-Level Optimization

**What**: Optimize phase shifters and couplings

**Why**: Minimize total insertion loss

**How**:
1. Extract tunable parameters from netlist (phase angles, coupler ratios)
2. Define objective function: minimize insertion loss
3. Use SAX to simulate full circuit for each parameter set
4. Run multi-start Nelder-Mead optimizer
5. Return optimized parameters and loss improvement

**Example**:
- 8-QAM: Optimize 14 parameters (6 phase angles + 2 coupler ratios + 6 phase angles for MZMs)
- Result: 3.2 dB → 1.4 dB (1.8 dB improvement)

---

## DRC Validation

### How DRC Works

**Tool**: KLayout (industry-standard DRC tool)

**Process**:
1. Component is written to temporary GDS file
2. KLayout is invoked in batch mode with DRC script
3. DRC script checks design rules:
   - Waveguide spacing (minimum 2-3µm)
   - Routing overlaps
   - Minimum feature sizes
   - Metal layer clearances
4. DRC report (XML) is generated
5. Report is parsed to count violations

### KLayout Integration

**Check for KLayout**:
```python
def _check_klayout_available(self) -> bool:
    result = subprocess.run(["klayout", "-v"], ...)
    return result.returncode == 0
```

**Run DRC**:
```python
cmd = [
    "klayout",
    "-b",  # Batch mode
    "-r", drc_script_path,  # DRC script
    "-rd", f"input={gds_path}",
    "-rd", f"report={drc_report_path}"
]
subprocess.run(cmd, ...)
```

**Parse Report**:
- XML format with violation items
- Count violations by category
- Extract violation locations

### What Design Rules Are Checked

**Default checks** (if no custom script):
- Basic geometric properties
- Feature size validation
- Layer checks

**Custom DRC script** (if provided):
- Foundry-specific design rules
- Custom spacing requirements
- Metal layer rules
- Any custom checks defined in script

### How Violations Are Detected and Reported

**Detection**:
- KLayout DRC script runs checks
- Violations are written to XML report
- Report is parsed to extract violation details

**Reporting**:
- Total violation count
- Violations by category
- Specific error messages
- Suggestions for fixing

### YAML Netlist Integration (PhIDO-Inspired)

**New Feature**: After Python code execution, the framework:
1. Extracts netlist from component using `component.get_netlist()`
2. Converts to YAML format for validation
3. Validates spacing, routing feasibility, and port connections
4. Automatically fixes spacing issues in YAML
5. Rebuilds component using `gf.read.from_yaml()` (GDSFactory native)

**Benefits**:
- Catches routing/placement errors before full validation
- Fixes spacing issues automatically
- Uses GDSFactory's native YAML support for automatic routing
- PhIDO-inspired netlist-based validation approach

**Routing Collision Auto-Correction**:
- When routing collision detected, framework attempts YAML-based fix:
  1. Extract component before collision occurs
  2. Extract netlist → Convert to YAML
  3. Fix spacing in YAML (100µm minimum for routing safety)
  4. Rebuild using `gf.read.from_yaml()` with automatic routing
- Falls back to code-based spacing fix if YAML approach fails

### Comparison with PhIDO

**PICasso**:
- Uses KLayout directly (industry standard)
- Custom DRC scripts supported
- XML report parsing
- Integration with validation pipeline

**PhIDO**:
- May use different DRC approach
- Different violation reporting format
- Both check physical design rules

**Key Difference**: PICasso uses KLayout, which is the industry-standard tool for photonic DRC.

---

## Result Saving and Checkpoints

### Directory Structure

```
fin_picasso_framework/output/benchmark_results/
├── raw_llm/                    # Before framework processing
│   ├── code/                   # Python code files
│   ├── gds/                    # GDS files (if generated)
│   └── errors/                 # Error logs
├── framework_processed/        # After framework processing
│   ├── code/                   # Final code
│   ├── gds/                    # Final GDS files
│   ├── validation_reports/     # JSON reports
│   └── optimization/           # Optimization results
└── checkpoints/                # Debug checkpoints
    ├── pilot/                  # After pilot validation
    ├── pnr/                    # After P&R validation
    ├── drc/                    # After DRC validation
    ├── sax/                    # After SAX validation
    ├── functional/             # After functional validation
    └── optimization/           # After optimization
```

### What is Saved

**Raw LLM** (before framework):
- Code from first attempt
- GDS file (if component was created)
- Error logs (if execution failed)

**Framework Processed** (after framework):
- Final code (after retries)
- Final GDS file
- Validation reports (JSON)
- Optimization results (JSON)

**Checkpoints** (at each stage):
- Code snapshot
- Component (as GDS)
- Validation results
- Error messages
- Timestamp and metadata

### Checkpoint Usage

**View checkpoints**:
```python
from fin_picasso_framework.debug import CheckpointViewer

viewer = CheckpointViewer()
checkpoints = viewer.list_checkpoints(problem_idx=2, sample_idx=0)
details = viewer.get_checkpoint_details(checkpoint_file)
chain = viewer.get_checkpoint_chain(problem_idx=2, sample_idx=0, attempt=1)
```

**Export checkpoint data**:
```python
export_file = viewer.export_checkpoint_data(problem_idx=2, sample_idx=0)
```

---

## Error Handling and Robustness

### Error Extraction

**Module**: `fin_picasso_framework/error_handling/error_extractor.py`

**Process**:
1. Error message analyzed with regex patterns
2. Error categorized (port_mismatch, missing_route, etc.)
3. Code snippet extracted (if available)
4. Fix suggestions generated
5. Prevention rules created

**Error Categories**:
- Port mismatch
- SAX component not found
- Package error
- Routing error
- Spacing violation
- Mirror error
- Syntax error
- Missing route
- Incomplete routing
- Wrong API
- DRC violation
- Functional failure

### Robustness Verification

**Module**: `fin_picasso_framework/robustness/template_checker.py`

**After pass@3 failures**:
1. Analyze error patterns
2. Check template coverage
3. Check pilot coverage
4. Check injection coverage
5. Identify gaps
6. Generate recommendations

**Robustness Score**: 0-1 based on coverage and gaps

### Dynamic Pilot Updates

**Module**: `fin_picasso_framework/pilot/pilot_prompt_updater.py`

**Process**:
1. Analyze failed cases after pass@3
2. Identify missing patterns
3. Update pilot rules dynamically
4. Add learned patterns to pilot prompt
5. Verify robustness

---

## Summary

PICasso framework provides:

1. **Comprehensive Validation**: Pilot → P&R → DRC → SAX → Functional
2. **Detailed Feedback**: Error-specific feedback with examples and step-by-step fixes
3. **Two-Level Optimization**: Device geometries + circuit parameters
4. **Result Tracking**: Raw LLM vs framework results with checkpoints
5. **Robustness Verification**: Template and prompt coverage analysis
6. **Error Learning**: Dynamic pilot rule updates based on failures

The framework ensures generated designs are:
- ✅ Structurally correct (P&R, DRC)
- ✅ Functionally correct (SAX, Functional)
- ✅ Optimized for performance (Device + Circuit optimization)
- ✅ Manufacturable (DRC compliance)

