"""
Hardening tests: rejected mutations, agent violation paths, ExactCritic fails.

These exist because happy-path coverage does not exercise the product —
the invariants. Every test below asserts a *rejection* or a failed critique.

Run:  python -m gd_picasso.pcg.test_pcg_rejection
"""

from __future__ import annotations

import sys

from gd_picasso.agents.exact_critic import ExactCritic
from gd_picasso.agents.schematic_agent import SchematicAgent
from gd_picasso.agents.triage_agent import TriageAgent
from gd_picasso.pcg import (
    PCGMutationError,
    PCGNode,
    PCGStore,
    RefLevel,
    from_gf_yaml,
    to_gf_yaml,
)
from gd_picasso.pcg.types import PortKind, PCGPort


def test_a1_rejected_double_connect() -> None:
    a1 = SchematicAgent()
    store = PCGStore(default_agent="A1")
    a1.add_component(store, "a", "mmi1x2")
    a1.add_component(store, "b", "straight")
    a1.connect(store, "a", "o2", "b", "o1")
    raised = False
    try:
        a1.connect(store, "a", "o2", "b", "o2")
    except PCGMutationError as e:
        raised = True
        assert "already connected" in str(e)
    assert raised
    connect_ops = [e for e in store.journal.entries if e.op == "connect"]
    assert len(connect_ops) == 1, "rejected connect must not append to journal"


def test_a1_batch_stops_on_illegal_mutation() -> None:
    a1 = SchematicAgent()
    store = PCGStore()
    a1.add_component(store, "a", "mmi1x2")
    a1.add_component(store, "b", "straight")
    raised = False
    try:
        a1.apply_mutations(
            store,
            [
                {"op": "connect", "src": "a", "src_port": "o2", "dst": "b", "dst_port": "o1"},
                {"op": "connect", "src": "a", "src_port": "o2", "dst": "b", "dst_port": "o2"},
            ],
        )
    except PCGMutationError:
        raised = True
    assert raised
    # Atomic batch: first connect must not stick after rollback
    assert len(store.edges) == 0
    assert not any(e.op == "connect" for e in store.journal.entries)


def test_connect_rejects_unknown_port() -> None:
    store = PCGStore()
    store.add_node(
        PCGNode(id="a", component="mmi1x2", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    store.add_node(
        PCGNode(id="b", component="straight", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    raised = False
    try:
        store.connect("a", "o99", "b", "o1")
    except PCGMutationError as e:
        raised = True
        assert "o99" in str(e)
    assert raised


def test_l1_yaml_omits_spurious_placements() -> None:
    yaml_in = """\
instances:
  wg:
    component: straight
    settings: {length: 10}
routes: {}
ports:
  in: wg,o1
  out: wg,o2
"""
    store = from_gf_yaml(yaml_in)
    out = to_gf_yaml(store)
    assert "placements:" not in out


def test_batch_keyerror_rolls_back() -> None:
    a1 = SchematicAgent()
    store = PCGStore()
    a1.add_component(store, "a", "mmi1x2")
    a1.add_component(store, "b", "straight")
    raised = False
    try:
        a1.apply_mutations(
            store,
            [
                {"op": "connect", "src": "a", "src_port": "o2", "dst": "b", "dst_port": "o1"},
                {"op": "connect", "src": "a"},  # missing keys → KeyError
            ],
        )
    except KeyError:
        raised = True
    assert raised
    assert len(store.edges) == 0


def test_accumulate_path_missing_hop_raises() -> None:
    from gd_picasso.pcg.spa import accumulate_path

    store = PCGStore()
    store.add_node(
        PCGNode(id="a", component="straight", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    store.add_node(
        PCGNode(id="b", component="straight", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    # no edge a—b
    raised = False
    try:
        accumulate_path(store, ["a", "b"])
    except ValueError as e:
        raised = True
        assert "No optical edge" in str(e)
    assert raised


def test_exact_critic_second_pass_still_flags_dangling() -> None:
    store = PCGStore()
    store.add_node(
        PCGNode(id="a", component="mmi1x2", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    store.set_exported_ports({"in": "a,o1"})
    c1 = ExactCritic().review(store)
    assert c1.ok is False
    c2 = ExactCritic().review(store)
    assert c2.ok is False
    assert any("Dangling" in p for p in c2.problems)


def test_exact_critic_flags_unknown_component() -> None:
    store = PCGStore()
    store.add_node(
        PCGNode(
            id="x",
            component="not_a_real_pcell",
            level=RefLevel.L1_CIRCUIT,
            ports={"o1": PCGPort(name="o1", kind=PortKind.OPTICAL)},
        ),
        skip_component_check=True,
    )
    critique = ExactCritic().review(store)
    assert critique.ok is False
    assert any("Unknown component" in p for p in critique.problems)


def test_exact_critic_flags_nonexported_dangling() -> None:
    store = PCGStore()
    store.add_node(
        PCGNode(id="a", component="mmi1x2", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    # export only o1 — o2/o3 dangling
    store.set_exported_ports({"in": "a,o1"})
    critique = ExactCritic().review(store)
    assert critique.ok is False
    assert any("Dangling" in p for p in critique.problems)


def test_set_param_rejects_bogus_key_via_agent() -> None:
    a1 = SchematicAgent()
    store = PCGStore()
    a1.add_component(store, "s", "straight", {"length": 10})
    raised = False
    try:
        a1.set_param(store, "s", "not_a_real_param_xyz", 1)
    except PCGMutationError as e:
        raised = True
        assert "not in signature" in str(e)
    assert raised
    assert "not_a_real_param_xyz" not in store.nodes["s"].params


def test_triage_routes_dangling_to_a1() -> None:
    store = PCGStore()
    store.add_node(
        PCGNode(id="a", component="mmi1x2", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    decision = TriageAgent().triage(
        store,
        [{"kind": "dangling", "elements": ["a", "o2"], "evidence": {}}],
    )
    assert decision.reinvoke == "A1"
    assert len(decision.added_constraints) == 1
    assert any(e.op == "A4_triage" for e in store.journal.entries)


def test_malformed_yaml_rejected_before_partial_graph() -> None:
    bad = """\
instances:
  a: {component: straight, settings: {}}
  b: {component: straight, settings: {}}
routes:
  optical:
    links:
      a,o2: b,o1
      broken_ref: also_broken
ports:
  in: a,o1
  out: b,o2
"""
    raised = False
    try:
        from_gf_yaml(bad)
    except PCGMutationError:
        raised = True
    assert raised


def run_all() -> int:
    tests = [
        test_a1_rejected_double_connect,
        test_a1_batch_stops_on_illegal_mutation,
        test_exact_critic_flags_unknown_component,
        test_exact_critic_flags_nonexported_dangling,
        test_set_param_rejects_bogus_key_via_agent,
        test_triage_routes_dangling_to_a1,
        test_malformed_yaml_rejected_before_partial_graph,
        test_connect_rejects_unknown_port,
        test_l1_yaml_omits_spurious_placements,
        test_batch_keyerror_rolls_back,
        test_accumulate_path_missing_hop_raises,
        test_exact_critic_second_pass_still_flags_dangling,
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
