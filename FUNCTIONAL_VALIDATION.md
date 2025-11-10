# Functional Validation: VHDL/SPICE-Style Testbenches for Photonic Circuits

## Question: "How do we validate the functionality? Do we have testbenches like VHDL or SPICE codes?"

**Answer: YES! We now have functional validation using SAX as our "SPICE simulator".**

## Overview

Previously, we only validated **structure** (components exist, connections are correct). Now we validate **function** (does the circuit actually work as intended?).

This is analogous to:
- **VHDL testbenches**: Apply test vectors, check outputs match expected behavior
- **SPICE simulation checks**: Verify AC/DC characteristics, frequency response, etc.

## Current Validation Pipeline

```
┌──────────────────────────────────────────────────────────────────────┐
│ VALIDATION STAGES                                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ 1. P&R (Place & Route)        ✅ Structural                         │
│    └─ Check: Layout can be placed and routed                        │
│                                                                      │
│ 2. DRC (Design Rule Check)    ✅ Structural                         │
│    └─ Check: No design rule violations                              │
│                                                                      │
│ 3. SAX Compilation            ✅ Structural                         │
│    └─ Check: S-parameter model can be built                         │
│                                                                      │
│ 4. Functional Validation      ✅ FUNCTIONAL (NEW!)                  │
│    └─ Check: Circuit behaves as designed (like VHDL/SPICE)          │
│                                                                      │
│ 5. Device Optimization        ⚙️  Performance                       │
│    └─ Optimize: Component geometries to match target losses         │
│                                                                      │
│ 6. Circuit Optimization       ⚙️  Performance                       │
│    └─ Optimize: Phase shifters and couplings for min insertion loss │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## How Functional Validation Works

### The SAX "Simulator"

We use **SAX (Scattering Analysis eXtension)** as our simulator:
- SAX = SPICE for photonic circuits
- Computes S-parameters (scattering matrices) for arbitrary photonic netlists
- Fast, accurate, physics-based simulation

### Test Methodology (VHDL-Style)

For each circuit type, we define:

1. **Test Vectors**: Input signals/phase configurations to apply
2. **Expected Behavior**: What outputs should look like
3. **Pass Criteria**: Quantitative thresholds (e.g., separation > 0.05, ER > 20 dB)

## Testbench Examples

### Example 1: 8-QAM Modulator

**Question:** How do we know the 8-QAM actually produces 8 distinct states?

**Testbench:**

```python
# Test procedure:
# 1. Identify 3 phase shifters (bit1, bit2, bit3)
# 2. Apply all 8 binary combinations:
#    [0,0,0], [0,0,1], [0,1,0], [0,1,1],
#    [1,0,0], [1,0,1], [1,1,0], [1,1,1]
#    (where 0 → phase=0, 1 → phase=π)
# 3. For each state, simulate S-parameters using SAX
# 4. Extract output complex amplitude S21
# 5. Plot constellation points (Re(S21), Im(S21))
# 6. Verify 8 distinct points with minimum separation > threshold

# Pass criteria:
min_separation > 0.05  # Normalized to |S21| ~ 1
num_unique_points == 8
```

**Example Output:**
```
✅ Functional test passed: 8-QAM Constellation
   Expected: 8 distinct points with separation > 0.05
   Actual: Min separation = 0.1234

   Constellation points:
     [0,0,0] → ( 0.50,  0.50)
     [0,0,1] → (-0.50,  0.50)
     [0,1,0] → ( 0.50, -0.50)
     [0,1,1] → (-0.50, -0.50)
     [1,0,0] → ( 0.71,  0.00)
     [1,0,1] → ( 0.00,  0.71)
     [1,1,0] → (-0.71,  0.00)
     [1,1,1] → ( 0.00, -0.71)
```

### Example 2: Mach-Zehnder Modulator (MZM)

**Question:** How do we verify the MZM has good extinction ratio?

**Testbench:**

```python
# Test procedure:
# 1. Identify phase shifter
# 2. Sweep phase from 0 to 2π (100 points)
# 3. For each phase, simulate S21
# 4. Calculate transmission T = |S21|²
# 5. Find max and min transmission
# 6. Calculate extinction ratio ER = 10*log10(Tmax/Tmin)

# Pass criteria:
ER > 20 dB  # Good modulator should have > 20 dB ER
```

**Example Output:**
```
✅ Functional test passed: MZM Extinction Ratio
   Expected: ER > 20 dB
   Actual: ER = 27.3 dB

   Details:
     P_max = 0.95  (at phase = 0°)
     P_min = 0.002 (at phase = 180°)
     ER = 27.3 dB
```

### Example 3: QPSK Modulator

**Question:** How do we verify QPSK produces 4 states at 0°, 90°, 180°, 270°?

**Testbench:**

```python
# Test procedure:
# 1. Identify 2 MZMs (I and Q arms)
# 2. Apply 4 QPSK states:
#    [0,0]   → 0°   (both OFF)
#    [0,π]   → 90°  (Q ON)
#    [π,0]   → 180° (I ON)
#    [π,π]   → 270° (both ON)
# 3. For each state, simulate S21
# 4. Plot constellation (Re(S21), Im(S21))
# 5. Verify 4 points with 90° separation

# Pass criteria:
min_separation > 0.1
num_unique_points == 4
```

### Example 4: Optical Switch (2×2)

**Question:** How do we verify switch can route input to both outputs?

**Testbench:**

```python
# Test procedure:
# 1. Identify phase shifter (switch control)
# 2. Set phase = 0 (BAR state)
#    → Check S21 > 0.9, S22 < 0.1 (input1 → output1)
# 3. Set phase = π (CROSS state)
#    → Check S21 < 0.1, S22 > 0.9 (input1 → output2)
# 4. Calculate crosstalk = 10*log10(Poff/Pon)

# Pass criteria:
crosstalk < -20 dB  # Good switch has < -20 dB crosstalk
```

## Implemented Testbenches

Currently implemented in [`functional_validator.py`](hf_inference_workflow/validators/functional_validator.py):

| Circuit Type | Testbench | Pass Criteria |
|--------------|-----------|---------------|
| 8-QAM | Constellation diagram | 8 distinct points, min separation > 0.05 |
| QPSK | Constellation diagram | 4 distinct points, min separation > 0.1 |
| MZM (Modulator) | Extinction ratio | ER > 20 dB |
| MZI (Interferometer) | Reciprocity check | \|S21 - S12\| < 0.01 |
| 2×2 Switch | Crosstalk | < -20 dB |
| Generic Passive | SAX compilation | Circuit compiles successfully |

More testbenches to be added for:
- 16-QAM, 64-QAM (M-QAM modulators)
- Ring resonator filters (Q-factor, FSR)
- WDM mux/demux (channel isolation)
- N×N switches (insertion loss, crosstalk matrix)

## Comparison to VHDL/SPICE

### VHDL Testbench (Digital)

```vhdl
-- VHDL testbench for 8-bit adder
entity tb_adder is end entity;

architecture test of tb_adder is
begin
  process
  begin
    -- Apply test vectors
    A <= "00000001"; B <= "00000001"; wait for 10 ns;
    assert (SUM = "00000010") report "Test 1 failed" severity error;

    A <= "11111111"; B <= "00000001"; wait for 10 ns;
    assert (SUM = "00000000") report "Test 2 failed" severity error;

    wait;
  end process;
end architecture;
```

### Our Photonic Testbench (Analog)

```python
# Photonic testbench for 8-QAM
def _test_8qam(self, component):
    # Apply test vectors (phase configurations)
    test_vectors = [(0,0,0), (0,0,π), (0,π,0), ...]

    constellation_points = []
    for phases in test_vectors:
        # Simulate circuit with SAX (like SPICE)
        S = sax_circuit(**phases)

        # Extract output (complex amplitude)
        s21 = S[('out', 'in')]
        constellation_points.append((Re(s21), Im(s21)))

    # Check pass criteria
    min_sep = min_pairwise_distance(constellation_points)
    assert min_sep > 0.05, f"Constellation points too close: {min_sep}"
```

**Similarities:**
- ✅ Apply test vectors
- ✅ Simulate response
- ✅ Check against expected behavior
- ✅ Pass/fail criteria

**Differences:**
- VHDL: Digital (0/1), time-domain simulation
- Photonic: Analog (complex S-parameters), frequency-domain simulation
- VHDL: Gate-level/RTL models
- Photonic: S-parameter/FDTD models

## Configuration

Enable/disable in [`config.py`](hf_inference_workflow/config.py):

```python
# Functional Validation (NEW - Like VHDL/SPICE Testbenches)
ENABLE_FUNCTIONAL_VALIDATION = True  # Enable functional testing using SAX simulation
                                      # Tests circuit behavior (e.g., 8-QAM produces 8 states)
                                      # Similar to VHDL testbenches or SPICE simulation checks
```

## Usage

Functional validation is automatically run during the validation pipeline:

```python
from hf_inference_workflow.gen_data_validated import generate_with_validation

result = generate_with_validation(
    agent=agent,
    prompt=PYTHON_PROMPT_TEMPLATE,
    problem_desc="Create an 8-QAM modulator...",
    circuit_type="8-qam modulator",
    ...
)

# Check functional test results
if result['validation_reports']['functional']['passed']:
    print(f"✅ Functional test passed: {result['validation_reports']['functional']['test_name']}")
    print(f"   {result['validation_reports']['functional']['actual']}")
else:
    print(f"❌ Functional test failed: {result['validation_reports']['functional']['error']}")
```

## Current Status

**Implemented:** ✅
- FunctionalValidator class with 8 testbenches
- Integration into validation pipeline
- Configuration flag in config.py
- **Spec@k Metric Enforcement** (functional validation now required)

**Enforcement Mode:**
- **Pass@k**: Soft-fail (structural validation only)
- **Spec@k**: Hard requirement (structural + functional validation)
- Configurable via `ENABLE_FUNCTIONAL_VALIDATION` in config.py

**To Do:**
- [ ] Add more testbenches (16-QAM, 64-QAM, filters, switches)
- [x] Make functional validation a hard requirement for Spec@k
- [ ] Add testbench visualizations (constellation diagrams, transmission curves)
- [x] Export functional test results to CSV for benchmarking
- [ ] Add LLM feedback for functional test failures

## Metric Integration

Functional validation is now part of the **Spec@k metric**:
- **Pass@k**: Probability ≥k samples pass structural validation
- **Spec@k**: Probability ≥k samples pass structural + functional validation
- **Always**: Spec@k ≤ Pass@k (stricter requirement)

See [METRICS_DEFINITION.md](METRICS_DEFINITION.md) for complete definitions.

## Benefits

1. **Early Bug Detection**: Catch functional bugs before fabrication
   - Example: 8-QAM with wrong topology passes structural checks but fails functional test

2. **Confidence in Generated Designs**: Know the circuit actually works, not just "looks right"

3. **Performance Guarantees**: Quantitative metrics (ER, crosstalk, separation)

4. **Paper Contribution**: Novel application of SAX for automated validation
   - "We validate not just structure but function using physics-based simulation"

## Example: Why This Matters

**Before functional validation:**
```
LLM generates 8-QAM modulator
├─ P&R: ✅ Layout OK
├─ DRC: ✅ No violations
├─ SAX: ✅ Compiles
└─ Result: ACCEPTED ✅

Problem: LLM used wrong MMI splitting ratios
         → Only 4 distinct states instead of 8
         → Discovered after fabrication 💸💸💸
```

**After functional validation:**
```
LLM generates 8-QAM modulator
├─ P&R: ✅ Layout OK
├─ DRC: ✅ No violations
├─ SAX: ✅ Compiles
├─ Functional: ❌ Only 4 distinct constellation points (expected 8)
└─ Result: REJECTED, retry with feedback ❌

LLM receives feedback: "Constellation test failed: only 4 states detected"
LLM regenerates with correct topology
├─ Functional: ✅ 8 distinct points with min sep = 0.12
└─ Result: ACCEPTED ✅

Outcome: Bug caught before fabrication! 🎉
```

## Next Steps

1. **Run Benchmarks**: Test on Pic_set.txt problems with functional validation enabled
2. **Analyze Failures**: See which circuits pass structural but fail functional tests
3. **Add More Testbenches**: Extend to all 36 problem types
4. **Improve Feedback**: Generate specific LLM feedback for functional test failures
   - "Your 8-QAM only produces 4 states. Check MMI splitting ratios."
   - "MZM extinction ratio too low (12 dB). Increase phase shifter length."

---

**Summary:** We now have VHDL/SPICE-style functional validation for photonic circuits using SAX simulation. This catches bugs that structural validation misses and provides confidence that generated designs actually work.
