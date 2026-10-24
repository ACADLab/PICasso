"""
Photonic Circuit Graph — Legalization.

- ``detect_dangling_ports``: ledger-only (safe for round-trip gate).
- ``insert_terminators``: insert terminator nodes on non-exported dangling
  optical ports (changes topology — use after the lossless gate).
- ``add_tapers``: insert a linear taper on optical edges whose port widths differ.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Set, Tuple

from .store import PCGStore
from .types import (
    AttachmentKind,
    ConstraintEntry,
    ConstraintKind,
    ConstraintStatus,
    EdgeLayer,
    PCGEdge,
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

    Always returns an entry for every currently dangling port so repeated
    critic scans cannot miss unresolved dangles. When ``record`` is True,
    only *new* ``(node, port)`` keys are appended to the ledger (no dupes).
    """
    connected = _connected_optical(store)
    existing: Dict[Tuple[str, str], ConstraintEntry] = {}
    for c in store.constraints:
        if c.kind == ConstraintKind.DANGLING_PORT and len(c.elements) >= 2:
            existing[(c.elements[0], c.elements[1])] = c

    entries: List[ConstraintEntry] = []
    for nid, node in store.nodes.items():
        for pname in node.ports:
            if (nid, pname) in connected:
                continue
            key = (nid, pname)
            if key in existing:
                entries.append(existing[key])
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
                existing[key] = entry

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


# gdsfactory.components.taper default length (linear taper, µm).
_TAPER_LENGTH_UM = 10.0
# Ignore binary float noise. 500 nm vs 450 nm is 0.05 µm and is not noise.
_WIDTH_MATCH_TOL_UM = 1e-6


def _port_width_um(node: PCGNode, port_name: str) -> Optional[float]:
    port = node.ports.get(port_name)
    if port is None:
        return None
    return float(port.width_um)


def _optical_neighbors(store: PCGStore, nid: str) -> List[str]:
    out: List[str] = []
    for e in store.edges:
        if e.layer != EdgeLayer.OPTICAL:
            continue
        if e.src_node == nid:
            out.append(e.dst_node)
        elif e.dst_node == nid:
            out.append(e.src_node)
    return out


def legalize_taper_placements(
    store: PCGStore,
    *,
    agent: str = "legalize",
    force: bool = True,
) -> List[str]:
    """Place taper instances between their two optically connected neighbors.

    ``add_tapers`` inserts topology-only nodes with no (x, y). Torch place may
    leave them off the CS↔SiEPIC corridor. This pass snaps each taper to the
    midpoint of its two neighbors so LiDAR can instantiate a real
    ``ComponentReference`` with reachable ports before ``route_bundle``.
    """
    updated: List[str] = []
    for nid, node in list(store.nodes.items()):
        if node.component != "taper":
            continue
        nbrs = _optical_neighbors(store, nid)
        placed = [
            store.nodes[n]
            for n in nbrs
            if n in store.nodes
            and store.nodes[n].x is not None
            and store.nodes[n].y is not None
        ]
        if len(placed) < 2:
            if placed:
                x = float(placed[0].x) + 0.5 * _TAPER_LENGTH_UM
                y = float(placed[0].y)
            elif node.x is not None and node.y is not None and not force:
                continue
            else:
                x, y = 0.0, 0.0
        else:
            x = 0.5 * (float(placed[0].x) + float(placed[1].x))
            y = 0.5 * (float(placed[0].y) + float(placed[1].y))
        if (
            not force
            and node.x is not None
            and node.y is not None
            and abs(float(node.x) - x) < 1e-6
            and abs(float(node.y) - y) < 1e-6
        ):
            continue
        store.set_placement(
            nid, x=x, y=y, rotation=int(node.rotation or 0), agent=agent
        )
        updated.append(nid)
    return updated


def add_tapers(store: PCGStore, *, agent: str = "legalize") -> List[str]:
    """Insert a linear ``taper`` on every optical edge whose port widths differ.

    A cornerstone / generic_tech strip port is 0.5 µm. A SiEPIC cell such as
    ``ebeam_y_adiabatic`` or ``ebeam_DC_te895`` (ubcpdk 3.3.2) is 0.45 µm.
    The edge is replaced by ``src → taper.o1`` and ``taper.o2 → dst``, with
    ``width1`` / ``width2`` set to the two port widths. Each insertion is
    recorded in the store mutation journal (``disconnect``, ``add_node``,
    ``connect``, and ``insert_taper``).

    Newly inserted tapers inherit a midpoint placement when both endpoints
    already have (x, y), so the placer / LiDAR hand-off never sees an
    unplaced taper reference.
    """
    mismatched: List[Tuple[PCGEdge, float, float]] = []
    for edge in store.edges:
        if edge.layer != EdgeLayer.OPTICAL:
            continue
        src = store.nodes.get(edge.src_node)
        dst = store.nodes.get(edge.dst_node)
        if src is None or dst is None:
            continue
        w_src = _port_width_um(src, edge.src_port)
        w_dst = _port_width_um(dst, edge.dst_port)
        if w_src is None or w_dst is None:
            continue
        if abs(w_src - w_dst) <= _WIDTH_MATCH_TOL_UM:
            continue
        mismatched.append((edge, w_src, w_dst))

    inserted: List[str] = []
    for edge, w_src, w_dst in mismatched:
        src = store.nodes[edge.src_node]
        dst = store.nodes[edge.dst_node]
        sp = src.ports[edge.src_port]
        dp = dst.ports[edge.dst_port]
        tid = f"taper_{edge.src_node}_{edge.src_port}_{edge.dst_node}_{edge.dst_port}"
        if tid in store.nodes:
            tid = f"{tid}_{uuid.uuid4().hex[:6]}"
        store.disconnect(
            edge.src_node,
            edge.src_port,
            edge.dst_node,
            edge.dst_port,
            agent=agent,
        )
        seed_x: Optional[float] = None
        seed_y: Optional[float] = None
        if (
            src.x is not None
            and src.y is not None
            and dst.x is not None
            and dst.y is not None
        ):
            seed_x = 0.5 * (float(src.x) + float(dst.x))
            seed_y = 0.5 * (float(src.y) + float(dst.y))
        taper = PCGNode(
            id=tid,
            component="taper",
            level=RefLevel.L2_PLACED if seed_x is not None else RefLevel.L1_CIRCUIT,
            params={
                "length": _TAPER_LENGTH_UM,
                "width1": w_src,
                "width2": w_dst,
            },
            ports={
                "o1": PCGPort(
                    name="o1",
                    kind=PortKind.OPTICAL,
                    width_um=w_src,
                    layer=sp.layer,
                    polarization=sp.polarization,
                ),
                "o2": PCGPort(
                    name="o2",
                    kind=PortKind.OPTICAL,
                    width_um=w_dst,
                    layer=dp.layer,
                    polarization=dp.polarization,
                ),
            },
            x=seed_x,
            y=seed_y,
            rotation=0,
            mirror=False,
        )
        if seed_x is not None:
            taper._placement_dirty = True
        store.add_node(taper, agent=agent)
        if seed_x is not None and seed_y is not None:
            store.set_placement(
                tid, x=seed_x, y=seed_y, rotation=0, mirror=False, agent=agent
            )
        up = store.connect(
            edge.src_node,
            edge.src_port,
            tid,
            "o1",
            layer=edge.layer,
            bundle=edge.bundle,
            attachment=edge.attachment,
            agent=agent,
        )
        down = store.connect(
            tid,
            "o2",
            edge.dst_node,
            edge.dst_port,
            layer=edge.layer,
            bundle=edge.bundle,
            attachment=edge.attachment,
            agent=agent,
        )
        up.constraint_group = edge.constraint_group
        down.constraint_group = edge.constraint_group
        down.phase_rad = edge.phase_rad
        down.loss_dB = edge.loss_dB
        down.length_um = edge.length_um
        down.n_crossings = edge.n_crossings
        store.journal.append(
            "insert_taper",
            {
                "id": tid,
                "src": f"{edge.src_node},{edge.src_port}",
                "dst": f"{edge.dst_node},{edge.dst_port}",
                "width1_um": w_src,
                "width2_um": w_dst,
                "length_um": _TAPER_LENGTH_UM,
                "x": seed_x,
                "y": seed_y,
            },
            agent=agent,
        )
        inserted.append(tid)
    return inserted
