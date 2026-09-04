"""
PCG invariant tests — mutation negatives and hash invariance.

These are the direct evidence for the claim that illegal states are
unrepresentable, and that topology_hash / layout_hash behave as advertised.

Run:  python -m gd_picasso.pcg.test_pcg_invariants
"""

from __future__ import annotations

import sys

from gd_picasso.pcg import (
    EdgeLayer,
    PCGMutationError,
    PCGNode,
    PCGStore,
    RefLevel,
)


def _two_node_store() -> PCGStore:
    store = PCGStore()
    store.add_node(
        PCGNode(id="a", component="mmi1x2", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    store.add_node(
        PCGNode(id="b", component="straight", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    return store


def test_double_connect_raises() -> None:
    store = _two_node_store()
    store.connect("a", "o2", "b", "o1")
    raised = False
    try:
        store.connect("a", "o2", "b", "o2")  # a.o2 already occupied
    except PCGMutationError as e:
        raised = True
        assert "already connected" in str(e)
    assert raised, "double-connect on occupied port should raise"


def test_reverse_order_double_connect_raises() -> None:
    """Optical links are physically undirected — a→b then b→a must raise.

    MultiDiGraph would happily store a parallel reverse edge unless degree
    is checked on both endpoints regardless of direction.
    """
    store = _two_node_store()
    store.connect("a", "o2", "b", "o1")
    raised = False
    try:
        store.connect("b", "o1", "a", "o2")  # reverse of existing link
    except PCGMutationError as e:
        raised = True
        assert "already connected" in str(e)
    assert raised, "reverse-order double-connect must raise (optical undirected)"


def test_self_loop_raises() -> None:
    store = _two_node_store()
    raised = False
    try:
        store.connect("a", "o1", "a", "o1")
    except PCGMutationError as e:
        raised = True
        assert "Self-loop" in str(e)
    assert raised, "self-loop on same port should raise"


def test_out_of_signature_param_raises() -> None:
    store = PCGStore()
    store.add_node(
        PCGNode(id="s", component="straight", level=RefLevel.L1_CIRCUIT),
        skip_component_check=False,  # need real component for signature check
    )
    raised = False
    try:
        store.set_param("s", "not_a_real_param_xyz", 42)
    except PCGMutationError as e:
        raised = True
        assert "not in signature" in str(e) or "set_param" in str(e)
    assert raised, "out-of-signature param should raise"


def test_duplicate_node_id_raises() -> None:
    store = _two_node_store()
    raised = False
    try:
        store.add_node(
            PCGNode(id="a", component="mmi1x2"),
            skip_component_check=True,
        )
    except PCGMutationError as e:
        raised = True
        assert "Duplicate" in str(e)
    assert raised, "duplicate node id should raise"


def test_topology_hash_invariant_to_insertion_order() -> None:
    """Same nodes/edges inserted in different order → same topology_hash."""
    s1 = PCGStore()
    s1.add_node(PCGNode(id="a", component="mmi1x2", params={"x": 1}), skip_component_check=True)
    s1.add_node(PCGNode(id="b", component="straight", params={"length": 10}), skip_component_check=True)
    s1.connect("a", "o2", "b", "o1")

    s2 = PCGStore()
    s2.add_node(PCGNode(id="b", component="straight", params={"length": 10}), skip_component_check=True)
    s2.add_node(PCGNode(id="a", component="mmi1x2", params={"x": 1}), skip_component_check=True)
    s2.connect("a", "o2", "b", "o1")

    assert s1.topology_hash() == s2.topology_hash(), \
        "topology_hash must be invariant to insertion order"


def test_topology_hash_invariant_to_placement() -> None:
    """Moving a node must not change topology_hash."""
    store = _two_node_store()
    store.connect("a", "o2", "b", "o1")
    h_before = store.topology_hash()

    node = store.nodes["a"]
    # mutate placement via model_copy / direct field set
    node.x = 100.0
    node.y = 50.0
    node.rotation = 90
    node.mirror = True

    h_after = store.topology_hash()
    assert h_before == h_after, \
        "topology_hash must be invariant to placement edits"


def test_layout_hash_changes_on_move() -> None:
    """Moving a placed node must change layout_hash; L1 returns None."""
    store = _two_node_store()
    store.connect("a", "o2", "b", "o1")
    assert store.layout_hash() is None, "L1 (no geometry) → layout_hash is None"

    for nid, (x, y) in [("a", (0.0, 0.0)), ("b", (40.0, 0.0))]:
        n = store.nodes[nid]
        n.x, n.y, n.rotation, n.mirror = x, y, 0, False

    h1 = store.layout_hash()
    assert h1 is not None

    store.nodes["b"].x = 80.0  # move
    h2 = store.layout_hash()
    assert h2 is not None
    assert h1 != h2, "layout_hash must change when a node moves"


def run_all() -> int:
    tests = [
        test_double_connect_raises,
        test_reverse_order_double_connect_raises,
        test_self_loop_raises,
        test_out_of_signature_param_raises,
        test_duplicate_node_id_raises,
        test_topology_hash_invariant_to_insertion_order,
        test_topology_hash_invariant_to_placement,
        test_layout_hash_changes_on_move,
    ]
    passed = 0
    failed = 0
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
