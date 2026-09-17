"""
A3 — Optimization agent: selects FoM weights, restart budget, stop rule.

The optimizer itself (JAX/SAX GD) stays outside; this agent only controls it.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from gd_picasso.pcg.store import PCGStore


class OptControl(BaseModel):
    objective: str = "il_max"
    max_iter: int = 200
    restarts: int = 4
    tol: float = 1e-4
    use_gradients: bool = True
    weights: Dict[str, float] = Field(
        default_factory=lambda: {"il": 1.0, "er": 0.5, "phase": 1.0}
    )


class OptimizationAgent:
    """A3: controller for the differentiable FoM loop."""

    def __init__(self) -> None:
        self.control = OptControl()

    def propose(
        self,
        store: PCGStore,
        metrics: Optional[Dict[str, float]] = None,
    ) -> OptControl:
        metrics = metrics or {}
        ctrl = self.control.model_copy(deep=True)
        n = len(store.nodes)
        if n > 20:
            ctrl.restarts = max(2, ctrl.restarts // 2)
            ctrl.max_iter = min(400, ctrl.max_iter + 100)
        if metrics.get("il_db", 0) > 5.0:
            ctrl.weights["il"] = 2.0
        store.journal.append(
            "A3_propose_opt",
            ctrl.model_dump(),
            agent="A3",
        )
        self.control = ctrl
        return ctrl

    def should_stop(self, history: list) -> bool:
        if len(history) < 2:
            return False
        return abs(history[-1] - history[-2]) < self.control.tol
