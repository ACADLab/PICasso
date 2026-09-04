"""
Photonic Circuit Graph — Legalization.

Detects dangling ports and emits ConstraintEntry records.
Does NOT insert nodes — insertion changes the circuit boundary and
invalidates the round-trip comparison.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import List

from .store import PCGStore
from .types import (
    ConstraintEntry,
    ConstraintKind,
    ConstraintStatus,
    EdgeLayer,
)


def detect_dangling_ports(store: PCGStore) -> List[ConstraintEntry]:
    """Scan optical ports for degree-0 and return constraint entries.

    Each dangling port produces a ``ConstraintEntry(kind=DANGLING_PORT)``.
    These are added to the store's constraint ledger but no nodes are
    inserted — dangling ports are a legalization *decision*, not a
    losslessness property.
    """
    # Build port-degree map for optical edges
    connected: set[tuple[str, str]] = set()
    for e in store.edges:
        if e.layer == EdgeLayer.OPTICAL:
            connected.add((e.src_node, e.src_port))
            connected.add((e.dst_node, e.dst_port))

    entries: List[ConstraintEntry] = []
    for nid, node in store.nodes.items():
        for pname, port in node.ports.items():
            if (nid, pname) not in connected:
                entry = ConstraintEntry(
                    id=f"dangling_{uuid.uuid4().hex[:8]}",
                    kind=ConstraintKind.DANGLING_PORT,
                    elements=[nid, pname],
                    status=ConstraintStatus.OPEN,
                    evidence={"component": node.component},
                )
                entries.append(entry)
                store.add_constraint(entry)

    return entries


def add_tapers(store: PCGStore) -> None:
    """Stub — all generic_tech ports are 500 nm; tapers not needed for PIC-Set."""
    raise NotImplementedError(
        "all generic_tech ports are 500 nm; tapers not needed for PIC-Set"
    )
