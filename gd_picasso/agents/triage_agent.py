"""
A4 — Verification / triage agent.

Converts DRC/LVS/SAX failures into constraint-ledger entries attached to
specific graph elements, plus a routing decision for which agent to re-invoke.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from gd_picasso.pcg.store import PCGStore
from gd_picasso.pcg.types import (
    ConstraintEntry,
    ConstraintKind,
    ConstraintStatus,
)


class TriageDecision(BaseModel):
    reinvoke: str  # A0 | A1 | A2 | A3 | none
    added_constraints: List[str] = Field(default_factory=list)
    summary: str = ""


class TriageAgent:
    """A4: map machine failures → ledger entries + next-agent routing."""

    KIND_MAP = {
        "spacing": ConstraintKind.SPACING,
        "drc": ConstraintKind.SPACING,
        "dangling": ConstraintKind.DANGLING_PORT,
        "port": ConstraintKind.PORT_DEGREE,
        "phase": ConstraintKind.MATCHED_LENGTH,
        "thermal": ConstraintKind.THERMAL_KEEPAWAY,
    }

    def triage(
        self,
        store: PCGStore,
        failures: List[Dict[str, Any]],
    ) -> TriageDecision:
        added: List[str] = []
        needs_schematic = False
        needs_pnr = False
        needs_opt = False

        for f in failures:
            kind_key = str(f.get("kind", "custom")).lower()
            kind = self.KIND_MAP.get(kind_key, ConstraintKind.CUSTOM)
            cid = f.get("id") or f"c_{uuid.uuid4().hex[:8]}"
            elements = list(f.get("elements") or [])
            entry = ConstraintEntry(
                id=cid,
                kind=kind,
                elements=elements,
                status=ConstraintStatus.OPEN,
                evidence=dict(f.get("evidence") or {"raw": f}),
            )
            store.add_constraint(entry, agent="A4")
            added.append(cid)

            if kind in (ConstraintKind.DANGLING_PORT, ConstraintKind.PORT_DEGREE):
                needs_schematic = True
            elif kind in (ConstraintKind.SPACING, ConstraintKind.THERMAL_KEEPAWAY):
                needs_pnr = True
            elif kind == ConstraintKind.MATCHED_LENGTH:
                needs_opt = True
                needs_pnr = True

        if needs_schematic:
            reinvoke = "A1"
        elif needs_pnr:
            reinvoke = "A2"
        elif needs_opt:
            reinvoke = "A3"
        else:
            reinvoke = "none"

        decision = TriageDecision(
            reinvoke=reinvoke,
            added_constraints=added,
            summary=f"{len(added)} constraint(s); next={reinvoke}",
        )
        store.journal.append(
            "A4_triage",
            decision.model_dump(),
            agent="A4",
        )
        return decision
