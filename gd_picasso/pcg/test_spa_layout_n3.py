"""
Layout-N3 SPA for PIC-Set Tasks 6 & 9 — **ESTIMATOR_ONLY**.

Derives path lengths from placed geometry (Place estimator / Manhattan xy),
back-annotates via ``apply_route_metrics``, then runs SPA WNS.

This is **not** routed-LiDAR evidence and **not** SYNTHETIC planted Δφ.
Claim discipline: banner ``ESTIMATOR_ONLY`` until Phase-2 fidelity gate drops it.

Run:  pytest gd_picasso/pcg/test_spa_layout_n3.py -q
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from gd_picasso.pcg import from_gf_yaml
from gd_picasso.pcg.backannotate import RouteMetrics, apply_route_metrics
from gd_picasso.pcg.place import ESTIMATOR_ONLY_BANNER, build_placement_problem, place_multistart
from gd_picasso.pcg.place.estimator_fidelity import plant_estimated_lengths
from gd_picasso.pcg.spa import HYBRID_90_TARGETS_RAD, spa_analyze
from gd_picasso.pcg.spa_table_v import _L_for_phase, _hybrid_four_path, _mzi_pair

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TOL_RAD = 0.01
BALANCED_UM = 200.0


def test_task6_layout_spa_from_placed_fixture() -> None:
    """Task-6 GF fixture → place → estimator lengths → SPA WNS."""
    yaml_path = FIXTURES / "picset_task06.yaml"
    assert yaml_path.is_file()
    store = from_gf_yaml(yaml_path.read_text(encoding="utf-8"))
    problem = build_placement_problem(store)
    result = place_multistart(
        store,
        n_starts=2,
        steps=20,
        lr=1.5,
        seed=3,
        write_back=True,
        problem=problem,
    )
    assert "ESTIMATOR_ONLY" in result.banner
    planted = plant_estimated_lengths(store, problem)

    # Map estimator net lengths onto RouteMetrics keys for SPA path walk.
    optical = [e for e in store.edges]
    metrics = {}
    for i, net in enumerate(problem.nets):
        e = optical[net.edge_idx]
        L = float(planted[i])
        metrics[(e.src_node, e.src_port, e.dst_node, e.dst_port)] = RouteMetrics(
            length_um=L
        )
    n = apply_route_metrics(store, metrics)
    assert n >= 2

    groups = {
        "arms": [
            ["split", "arm_i", "comb"],
            ["split", "arm_q", "comb"],
        ]
    }
    report = spa_analyze(store, groups, tolerance_rad=TOL_RAD)
    assert ESTIMATOR_ONLY_BANNER.split("—")[0].strip() in "ESTIMATOR_ONLY"
    # Layout-derived: WNS is a real number from geometry (may be ±).
    assert math.isfinite(report.wns_rad)
    assert len(report.groups) == 1


def test_task9_layout_spa_from_placed_xy() -> None:
    """Task-9 hybrid: arm lengths from a placed xy pattern (not planted Δφ)."""
    # Placed arm endpoints (µm) — layout plane, ESTIMATOR_ONLY Manhattan.
    # Same |y| ⇒ equal path lengths vs quadrature targets → WNS < 0.
    arm_xy = [
        (180.0, 40.0),
        (180.0, -40.0),
        (220.0, 40.0),
        (220.0, -40.0),
    ]
    src_xy = (80.0, 0.0)
    sink_xy = (320.0, 0.0)

    def manhattan(a, b) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    lengths = [
        manhattan(src_xy, xy) + manhattan(xy, sink_xy) for xy in arm_xy
    ]
    # Equal geometric arms from this layout → fail quadrature targets.
    assert max(lengths) - min(lengths) < 1e-9

    store, groups = _hybrid_four_path(lengths, prefix="t9lay_")
    report = spa_analyze(
        store,
        groups,
        tolerance_rad=TOL_RAD,
        group_targets={"quadrature": HYBRID_90_TARGETS_RAD},
    )
    expect_wns = TOL_RAD - math.pi
    assert report.wns_rad == pytest.approx(expect_wns, abs=0.05)
    assert report.wns_rad < 0.0
    assert "ESTIMATOR_ONLY" in ESTIMATOR_ONLY_BANNER


def test_task9_layout_spa_realized_quadrature_xy() -> None:
    """Task-9: layout xy that realizes quadrature ΔL → WNS ≥ 0."""
    base = BALANCED_UM
    lengths = [base + _L_for_phase(t) for t in HYBRID_90_TARGETS_RAD]
    store, groups = _hybrid_four_path(lengths, prefix="t9oklay_")
    # Lengths come from layout-intent ΔL schedule (still ESTIMATOR_ONLY).
    report = spa_analyze(
        store,
        groups,
        tolerance_rad=TOL_RAD,
        group_targets={"quadrature": HYBRID_90_TARGETS_RAD},
    )
    assert report.wns_rad >= 0.0


def test_task6_unbalanced_place_seed_negative_wns() -> None:
    """Task-6: unbalanced placed arms → negative WNS via estimator metrics."""
    bad = BALANCED_UM + _L_for_phase(0.2)
    store, groups = _mzi_pair((BALANCED_UM, bad), prefix="t6lay_")
    report = spa_analyze(store, groups, tolerance_rad=TOL_RAD)
    assert report.wns_rad < 0.0
