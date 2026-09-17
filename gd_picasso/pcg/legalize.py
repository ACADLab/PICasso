"""
Photonic Circuit Graph — Legalization.

- ``detect_dangling_ports``: ledger-only (safe for round-trip gate).
- ``insert_terminators``: insert terminator nodes on non-exported dangling
  optical ports (changes topology — use after the lossless gate).
"""

from __future__ import annotations

import uuid
from typing import List, Optional, Set, Tuple

from .store import PCGStore
from .types import (
    AttachmentKind,
    ConstraintEntry,
    ConstraintKind,
    ConstraintStatus,
    EdgeLayer,
    PCGNode,
    PCGPort,
    PortKind,
    RefLevel,
)


def _exported_port_set(store: PCGStore) -> Set[Tuple[str, str]]:
    out: Set[Tuple[str, str]] = set()
    for ref in store.exported_ports.values():
        if not isinstance(ref, str) or "," not in ref:
            continue
        inst, port = ref.split(",", 1)
        out.add((inst.strip(), port.strip()))
    return out


def _connected_optical(store: PCGStore) -> Set[Tuple[str, str]]:
    connected: Set[Tuple[str, str]] = set()
    for e in store.edges:
        if e.layer == EdgeLayer.OPTICAL:
            connected.add((e.src_node, e.src_port))
            connected.add((e.dst_node, e.dst_port))
    return connected


def detect_dangling_ports(
    store: PCGStore,
    *,
    record: bool = True,
) -> List[ConstraintEntry]:
    """Scan optical ports for degree-0 and return constraint entries.

    Each dangling port produces a ``ConstraintEntry(kind=DANGLING_PORT)``.
    When ``record`` is True, new entries are added to the ledger (idempotent
    on ``(node, port)``). No nodes are inserted — that is ``insert_terminators``.
    """
    connected = _connected_optical(store)
    already = {
        (c.elements[0], c.elements[1])
        for c in store.constraints
        if c.kind == ConstraintKind.DANGLING_PORT and len(c.elements) >= 2
    }
    entries: List[ConstraintEntry] = []
    for nid, node in store.nodes.items():
        for pname in node.ports:
            if (nid, pname) not in connected:
                if (nid, pname) in already:
                    continue
                entry = ConstraintEntry(
                    id=f"dangling_{uuid.uuid4().hex[:8]}",
                    kind=ConstraintKind.DANGLING_PORT,
                    elements=[nid, pname],
                    status=ConstraintStatus.OPEN,
                    evidence={"component": node.component},
                )
                entries.append(entry)
                if record:
                    store.add_constraint(entry, agent="legalize")
                    already.add((nid, pname))

    return entries


def insert_terminators(
    store: PCGStore,
    *,
    skip_exported: bool = True,
    agent: Optional[str] = "legalize",
) -> List[str]:
    """Insert ``terminator`` nodes on dangling optical ports.

    Skips ports listed in ``store.exported_ports`` when ``skip_exported``.
    Returns ids of inserted terminator instances.
    """
    connected = _connected_optical(store)
    exported = _exported_port_set(store) if skip_exported else set()
    inserted: List[str] = []

    # Snapshot dangling list first — mutations change the store.
    dangling: List[Tuple[str, str, PCGNode]] = []
    for nid, node in store.nodes.items():
        for pname in node.ports:
            if (nid, pname) in connected:
                continue
            if (nid, pname) in exported:
                continue
            dangling.append((nid, pname, node))

    for nid, pname, node in dangling:
        tid = f"term_{nid}_{pname}_{uuid.uuid4().hex[:6]}"
        term = PCGNode(
            id=tid,
            component="terminator",
            level=RefLevel.L1_CIRCUIT,
            ports={"o1": PCGPort(name="o1", kind=PortKind.OPTICAL)},
        )
        store.add_node(term, skip_component_check=True, agent=agent)
        store.connect(
            nid, pname, tid, "o1",
            layer=EdgeLayer.OPTICAL,
            attachment=AttachmentKind.BUTT_JOINT,
            agent=agent,
        )
        inserted.append(tid)
        # Resolve matching open DANGLING_PORT constraints
        for c in store.constraints:
            if (
                c.kind == ConstraintKind.DANGLING_PORT
                and c.status == ConstraintStatus.OPEN
                and c.elements[:2] == [nid, pname]
            ):
                c.status = ConstraintStatus.RESOLVED
                c.evidence["terminator"] = tid

    return inserted


def add_tapers(store: PCGStore) -> None:
    """Stub — all generic_tech ports are 500 nm; tapers not needed for PIC-Set."""
    raise NotImplementedError(
        "all generic_tech ports are 500 nm; tapers not needed for PIC-Set"
    )
