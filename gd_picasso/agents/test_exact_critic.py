"""Unit tests for fortified ExactCritic (planarity, bounds, polarization)."""

from __future__ import annotations

from pathlib import Path

import pytest

from gd_picasso.agents.exact_critic import ExactCritic, count_aabb_crossings
from gd_picasso.pcg import PCGMutationError, PCGNode, PCGStore, RefLevel, from_gf_yaml
from gd_picasso.pcg.spa_protocol import N1_TASK_SUBSET
from gd_picasso.pcg.types import PCGPort, PortKind

PICSET = Path(__file__).resolve().parents[1] / "pcg" / "fixtures" / "picset"


def _two_straights(store: PCGStore) -> None:
    store.add_node(
        PCGNode(id="a", component="straight", params={"length": 10.0}),
        skip_component_check=True,
    )
    store.add_node(
        PCGNode(id="b", component="straight", params={"length": 10.0}),
        skip_component_check=True,
    )


def test_bounds_reject_zero_length_at_set_param() -> None:
    store = PCGStore()
    store.add_node(
        PCGNode(id="a", component="straight", params={"length": 10.0}),
        skip_component_check=True,
    )
    with pytest.raises(PCGMutationError) as ei:
        store.set_param("a", "length", 0.0)
    assert "out_of_bounds_param" in str(ei.value)


def test_bounds_reject_small_bend_radius() -> None:
    store = PCGStore()
    store.add_node(
        PCGNode(id="b", component="bend_euler", params={"radius": 10.0}),
        skip_component_check=True,
    )
    with pytest.raises(PCGMutationError) as ei:
        store.set_param("b", "radius", 4.0)
    assert "out_of_bounds_param" in str(ei.value)


def test_critic_flags_out_of_bounds_existing_param() -> None:
    store = PCGStore()
    # Bypass set_param by planting a bad value at construction
    store.add_node(
        PCGNode(id="a", component="straight", params={"length": 0.0}),
        skip_component_check=True,
    )
    store.set_exported_ports({"in": "a,o1", "out": "a,o2"})
    c = ExactCritic().review(store)
    assert not c.ok
    assert any("out_of_bounds_param" in p for p in c.problems)


def test_polarization_mismatch_rejected_on_connect() -> None:
    store = PCGStore()
    a = PCGNode(id="a", component="straight", params={"length": 10.0})
    a.ports = {
        "o1": PCGPort(name="o1", kind=PortKind.OPTICAL, polarization="TE"),
        "o2": PCGPort(name="o2", kind=PortKind.OPTICAL, polarization="TE"),
    }
    b = PCGNode(id="b", component="straight", params={"length": 10.0})
    b.ports = {
        "o1": PCGPort(name="o1", kind=PortKind.OPTICAL, polarization="TM"),
        "o2": PCGPort(name="o2", kind=PortKind.OPTICAL, polarization="TM"),
    }
    store.add_node(a, skip_component_check=True)
    store.add_node(b, skip_component_check=True)
    with pytest.raises(PCGMutationError) as ei:
        store.connect("a", "o2", "b", "o1")
    assert "polarization mismatch" in str(ei.value)


def test_portkind_mismatch_rejected_on_connect() -> None:
    store = PCGStore()
    a = PCGNode(id="a", component="straight", params={"length": 10.0})
    a.ports = {
        "o1": PCGPort(name="o1", kind=PortKind.OPTICAL, polarization="TE"),
        "o2": PCGPort(name="o2", kind=PortKind.OPTICAL, polarization="TE"),
    }
    b = PCGNode(id="b", component="straight", params={"length": 10.0})
    b.ports = {
        "o1": PCGPort(name="o1", kind=PortKind.ELECTRICAL, polarization="TE"),
        "o2": PCGPort(name="o2", kind=PortKind.ELECTRICAL, polarization="TE"),
    }
    store.add_node(a, skip_component_check=True)
    store.add_node(b, skip_component_check=True)
    with pytest.raises(PCGMutationError) as ei:
        store.connect("a", "o2", "b", "o1")
    assert "PortKind mismatch" in str(ei.value)


def test_aabb_crossing_detected() -> None:
    store = PCGStore()
    # Four nodes at corners of a square; diagonals cross
    for nid, xy in [
        ("a", (0.0, 0.0)),
        ("b", (10.0, 10.0)),
        ("c", (0.0, 10.0)),
        ("d", (10.0, 0.0)),
    ]:
        n = PCGNode(
            id=nid,
            component="straight",
            params={"length": 10.0},
            x=xy[0],
            y=xy[1],
            level=RefLevel.L2_PLACED,
        )
        store.add_node(n, skip_component_check=True)
    store.connect("a", "o1", "b", "o1")  # diagonal
    store.connect("c", "o1", "d", "o1")  # other diagonal
    store.set_exported_ports(
        {
            "a_out": "a,o2",
            "b_out": "b,o2",
            "c_out": "c,o2",
            "d_out": "d,o2",
        }
    )
    assert count_aabb_crossings(store) >= 1
    c = ExactCritic().review(store)
    assert not c.ok
    assert any("n_crossings" in p for p in c.problems)


def test_planar_tree_ok() -> None:
    store = PCGStore()
    _two_straights(store)
    store.connect("a", "o2", "b", "o1")
    store.set_exported_ports({"in": "a,o1", "out": "b,o2"})
    c = ExactCritic().review(store)
    assert c.ok, c.problems


def test_disconnected_nodes_fail_connectivity() -> None:
    store = PCGStore()
    _two_straights(store)
    # No optical edge — two isolated nodes
    store.set_exported_ports(
        {"a_in": "a,o1", "a_out": "a,o2", "b_in": "b,o1", "b_out": "b,o2"}
    )
    c = ExactCritic().review(store)
    assert not c.ok
    assert any("wrong_connectivity" in p or "disconnected" in p for p in c.problems)


def test_extract_yaml_strips_unfenced_prose() -> None:
    from gd_picasso.pcg.run_n1_campaign import extract_yaml_block

    raw = (
        "Sure! Here is the netlist:\n\n"
        "instances:\n  a:\n    component: straight\n"
        "ports:\n  in: a,o1\n\n"
        "Hope that helps!"
    )
    out = extract_yaml_block(raw)
    assert out.lstrip().startswith("instances:")
    assert "Hope that helps" not in out
    assert "Sure!" not in out


@pytest.mark.parametrize("task_id", list(N1_TASK_SUBSET))
def test_n1_fixtures_pass_exact_critic(task_id: int) -> None:
    path = PICSET / f"task_{task_id:02d}.yaml"
    assert path.is_file(), f"missing fixture {path}"
    store = from_gf_yaml(path.read_text(encoding="utf-8"))
    critique = ExactCritic().review(store)
    assert critique.ok, f"task {task_id}: {critique.problems}"
