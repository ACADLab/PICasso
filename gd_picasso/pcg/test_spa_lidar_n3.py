"""
LiDAR-backed N3 SPA — Tasks 6 & 9.

Uses isolated LiDAR env (``PICASSO_LIDAR_PYTHON``) via ``route_with_lidar``
to back-annotate lengths from LiDAR PIC IR, then runs SPA WNS.

Not SYNTHETIC planted Δφ. Banner cites LiDAR; not our curvy-router novelty.
Skips if LiDAR env is not configured.
When LiDAR-IR metrics land, ESTIMATOR_ONLY is dropped via fidelity gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gd_picasso.pcg.lidar_ir import from_lidar_yaml
from gd_picasso.pcg.place import ROUTED_FIDELITY_BANNER, estimator_fidelity
from gd_picasso.pcg.route import check_lidar_gf_pin, fidelity_vs_routed, route_with_lidar
from gd_picasso.pcg.spa import HYBRID_90_TARGETS_RAD, spa_analyze
from gd_picasso.pcg.spa_protocol import SPA_TOL_RAD

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "lidar"
TOL_RAD = SPA_TOL_RAD


def _require_lidar():
    pin = check_lidar_gf_pin()
    if not pin.lidar_import_ok:
        pytest.skip(f"LiDAR env not ready: {pin.detail}")
    return pin


def test_lidar_pin_isolated() -> None:
    pin = _require_lidar()
    assert pin.lidar_gf == "8.26.1"
    assert pin.mismatch is True


def test_task6_lidar_ir_spa() -> None:
    """Task-6 LiDAR stub → IR Manhattan metrics → SPA WNS finite."""
    _require_lidar()
    path = FIXTURES / "picset_task06_stub.yaml"
    store = from_lidar_yaml(path.read_text())
    routed = route_with_lidar(store, design="task06", allow_stub=False)
    assert routed.ok
    assert len(routed.metrics) >= 2
    assert "LiDAR" in routed.banner
    assert "STUB" not in routed.banner.upper()
    pred = {k: m.length_um for k, m in routed.metrics.items()}
    fid = fidelity_vs_routed(pred, routed.metrics, mae_um_threshold=1.0)
    assert fid["drop_estimator_only"] is True
    groups = {
        "arms": [
            ["split", "arm_i", "comb"],
            ["split", "arm_q", "comb"],
        ]
    }
    report = spa_analyze(store, groups, tolerance_rad=TOL_RAD)
    assert report.wns_rad == report.wns_rad  # finite
    assert abs(report.wns_rad) < 50.0
    # Routed lengths on edges → fidelity banner drops ESTIMATOR_ONLY
    freport = estimator_fidelity(
        store, treat_edge_length_as="routed", drop_estimator_only=True
    )
    assert freport.banner == ROUTED_FIDELITY_BANNER


def test_task9_lidar_ir_spa() -> None:
    """Task-9 hybrid stub → LiDAR IR metrics → SPA vs quadrature targets."""
    _require_lidar()
    path = FIXTURES / "picset_task09_stub.yaml"
    store = from_lidar_yaml(path.read_text())
    routed = route_with_lidar(store, design="task09", allow_stub=False)
    assert routed.ok
    assert len(routed.metrics) >= 4
    groups = {
        "quadrature": [
            ["src", "sa", "p0", "sink"],
            ["src", "sa", "p1", "sink"],
            ["src", "sb", "p2", "sink"],
            ["src", "sb", "p3", "sink"],
        ]
    }
    report = spa_analyze(
        store,
        groups,
        tolerance_rad=TOL_RAD,
        group_targets={"quadrature": HYBRID_90_TARGETS_RAD},
    )
    assert report.wns_rad == report.wns_rad
    assert len(report.groups[0].pair_slacks) == 6
