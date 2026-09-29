"""
Estimator fidelity: predicted vs lengths (planted OK until routes exist).

Banner every report **ESTIMATOR_ONLY**.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..store import PCGStore
from ..types import EdgeLayer
from . import ESTIMATOR_ONLY_BANNER
from .tensors import (
    PlacementProblem,
    arm_length_estimate,
    build_placement_problem,
    estimated_net_length,
)


@dataclass
class NetFidelity:
    src: str
    dst: str
    predicted_um: float
    reference_um: float
    abs_err_um: float


@dataclass
class FidelityReport:
    """Predicted vs planted/reference length comparison."""

    banner: str = ESTIMATOR_ONLY_BANNER
    mode: str = "planted"  # planted | routed | self
    nets: List[NetFidelity] = field(default_factory=list)
    mae_um: float = 0.0
    max_err_um: float = 0.0
    corr: float = float("nan")
    arm_delta_pred_um: Dict[str, float] = field(default_factory=dict)
    arm_delta_ref_um: Dict[str, float] = field(default_factory=dict)

    def summary_lines(self) -> List[str]:
        lines = [
            self.banner,
            f"mode={self.mode}  n_nets={len(self.nets)}  "
            f"MAE={self.mae_um:.3f} µm  max|err|={self.max_err_um:.3f} µm  "
            f"corr={self.corr:.4f}",
        ]
        for gid in sorted(self.arm_delta_pred_um):
            lines.append(
                f"  armΔ[{gid}] pred={self.arm_delta_pred_um[gid]:.3f} µm  "
                f"ref={self.arm_delta_ref_um.get(gid, float('nan')):.3f} µm"
            )
        return lines


def _reference_lengths(
    store: PCGStore,
    problem: PlacementProblem,
    *,
    prefer_edge_length: bool = True,
    treat_edge_length_as: str = "planted",
) -> tuple[np.ndarray, str]:
    """Per-net reference length from edge.length_um or estimator at store xy.

    Until a real router back-annotates, ``length_um`` is treated as **planted**
    (``treat_edge_length_as='planted'``). Pass ``'routed'`` only when lengths
    come from routed geometry.
    """
    optical = [e for e in store.edges if e.layer == EdgeLayer.OPTICAL]
    refs = np.zeros(len(problem.nets), dtype=np.float64)
    n_from_edge = 0
    for i, net in enumerate(problem.nets):
        e = optical[net.edge_idx] if net.edge_idx < len(optical) else None
        if prefer_edge_length and e is not None and e.length_um is not None:
            refs[i] = float(e.length_um)
            n_from_edge += 1
        else:
            refs[i] = estimated_net_length(problem, net)
    if n_from_edge == len(problem.nets) and problem.nets:
        mode = treat_edge_length_as
    elif n_from_edge > 0:
        mode = f"mixed_{treat_edge_length_as}_estimator"
    else:
        mode = "planted"
    return refs, mode


def plant_estimated_lengths(
    store: PCGStore,
    problem: Optional[PlacementProblem] = None,
) -> np.ndarray:
    """Write estimator lengths onto edges as planted references (spike helper).

    Returns the planted length vector (also stored on ``edge.length_um``).
    """
    prob = problem or build_placement_problem(store)
    optical = [e for e in store.edges if e.layer == EdgeLayer.OPTICAL]
    planted = np.zeros(len(prob.nets), dtype=np.float64)
    for i, net in enumerate(prob.nets):
        L = estimated_net_length(prob, net)
        planted[i] = L
        if net.edge_idx < len(optical):
            optical[net.edge_idx].length_um = L
    return planted


def estimator_fidelity(
    store: PCGStore,
    *,
    problem: Optional[PlacementProblem] = None,
    xy: Optional[np.ndarray] = None,
    theta: Optional[np.ndarray] = None,
    prefer_edge_length: bool = True,
    treat_edge_length_as: str = "planted",
    reference_um: Optional[np.ndarray] = None,
) -> FidelityReport:
    """Compare predicted net lengths to planted/routed references.

    Until routed geometry exists, references are planted estimator lengths
    (same formula at a reference placement) — still bannered ESTIMATOR_ONLY.
    """
    prob = problem or build_placement_problem(store)
    xy_arr = prob.xy if xy is None else xy
    th_arr = prob.theta_rad if theta is None else theta

    pred = np.array(
        [
            estimated_net_length(prob, net, xy=xy_arr, theta=th_arr)
            for net in prob.nets
        ],
        dtype=np.float64,
    )
    ref_prob = build_placement_problem(store)
    if reference_um is not None:
        refs = np.asarray(reference_um, dtype=np.float64)
        mode = treat_edge_length_as
        if len(refs) != len(prob.nets):
            raise ValueError(
                f"reference_um length {len(refs)} != n_nets {len(prob.nets)}"
            )
    else:
        refs, mode = _reference_lengths(
            store,
            ref_prob,
            prefer_edge_length=prefer_edge_length,
            treat_edge_length_as=treat_edge_length_as,
        )

    rows: List[NetFidelity] = []
    for i, net in enumerate(prob.nets):
        err = abs(float(pred[i]) - float(refs[i]))
        rows.append(
            NetFidelity(
                src=f"{net.src.node_id},{net.src.port}",
                dst=f"{net.dst.node_id},{net.dst.port}",
                predicted_um=float(pred[i]),
                reference_um=float(refs[i]),
                abs_err_um=err,
            )
        )

    mae = float(np.mean([r.abs_err_um for r in rows])) if rows else 0.0
    max_err = float(np.max([r.abs_err_um for r in rows])) if rows else 0.0
    if len(rows) >= 2 and np.std(pred) > 1e-12 and np.std(refs) > 1e-12:
        corr = float(np.corrcoef(pred, refs)[0, 1])
    else:
        corr = float("nan")

    arm_pred: Dict[str, float] = {}
    arm_ref: Dict[str, float] = {}
    for g in prob.phase_groups:
        if len(g.arm_net_indices) < 2:
            continue
        lp = [
            arm_length_estimate(prob, arm, xy=xy_arr, theta=th_arr)
            for arm in g.arm_net_indices
        ]
        # Reference arm Δ from planted per-net refs when available
        lr = []
        for arm in g.arm_net_indices:
            lr.append(float(sum(refs[i] for i in arm)))
        arm_pred[g.group_id] = float(max(lp) - min(lp))
        arm_ref[g.group_id] = float(max(lr) - min(lr)) if lr else float("nan")

    return FidelityReport(
        banner=ESTIMATOR_ONLY_BANNER,
        mode=mode,
        nets=rows,
        mae_um=mae,
        max_err_um=max_err,
        corr=corr,
        arm_delta_pred_um=arm_pred,
        arm_delta_ref_um=arm_ref,
    )


def phi_ablation_eligible(problem: PlacementProblem) -> bool:
    """True if at least one phase group has ≥2 arms (φ term can be nonzero)."""
    return any(len(g.arm_net_indices) >= 2 for g in problem.phase_groups)
