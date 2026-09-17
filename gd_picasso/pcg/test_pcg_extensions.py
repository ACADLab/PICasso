"""
Tests for journal, legalize, placement dirty-bit, and malformed YAML links.

Run:  python -m gd_picasso.pcg.test_pcg_extensions
"""

from __future__ import annotations

import sys

from gd_picasso.pcg import (
    PCGMutationError,
    PCGNode,
    PCGStore,
    RefLevel,
    detect_dangling_ports,
    from_gf_yaml,
    insert_terminators,
    to_gf_yaml,
)
from gd_picasso.pcg.spa import spa_v0
from gd_picasso.pcg.backannotate import RouteMetrics, apply_route_metrics


def test_journal_records_mutations() -> None:
    store = PCGStore(default_agent="test")
    store.add_node(
        PCGNode(id="a", component="mmi1x2", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    store.add_node(
        PCGNode(id="b", component="straight", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    store.connect("a", "o2", "b", "o1")
    ops = [e.op for e in store.journal.entries]
    assert ops == ["add_node", "add_node", "connect"], ops
    assert all(e.agent == "test" for e in store.journal.entries)


def test_placement_dirty_roundtrip() -> None:
    yaml_in = """\
instances:
  wg:
    component: straight
    settings: {length: 10}
placements:
  wg: {x: 0, y: 0, rotation: 0, mirror: false}
routes: {}
ports:
  in: wg,o1
  out: wg,o2
"""
    store = from_gf_yaml(yaml_in)
    store.set_placement("wg", x=42.0, y=7.0)
    out = to_gf_yaml(store)
    assert "42" in out
    store2 = from_gf_yaml(out)
    assert store2.nodes["wg"].x == 42.0


def test_malformed_link_raises() -> None:
    bad = """\
instances:
  a:
    component: straight
    settings: {}
routes:
  optical:
    links:
      a,o1: not_a_port_ref
ports:
  in: a,o1
  out: a,o2
"""
    raised = False
    try:
        from_gf_yaml(bad)
    except PCGMutationError as e:
        raised = True
        assert "Malformed" in str(e)
    assert raised


def test_dangling_and_terminators() -> None:
    store = PCGStore()
    store.add_node(
        PCGNode(id="a", component="mmi1x2", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    store.set_exported_ports({"in": "a,o1"})
    dangling = detect_dangling_ports(store)
    # o1 exported; o2,o3 dangling
    assert len(dangling) >= 2
    inserted = insert_terminators(store, skip_exported=True)
    assert len(inserted) >= 2
    # second detect should not duplicate
    more = detect_dangling_ports(store)
    assert more == []


def test_ring_bus_edge_counts() -> None:
    from gd_picasso.pcg.pcg_roundtrip_test import FIXTURE_RING

    store = from_gf_yaml(FIXTURE_RING)
    assert len(store.nodes) == 3
    assert len(store.edges) == 3  # 2 routes + 1 same-inst connection
    # same-node different-port feedback present
    feedback = [
        e for e in store.edges
        if e.src_node == "dc" and e.dst_node == "dc"
    ]
    assert len(feedback) == 1


def test_spa_phase_slack() -> None:
    store = PCGStore()
    for nid, comp in [("s", "mmi1x2"), ("u", "straight"), ("l", "straight"), ("c", "mmi1x2")]:
        store.add_node(
            PCGNode(id=nid, component=comp, level=RefLevel.L1_CIRCUIT),
            skip_component_check=True,
        )
    store.connect("s", "o2", "u", "o1")
    store.connect("s", "o3", "l", "o1")
    store.connect("u", "o2", "c", "o2")
    store.connect("l", "o2", "c", "o3")
    apply_route_metrics(
        store,
        {
            ("s", "o2", "u", "o1"): RouteMetrics(length_um=100.0),
            ("s", "o3", "l", "o1"): RouteMetrics(length_um=110.0),
            ("u", "o2", "c", "o2"): RouteMetrics(length_um=100.0),
            ("l", "o2", "c", "o3"): RouteMetrics(length_um=100.0),
        },
    )
    report = spa_v0(
        store,
        {"arms": [["s", "u", "c"], ["s", "l", "c"]]},
        tolerance_rad=0.01,
    )
    assert len(report.groups) == 1
    # unequal arm lengths → likely negative slack
    assert report.groups[0].delta_phi_rad != 0.0


def test_ports_populated_on_import() -> None:
    store = from_gf_yaml(
        "instances:\n  r:\n    component: ring_single\n    settings: {}\n"
        "placements: {}\nroutes: {}\nports:\n  in: r,o1\n  out: r,o2\n"
    )
    assert "o1" in store.nodes["r"].ports
    assert "o2" in store.nodes["r"].ports


def run_all() -> int:
    tests = [
        test_journal_records_mutations,
        test_placement_dirty_roundtrip,
        test_malformed_link_raises,
        test_dangling_and_terminators,
        test_ring_bus_edge_counts,
        test_spa_phase_slack,
        test_ports_populated_on_import,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {t.__name__}: {exc}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {len(tests)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
