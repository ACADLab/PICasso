"""
Exact schematic critic (A1 companion) — no LLM.

Port-degree, dangling ports, unknown components, and basic connectivity
checks against the PCG store. Semantic topology judgment stays elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from gd_picasso.pcg.legalize import detect_dangling_ports
from gd_picasso.pcg.pdk_ports import COMPONENT_PORT_MAP
from gd_picasso.pcg.store import PCGStore
from gd_picasso.pcg.types import ConstraintStatus, EdgeLayer


@dataclass
class ExactCritique:
    ok: bool
    problems: List[str] = field(default_factory=list)
    constraint_ids: List[str] = field(default_factory=list)


class ExactCritic:
    """Deterministic critic over a PCGStore."""

    def review(self, store: PCGStore) -> ExactCritique:
        problems: List[str] = []
        constraint_ids: List[str] = []

        for nid, node in store.nodes.items():
            if node.component not in COMPONENT_PORT_MAP:
                problems.append(f"Unknown component '{node.component}' on node '{nid}'")

        # Optical degree > 1 is already rejected at connect-time; re-check for safety
        degree = {}
        for e in store.edges:
            if e.layer != EdgeLayer.OPTICAL:
                continue
            for key in ((e.src_node, e.src_port), (e.dst_node, e.dst_port)):
                degree[key] = degree.get(key, 0) + 1
        for (nid, port), d in degree.items():
            if d > 1:
                problems.append(f"Optical port {nid}.{port} has degree {d}")

        dangling = detect_dangling_ports(store, record=True)
        exported = set()
        for ref in store.exported_ports.values():
            if isinstance(ref, str) and "," in ref:
                a, b = ref.split(",", 1)
                exported.add((a.strip(), b.strip()))
        for entry in dangling:
            constraint_ids.append(entry.id)
            nid, pname = entry.elements[0], entry.elements[1]
            if (nid, pname) not in exported:
                problems.append(f"Dangling optical port {nid}.{pname}")

        return ExactCritique(ok=not problems, problems=problems, constraint_ids=constraint_ids)
