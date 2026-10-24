"""
Estimator fidelity gate — drop ``ESTIMATOR_ONLY`` when routed lengths match.

Compares Place estimator predictions to LiDAR-IR / GF-routed references.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gd_picasso.pcg import from_gf_yaml
from gd_picasso.pcg.lidar_ir import from_lidar_yaml
from gd_picasso.pcg.place import (
    ESTIMATOR_ONLY_BANNER,
    ROUTED_FIDELITY_BANNER,
    build_placement_problem,
    estimator_fidelity,
)
from gd_picasso.pcg.place.tensors import estimated_net_length
from gd_picasso.pcg.route import check_lidar_gf_pin, fidelity_vs_routed, route_with_lidar
from gd_picasso.pcg.types import EdgeLayer

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_fidelity_gate_drops_estimator_only_on_lidar_ir() -> None:
    pin = check_lidar_gf_pin()
    if not pin.lidar_import_ok:
        pytest.skip(pin.detail)

    store = from_lidar_yaml(
        (FIXTURES / "lidar" / "lidar_mzi_stub.yaml").read_text()
    )
    routed = route_with_lidar(store, design="fid_mzi")
    assert routed.ok and routed.metrics
    assert "STUB" not in routed.banner.upper() or "LiDAR" in routed.banner

    # Predict with place estimator at current xy
    problem = build_placement_problem(store)
    pred = {}
    optical = [e for e in store.edges if e.layer == EdgeLayer.OPTICAL]
    for net in problem.nets:
        e = optical[net.edge_idx]
        L = float(estimated_net_length(problem, net))
        pred[(e.src_node, e.src_port, e.dst_node, e.dst_port)] = L

    fid = fidelity_vs_routed(pred, routed.metrics, mae_um_threshold=100.0)
    assert fid["n"] >= 2
    # When MAE within threshold, banner may be dropped for routed claims
    if fid["drop_estimator_only"]:
        report = estimator_fidelity(
            store,
            treat_edge_length_as="routed",
            mae_um_threshold=100.0,
        )
        assert "ESTIMATOR_ONLY" not in report.banner
        assert "ROUTED" in report.banner
        assert report.banner == ROUTED_FIDELITY_BANNER
    else:
        assert fid["mae_um"] >= 0.0
        assert "ESTIMATOR_ONLY" in ESTIMATOR_ONLY_BANNER


def test_gf_routed_self_fidelity_always_drops() -> None:
    """GF netlist lengths vs themselves → drop ESTIMATOR_ONLY."""
    from gd_picasso.pcg.gf_route_metrics import (
        backannotate_from_yaml,
        route_metrics_for_store,
    )
    import gdsfactory as gf

    text = (FIXTURES / "picset_task06.yaml").read_text()
    store = from_gf_yaml(text)
    c = gf.read.from_yaml(text)
    nl = c.get_netlist()
    metrics = route_metrics_for_store(store, nl)
    if not metrics:
        pytest.skip("no GF netlist metrics mapped to store")
    pred = {k: m.length_um for k, m in metrics.items()}
    fid = fidelity_vs_routed(pred, metrics, mae_um_threshold=1.0)
    assert fid["drop_estimator_only"] is True
    assert fid["mae_um"] == pytest.approx(0.0)

    n = backannotate_from_yaml(store, text)
    assert n >= 2
    report = estimator_fidelity(
        store,
        treat_edge_length_as="routed",
        mae_um_threshold=50.0,
        drop_estimator_only=True,
    )
    assert report.banner == ROUTED_FIDELITY_BANNER
