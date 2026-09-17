"""
A1 — Schematic agent: propose typed graph mutations; exact critic gates them.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from gd_picasso.agents.exact_critic import ExactCritic, ExactCritique
from gd_picasso.pcg.store import PCGMutationError, PCGStore
from gd_picasso.pcg.types import AttachmentKind, EdgeLayer, PCGNode, RefLevel


class SchematicAgent:
    """Generator/critic pair over PCGStore mutations (no free-form file edits)."""

    def __init__(self, critic: Optional[ExactCritic] = None) -> None:
        self.critic = critic or ExactCritic()

    def add_component(
        self,
        store: PCGStore,
        node_id: str,
        component: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        store.add_node(
            PCGNode(
                id=node_id,
                component=component,
                params=dict(params or {}),
                level=RefLevel.L1_CIRCUIT,
            ),
            skip_component_check=True,
            agent="A1",
        )

    def connect(
        self,
        store: PCGStore,
        src: str,
        src_port: str,
        dst: str,
        dst_port: str,
        *,
        bundle: Optional[str] = "optical",
    ) -> None:
        store.connect(
            src, src_port, dst, dst_port,
            layer=EdgeLayer.OPTICAL,
            bundle=bundle,
            attachment=AttachmentKind.ROUTED,
            agent="A1",
        )

    def set_param(self, store: PCGStore, node_id: str, key: str, value: Any) -> None:
        store.set_param(node_id, key, value, agent="A1")

    def critique(self, store: PCGStore) -> ExactCritique:
        return self.critic.review(store)

    def apply_mutations(
        self,
        store: PCGStore,
        mutations: List[Dict[str, Any]],
    ) -> ExactCritique:
        """Apply a batch atomically — roll back the store on any failure."""
        snap = store.snapshot()
        try:
            for m in mutations:
                op = m.get("op")
                if op == "add_node":
                    self.add_component(
                        store, m["id"], m["component"], m.get("params")
                    )
                elif op == "connect":
                    self.connect(
                        store, m["src"], m["src_port"], m["dst"], m["dst_port"],
                        bundle=m.get("bundle", "optical"),
                    )
                elif op == "set_param":
                    self.set_param(store, m["node"], m["key"], m["value"])
                else:
                    raise PCGMutationError("A1", f"Unknown op {op!r}")
        except Exception:
            store.restore(snap)
            raise
        return self.critique(store)
