"""
PICasso Benchmarking Metrics

Implements three novel metrics for photonic circuit generation:
1. Spec@k: Specification satisfaction @k (structural + functional)
2. Opt-Efficiency: Optimization improvement (normalized IL reduction)
3. Robustness Score: Combined correctness + performance metric
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


def compute_spec_at_k(results: List[Dict], k: int = 3) -> float:
    """
    Compute Spec@k: Specification satisfaction @k.

    Spec@k extends Pass@k by requiring BOTH structural AND functional validation.

    Args:
        results: List of generation results with validation reports
        k: Number of samples to consider (default: 3)

    Returns:
        Spec@k score (0.0 to 1.0)
    """
    # Count samples passing both structural and functional validation
    spec_successes = []

    for r in results:
        structural_pass = r.get('success', False)
        functional_pass = r.get('validation_reports', {}).get('functional', {}).get('passed', False)

        spec_successes.append(structural_pass and functional_pass)

    num_correct = sum(spec_successes)
    num_samples = len(results)

    return estimate_pass_at_k(num_samples, num_correct, k)


def compute_opt_efficiency(result: Dict) -> float:
    """
    Compute Opt-Efficiency: Normalized optimization improvement.

    Formula: Opt-Efficiency = (IL_before - IL_after) / IL_before

    Args:
        result: Generation result with optimization reports

    Returns:
        Opt-Efficiency score (0.0 to 1.0)
    """
    opt_report = result.get('validation_reports', {}).get('optimization', {})

    before = opt_report.get('circuit_loss_before_db')
    after = opt_report.get('circuit_loss_after_db')

    # Return 0.0 if optimization data unavailable or invalid
    if before is None or after is None or before == 0:
        return 0.0

    improvement = before - after
    efficiency = improvement / before

    # Clamp to [0, 1] range (efficiency can be negative if optimization made things worse)
    return max(0.0, min(1.0, efficiency))


def compute_robustness_score(
    spec_at_k: float,
    opt_efficiency: float,
    alpha: float = 0.7,
    beta: float = 0.3
) -> float:
    """
    Compute Robustness Score: Combined correctness + performance metric.

    Formula: Robustness = α × Spec@k + β × Opt-Efficiency

    Args:
        spec_at_k: Spec@k score
        opt_efficiency: Opt-Efficiency score
        alpha: Weight for Spec@k (default: 0.7)
        beta: Weight for Opt-Efficiency (default: 0.3)

    Returns:
        Robustness score (0.0 to 1.0)
    """
    # Validate weights sum to 1.0
    if abs(alpha + beta - 1.0) > 1e-6:
        raise ValueError(f"Weights must sum to 1.0, got α={alpha}, β={beta}")

    return alpha * spec_at_k + beta * opt_efficiency


def compute_metrics_for_circuit(
    results: List[Dict],
    k: int = 3,
    alpha: float = 0.7,
    beta: float = 0.3
) -> Dict:
    """
    Compute all metrics for a single circuit type.

    Args:
        results: List of generation results for this circuit
        k: Number of samples to consider
        alpha: Spec@k weight in robustness score
        beta: Opt-Efficiency weight in robustness score

    Returns:
        Dictionary with all computed metrics
    """
    # Pass@k (structural only)
    structural_successes = sum(1 for r in results if r.get('success', False))
    pass_at_k = estimate_pass_at_k(len(results), structural_successes, k)

    # Spec@k (structural + functional)
    spec_at_k = compute_spec_at_k(results, k)

    # Average Opt-Efficiency
    opt_efficiencies = [compute_opt_efficiency(r) for r in results if r.get('success', False)]
    avg_opt_efficiency = np.mean(opt_efficiencies) if opt_efficiencies else 0.0

    # Robustness Score
    robustness = compute_robustness_score(spec_at_k, avg_opt_efficiency, alpha, beta)

    return {
        'pass_at_k': float(pass_at_k),
        'spec_at_k': float(spec_at_k),
        'avg_opt_efficiency': float(avg_opt_efficiency),
        'robustness_score': float(robustness),
        'num_samples': len(results),
        'num_structural_pass': structural_successes,
        'num_spec_pass': sum(1 for r in results if r.get('success', False) and
                            r.get('validation_reports', {}).get('functional', {}).get('passed', False))
    }


def compute_comparison_metrics(
    raw_llm_results: List[Dict],
    framework_results: List[Dict],
    k: int = 3
) -> Dict:
    """
    Compute comparison metrics between raw LLM and framework.

    Args:
        raw_llm_results: Results from vanilla LLM (Phase 1)
        framework_results: Results from PICasso framework (Phase 2)
        k: Number of samples to consider

    Returns:
        Dictionary with comparison metrics
    """
    raw_metrics = compute_metrics_for_circuit(raw_llm_results, k)
    framework_metrics = compute_metrics_for_circuit(framework_results, k)

    return {
        'raw_llm': raw_metrics,
        'framework': framework_metrics,
        'improvement': {
            'pass_at_k': framework_metrics['pass_at_k'] - raw_metrics['pass_at_k'],
            'spec_at_k': framework_metrics['spec_at_k'] - raw_metrics['spec_at_k'],
            'opt_efficiency': framework_metrics['avg_opt_efficiency'] - raw_metrics['avg_opt_efficiency'],
            'robustness_score': framework_metrics['robustness_score'] - raw_metrics['robustness_score']
        }
    }
