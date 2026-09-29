"""
Top-level PICasso+ agent state machine scaffold.

Wires A0–A4 around a shared PCGStore. Closes the schematic path
A0 → elaborator → A1 mutations → ExactCritic → A4 triage. Full
generate→P&R→sim still waits on placement/routing kernels.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from gd_picasso.agents.elaborator import ElaboratorError, TopologyElaborator
from gd_picasso.agents.exact_critic import ExactCritique
from gd_picasso.agents.intent_agent import IntentAgent, TypedIntent
from gd_picasso.agents.optimization_agent import OptimizationAgent
from gd_picasso.agents.physical_design_agent import PhysicalDesignAgent
from gd_picasso.agents.schematic_agent import SchematicAgent
from gd_picasso.agents.triage_agent import TriageAgent, TriageDecision
from gd_picasso.pcg.store import PCGStore

_DANGLING_RE = re.compile(r"Dangling optical port (\S+)\.(\S+)")
_UNKNOWN_RE = re.compile(r"Unknown component '([^']+)' on node '([^']+)'")
_DEGREE_RE = re.compile(r"Optical port (\S+)\.(\S+) has degree")


class AgentStateMachine:
    """Minimal controller: intent → elaborate → schematic critique → triage."""

    def __init__(self, store: Optional[PCGStore] = None) -> None:
        self.store = store or PCGStore(default_agent="orchestrator")
        self.a0 = IntentAgent()
        self.elaborator = TopologyElaborator()
        self.a1 = SchematicAgent()
        self.a2 = PhysicalDesignAgent()
        self.a3 = OptimizationAgent()
        self.a4 = TriageAgent()
        self.last_intent: Optional[TypedIntent] = None
        self.last_critique: Optional[ExactCritique] = None
        self.last_triage: Optional[TriageDecision] = None
        self.last_mutations: List[Dict[str, Any]] = []

    def run_intent(self, problem_text: str) -> TypedIntent:
        self.last_intent = self.a0.capture(problem_text)
        self.store.journal.append(
            "A0_intent",
            self.last_intent.model_dump(),
            agent="A0",
        )
        return self.last_intent

    def critique_schematic(self) -> ExactCritique:
        self.last_critique = self.a1.critique(self.store)
        return self.last_critique

    def triage_failures(self, failures: List[Dict[str, Any]]) -> TriageDecision:
        self.last_triage = self.a4.triage(self.store, failures)
        return self.last_triage

    def propose_pnr_knobs(self, metrics: Optional[Dict[str, float]] = None):
        return self.a2.propose(self.store, metrics)

    def propose_opt(self, metrics: Optional[Dict[str, float]] = None):
        return self.a3.propose(self.store, metrics)

    @staticmethod
    def critique_to_failures(critique: ExactCritique) -> List[Dict[str, Any]]:
        """Map ExactCritic problems into A4 failure dicts."""
        failures: List[Dict[str, Any]] = []
        for problem in critique.problems:
            m = _DANGLING_RE.search(problem)
            if m:
                failures.append(
                    {
                        "kind": "dangling",
                        "elements": [m.group(1), m.group(2)],
                        "evidence": {"from": "ExactCritic", "message": problem},
                    }
                )
                continue
            m = _DEGREE_RE.search(problem)
            if m:
                failures.append(
                    {
                        "kind": "port",
                        "elements": [m.group(1), m.group(2)],
                        "evidence": {"from": "ExactCritic", "message": problem},
                    }
                )
                continue
            m = _UNKNOWN_RE.search(problem)
            if m:
                failures.append(
                    {
                        "kind": "custom",
                        "elements": [m.group(2)],
                        "evidence": {
                            "from": "ExactCritic",
                            "message": problem,
                            "component": m.group(1),
                        },
                    }
                )
                continue
            failures.append(
                {
                    "kind": "custom",
                    "elements": [],
                    "evidence": {"from": "ExactCritic", "message": problem},
                }
            )
        return failures

    def run_a0_a1_critique_a4(self, problem_text: str) -> Dict[str, Any]:
        """Full schematic path: A0 → elaborator → A1 → ExactCritic → A4.

        Returns a dict with intent, mutations, critique, failures, and triage
        for assertion-friendly unit tests.
        """
        intent = self.run_intent(problem_text)
        if not intent.topology_program:
            raise ElaboratorError(
                "No topology_program from A0; cannot elaborate schematic path"
            )
        mutations = self.elaborator.elaborate(intent)
        self.last_mutations = list(mutations.mutations)
        critique = self.a1.apply_elaboration(
            self.store,
            mutations.mutations,
            mutations.exported_ports,
        )
        self.last_critique = critique
        failures = self.critique_to_failures(critique)
        triage = self.triage_failures(failures)
        return {
            "intent": intent,
            "mutations": mutations.mutations,
            "exported_ports": mutations.exported_ports,
            "critique": critique,
            "failures": failures,
            "triage": triage,
        }
