"""B3: real 4x4 / 8x8 Clements expanded fixtures (not 4-node proxies)."""

from __future__ import annotations

from pathlib import Path

from gd_picasso.pcg.bridge import from_gf_yaml
from gd_picasso.pcg.clements_scale import clements_mzi_count

FIX = Path(__file__).resolve().parent / "fixtures" / "clements"


def test_clements_4x4_core_node_count() -> None:
    path = FIX / "clements_4x4_core.yaml"
    assert path.is_file()
    store = from_gf_yaml(path.read_text())
    assert clements_mzi_count(4) == 6
    assert len(store.nodes) == 24  # 6 MZIs × 4 CS cells
    comps = [n.component for n in store.nodes.values()]
    assert comps.count("mmi2x2") == 12
    assert comps.count("straight_heater_metal") == 6


def test_clements_8x8_core_node_count() -> None:
    path = FIX / "clements_8x8_core.yaml"
    assert path.is_file()
    store = from_gf_yaml(path.read_text())
    assert clements_mzi_count(8) == 28
    assert len(store.nodes) == 112  # 28 × 4
    comps = [n.component for n in store.nodes.values()]
    assert comps.count("mmi2x2") == 56
    assert comps.count("straight_heater_metal") == 28


def test_clements_4x4_mesh_has_rails() -> None:
    path = FIX / "clements_4x4_expanded.yaml"
    store = from_gf_yaml(path.read_text())
    assert len(store.nodes) > 24
    assert any(nid.startswith("in_") for nid in store.nodes)
    assert any(nid.startswith("rail_") for nid in store.nodes)
    assert store.exported_ports
