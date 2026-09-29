"""
Lane Place spike — estimator-only photonic placement (Tier-2 preview).

All results are **ESTIMATOR_ONLY** until routed geometry exists.
No DREAMPlace / FFT density / GPU router.
"""

from __future__ import annotations

ESTIMATOR_ONLY_BANNER = (
    "ESTIMATOR_ONLY — predicted L/φ vs planted or pre-route estimates; "
    "not validated against routed geometry."
)

from .tensors import PlacementProblem, build_placement_problem
from .objective import ObjectiveWeights, evaluate_objective
from .optimize import PlaceResult, place_multistart
from .estimator_fidelity import FidelityReport, estimator_fidelity

__all__ = [
    "ESTIMATOR_ONLY_BANNER",
    "PlacementProblem",
    "build_placement_problem",
    "ObjectiveWeights",
    "evaluate_objective",
    "PlaceResult",
    "place_multistart",
    "FidelityReport",
    "estimator_fidelity",
]
