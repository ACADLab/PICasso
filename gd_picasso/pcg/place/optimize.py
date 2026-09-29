"""
Multi-start gradient descent placement; write-back via store.set_placement.

θ is held discrete (fixture / seed rotation). Only (x, y) are optimized.
No DREAMPlace / Nesterov / FFT — plain finite-difference GD for the spike.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..store import PCGStore
from .objective import ObjectiveTerms, ObjectiveWeights, evaluate_objective
from .tensors import PlacementProblem, build_placement_problem

AGENT_NAME = "place_spike"


@dataclass
class PlaceResult:
    """One multi-start run (ESTIMATOR_ONLY)."""

    xy: np.ndarray
    theta_rad: np.ndarray
    terms: ObjectiveTerms
    start_terms: ObjectiveTerms
    n_starts: int
    best_start: int
    history: List[float] = field(default_factory=list)
    banner: str = (
        "ESTIMATOR_ONLY — predicted L/φ vs planted or pre-route estimates; "
        "not validated against routed geometry."
    )

    def summary(self) -> Dict[str, float]:
        out = {
            "n_starts": float(self.n_starts),
            "best_start": float(self.best_start),
            "start_total": self.start_terms.total,
            "final_total": self.terms.total,
            "start_W_cos": self.start_terms.W_cos,
            "final_W_cos": self.terms.W_cos,
            "start_D": self.start_terms.D,
            "final_D": self.terms.D,
            "start_phi_sq": self.start_terms.phi_sq,
            "final_phi_sq": self.terms.phi_sq,
        }
        for k, v in self.terms.delta_phi_hat.items():
            out[f"final_dphi[{k}]"] = v
        return out


def _finite_diff_grad(
    problem: PlacementProblem,
    xy: np.ndarray,
    theta: np.ndarray,
    weights: ObjectiveWeights,
    eps: float = 1e-2,
) -> np.ndarray:
    """∂total/∂xy via central differences (movable nodes only)."""
    g = np.zeros_like(xy)
    base = evaluate_objective(problem, xy, theta, weights).total
    for i in range(problem.n_nodes):
        if not problem.movable[i]:
            continue
        for d in (0, 1):
            xp = xy.copy()
            xm = xy.copy()
            xp[i, d] += eps
            xm[i, d] -= eps
            fp = evaluate_objective(problem, xp, theta, weights).total
            fm = evaluate_objective(problem, xm, theta, weights).total
            g[i, d] = (fp - fm) / (2.0 * eps)
            # unused base keeps API clear for future autodiff swap
            _ = base
    return g


def _gd_one(
    problem: PlacementProblem,
    xy0: np.ndarray,
    theta: np.ndarray,
    weights: ObjectiveWeights,
    *,
    steps: int = 40,
    lr: float = 2.0,
    eps: float = 1e-2,
) -> Tuple[np.ndarray, List[float]]:
    xy = xy0.copy()
    hist: List[float] = []
    for _ in range(steps):
        terms = evaluate_objective(problem, xy, theta, weights)
        hist.append(terms.total)
        grad = _finite_diff_grad(problem, xy, theta, weights, eps=eps)
        # Clip gradient to avoid wild jumps on coarse eps
        gn = np.linalg.norm(grad)
        if gn > 100.0:
            grad = grad * (100.0 / gn)
        xy = xy - lr * grad
    hist.append(evaluate_objective(problem, xy, theta, weights).total)
    return xy, hist


def _asymmetric_seeds(
    problem: PlacementProblem,
    n_starts: int,
    rng: np.random.Generator,
) -> List[np.ndarray]:
    """Initial XY seeds including deliberate arm imbalance for φ ablation."""
    seeds: List[np.ndarray] = [problem.xy.copy()]
    for s in range(1, n_starts):
        xy = problem.xy.copy()
        # Random jitter
        xy = xy + rng.normal(0.0, 15.0 + 5.0 * s, size=xy.shape)
        # Push alternate mid-nodes in opposite y to break symmetry
        if problem.n_nodes >= 3:
            for i in range(problem.n_nodes):
                if not problem.movable[i]:
                    continue
                xy[i, 1] += (8.0 * s) * (1.0 if i % 2 == 0 else -1.0)
                xy[i, 0] += (5.0 * s) * (1.0 if i % 3 == 0 else -0.5)
        seeds.append(xy)
    return seeds


def place_multistart(
    store: PCGStore,
    *,
    weights: Optional[ObjectiveWeights] = None,
    n_starts: int = 4,
    steps: int = 40,
    lr: float = 2.0,
    seed: int = 0,
    write_back: bool = True,
    problem: Optional[PlacementProblem] = None,
) -> PlaceResult:
    """Multi-start GD on (x,y); optionally write placements into ``store``."""
    w = weights or ObjectiveWeights()
    prob = problem or build_placement_problem(store)
    rng = np.random.default_rng(seed)
    seeds = _asymmetric_seeds(prob, n_starts, rng)

    start_terms = evaluate_objective(prob, seeds[0], prob.theta_rad, w)
    best_xy = seeds[0]
    best_terms = start_terms
    best_start = 0
    best_hist: List[float] = [start_terms.total]

    for si, xy0 in enumerate(seeds):
        xy_f, hist = _gd_one(prob, xy0, prob.theta_rad, w, steps=steps, lr=lr)
        terms = evaluate_objective(prob, xy_f, prob.theta_rad, w)
        if terms.total < best_terms.total:
            best_xy = xy_f
            best_terms = terms
            best_start = si
            best_hist = hist

    if write_back:
        write_placement(store, prob, best_xy, agent=AGENT_NAME)

    return PlaceResult(
        xy=best_xy,
        theta_rad=prob.theta_rad.copy(),
        terms=best_terms,
        start_terms=start_terms,
        n_starts=n_starts,
        best_start=best_start,
        history=best_hist,
    )


def write_placement(
    store: PCGStore,
    problem: PlacementProblem,
    xy: np.ndarray,
    *,
    agent: str = AGENT_NAME,
    node_ids: Optional[Sequence[str]] = None,
) -> None:
    """Persist (x,y) via ``store.set_placement``; rotation left unchanged."""
    ids = list(node_ids) if node_ids is not None else problem.node_ids
    for i, nid in enumerate(ids):
        rot = int(round(math_degrees(problem.theta_rad[i])))
        store.set_placement(
            nid,
            x=float(xy[i, 0]),
            y=float(xy[i, 1]),
            rotation=rot,
            agent=agent,
        )


def math_degrees(rad: float) -> float:
    return float(np.degrees(rad))
