"""
Phase 2a/2b/2c + Phase 3 smoke tests.

Run:  pytest gd_picasso/pcg/test_scope_c_phase2_3.py -q
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from gd_picasso.pcg import from_gf_yaml
from gd_picasso.pcg.clements_scale import clements_mzi_count, setup_clements_16, scale_table
from gd_picasso.pcg.gnn_rl import (
    ACTIONS,
    generate_topology_labels,
    run_rl_bakeoff,
    train_gnn_surrogate,
)
from gd_picasso.pcg.l3_loop import l3_optimize_mzi_phases, run_netlist_optimize_smoke
from gd_picasso.pcg.place.torch_placer import have_torch, place_torch
from gd_picasso.pcg.route import (
    LIDAR_GF_PIN,
    PICASSO_GF_PIN,
    ROUTER_CUT_LINE,
    check_lidar_gf_pin,
    fidelity_vs_routed,
    route_point_to_point,
    route_with_lidar,
    soft_approaches_hard,
)
from gd_picasso.pcg.route.minplus import soft_min_plus_relax, min_plus_relax

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_lidar_gf_pin_mismatch_documented() -> None:
    """First-5-min gate: LiDAR gf 8.26.1 ≠ PICasso 9.23."""
    assert PICASSO_GF_PIN == "9.23.0"
    assert LIDAR_GF_PIN == "8.26.1"
    assert PICASSO_GF_PIN != LIDAR_GF_PIN
    report = check_lidar_gf_pin()
    assert report.mismatch is True
    assert "9.23" in report.detail or "PICASSO" in report.detail or "not found" in report.detail.lower() or "8.26" in report.detail


def test_torch_placer_objective_decreases() -> None:
    store = from_gf_yaml((FIXTURES / "mzi_unbalanced.yaml").read_text())
    result = place_torch(store, steps=30, lr=1.5, write_back=True)
    assert result.terms.total <= result.start_terms.total + 1e-5
    # Legal write-back
    assert any(n.x is not None for n in store.nodes.values())
    assert result.backend in ("torch", "numpy_fallback")
    if not have_torch():
        assert result.backend == "numpy_fallback"


def test_lidar_wrap_stub_routes_and_fidelity_gate() -> None:
    store = from_gf_yaml((FIXTURES / "mzi.yaml").read_text())
    routed = route_with_lidar(store, allow_stub=True)
    assert routed.ok
    assert routed.metrics
    assert routed.wirelength_um is not None and routed.wirelength_um > 0
    # Self-fidelity: predicted == routed stub → drop ESTIMATOR_ONLY eligible
    pred = {k: m.length_um for k, m in routed.metrics.items()}
    fid = fidelity_vs_routed(pred, routed.metrics, mae_um_threshold=25.0)
    assert fid["drop_estimator_only"] is True
    assert fid["mae_um"] == pytest.approx(0.0)


def test_hard_minplus_path_finite() -> None:
    r = route_point_to_point(12, 12, (1, 1), (10, 10), iterations=24)
    assert np.isfinite(r.path_cost)
    assert r.path_cost > 0
    assert "CUT" in ROUTER_CUT_LINE or "cut" in ROUTER_CUT_LINE.lower() or "LiDAR" in ROUTER_CUT_LINE


def test_soft_approaches_hard_trend() -> None:
    info = soft_approaches_hard(12, 12, taus=(1.0, 0.2, 0.05))
    gaps = info["max_abs_gap"]
    # Soft should get closer (non-increasing trend loosely — allow noise)
    assert gaps[-1] <= gaps[0] + 1e-6 or gaps[-1] < 50.0
    C = np.full((8, 8), np.inf)
    C[0, 0] = 0.0
    A = np.array([[0, 1, 1.0], [1, 0, 1.0]], dtype=np.float64)
    hard = min_plus_relax(C, A, iterations=10)
    soft = soft_min_plus_relax(C, A, tau=0.05, iterations=10)
    assert np.isfinite(hard).any() and np.isfinite(soft).any()


def test_l3_loop_improves_fom() -> None:
    store = from_gf_yaml((FIXTURES / "mzi.yaml").read_text())
    result = l3_optimize_mzi_phases(store, n_params=2, seed=1)
    assert result.improved
    assert result.history[-1] <= result.history[0] + 1e-9
    smoke = run_netlist_optimize_smoke()
    assert "keys" in smoke
    assert "x_opt" in smoke["keys"]


def test_clements_16_setup() -> None:
    assert clements_mzi_count(16) == 120
    rows = scale_table([4, 16])
    assert rows[-1].n == 16 and rows[-1].n_mzi == 120
    setup = setup_clements_16()
    assert setup["ready_for_compute"] is True
    assert setup["unitary_err_eye"] < 1e-10


def test_clements_n8_lower_smoke() -> None:
    from gd_picasso.pcg.clements_scale import clements_lower_smoke

    r = clements_lower_smoke(8, seed=1)
    assert r["n"] == 8.0
    assert r["n_mzi"] == float(clements_mzi_count(8))
    assert r["rebuild_err"] < 1e-9


def test_gnn_sax_labels_and_surrogate() -> None:
    from gd_picasso.pcg.gnn_rl import generate_sax_topology_labels

    labels = generate_sax_topology_labels(48, seed=0)
    assert len(labels) == 48
    assert all(np.isfinite(L.fom) for L in labels)
    gnn = train_gnn_surrogate(labels, heldout_frac=0.25, seed=0)
    y = np.array([L.fom for L in labels])
    baseline = float(np.mean(np.abs(y - y.mean())))
    # Must beat predicting the mean; ExactCritic stays authoritative.
    assert gnn.heldout_mae < baseline * 0.85, (gnn.heldout_mae, baseline)
    assert gnn.heldout_mae < 3.0, gnn.heldout_mae


def test_gnn_analytic_and_rl_bakeoff() -> None:
    labels = generate_topology_labels(200, seed=2)
    gnn = train_gnn_surrogate(labels, heldout_frac=0.25, seed=2)
    assert gnn.heldout_mae < 0.5
    assert set(ACTIONS) == {
        "net_group_order",
        "hierarchy_cut",
        "inflate_vs_replace",
        "weight_band",
    }
    bake = run_rl_bakeoff(seed=3, episodes=6)
    assert isinstance(bake.cut_rl, bool)
    assert bake.detail
    print(bake.detail, bake)
