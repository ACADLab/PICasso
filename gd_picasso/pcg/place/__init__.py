"""
Lane Place spike — photonic placement (Tier-2 preview).

Results are **ESTIMATOR_ONLY** until routed geometry exists and
``fidelity_vs_routed`` / ``estimator_fidelity(..., treat_edge_length_as='routed')``
clears the banner (``ROUTED_FIDELITY_BANNER``).
No DREAMPlace / FFT density / GPU router novelty claims.
"""

from __future__ import annotations

ESTIMATOR_ONLY_BANNER = (
    "ESTIMATOR_ONLY — predicted L/φ vs planted or pre-route estimates; "
    "not validated against routed geometry."
)

ROUTED_FIDELITY_BANNER = (
    "ROUTED — lengths from routed / LiDAR-IR geometry; "
    "estimator-only banner cleared via fidelity_vs_routed gate."
)

from .tensors import PlacementProblem, build_placement_problem
from .objective import ObjectiveWeights, evaluate_objective
from .optimize import PlaceResult, place_multistart
from .estimator_fidelity import FidelityReport, estimator_fidelity
from .torch_placer import have_torch, place_torch
from .torch_fom import F_torch, LOSS_DB_PER_CM

__all__ = [
    "ESTIMATOR_ONLY_BANNER",
    "ROUTED_FIDELITY_BANNER",
    "PlacementProblem",
    "build_placement_problem",
    "ObjectiveWeights",
    "evaluate_objective",
    "PlaceResult",
    "place_multistart",
    "FidelityReport",
    "estimator_fidelity",
    "have_torch",
    "place_torch",
    "F_torch",
    "LOSS_DB_PER_CM",
]
