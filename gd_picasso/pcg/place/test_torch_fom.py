"""B2: differentiable F_torch / overlap_loss gradients + Task-20 separation gate."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from gd_picasso.pcg.bridge import from_gf_yaml
from gd_picasso.pcg.place.objective import ObjectiveWeights, evaluate_objective
from gd_picasso.pcg.place.tensors import build_placement_problem
from gd_picasso.pcg.place.torch_fom import (
    F_torch,
    LOSS_DB_PER_CM,
    PORT_EMISSION_MARGIN_UM,
    X_STAGE_GAP_UM,
    Y_CHANNEL_PITCH_UM,
    enforce_x_stage_gap,
    expanded_half_extents,
    hard_separation_ok,
    overlap_loss,
    placement_fom_loss,
    topo_stage_indices,
    x_stage_loss,
    y_pitch_loss,
)
from gd_picasso.pcg.place.torch_placer import have_torch, place_torch

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "picset" / "task_01.yaml"
TASK20 = Path(__file__).resolve().parents[1] / "fixtures" / "picset" / "task_20.yaml"


@pytest.mark.skipif(not have_torch(), reason="torch not installed")
def test_f_torch_gradients_flow_to_xy() -> None:
    import torch

    store = from_gf_yaml(FIXTURE.read_text())
    problem = build_placement_problem(store)
    assert any(len(g.arm_net_indices) >= 2 for g in problem.phase_groups)

    # Break arm-length symmetry so ∂F/∂xy is nonzero (balanced MZI is stationary).
    xy0 = problem.xy.copy()
    xy0[1, 1] += 25.0
    xy = torch.tensor(xy0, dtype=torch.float64, requires_grad=True)
    w = ObjectiveWeights(lambda_F=1.0, lambda_D=0.0, lambda_phi=0.0, lambda_overlap=0.0)
    F = F_torch(xy, problem, w, loss_dB_per_cm=LOSS_DB_PER_CM)
    assert torch.isfinite(F)
    F.backward()
    assert xy.grad is not None
    gnorm = float(torch.linalg.norm(xy.grad).item())
    assert gnorm > 0.0


@pytest.mark.skipif(not have_torch(), reason="torch not installed")
def test_overlap_loss_gradients_and_port_margins() -> None:
    import torch

    store = from_gf_yaml(FIXTURE.read_text())
    problem = build_placement_problem(store)
    # Collapse two cells onto each other → soft overlap must be > 0.
    xy0 = problem.xy.copy()
    xy0[1] = xy0[0].copy()
    xy = torch.tensor(xy0, dtype=torch.float64, requires_grad=True)
    L = overlap_loss(xy, problem)
    assert float(L.item()) > 0.0
    L.backward()
    assert xy.grad is not None
    assert float(torch.linalg.norm(xy.grad).item()) > 0.0

    raw = problem.half_extents
    expanded = expanded_half_extents(problem, margin_um=PORT_EMISSION_MARGIN_UM)
    assert np.all(expanded >= raw - 1e-9)
    # Connected optical ports should inflate at least one axis on some cell.
    assert float(np.max(expanded - raw)) >= PORT_EMISSION_MARGIN_UM - 1e-6


@pytest.mark.skipif(not have_torch(), reason="torch not installed")
def test_y_pitch_loss_penalizes_collapsed_arms() -> None:
    import torch

    store = from_gf_yaml(FIXTURE.read_text())
    problem = build_placement_problem(store)
    xy0 = problem.xy.copy()
    # Collapse all cells onto one Y channel → pitch violation.
    xy0[:, 1] = 0.0
    xy = torch.tensor(xy0, dtype=torch.float64, requires_grad=True)
    L = y_pitch_loss(xy, problem, pitch_um=Y_CHANNEL_PITCH_UM)
    assert float(L.item()) > 0.0
    L.backward()
    assert xy.grad is not None
    assert float(torch.linalg.norm(xy.grad).item()) > 0.0


@pytest.mark.skipif(not have_torch(), reason="torch not installed")
def test_x_stage_loss_penalizes_collapsed_columns() -> None:
    import torch

    store = from_gf_yaml(TASK20.read_text())
    problem = build_placement_problem(store)
    comps = {nid: store.nodes[nid].component for nid in store.nodes}
    stages = topo_stage_indices(problem, store_components=comps)
    assert int(stages.max()) >= 1

    xy0 = problem.xy.copy()
    # Collapse every column onto x=0 → consecutive stages under-gapped.
    xy0[:, 0] = 0.0
    xy = torch.tensor(xy0, dtype=torch.float64, requires_grad=True)
    L = x_stage_loss(
        xy, problem, min_gap_um=X_STAGE_GAP_UM, store_components=comps
    )
    assert float(L.item()) > 0.0
    L.backward()
    assert xy.grad is not None
    assert float(torch.linalg.norm(xy.grad).item()) > 0.0

    snapped = enforce_x_stage_gap(
        xy0, problem, min_gap_um=X_STAGE_GAP_UM, store_components=comps
    )
    st = topo_stage_indices(problem, store_components=comps)
    uniq = sorted({int(s) for s in st.tolist()})
    means = [
        float(np.mean(snapped[[i for i in range(problem.n_nodes) if int(st[i]) == s], 0]))
        for s in uniq
    ]
    for a, b in zip(means, means[1:]):
        assert b - a >= X_STAGE_GAP_UM - 1e-6


@pytest.mark.skipif(not have_torch(), reason="torch not installed")
def test_place_torch_uses_lambda_F() -> None:
    store = from_gf_yaml(FIXTURE.read_text())
    w = ObjectiveWeights(
        lambda_F=0.05,
        lambda_D=0.0,
        lambda_phi=0.1,
        lambda_overlap=10.0,
        alpha=1.4,
    )
    r = place_torch(store, weights=w, steps=15, lr=1.0, write_back=False)
    assert r.backend == "torch"
    assert np.isfinite(r.terms.total)
    assert np.isfinite(r.terms.F_hat)
    terms = evaluate_objective(
        build_placement_problem(store), r.xy, r.theta_rad, w
    )
    assert abs(terms.F_hat) > 0.0 or abs(r.terms.F_hat) > 0.0


@pytest.mark.skipif(not have_torch(), reason="torch not installed")
def test_task20_clements_strict_geometric_separation() -> None:
    """Validation gate: Clements 4×4 (Task 20) exits with zero AABB overlaps."""
    import torch

    store = from_gf_yaml(TASK20.read_text())
    problem0 = build_placement_problem(store)
    # Seeded layout on Task 20 is typically stacked → overlaps expected pre-opt.
    ok0, viol0, _ = hard_separation_ok(problem0.xy, problem0)
    assert viol0 > 0 or not ok0

    # λ_overlap must dominate W_cos on this dense mesh; keep FoM/phase on.
    w = ObjectiveWeights(
        lambda_F=0.05,
        lambda_phi=0.05,
        lambda_overlap=1000.0,
        lambda_D=0.0,
        alpha=1.4,
    )
    r = place_torch(store, weights=w, steps=150, lr=6.0, write_back=True)
    assert r.backend == "torch"

    problem = build_placement_problem(store)
    ok, viol, min_sep = hard_separation_ok(r.xy, problem)
    assert ok, f"Task-20 still has {viol} overlaps; min_sep={min_sep:.3f} µm"
    assert viol == 0
    assert min_sep > 0.0
    xy_t = torch.tensor(r.xy, dtype=torch.float64)
    # Softplus tail remains >0 even when hard-separated; just require finite.
    assert torch.isfinite(overlap_loss(xy_t, problem))
    assert torch.isfinite(placement_fom_loss(xy_t, problem, w))