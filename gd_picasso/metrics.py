"""
PICasso Benchmarking Metrics

Implements metrics for photonic circuit generation:
1. Spec@k: Specification satisfaction @k (structural + functional)
2. OptEff: Optimization efficiency (normalized IL reduction with ε stabilization)
3. RobustPass: Robustness under perturbations
4. Overall Robustness Score R: Combined correctness + performance metric (correctness-gated)
"""

import numpy as np
from typing import List, Dict, Optional


def estimate_pass_at_k(num_samples: int, num_correct: int, k: int) -> float:
    """
    Numerically stable pass@k computation.

    Formula: pass@k = 1 - C(n-c, k) / C(n, k)

    Args:
        num_samples: Total number of samples (n)
        num_correct: Number of correct samples (c)
        k: Number of samples to consider

    Returns:
        pass@k score (0.0 to 1.0)
    """
    if num_correct >= k:
        return 1.0
    if num_correct == 0:
        return 0.0

    # Numerically stable computation using product form
    numerator = np.prod(np.arange(num_samples - num_correct,
                                   num_samples - num_correct - k, -1))
    denominator = np.prod(np.arange(num_samples, num_samples - k, -1))

    return 1.0 - numerator / denominator


def compute_spec_at_k_structural(results: List[Dict], k: int = 3) -> float:
    """
    Compute Spec@k_structural: Structural specification satisfaction @k.
    
    For Phase 1 (vanilla LLM baseline): Only checks structural correctness.
    
    Structural Pass Criteria:
    - ✅ YAML builds into gdsfactory component (component_built = True)
    - ✅ DRC passes (drc_passed = True)
    
    Formula: Spec@k_structural = 1 - C(n-c_s, k) / C(n, k)
    Where c_s = number of structurally valid samples.
    
    Args:
        results: List of generation results with validation reports
        k: Number of samples to consider (default: 3)
    
    Returns:
        Spec@k_structural score (0.0 to 1.0)
    """
    # Count samples passing structural validation
    structural_successes = []
    
    for r in results:
        # Structural pass: component built AND DRC passed
        component_built = r.get('component_built', False)
        drc_passed = r.get('drc_passed', True)  # Default True if DRC not checked
        
        structural_successes.append(component_built and drc_passed)
    
    num_correct = sum(structural_successes)
    num_samples = len(results)
    
    return estimate_pass_at_k(num_samples, num_correct, k)


def compute_spec_at_k_full(results: List[Dict], k: int = 3) -> float:
    """
    Compute Spec@k_full: Full specification satisfaction @k.
    
    For Phase 2 (PICasso framework): Checks structural + functional + optimization correctness.
    
    Full Pass Criteria:
    - ✅ Structural Pass: Component builds, DRC passes
    - ✅ Functional Pass: Circuit behavior matches specification (SAX validation)
    - ✅ Optimization Pass: Optimization completed successfully (if enabled)
    
    Formula: Spec@k_full = 1 - C(n-c_f, k) / C(n, k)
    Where c_f = number of samples passing structural AND functional AND optimization validation.
    
    Args:
        results: List of generation results with validation reports
        k: Number of samples to consider (default: 3)
    
    Returns:
        Spec@k_full score (0.0 to 1.0)
    """
    # Count samples passing structural, functional, and optimization validation
    full_successes = []
    
    for r in results:
        # Structural pass: component built AND DRC passed
        component_built = r.get('component_built', False)
        drc_passed = r.get('drc_passed', True)  # Default True if DRC not checked
        structural_pass = component_built and drc_passed
        
        # Functional pass: SAX validation passed
        functional_pass = r.get('functional_pass', False)
        
        # Optimization pass: optimization completed (if enabled)
        # If optimization is not enabled, this is considered passed
        optimization_done = r.get('optimization_done', True)  # Default True if optimization not enabled
        
        full_successes.append(structural_pass and functional_pass and optimization_done)
    
    num_correct = sum(full_successes)
    num_samples = len(results)
    
    return estimate_pass_at_k(num_samples, num_correct, k)


def compute_spec_at_k(results: List[Dict], k: int = 3) -> float:
    """
    Compute Spec@k: Specification satisfaction @k (legacy function, now calls Spec@k_full).
    
    This is kept for backward compatibility. Use compute_spec_at_k_full() for clarity.
    
    Args:
        results: List of generation results with validation reports
        k: Number of samples to consider (default: 3)
    
    Returns:
        Spec@k score (0.0 to 1.0)
    """
    return compute_spec_at_k_full(results, k)


def compute_opt_efficiency(result: Dict, epsilon: float = 0.1) -> float:
    """
    Compute Opt-Efficiency: Normalized optimization improvement with ε stabilization.

    Formula: OptEff_i = (IL_before - IL_after) / (IL_before + ε)
    Then clamped to [0, 1]: OptEff_i* = max(0, min(1, OptEff_i))

    Args:
        result: Generation result with optimization reports
        epsilon: Small constant to avoid division by zero (default: 0.1 dB)

    Returns:
        Opt-Efficiency score (0.0 to 1.0)
    """
    opt_report = result.get('validation_reports', {}).get('optimization', {})

    before = opt_report.get('circuit_loss_before_db')
    after = opt_report.get('circuit_loss_after_db')

    # Return 0.0 if optimization data unavailable or invalid
    if before is None or after is None or before < 0:
        return 0.0

    # Formula: OptEff_i = (IL_before - IL_after) / (IL_before + ε)
    improvement = before - after
    opt_eff = improvement / (before + epsilon)

    # Clamp to [0, 1] range (efficiency can be negative if optimization made things worse)
    return max(0.0, min(1.0, opt_eff))


def compute_robust_pass_score(
    results: List[Dict],
    num_perturbations: int = 10,
    perturbation_params: Optional[Dict] = None
) -> float:
    """
    Compute RobustPass: Robustness under perturbations.

    For each spec-satisfying sample, generate M perturbed versions and check if they still pass spec.
    Robust_i = (1/M) * sum(r_{i,j} for j=1..M) where r_{i,j} = 1 if perturbed sample passes spec
    RobustPass = (1/c) * sum(Robust_i for all spec-satisfying samples) if c > 0, else 0

    Args:
        results: List of generation results with validation reports
        num_perturbations: Number of perturbations per sample (M, default: 10)
        perturbation_params: Parameters for perturbations (waveguide width offsets, coupling variations, etc.)

    Returns:
        RobustPass score (0.0 to 1.0)
    """
    if perturbation_params is None:
        perturbation_params = {
            'width_offset_std': 0.01,  # 1% standard deviation
            'coupling_variation_std': 0.05,  # 5% standard deviation
            'loss_noise_std': 0.1,  # 0.1 dB standard deviation
            'wavelength_drift': 0.1e-9,  # 0.1 nm drift
            'phase_error_std': 0.05,  # 5% phase error
        }

    # Count spec-satisfying samples
    spec_satisfying = []
    for r in results:
        structural_pass = r.get('success', False)
        functional_pass = r.get('validation_reports', {}).get('functional', {}).get('passed', False)
        if structural_pass and functional_pass:
            spec_satisfying.append(r)

    if len(spec_satisfying) == 0:
        return 0.0

    # For each spec-satisfying sample, compute robustness
    robust_scores = []
    for result in spec_satisfying:
        # TODO: Implement actual perturbation generation and validation
        # For now, return placeholder (0.8 = 80% of perturbations pass)
        # This should be replaced with actual perturbation logic
        robust_scores.append(0.8)  # Placeholder

    # Average robustness across all spec-satisfying samples
    return np.mean(robust_scores) if robust_scores else 0.0


def compute_overall_robustness(
    spec_at_k: float,
    opt_efficiency: float,
    robust_pass: float,
    alpha: float = 0.5,
    beta: float = 0.2,
    gamma: float = 0.3
) -> float:
    """
    Compute Overall Robustness Score R: Combined correctness + performance metric (correctness-gated).

    Formula: R = Spec@k × (α + β·OptEff + γ·RobustPass) where α + β + γ = 1

    Properties:
    - If Spec@k = 0, then R = 0 (correctness-gated)
    - As OptEff and RobustPass increase, R increases, but only to the extent that Spec@k is high
    - R ∈ [0, 1] by construction

    Args:
        spec_at_k: Spec@k score
        opt_efficiency: Average Opt-Efficiency score
        robust_pass: RobustPass score
        alpha: Weight for base term (default: 0.5)
        beta: Weight for OptEff (default: 0.2)
        gamma: Weight for RobustPass (default: 0.3)

    Returns:
        Overall Robustness Score R (0.0 to 1.0)
    """
    # Validate weights sum to 1.0
    if abs(alpha + beta + gamma - 1.0) > 1e-6:
        raise ValueError(f"Weights must sum to 1.0, got α={alpha}, β={beta}, γ={gamma}")

    # Correctness-gated: R = 0 if Spec@k = 0
    if spec_at_k == 0:
        return 0.0

    # Formula: R = Spec@k × (α + β·OptEff + γ·RobustPass)
    weighted_sum = alpha + beta * opt_efficiency + gamma * robust_pass
    robustness = spec_at_k * weighted_sum

    # Clamp to [0, 1] (should already be in range, but ensure)
    return max(0.0, min(1.0, robustness))


def compute_metrics_for_circuit(
    results: List[Dict],
    k: int = 3,
    alpha: float = 0.5,
    beta: float = 0.2,
    gamma: float = 0.3,
    epsilon: float = 0.1,
    compute_robust_pass: bool = False,
    phase: str = "picasso"  # "vanilla" or "picasso"
) -> Dict:
    """
    Compute all metrics for a single circuit type.

    Args:
        results: List of generation results for this circuit
        k: Number of samples to consider
        alpha: Base weight in robustness score
        beta: OptEff weight in robustness score
        gamma: RobustPass weight in robustness score
        epsilon: Small constant for OptEff calculation (default: 0.1 dB)
        compute_robust_pass: Whether to compute RobustPass (can be slow, default: False)
        phase: "vanilla" (Phase 1) or "picasso" (Phase 2), determines which Spec@k to compute

    Returns:
        Dictionary with all computed metrics
    """
    # Pass@k (structural only - legacy)
    structural_successes = sum(1 for r in results if r.get('success', False))
    pass_at_k = estimate_pass_at_k(len(results), structural_successes, k)

    # Spec@k_structural (used for both Phase 1 and Phase 2)
    spec_at_k_structural = compute_spec_at_k_structural(results, k)
    
    # Spec@k_full (evaluated separately for both phases)
    spec_at_k_full = compute_spec_at_k_full(results, k)
    
    # Use Spec@k_structural as the primary metric for both phases
    spec_at_k = spec_at_k_structural

    # Average Opt-Efficiency
    opt_efficiencies = [
        compute_opt_efficiency(r, epsilon=epsilon)
        for r in results
        if r.get('success', False)
    ]
    avg_opt_efficiency = np.mean(opt_efficiencies) if opt_efficiencies else 0.0

    # RobustPass (optional, can be slow)
    robust_pass_val = 0.0
    if compute_robust_pass:
        robust_pass_val = compute_robust_pass_score(results)

    # Overall Robustness Score R
    robustness = compute_overall_robustness(
        spec_at_k, avg_opt_efficiency, robust_pass_val, alpha, beta, gamma
    )

    # Count structural passes (for Spec@k_structural)
    num_structural_pass = sum(1 for r in results 
                              if r.get('component_built', False) and r.get('drc_passed', True))
    
    # Count full passes (for Spec@k_full)
    num_full_pass = sum(1 for r in results
                       if (r.get('component_built', False) and r.get('drc_passed', True) and
                           r.get('functional_pass', False) and r.get('optimization_done', True)))
    
    return {
        'pass_at_k': float(pass_at_k),
        'spec_at_k_structural': float(spec_at_k_structural),
        'spec_at_k_full': float(spec_at_k_full),
        'spec_at_k': float(spec_at_k),  # Depends on phase
        'avg_opt_efficiency': float(avg_opt_efficiency),
        'robust_pass': float(robust_pass_val),
        'robustness_score': float(robustness),
        'num_samples': len(results),
        'num_structural_pass': num_structural_pass,
        'num_full_pass': num_full_pass
    }


def compute_comparison_metrics(
    raw_llm_results: List[Dict],
    framework_results: List[Dict],
    k: int = 3,
    compute_robust_pass: bool = False
) -> Dict:
    """
    Compute comparison metrics between raw LLM and framework.

    Args:
        raw_llm_results: Results from vanilla LLM (Phase 1)
        framework_results: Results from PICasso framework (Phase 2)
        k: Number of samples to consider
        compute_robust_pass: Whether to compute RobustPass (can be slow, default: False)

    Returns:
        Dictionary with comparison metrics
    """
    raw_metrics = compute_metrics_for_circuit(raw_llm_results, k, compute_robust_pass=compute_robust_pass)
    framework_metrics = compute_metrics_for_circuit(framework_results, k, compute_robust_pass=compute_robust_pass)

    return {
        'raw_llm': raw_metrics,
        'framework': framework_metrics,
        'improvement': {
            'pass_at_k': framework_metrics['pass_at_k'] - raw_metrics['pass_at_k'],
            'spec_at_k': framework_metrics['spec_at_k'] - raw_metrics['spec_at_k'],
            'opt_efficiency': framework_metrics['avg_opt_efficiency'] - raw_metrics['avg_opt_efficiency'],
            'robust_pass': framework_metrics['robust_pass'] - raw_metrics['robust_pass'],
            'robustness_score': framework_metrics['robustness_score'] - raw_metrics['robustness_score']
        }
    }

