"""
Lane Agents tests: A0 elaborator → ExactCritic accept/reject → SM path.

gf-free; exercises deterministic topology expansion and the A0→A1→critique→A4
controller path without touching bridge/fixtures/place.

A1 batch ops obey ``A1_MUTATION_CONTRACT.md`` v1; exports are store-direct.

Run:  pytest gd_picasso/agents/test_elaborator_path.py -q
"""

from __future__ import annotations

import pytest

from gd_picasso.agents.elaborator import (
    ElaboratorError,
    TopologyElaborator,
    parse_topology_program,
)
from gd_picasso.agents.exact_critic import ExactCritic
from gd_picasso.agents.intent_agent import IntentAgent, TypedIntent
from gd_picasso.agents.schematic_agent import SchematicAgent
from gd_picasso.agents.state_machine import AgentStateMachine
from gd_picasso.pcg.store import PCGMutationError, PCGStore


def test_parse_mzi_program_kwargs() -> None:
    name, kwargs = parse_topology_program(
        "mzi(arms=2, ps=straight_heater_metal)"
    )
    assert name == "mzi"
    assert kwargs["arms"] == 2
    assert kwargs["ps"] == "straight_heater_metal"


def test_parse_mzm_program_kwargs() -> None:
    name, kwargs = parse_topology_program("mzm(dual_drive=true)")
    assert name == "mzm"
    assert kwargs["dual_drive"] is True


def test_elaboration_emits_only_contract_batch_ops() -> None:
    result = TopologyElaborator().elaborate_program(
        "mzi(arms=2, ps=straight_heater_metal)"
    )
    allowed = {"add_node", "connect", "set_param"}
    assert all(m["op"] in allowed for m in result.mutations)
    assert "set_exported_ports" not in {m["op"] for m in result.mutations}
    assert result.exported_ports


def test_exact_critic_accepts_mzi_elaboration() -> None:
    elaborator = TopologyElaborator()
    intent = TypedIntent(
        topology_program="mzi(arms=2, ps=straight_heater_metal)",
        role="interferometer",
    )
    result = elaborator.elaborate(intent)
    store = PCGStore(default_agent="A1")
    critique = SchematicAgent().apply_elaboration(
        store, result.mutations, result.exported_ports
    )
    assert critique.ok is True, critique.problems
    assert set(store.nodes) == {"splitter", "ps_upper", "ps_lower", "combiner"}
    assert store.nodes["ps_upper"].component == "straight_heater_metal"
    assert store.nodes["ps_lower"].component == "straight"
    assert store.exported_ports == {"in": "splitter,o1", "out": "combiner,o1"}
    assert ExactCritic().review(store).ok is True


def test_exact_critic_accepts_mzm_elaboration() -> None:
    elaborator = TopologyElaborator()
    intent = TypedIntent(
        topology_program="mzm(dual_drive=true)",
        role="modulator",
    )
    result = elaborator.elaborate(intent)
    store = PCGStore(default_agent="A1")
    critique = SchematicAgent().apply_elaboration(
        store, result.mutations, result.exported_ports
    )
    assert critique.ok is True, critique.problems
    assert store.nodes["combiner"].component == "mmi2x2"
    assert store.nodes["ps_upper"].component == "straight_heater_metal"
    assert store.nodes["ps_lower"].component == "straight_heater_metal"
    assert store.exported_ports == {
        "in": "splitter,o1",
        "out1": "combiner,o3",
        "out2": "combiner,o4",
    }


def test_exact_critic_rejects_incomplete_elaboration() -> None:
    """Omit exports → dangling ports → ExactCritic fails."""
    result = TopologyElaborator().elaborate_program(
        "mzi(arms=2, ps=straight_heater_metal)"
    )
    store = PCGStore(default_agent="A1")
    critique = SchematicAgent().apply_elaboration(
        store, result.mutations, exported_ports=None
    )
    assert critique.ok is False
    assert any("Dangling" in p for p in critique.problems)


def test_exact_critic_rejects_unknown_component_mutation() -> None:
    """Illegal component passes A1 add (skip check) but ExactCritic rejects."""
    store = PCGStore(default_agent="A1")
    critique = SchematicAgent().apply_mutations(
        store,
        [
            {
                "op": "add_node",
                "id": "bad",
                "component": "not_a_real_pcell",
                "params": {},
            },
        ],
    )
    assert critique.ok is False
    assert any("Unknown component" in p for p in critique.problems)


def test_store_rejects_illegal_double_connect_after_elaboration() -> None:
    result = TopologyElaborator().elaborate_program(
        "mzi(arms=2, ps=straight_heater_metal)"
    )
    store = PCGStore(default_agent="A1")
    a1 = SchematicAgent()
    critique = a1.apply_elaboration(store, result.mutations, result.exported_ports)
    assert critique.ok is True
    with pytest.raises(PCGMutationError) as ei:
        a1.connect(store, "splitter", "o2", "ps_lower", "o2")
    assert "already connected" in str(ei.value)


def test_a1_batch_rolls_back_illegal_mutation_on_elaborated_graph() -> None:
    result = TopologyElaborator().elaborate_program("mzm(dual_drive=true)")
    store = PCGStore(default_agent="A1")
    a1 = SchematicAgent()
    assert a1.apply_elaboration(
        store, result.mutations, result.exported_ports
    ).ok is True
    n_edges = len(store.edges)
    with pytest.raises(PCGMutationError):
        a1.apply_mutations(
            store,
            [
                {
                    "op": "connect",
                    "src": "splitter",
                    "src_port": "o2",
                    "dst": "combiner",
                    "dst_port": "o3",
                },
            ],
        )
    assert len(store.edges) == n_edges


def test_elaborator_rejects_unsupported_program() -> None:
    with pytest.raises(ElaboratorError):
        TopologyElaborator().elaborate_program("ring_bus(coupler=coupler)")


def test_intent_agent_programs_match_elaborator() -> None:
    a0 = IntentAgent()
    mzi_intent = a0.capture("Build a Mach-Zehnder interferometer")
    assert mzi_intent.topology_program is not None
    assert mzi_intent.topology_program.startswith("mzi")
    TopologyElaborator().elaborate(mzi_intent)

    mzm_intent = a0.capture("Build an MZM dual-drive modulator")
    assert mzm_intent.topology_program is not None
    assert mzm_intent.topology_program.startswith("mzm")
    TopologyElaborator().elaborate(mzm_intent)


def test_sm_path_a0_a1_critique_a4_mzi() -> None:
    sm = AgentStateMachine()
    result = sm.run_a0_a1_critique_a4("Design a Mach-Zehnder interferometer")
    intent = result["intent"]
    critique = result["critique"]
    triage = result["triage"]
    assert intent.topology_program is not None
    assert intent.topology_program.startswith("mzi")
    assert any(m["op"] == "add_node" for m in result["mutations"])
    assert "set_exported_ports" not in {m["op"] for m in result["mutations"]}
    assert result["exported_ports"]
    assert critique.ok is True, critique.problems
    assert result["failures"] == []
    assert triage.reinvoke == "none"
    assert any(e.op == "A0_intent" for e in sm.store.journal.entries)
    assert any(e.op == "A4_triage" for e in sm.store.journal.entries)
    assert "splitter" in sm.store.nodes


def test_sm_path_a0_a1_critique_a4_mzm() -> None:
    sm = AgentStateMachine()
    result = sm.run_a0_a1_critique_a4("Design an MZM dual-drive modulator")
    assert result["intent"].topology_program.startswith("mzm")
    assert result["critique"].ok is True, result["critique"].problems
    assert result["triage"].reinvoke == "none"
    assert sm.store.nodes["combiner"].component == "mmi2x2"


def test_sm_path_triages_when_critique_fails() -> None:
    """Force a bad store after A0, then run critique→A4 mapping."""
    sm = AgentStateMachine()
    sm.run_intent("Design a Mach-Zehnder interferometer")
    sm.a1.add_component(sm.store, "a", "mmi1x2")
    sm.store.set_exported_ports({"in": "a,o1"}, agent="A1")
    critique = sm.critique_schematic()
    assert critique.ok is False
    failures = sm.critique_to_failures(critique)
    assert failures
    assert all(f["kind"] == "dangling" for f in failures)
    triage = sm.triage_failures(failures)
    assert triage.reinvoke == "A1"
