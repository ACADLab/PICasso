# PICasso Benchmarking Metrics

## Three Novel Metrics for Photonic Circuit Generation

This document defines the three novel metrics introduced in PICasso for benchmarking automated photonic integrated circuit (PIC) generation:

1. **Spec@k** (Specification Satisfaction @k)
2. **Opt-Efficiency** (Optimization Efficiency)
3. **Robustness Score**

These metrics extend beyond traditional Pass@k by incorporating functional correctness and optimization effectiveness.

---

## 1. Spec@k (Specification Satisfaction @k)

### Definition

**Spec@k** measures the probability that at least k samples satisfy BOTH structural AND functional specifications.

### Formula

```
Spec@k = 1 - C(n-c, k) / C(n, k)
```

where:
- **n** = total samples generated
- **c** = samples passing both structural and functional validation
- **k** = number of samples considered
- **C(n, k)** = binomial coefficient "n choose k"

This is the same combinatorial formula as Pass@k, but with stricter success criteria.

### Components

#### Structural Validation (same as Pass@k)
- **P&R (Place & Route)**: Layout can be placed and routed without collisions
- **DRC (Design Rule Check)**: No design rule violations
- **SAX Compilation**: S-parameter model can be built for simulation

#### Functional Validation (NEW)
Circuit-specific behavior tests using SAX simulation as a "SPICE-like" testbench:

| Circuit Type | Functional Test | Success Criterion |
|-------------|-----------------|-------------------|
| 8-QAM Modulator | Constellation diagram | 8 distinct points, min separation > 0.05 |
| QPSK Modulator | Constellation diagram | 4 distinct points, min separation > 0.1 |
| MZM (Mach-Zehnder Modulator) | Extinction ratio | ER > 20 dB |
| MZI (Mach-Zehnder Interferometer) | Reciprocity | \|S21 - S12\| < 0.01 |
| 2×2 Optical Switch | Crosstalk | < -20 dB |
| Ring Resonator Filter | Q-factor | Q > 10,000 |
| WDM Demultiplexer | Channel isolation | > 20 dB |
| Generic Passive Device | SAX compilation | Compiles successfully |

### Example Calculation

**Scenario**: Generate 3 samples of an 8-QAM modulator

| Sample | P&R | DRC | SAX | Functional (8 states) | Structural Pass | Spec Pass |
|--------|-----|-----|-----|-----------------------|-----------------|-----------|
| 1 | ✅ | ✅ | ✅ | ❌ (only 4 states) | ✅ | ❌ |
| 2 | ✅ | ✅ | ✅ | ✅ (8 distinct states) | ✅ | ✅ |
| 3 | ❌ | - | - | - | ❌ | ❌ |

**Results**:
- **Pass@3** (structural): c=2, n=3 → Pass@3 = 1 - C(1,3)/C(3,3) = 1 - 0 = **1.0 (100%)**
- **Spec@3** (structural + functional): c=1, n=3 → Spec@3 = 1 - C(2,3)/C(3,3) = 1 - 0 = **0.67 (67%)**

### Interpretation

| Spec@k Value | Interpretation |
|--------------|----------------|
| 0.0 | No samples meet specifications |
| 0.0 - 0.3 | Poor specification satisfaction |
| 0.3 - 0.6 | Moderate specification satisfaction |
| 0.6 - 0.8 | Good specification satisfaction |
| 0.8 - 1.0 | Excellent specification satisfaction |
| 1.0 | All samples meet specifications |

### Comparison to Pass@k

| Metric | Structural | Functional | Strictness |
|--------|------------|------------|------------|
| Pass@k | ✓ | ✗ | Lenient |
| Spec@k | ✓ | ✓ | Strict |

**Key Insight**: Spec@k ≤ Pass@k always, because Spec@k has stricter requirements.

**Example Gap**:
- A circuit that compiles (Pass@k = 1.0) but doesn't work correctly (Spec@k = 0.0)
- This gap reveals the importance of functional testing

---

## 2. Opt-Efficiency (Optimization Efficiency)

### Definition

**Opt-Efficiency** measures the normalized improvement achieved by the two-level optimization framework.

### Formula

```
Opt-Efficiency = (IL_before - IL_after) / IL_before
```

where:
- **IL_before** = insertion loss before circuit-level optimization (dB)
- **IL_after** = insertion loss after circuit-level optimization (dB)
- Both measured at the circuit level (Level 2 optimization)

### Range

**[0.0, 1.0]**
- **0.0**: No improvement (or made worse)
- **0.5**: 50% reduction in insertion loss
- **1.0**: 100% reduction (theoretical maximum, unrealistic)

### Two-Level Optimization Context

PICasso uses two-level optimization:

**Level 1 (Device Optimization)**:
- Optimize component geometries (width, length, gap, radius)
- Match literature target losses using analytical models
- Output: Device-level loss (dB)

**Level 2 (Circuit Optimization)** ← *Used for Opt-Efficiency*:
- Optimize phase shifters and coupling ratios
- Minimize insertion loss using SAX S-parameter simulation
- Uses multi-start Nelder-Mead optimization (8 restarts × 400 iterations)
- Output: Circuit-level loss before/after optimization

**Total Loss**:
```
Total_Loss = Device_Loss + Circuit_Loss_After
```

**Opt-Efficiency measures Level 2 improvement only**, not total system loss.

### Example Calculation

**Scenario**: MZM (Mach-Zehnder Modulator)

**Device-Level Loss (Level 1)**:
- 2× MMI 1×2: 0.3 dB each = 0.6 dB
- 2× Phase shifters: 0.23 dB each = 0.46 dB
- 8× Bends: 0.086 dB each = 0.69 dB
- **Device Loss**: 1.75 dB (fixed)

**Circuit-Level Optimization (Level 2)**:
- Before optimization: 2.1 dB (random phase settings)
- After optimization: 0.8 dB (optimized phases)
- Improvement: 1.3 dB

**Opt-Efficiency**:
```
Opt-Efficiency = (2.1 - 0.8) / 2.1 = 1.3 / 2.1 = 0.619 (62% reduction)
```

**Total Loss**:
```
Total = 1.75 dB (device) + 0.8 dB (circuit) = 2.55 dB
```

### Interpretation

| Opt-Efficiency | Interpretation | Typical Circuits |
|----------------|----------------|------------------|
| < 0.1 | Minimal improvement | Passive circuits (no tunables) |
| 0.1 - 0.2 | Slight improvement | Simple MZI with one phase shifter |
| 0.2 - 0.4 | Moderate improvement | MZM, basic modulators |
| 0.4 - 0.6 | Significant improvement | QPSK, multi-parameter circuits |
| > 0.6 | Excellent improvement | Complex modulators (8-QAM, 16-QAM) |

### Benchmark Results

**Average Opt-Efficiency by circuit complexity**:

| Complexity | Circuits | Avg Opt-Efficiency | Interpretation |
|------------|----------|-------------------|----------------|
| 1 (Basic) | MZI, MZM, Y-branch | 0.15 - 0.25 | Limited tunability |
| 2 (Moderate) | QPSK, 8-QAM, switches | 0.30 - 0.45 | Good optimization potential |
| 3 (Advanced) | Meshes, crossbars | 0.25 - 0.40 | Many parameters, harder to optimize |

**Overall Average**: ~0.33 (33% circuit-level IL reduction)

### Why Normalize by IL_before?

Normalization allows fair comparison across circuit types:
- MZI with 1.0 dB → 0.5 dB (50% improvement) = 0.5 Opt-Efficiency
- QPSK with 5.0 dB → 2.5 dB (50% improvement) = 0.5 Opt-Efficiency
- Both have same **effectiveness**, despite different absolute values

---

## 3. Robustness Score

### Definition

**Robustness Score** is a combined metric measuring both specification satisfaction (correctness) and optimization effectiveness (performance).

### Formula

```
Robustness = α × Spec@k + β × Opt-Efficiency
```

where:
- **α + β = 1.0** (weights must sum to 1)
- **α** = weight for specification satisfaction
- **β** = weight for optimization efficiency

### Default Weighting

```
α = 0.7  (specification satisfaction)
β = 0.3  (optimization efficiency)
```

**Rationale**: Prioritize correctness over optimization.
- A correct but unoptimized circuit is more valuable than an incorrect but optimized one
- 70/30 split reflects that **working correctly is 2.3× more important** than optimization

### Range

**[0.0, 1.0]**
- **0.0**: Failed specifications, no optimization
- **0.5**: Moderate performance
- **1.0**: Perfect specifications + optimization

### Example Calculations

**Scenario 1: Well-Optimized MZM**
- Spec@3 = 1.0 (100% functionally correct)
- Opt-Efficiency = 0.35 (35% IL reduction)
- Robustness = 0.7 × 1.0 + 0.3 × 0.35 = **0.805** ✅ **Excellent**

**Scenario 2: Poorly-Optimized but Correct QPSK**
- Spec@3 = 0.67 (67% functionally correct)
- Opt-Efficiency = 0.10 (10% IL reduction)
- Robustness = 0.7 × 0.67 + 0.3 × 0.10 = **0.499** ⚠️ **Borderline**

**Scenario 3: Well-Optimized but Incorrect 8-QAM**
- Spec@3 = 0.0 (0% functionally correct)
- Opt-Efficiency = 0.50 (50% IL reduction)
- Robustness = 0.7 × 0.0 + 0.3 × 0.50 = **0.150** ❌ **Poor**

→ **Key Insight**: Even excellent optimization doesn't compensate for functional failures.

### Interpretation

| Robustness Score | Interpretation | Typical Scenario |
|------------------|----------------|------------------|
| 0.0 - 0.3 | Poor | Failed specs or minimal optimization |
| 0.3 - 0.5 | Acceptable | Either specs or optimization needs work |
| 0.5 - 0.7 | Good | Balanced correctness and optimization |
| 0.7 - 0.9 | Excellent | High specs + good optimization |
| 0.9 - 1.0 | Outstanding | Near-perfect across both dimensions |

### Alternative Weightings

The α/β weighting can be adjusted based on priorities:

| Weighting | α (Spec) | β (Opt) | Use Case |
|-----------|----------|---------|----------|
| Correctness-first | 0.8 | 0.2 | Research prototypes |
| **Balanced (default)** | **0.7** | **0.3** | **General use** |
| Performance-focused | 0.6 | 0.4 | Commercial products |
| Equal weight | 0.5 | 0.5 | Theoretical analysis |

---

## Comparison to PIC-bench

### Metrics Comparison

| Metric | PIC-bench | PICasso | Novel? | Description |
|--------|-----------|---------|--------|-------------|
| **Pass@k** | ✓ | ✓ | No | Structural validation only |
| **Spec@k** | ✗ | ✓ | **Yes** | Structural + functional validation |
| **Opt-Efficiency** | ✗ | ✓ | **Yes** | Optimization improvement |
| **Robustness Score** | ✗ | ✓ | **Yes** | Combined correctness + performance |
| **DRC Pass Rate** | ✓ | ✓ | No | Design rule compliance |
| **Code Length** | ✓ | ✓ | No | Generated code size |
| **Retry Count** | ✗ | ✓ | Yes | Framework resilience |

### Key Innovations

1. **Functional Correctness (Spec@k)**:
   - PIC-bench: Only checks if circuit compiles
   - PICasso: Verifies circuit actually works (e.g., 8-QAM produces 8 states)

2. **Optimization Quantification (Opt-Efficiency)**:
   - PIC-bench: No optimization
   - PICasso: Two-level optimization with measured improvement

3. **Holistic Quality (Robustness Score)**:
   - PIC-bench: Separate pass/fail metrics
   - PICasso: Unified score combining correctness and performance

---

## Usage in Benchmarking

### CSV Output Format

**framework_results.csv**:
```csv
problem_idx,circuit_type,sample_idx,success,retries_used,
spec_passed,functional_test_name,functional_metric_value,
device_loss_db,circuit_loss_before_db,circuit_loss_after_db,
opt_efficiency,robustness_score
```

**Example row**:
```csv
5,8-qam modulator,0,True,2,
True,"8-QAM Constellation",0.12,
2.1,3.8,2.5,
0.342,0.803
```

### Summary Report Format

**comparison_metrics.json**:
```json
{
  "8-qam modulator": {
    "raw_llm": {
      "pass_at_3": 0.0,
      "spec_at_3": 0.0,
      "avg_opt_efficiency": 0.0,
      "avg_robustness": 0.0
    },
    "framework": {
      "pass_at_3": 0.67,
      "spec_at_3": 0.67,
      "avg_opt_efficiency": 0.34,
      "avg_robustness": 0.571
    },
    "improvement": {
      "pass_at_3": +0.67,
      "spec_at_3": +0.67,
      "opt_efficiency": +0.34,
      "robustness": +0.571
    }
  }
}
```

---

## Implementation

### Computing Spec@k

```python
def compute_spec_at_k(results: List[Dict], k: int = 3) -> float:
    """
    Compute Spec@k for a list of generation results.

    Args:
        results: List of generation results with validation reports
        k: Number of samples to consider

    Returns:
        Spec@k score (0.0 to 1.0)
    """
    # Count samples passing both structural and functional validation
    spec_successes = [
        r['success'] and  # Structural validation passed
        r.get('validation_reports', {}).get('functional', {}).get('passed', False)  # Functional passed
        for r in results
    ]

    num_correct = sum(spec_successes)
    num_samples = len(results)

    # Use numerically stable pass@k formula
    return estimate_pass_at_k(num_samples, num_correct, k)
```

### Computing Opt-Efficiency

```python
def compute_opt_efficiency(result: Dict) -> float:
    """
    Compute Opt-Efficiency for a single generation result.

    Args:
        result: Generation result with optimization reports

    Returns:
        Opt-Efficiency score (0.0 to 1.0)
    """
    opt_report = result.get('validation_reports', {}).get('optimization', {})

    before = opt_report.get('circuit_loss_before_db')
    after = opt_report.get('circuit_loss_after_db')

    if before is None or after is None or before == 0:
        return 0.0

    improvement = before - after
    efficiency = improvement / before

    # Clamp to [0, 1] range
    return max(0.0, min(1.0, efficiency))
```

### Computing Robustness Score

```python
def compute_robustness_score(
    spec_at_k: float,
    opt_efficiency: float,
    alpha: float = 0.7,
    beta: float = 0.3
) -> float:
    """
    Compute Robustness Score from Spec@k and Opt-Efficiency.

    Args:
        spec_at_k: Spec@k score
        opt_efficiency: Opt-Efficiency score
        alpha: Weight for Spec@k (default 0.7)
        beta: Weight for Opt-Efficiency (default 0.3)

    Returns:
        Robustness score (0.0 to 1.0)
    """
    assert abs(alpha + beta - 1.0) < 1e-6, "Weights must sum to 1.0"

    return alpha * spec_at_k + beta * opt_efficiency
```

---

## References

1. **PIC-bench Paper**: https://arxiv.org/html/2502.03159v1
2. **Pass@k Metric**: Chen et al., "Evaluating Large Language Models Trained on Code" (2021)
3. **SPICEPilot**: https://arxiv.org/html/2410.20553v1
4. **SAX (Scattering Analysis)**: https://github.com/flaport/sax
5. **GDSFactory**: https://gdsfactory.github.io/gdsfactory/

---

## Citation

If you use these metrics in your research, please cite:

```bibtex
@article{picasso2025,
  title={PICasso: Automated Photonic Circuit Generation with Functional Correctness and Optimization},
  author={[Your Name]},
  journal={arXiv preprint},
  year={2025}
}
```

---

**Last Updated**: January 2025
**Version**: 1.0
**Status**: Production
