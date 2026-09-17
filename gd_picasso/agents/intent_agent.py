"""
A0 — Intent agent (NL → L0 typed intent).

Emits a structured intent object. Topology *programs* (e.g. mzi_tree) are
preferred over free-form node enumeration. LLM wiring is optional; the
schema is the contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IntentTarget(BaseModel):
    il_db: Optional[float] = None
    er_db: Optional[float] = None
    fsr_nm: Optional[float] = None
    splitting_ratio: Optional[float] = None
    bandwidth_nm: Optional[float] = None


class TypedIntent(BaseModel):
    """L0 intent — written into the journal / elaborator, not free YAML."""

    role: str = "passive"
    boundary_ports: Dict[str, str] = Field(default_factory=dict)
    targets: IntentTarget = Field(default_factory=IntentTarget)
    platform: str = "generic_tech"
    topology_program: Optional[str] = None  # e.g. "mzi_tree(stages=2, ...)"
    assumptions: List[str] = Field(default_factory=list)
    freeform_notes: str = ""


class IntentAgent:
    """A0: produce TypedIntent from natural language (LLM optional)."""

    def __init__(self, llm_agent: Any = None) -> None:
        self.llm = llm_agent

    def capture(self, problem_text: str) -> TypedIntent:
        """Heuristic capture; replace with schema-constrained LLM call later."""
        text = (problem_text or "").lower()
        intent = TypedIntent(freeform_notes=problem_text[:2000])
        if "mzi" in text or "mach-zehnder" in text:
            intent.topology_program = "mzi(arms=2, ps=straight_heater_metal)"
            intent.role = "interferometer"
        elif "ring" in text:
            intent.topology_program = "ring_bus(coupler=coupler)"
            intent.role = "resonator"
        elif "modulator" in text or "mzm" in text:
            intent.topology_program = "mzm(dual_drive=true)"
            intent.role = "modulator"
        else:
            intent.assumptions.append(
                "No topology program matched; free-form schematic required"
            )
        return intent

    def to_dict(self, intent: TypedIntent) -> Dict[str, Any]:
        return intent.model_dump()
