"""
Integration: full Scope-C path with LiDAR env.

- Pin check (gf 8.26.1 ≠ 9.23)
- LiDAR-IR Manhattan → SPA Tasks 6/9
- Optional PICRoute toy smoke (``--route``)
- Fidelity gate drops ESTIMATOR_ONLY when MAE passes

Skips when ``PICASSO_LIDAR_PYTHON`` / ``.lidar_env`` is not configured.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from gd_picasso.pcg.lidar_ir import from_lidar_yaml
from gd_picasso.pcg.place import ROUTED_FIDELITY_BANNER, estimator_fidelity
from gd_picasso.pcg.route import (
    LIDAR_GF_PIN,
    PICASSO_GF_PIN,
    check_lidar_gf_pin,
    fidelity_vs_routed,
    route_with_lidar,
)
from gd_picasso.pcg.spa import HYBRID_90_TARGETS_RAD, spa_analyze
from gd_picasso.pcg.spa_protocol import SPA_TOL_RAD

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TOL_RAD = SPA_TOL_RAD


@pytest.fixture(scope="module")
def lidar_pin():
    pin = check_lidar_gf_pin()
    if not pin.lidar_import_ok:
        pytest.skip(pin.detail)
    assert pin.lidar_gf == LIDAR_GF_PIN
    assert pin.mismatch is True
    assert PICASSO_GF_PIN == "9.23.0"
    return pin


def test_integration_lidar_ir_task6_spa_and_fidelity(lidar_pin) -> None:
    store = from_lidar_yaml(
        (FIXTURES / "lidar" / "picset_task06_stub.yaml").read_text()
    )
    routed = route_with_lidar(store, design="int_t6", allow_stub=False)
    assert routed.ok
    assert routed.metrics
    assert "LiDAR" in routed.banner
    assert "STUB" not in routed.banner.upper()

    pred = {k: m.length_um for k, m in routed.metrics.items()}
    fid = fidelity_vs_routed(pred, routed.metrics, mae_um_threshold=1.0)
    assert fid["drop_estimator_only"] is True

    report = estimator_fidelity(
        store,
        treat_edge_length_as="routed",
        drop_estimator_only=True,
    )
    assert report.banner == ROUTED_FIDELITY_BANNER

    groups = {
        "arms": [
            ["split", "arm_i", "comb"],
            ["split", "arm_q", "comb"],
        ]
    }
    spa = spa_analyze(store, groups, tolerance_rad=TOL_RAD)
    assert spa.wns_rad == spa.wns_rad
    assert abs(spa.wns_rad) < 50.0


def test_integration_lidar_ir_task9_spa(lidar_pin) -> None:
    store = from_lidar_yaml(
        (FIXTURES / "lidar" / "picset_task09_stub.yaml").read_text()
    )
    routed = route_with_lidar(store, design="int_t9", allow_stub=False)
    assert routed.ok and len(routed.metrics) >= 4
    groups = {
        "quadrature": [
            ["src", "sa", "p0", "sink"],
            ["src", "sa", "p1", "sink"],
            ["src", "sb", "p2", "sink"],
            ["src", "sb", "p3", "sink"],
        ]
    }
    spa = spa_analyze(
        store,
        groups,
        tolerance_rad=TOL_RAD,
        group_targets={"quadrature": HYBRID_90_TARGETS_RAD},
    )
    assert spa.wns_rad == spa.wns_rad
    assert len(spa.groups[0].pair_slacks) == 6


def test_integration_picroute_toy_smoke(lidar_pin) -> None:
    """Full PICRoute on LiDAR toy_example — cite LiDAR; not our A*."""
    toy = (
        REPO
        / ".lidar_env"
        / "LiDAR"
        / "src"
        / "picroute"
        / "benchmarks"
        / "toy_example"
        / "toy_example.gp.yml"
    )
    if not toy.is_file():
        pytest.skip(f"LiDAR toy missing: {toy}")
    driver = Path(__file__).resolve().parent / "route" / "lidar_driver.py"
    lidar_src = REPO / ".lidar_env" / "LiDAR" / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{lidar_src}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(
        os.pathsep
    )
    proc = subprocess.run(
        [lidar_pin.lidar_python, str(driver), str(toy), "--route"],
        text=True,
        capture_output=True,
        timeout=600,
        env=env,
        cwd=str(lidar_src.parent),
    )
    raw = (proc.stdout or "").strip()
    payload = None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        for line in reversed(raw.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
    assert payload is not None, f"no JSON from driver: stdout={raw[:300]!r} stderr={(proc.stderr or '')[:300]!r}"
    assert payload.get("ok") is True
    # Driver tries gdsfactory curvy routing first and falls back to PICRoute.
    assert payload.get("mode") in {"gf_curvy", "picroute"}
    assert payload.get("metrics")
    assert (payload.get("wirelength_um") or 0) > 0
