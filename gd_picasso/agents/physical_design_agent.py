"""
A2 — Physical-design agent: controller, not solver.

Writes only hyper-parameters (weights, density, net groups). Solvers stay
deterministic and live outside this module.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from gd_picasso.pcg.store import PCGStore


class PhysicalDesignKnobs(BaseModel):
    lambda_D: float = 1.0
    lambda_F: float = 1.0
    lambda_phi: float = 1.0
    lambda_T: float = 0.5
    target_density: float = 0.6
    aspect_ratio: float = 1.0
    net_groups: List[str] = Field(default_factory=list)
    routing_order_policy: str = "phase_critical_first"
    inflate: bool = False


class PhysicalDesignAgent:
    """A2: propose P&R hyper-parameters from metric vector + graph view."""

    def __init__(self) -> None:
        self.knobs = PhysicalDesignKnobs()

    def propose(
        self,
        store: PCGStore,
        metrics: Optional[Dict[str, float]] = None,
    ) -> PhysicalDesignKnobs:
        metrics = metrics or {}
        knobs = self.knobs.model_copy(deep=True)
        # Simple reactive policy — replace with LLM-over-typed-knobs later
        if metrics.get("n_drv", 0) > 0:
            knobs.inflate = True
            knobs.target_density = max(0.4, knobs.target_density - 0.1)
        if metrics.get("delta_phi_max", 0) > 0.05:
            knobs.lambda_phi = min(10.0, knobs.lambda_phi * 2.0)
        # Collect constraint groups from edges
        groups = sorted({
            e.constraint_group for e in store.edges if e.constraint_group
        })
        knobs.net_groups = groups
        store.journal.append(
            "A2_propose_knobs",
            knobs.model_dump(),
            agent="A2",
        )
        self.knobs = knobs
        return knobs
