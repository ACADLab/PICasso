"""
Synthetic Task-6 / Task-9 SPA harness — **SYNTHETIC_NOT_LAYOUT**.

Planted ``RouteMetrics`` lengths drive φ → WNS. This is a unit test of the
SPA comparator (same class of evidence as ``spa_table_v``), **not** evidence
that routed layout geometry predicts Spec failure. Do **not** claim layout N3.

Goldens
-------
- Task 6 (64-QAM proxy): planted arm Δφ = 0.2 rad → WNS = tol − 0.2 < 0
- Task 9 (90° hybrid): four equal-length paths vs quadrature targets → WNS < 0

Run:  pytest gd_picasso/pcg/test_spa_synthetic.py -q
"""

from __future__ import annotations

import math

import pytest

from gd_picasso.pcg.spa import HYBRID_90_TARGETS_RAD, spa_analyze
from gd_picasso.pcg.spa_table_v import _L_for_phase, _hybrid_four_path, _mzi_pair

# SYNTHETIC_NOT_LAYOUT — planted lengths only; no router / no GDS.
TOL_RAD = 0.01
BALANCED_UM = 200.0
TASK6_DPHI_RAD = 0.2


def test_task6_synthetic_wns_golden() -> None:
    """SYNTHETIC_NOT_LAYOUT: Task-6 planted Δφ → negative WNS golden."""
    bad = BALANCED_UM + _L_for_phase(TASK6_DPHI_RAD)
    store, groups = _mzi_pair((BALANCED_UM, bad), prefix="t6_")
    report = spa_analyze(store, groups, tolerance_rad=TOL_RAD)
    # Single pair: slack = tol − |Δφ|
    expect_wns = TOL_RAD - TASK6_DPHI_RAD
    assert report.wns_rad == pytest.approx(expect_wns)
    assert report.wns_rad < 0.0
    assert not report.all_ok


def test_task9_synthetic_wns_golden() -> None:
    """SYNTHETIC_NOT_LAYOUT: Task-9 equal arms vs quadrature → negative WNS."""
    store, groups = _hybrid_four_path(
        [BALANCED_UM] * 4, prefix="t9_"
    )
    report = spa_analyze(
        store,
        groups,
        tolerance_rad=TOL_RAD,
        group_targets={"quadrature": HYBRID_90_TARGETS_RAD},
    )
    # Worst pair target Δ is π (paths 0↔2 or 1↔3) with actual Δ = 0.
    expect_wns = TOL_RAD - math.pi
    assert report.wns_rad == pytest.approx(expect_wns)
    assert report.wns_rad < 0.0
    assert len(report.groups[0].pair_slacks) == 6


def test_task9_realized_targets_non_negative() -> None:
    """SYNTHETIC_NOT_LAYOUT: lengths realizing quadrature targets → WNS ≥ 0."""
    lengths = [BALANCED_UM + _L_for_phase(t) for t in HYBRID_90_TARGETS_RAD]
    store, groups = _hybrid_four_path(lengths, prefix="t9ok_")
    report = spa_analyze(
        store,
        groups,
        tolerance_rad=TOL_RAD,
        group_targets={"quadrature": HYBRID_90_TARGETS_RAD},
    )
    assert report.wns_rad >= 0.0
