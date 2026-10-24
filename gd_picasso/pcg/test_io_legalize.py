"""Tapeout I/O pad legalization — fiber-array GCs @ 127 µm pitch."""

from __future__ import annotations

from pathlib import Path

from gd_picasso.pcg.bridge import from_gf_yaml
from gd_picasso.pcg.io_legalize import (
    FIBER_ARRAY_PITCH_UM,
    legalize_io_pads,
    resolve_gc_component,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "picset" / "task_01.yaml"
TASK11 = Path(__file__).resolve().parent / "fixtures" / "picset" / "task_11.yaml"


def test_resolve_gc_component_by_pdk() -> None:
    assert resolve_gc_component("cornerstone") == "grating_coupler_elliptical"
    assert resolve_gc_component("siepic") == "ebeam_gc_te895"
    assert resolve_gc_component("cornerstone", override="custom_gc") == "custom_gc"


def test_legalize_io_pads_mzi_fiber_array() -> None:
    store = from_gf_yaml(FIXTURE.read_text())
    # Ensure placements exist for bbox.
    assert store.nodes["splitter"].x is not None
    n_before = len(store.nodes)
    n_edges_before = len(store.edges)
    result = legalize_io_pads(store, pdk="cornerstone")
    assert not result.skipped
    assert result.n_inputs == 1
    assert result.n_outputs == 1
    assert result.pitch_um == FIBER_ARRAY_PITCH_UM
    assert len(result.gc_ids) == 2
    assert len(store.nodes) == n_before + 2
    assert len(store.edges) == n_edges_before + 2

    gc_in = store.nodes["gc_in_0"]
    gc_out = store.nodes["gc_out_0"]
    assert gc_in.component == "grating_coupler_elliptical"
    assert gc_out.component == "grating_coupler_elliptical"
    assert gc_in.rotation == 180
    assert gc_out.rotation == 0
    assert gc_in.x is not None and gc_out.x is not None
    assert gc_in.x < float(store.nodes["splitter"].x)
    assert gc_out.x > float(store.nodes["combiner"].x)

    assert store.exported_ports["in"] == "gc_in_0,o1"
    assert store.exported_ports["out"] == "gc_out_0,o1"

    # Idempotent skip when GCs already present.
    again = legalize_io_pads(store, pdk="cornerstone")
    assert again.skipped


def test_legalize_io_pads_crossbar_pitch() -> None:
    store = from_gf_yaml(TASK11.read_text())
    # Seed missing placements so bbox / pitch math is defined.
    for i, (nid, node) in enumerate(store.nodes.items()):
        if node.x is None:
            store.set_placement(nid, x=float(i % 8) * 80.0, y=float(i // 8) * 50.0)

    result = legalize_io_pads(store, pdk="cornerstone", pitch_um=127.0)
    assert result.n_inputs == 4
    assert result.n_outputs == 4
    ys_in = sorted(float(store.nodes[g].y) for g in result.gc_ids if g.startswith("gc_in"))
    for a, b in zip(ys_in, ys_in[1:]):
        assert abs((b - a) - 127.0) < 1e-6
