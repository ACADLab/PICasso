"""
Top-level PICasso+ agent state machine scaffold.

Wires A0–A4 around a shared PCGStore. Does not yet close the full
generate→P&R→sim loop — that waits on placement/routing kernels.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from gd_picasso.agents.intent_agent import IntentAgent, TypedIntent
from gd_picasso.agents.optimization_agent import OptimizationAgent
from gd_picasso.agents.physical_design_agent import PhysicalDesignAgent
from gd_picasso.agents.schematic_agent import SchematicAgent
from gd_picasso.agents.triage_agent import TriageAgent, TriageDecision
from gd_picasso.pcg.store import PCGStore


class AgentStateMachine:
    """Minimal controller: intent → schematic critique → triage routing."""

    def __init__(self, store: Optional[PCGStore] = None) -> None:
        self.store = store or PCGStore(default_agent="orchestrator")
        self.a0 = IntentAgent()
        self.a1 = SchematicAgent()
        self.a2 = PhysicalDesignAgent()
        self.a3 = OptimizationAgent()
        self.a4 = TriageAgent()
        self.last_intent: Optional[TypedIntent] = None
        self.last_triage: Optional[TriageDecision] = None

    def run_intent(self, problem_text: str) -> TypedIntent:
        self.last_intent = self.a0.capture(problem_text)
        self.store.journal.append(
            "A0_intent",
            self.last_intent.model_dump(),
            agent="A0",
        )
        return self.last_intent

    def critique_schematic(self):
        return self.a1.critique(self.store)

    def triage_failures(self, failures: List[Dict[str, Any]]) -> TriageDecision:
        self.last_triage = self.a4.triage(self.store, failures)
        return self.last_triage

    def propose_pnr_knobs(self, metrics: Optional[Dict[str, float]] = None):
        return self.a2.propose(self.store, metrics)

    def propose_opt(self, metrics: Optional[Dict[str, float]] = None):
        return self.a3.propose(self.store, metrics)
