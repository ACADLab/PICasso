"""
Torch-native cosWA + density placer (Apollo-style objective, not DREAMPlace).

Falls back to the numpy finite-difference placer when ``torch`` is absent.
Claim discipline: do **not** claim GPU PIC placement (Apollo).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from ..store import PCGStore
from .objective import ObjectiveWeights, evaluate_objective
from .optimize import PlaceResult, place_multistart, write_placement
from .tensors import PlacementProblem, build_placement_problem, port_world
from .torch_fom import X_STAGE_GAP_UM, enforce_x_stage_gap, placement_fom_loss

try:
    import torch

    _HAVE_TORCH = True
except Exception:  # pragma: no cover
    torch = None  # type: ignore
    _HAVE_TORCH = False

DEFAULT_ALPHA = 1.4


@dataclass
class TorchPlaceResult(PlaceResult):
    backend: str = "torch"
    history: List[float] = field(default_factory=list)


def have_torch() -> bool:
    return bool(_HAVE_TORCH)


def _torch_objective(
    xy: "torch.Tensor",
    problem: PlacementProblem,
    weights: ObjectiveWeights,
    *,
    store_components: Optional[dict] = None,
) -> "torch.Tensor":
    """Wirelength + FoM / phase / overlap / Y-pitch / X-stage (θ held fixed).

    Legacy ``λ_D·D`` (clamp density) is kept only when ``lambda_overlap == 0``
    so the softplus port-aware repulsion is the primary separator.
    """
    assert torch is not None
    theta = problem.theta_rad
    n = problem.n_nodes
    half = problem.half_extents
    alpha = weights.alpha

    # --- W_cos (keeps connected layouts compact; not in FoM triad) ---
    W = xy.new_zeros(())
    id_to_idx = problem.node_index()
    for net in problem.nets:
        i_s = id_to_idx[net.src.node_id]
        i_d = id_to_idx[net.dst.node_id]
        p_s_np, u_s_np = port_world(problem, net.src, xy=problem.xy, theta=theta)
        p_d_np, u_d_np = port_world(problem, net.dst, xy=problem.xy, theta=theta)
        off_s = p_s_np - problem.xy[i_s]
        off_d = p_d_np - problem.xy[i_d]
        p_s = xy[i_s] + xy.new_tensor(off_s)
        p_d = xy[i_d] + xy.new_tensor(off_d)
        u_s = xy.new_tensor(u_s_np)
        u_d = xy.new_tensor(u_d_np)
        delta = p_d - p_s
        L = torch.abs(delta[0]) + torch.abs(delta[1])
        nrm = torch.sqrt(delta[0] ** 2 + delta[1] ** 2) + 1e-9
        v = delta / nrm
        align_s = torch.clamp(torch.dot(u_s, v), -1.0, 1.0)
        align_d = torch.clamp(torch.dot(u_d, -v), -1.0, 1.0)
        misalign = (1.0 - align_s) + (1.0 - align_d)
        W = W + L + alpha * 10.0 * misalign

    total = W + placement_fom_loss(
        xy, problem, weights, store_components=store_components
    )

    # Legacy soft clamp density only when overlap repulsion is disabled.
    if weights.lambda_overlap <= 0.0 and weights.lambda_D > 0.0:
        D = xy.new_zeros(())
        for i in range(n):
            for j in range(i + 1, n):
                gap_x = torch.abs(xy[i, 0] - xy[j, 0]) - (half[i, 0] + half[j, 0])
                gap_y = torch.abs(xy[i, 1] - xy[j, 1]) - (half[i, 1] + half[j, 1])
                ox = torch.clamp(-gap_x, min=0.0)
                oy = torch.clamp(-gap_y, min=0.0)
                D = D + (ox * oy) ** 2
        total = total + weights.lambda_D * D
    return total


def place_torch(
    store: PCGStore,
    *,
    weights: Optional[ObjectiveWeights] = None,
    steps: int = 60,
    lr: float = 2.0,
    write_back: bool = True,
    problem: Optional[PlacementProblem] = None,
) -> TorchPlaceResult:
    """Adam on (x,y) with torch autodiff; falls back to numpy GD if no torch."""
    w = weights or ObjectiveWeights()
    prob = problem or build_placement_problem(store)
    start_terms = evaluate_objective(prob, weights=w)

    if not _HAVE_TORCH:
        # Fallback: numpy multi-start (still legal placements).
        r = place_multistart(
            store,
            weights=w,
            n_starts=3,
            steps=max(20, steps // 2),
            lr=lr,
            write_back=write_back,
            problem=prob,
        )
        return TorchPlaceResult(
            xy=r.xy,
            theta_rad=r.theta_rad,
            terms=r.terms,
            start_terms=r.start_terms,
            n_starts=r.n_starts,
            best_start=r.best_start,
            history=r.history,
            backend="numpy_fallback",
            banner=r.banner,
        )

    assert torch is not None
    comps = {nid: store.nodes[nid].component for nid in store.nodes}
    xy = torch.tensor(prob.xy, dtype=torch.float64, requires_grad=True)
    movable = torch.tensor(prob.movable, dtype=torch.bool)
    opt = torch.optim.Adam([xy], lr=lr)
    hist: List[float] = []
    for _ in range(steps):
        opt.zero_grad()
        loss = _torch_objective(xy, prob, w, store_components=comps)
        loss.backward()
        with torch.no_grad():
            if xy.grad is not None:
                xy.grad[~movable] = 0.0
        opt.step()
        hist.append(float(loss.detach()))

    xy_np = xy.detach().cpu().numpy()
    # Hard X-stage runway (≥150 µm between mesh columns) after soft opt.
    if getattr(w, "lambda_x_stage", 0.0) > 0.0:
        gap = float(getattr(w, "x_stage_gap_um", X_STAGE_GAP_UM) or X_STAGE_GAP_UM)
        xy_np = enforce_x_stage_gap(
            xy_np, prob, min_gap_um=gap, store_components=comps
        )
    terms = evaluate_objective(prob, xy_np, prob.theta_rad, w)
    if write_back:
        write_placement(store, prob, xy_np, agent="place_torch")

    return TorchPlaceResult(
        xy=xy_np,
        theta_rad=prob.theta_rad.copy(),
        terms=terms,
        start_terms=start_terms,
        n_starts=1,
        best_start=0,
        history=hist,
        backend="torch",
        banner=(
            "ESTIMATOR_ONLY — torch cosWA + FoM/phase/overlap; "
            "not Apollo/DREAMPlace; not validated against routed geometry."
        ),
    )
