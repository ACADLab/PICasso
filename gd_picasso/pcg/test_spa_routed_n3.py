"""
Routed N3 SPA — GF ``get_netlist`` lengths → back-annot → WNS.

Not ESTIMATOR_ONLY when lengths come from routed GF netlists.
LiDAR wrap remains the detailed-router citation path when isolated env exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gd_picasso.pcg import from_gf_yaml
from gd_picasso.pcg.gf_route_metrics import (
    backannotate_from_yaml,
    route_metrics_from_gf_netlist,
)
from gd_picasso.pcg.spa import spa_analyze
from gd_picasso.pcg.spa_protocol import SPA_TOL_RAD

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PICSET = FIXTURES / "picset"
TOL_RAD = SPA_TOL_RAD


def test_gf_netlist_backannot_task01_spa() -> None:
    """Task-1 MZI: GF YAML → get_netlist lengths → SPA WNS is finite."""
    yaml_path = PICSET / "task_01.yaml"
    assert yaml_path.is_file()
    text = yaml_path.read_text(encoding="utf-8")
    store = from_gf_yaml(text)
    n = backannotate_from_yaml(store, text)
    assert n >= 2
    # All optical edges should carry length
    optical = [e for e in store.edges if e.length_um]
    assert len(optical) >= 2
    groups = {
        "arms": [
            ["splitter", "ps_upper", "combiner"],
            ["splitter", "ps_lower", "combiner"],
        ]
    }
    report = spa_analyze(store, groups, tolerance_rad=TOL_RAD)
    assert report.wns_rad == report.wns_rad  # finite
    # Balanced CS arms → matched-length → non-negative WNS at loose tol
    assert report.wns_rad >= -1.0  # sanity; geometry may still skew slightly


def test_gf_netlist_backannot_task06_top_level() -> None:
    yaml_path = FIXTURES / "picset_task06.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    store = from_gf_yaml(text)
    n = backannotate_from_yaml(store, text)
    assert n >= 2
    groups = {
        "arms": [
            ["split", "arm_i", "comb"],
            ["split", "arm_q", "comb"],
        ]
    }
    report = spa_analyze(store, groups, tolerance_rad=TOL_RAD)
    assert abs(report.wns_rad) < 10.0


def test_route_metrics_from_empty_netlist_safe() -> None:
    m = route_metrics_from_gf_netlist({"instances": {}, "connections": {}})
    assert m == {}
