"""
A1 — Schematic agent: propose typed graph mutations; exact critic gates them.

Batch ops follow ``gd_picasso/pcg/A1_MUTATION_CONTRACT.md`` (v1):
``add_node``, ``connect``, ``set_param`` only. Store-direct helpers such as
``set_exported_ports`` stay off the batch vocabulary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from gd_picasso.agents.exact_critic import ExactCritic, ExactCritique
from gd_picasso.pcg.store import PCGMutationError, PCGStore
from gd_picasso.pcg.types import AttachmentKind, EdgeLayer, PCGNode, RefLevel

# Keep in sync with A1_MUTATION_CONTRACT.md
A1_CONTRACT_VERSION = 1
A1_BATCH_OPS = frozenset({"add_node", "connect", "set_param"})


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

    def commit_mutations(
        self,
        store: PCGStore,
        mutations: List[Dict[str, Any]],
    ) -> None:
        """Apply a batch atomically without running ExactCritic.

        Use when the caller must set store-direct state (e.g. exported ports)
        before the first critic pass.
        """
        snap = store.snapshot()
        try:
            for m in mutations:
                op = m.get("op")
                if op not in A1_BATCH_OPS:
                    raise PCGMutationError(
                        "A1",
                        f"Unknown op {op!r} (frozen v{A1_CONTRACT_VERSION} "
                        f"allows {sorted(A1_BATCH_OPS)})",
                    )
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
        except Exception:
            store.restore(snap)
            raise

    def apply_mutations(
        self,
        store: PCGStore,
        mutations: List[Dict[str, Any]],
    ) -> ExactCritique:
        """Apply a batch atomically, then ExactCritic.review."""
        self.commit_mutations(store, mutations)
        return self.critique(store)

    def apply_elaboration(
        self,
        store: PCGStore,
        mutations: List[Dict[str, Any]],
        exported_ports: Optional[Dict[str, str]] = None,
        *,
        export_agent: str = "A0_elaborator",
    ) -> ExactCritique:
        """Commit A1 batch ops, set boundary ports (store-direct), then critique.

        Exports are intentionally outside the v1 batch vocabulary per Formal
        contract; they must be set before ExactCritic so boundary ports are
        not flagged as dangling.
        """
        snap = store.snapshot()
        try:
            self.commit_mutations(store, mutations)
            if exported_ports:
                store.set_exported_ports(exported_ports, agent=export_agent)
        except Exception:
            store.restore(snap)
            raise
        return self.critique(store)
