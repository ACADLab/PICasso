"""
Placement objective: W_cos + λ_D·D + λ_φ·Σ(Δφ̂_g)² (+ λ_F stub).

W_cos follows an Apollo-style cosine-weighted / orientation-aware wirelength
with α ≈ 1.4 (asymmetric bending proxy). Density D is a soft pairwise
overlap proxy — not an FFT Poisson solve.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from .tensors import (
    PlacementProblem,
    arm_length_estimate,
    port_world,
)

# Apollo cosWA scale (plan / design-note)
DEFAULT_ALPHA = 1.4
NEFF = 2.34
WAVELENGTH_UM = 1.55


@dataclass
class ObjectiveWeights:
    lambda_D: float = 1.0
    lambda_phi: float = 1.0
    lambda_F: float = 0.0  # stub — no SAX FoM in this spike
    alpha: float = DEFAULT_ALPHA
    neff: float = NEFF
    wavelength_um: float = WAVELENGTH_UM


@dataclass
class ObjectiveTerms:
    W_cos: float
    D: float
    phi_sq: float
    F_hat: float
    total: float
    delta_phi_hat: Dict[str, float]

    def as_dict(self) -> Dict[str, float]:
        return {
            "W_cos": self.W_cos,
            "D": self.D,
            "phi_sq": self.phi_sq,
            "F_hat": self.F_hat,
            "total": self.total,
            **{f"dphi[{k}]": v for k, v in self.delta_phi_hat.items()},
        }


def _cos_wa_net(
    problem: PlacementProblem,
    net_idx: int,
    xy: np.ndarray,
    theta: np.ndarray,
    alpha: float,
) -> float:
    """Orientation-aware wirelength for one 2-pin net.

    L = Manhattan(port_s, port_d)
    bend proxy from how poorly outward orientations face the connection:
        misalign = (1 - u_s·v) + (1 - u_d·(-v))
    W = L + α · R_eff · misalign
    """
    net = problem.nets[net_idx]
    p_s, u_s = port_world(problem, net.src, xy=xy, theta=theta)
    p_d, u_d = port_world(problem, net.dst, xy=xy, theta=theta)
    delta = p_d - p_s
    L = abs(delta[0]) + abs(delta[1])
    nrm = math.hypot(float(delta[0]), float(delta[1])) + 1e-9
    v = delta / nrm
    align_s = float(np.clip(np.dot(u_s, v), -1.0, 1.0))
    align_d = float(np.clip(np.dot(u_d, -v), -1.0, 1.0))
    misalign = (1.0 - align_s) + (1.0 - align_d)
    r_eff = 10.0  # bend-radius scale (µm)
    return L + alpha * r_eff * misalign


def wirelength_cos(
    problem: PlacementProblem,
    xy: np.ndarray,
    theta: np.ndarray,
    alpha: float = DEFAULT_ALPHA,
) -> float:
    if not problem.nets:
        return 0.0
    return float(
        sum(_cos_wa_net(problem, i, xy, theta, alpha) for i in range(len(problem.nets)))
    )


def density_proxy(
    problem: PlacementProblem,
    xy: np.ndarray,
) -> float:
    """Soft pairwise AABB overlap energy (no FFT)."""
    n = problem.n_nodes
    if n < 2:
        return 0.0
    half = problem.half_extents
    acc = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            gap_x = abs(xy[i, 0] - xy[j, 0]) - (half[i, 0] + half[j, 0])
            gap_y = abs(xy[i, 1] - xy[j, 1]) - (half[i, 1] + half[j, 1])
            ox = max(0.0, -gap_x)
            oy = max(0.0, -gap_y)
            if ox > 0.0 and oy > 0.0:
                acc += (ox * oy) ** 2
    return float(acc)


def phase_penalty(
    problem: PlacementProblem,
    xy: np.ndarray,
    theta: np.ndarray,
    *,
    neff: float = NEFF,
    wavelength_um: float = WAVELENGTH_UM,
) -> Tuple[float, Dict[str, float]]:
    """Σ_g (Δφ̂_g)² with Δφ̂ = 2π·neff·ΔL/λ from estimated arm lengths."""
    k = 2.0 * math.pi * neff / wavelength_um
    dphi: Dict[str, float] = {}
    total = 0.0
    for g in problem.phase_groups:
        if len(g.arm_net_indices) < 2:
            dphi[g.group_id] = 0.0
            continue
        lengths = [
            arm_length_estimate(problem, arm, xy=xy, theta=theta)
            for arm in g.arm_net_indices
        ]
        # Matched-length: max−min (same as SPA v0 two-path field)
        delta_L = max(lengths) - min(lengths)
        dp = k * delta_L
        dphi[g.group_id] = float(dp)
        total += dp * dp
    return float(total), dphi


def evaluate_objective(
    problem: PlacementProblem,
    xy: Optional[np.ndarray] = None,
    theta: Optional[np.ndarray] = None,
    weights: Optional[ObjectiveWeights] = None,
) -> ObjectiveTerms:
    """Evaluate W_cos + λ_D·D + λ_φ·Σ(Δφ̂)² (+ λ_F stub)."""
    w = weights or ObjectiveWeights()
    xy_arr = problem.xy if xy is None else xy
    th_arr = problem.theta_rad if theta is None else theta

    W = wirelength_cos(problem, xy_arr, th_arr, alpha=w.alpha)
    D = density_proxy(problem, xy_arr)
    phi_sq, dphi = phase_penalty(
        problem, xy_arr, th_arr, neff=w.neff, wavelength_um=w.wavelength_um
    )
    F = 0.0  # λ_F stub — no pre-route SAX FoM yet
    total = W + w.lambda_D * D + w.lambda_phi * phi_sq + w.lambda_F * F
    return ObjectiveTerms(
        W_cos=W,
        D=D,
        phi_sq=phi_sq,
        F_hat=F,
        total=total,
        delta_phi_hat=dphi,
    )
