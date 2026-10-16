"""
Exact schematic critic (A1 companion) — no LLM.

Checks: unknown components, optical port-degree, dangling ports,
PortKind/polarization compatibility, param bounds, graph planarity,
and (when placements exist) axis-aligned optical-edge crossings.
Semantic topology judgment stays elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import networkx as nx

from gd_picasso.pcg.legalize import detect_dangling_ports
from gd_picasso.pcg.pdk_ports import COMPONENT_PORT_MAP
from gd_picasso.pcg.store import (
    PCGMutationError,
    PCGStore,
    _PARAM_BOUNDS,
    _validate_param_bounds,
)
from gd_picasso.pcg.types import EdgeLayer


@dataclass
class ExactCritique:
    ok: bool
    problems: List[str] = field(default_factory=list)
    constraint_ids: List[str] = field(default_factory=list)


def _segments_intersect(
    a1: Tuple[float, float],
    a2: Tuple[float, float],
    b1: Tuple[float, float],
    b2: Tuple[float, float],
) -> bool:
    """Proper intersection of two open segments (shared endpoints do not count)."""

    def orient(p, q, r) -> float:
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

    def on_segment(p, q, r) -> bool:
        return (
            min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
            and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
        )

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)

    if o1 == 0 and on_segment(a1, b1, a2):
        return False  # touching endpoint / colinear touch — not a crossing
    if o2 == 0 and on_segment(a1, b2, a2):
        return False
    if o3 == 0 and on_segment(b1, a1, b2):
        return False
    if o4 == 0 and on_segment(b1, a2, b2):
        return False

    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def count_aabb_crossings(store: PCGStore) -> int:
    """Count crossings among optical edges using node (x, y) as endpoints.

    Returns 0 when fewer than two optical edges have both endpoints placed.
    Shared vertices (same node) do not count as crossings.
    """
    optical = [e for e in store.edges if e.layer == EdgeLayer.OPTICAL]
    segs: List[Tuple[Tuple[str, str], Tuple[float, float], Tuple[float, float]]] = []
    for e in optical:
        ns, nd = store.nodes.get(e.src_node), store.nodes.get(e.dst_node)
        if ns is None or nd is None:
            continue
        if ns.x is None or ns.y is None or nd.x is None or nd.y is None:
            continue
        segs.append(
            (
                (e.src_node, e.dst_node),
                (float(ns.x), float(ns.y)),
                (float(nd.x), float(nd.y)),
            )
        )
    n_cross = 0
    for i in range(len(segs)):
        nodes_i, a1, a2 = segs[i]
        for j in range(i + 1, len(segs)):
            nodes_j, b1, b2 = segs[j]
            # Skip edges that share a node (T-junction / fanout endpoint)
            if set(nodes_i) & set(nodes_j):
                continue
            if _segments_intersect(a1, a2, b1, b2):
                n_cross += 1
    return n_cross


class ExactCritic:
    """Deterministic critic over a PCGStore."""

    def review(self, store: PCGStore) -> ExactCritique:
        problems: List[str] = []
        constraint_ids: List[str] = []

        for nid, node in store.nodes.items():
            if node.component not in COMPONENT_PORT_MAP:
                problems.append(f"Unknown component '{node.component}' on node '{nid}'")

            # Param bounds re-check (taxonomy: out_of_bounds_param)
            for key, value in node.params.items():
                if key not in _PARAM_BOUNDS.get(node.component, {}):
                    continue
                try:
                    _validate_param_bounds(node.component, key, value)
                except PCGMutationError as exc:
                    problems.append(f"out_of_bounds_param: {nid}.{key}: {exc.reason}")

        # Optical degree > 1 is already rejected at connect-time; re-check for safety
        degree: Dict[Tuple[str, str], int] = {}
        for e in store.edges:
            if e.layer != EdgeLayer.OPTICAL:
                continue
            for key in ((e.src_node, e.src_port), (e.dst_node, e.dst_port)):
                degree[key] = degree.get(key, 0) + 1
        for (nid, port), d in degree.items():
            if d > 1:
                problems.append(f"Optical port {nid}.{port} has degree {d}")

        # Kind + polarization on existing optical edges
        for e in store.edges:
            if e.layer != EdgeLayer.OPTICAL:
                continue
            src = store.nodes.get(e.src_node)
            dst = store.nodes.get(e.dst_node)
            if src is None or dst is None:
                continue
            sp = src.ports.get(e.src_port) if src.ports else None
            dp = dst.ports.get(e.dst_port) if dst.ports else None
            if sp is None or dp is None:
                continue
            if sp.kind != dp.kind:
                problems.append(
                    f"PortKind mismatch on {e.src_node}.{e.src_port}—"
                    f"{e.dst_node}.{e.dst_port}: {sp.kind.value} vs {dp.kind.value}"
                )
            if (
                sp.polarization
                and dp.polarization
                and sp.polarization != dp.polarization
            ):
                problems.append(
                    f"polarization mismatch on {e.src_node}.{e.src_port}—"
                    f"{e.dst_node}.{e.dst_port}: "
                    f"{sp.polarization} vs {dp.polarization}"
                )

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

        # Undirected optical simple graph — connectivity + planarity
        g = nx.Graph()
        for nid in store.nodes:
            g.add_node(nid)
        for e in store.edges:
            if e.layer != EdgeLayer.OPTICAL:
                continue
            if e.src_node == e.dst_node:
                continue  # self-loop handled separately; skip for planarity
            g.add_edge(e.src_node, e.dst_node)
        # Disconnected / isolated nodes are wrong_connectivity (same for all arms)
        if len(store.nodes) > 1:
            if g.number_of_nodes() == 0 or not nx.is_connected(g):
                n_comp = (
                    nx.number_connected_components(g) if g.number_of_nodes() else 0
                )
                problems.append(
                    f"wrong_connectivity: optical graph is disconnected "
                    f"({n_comp} components, {g.number_of_nodes()} nodes)"
                )
        if g.number_of_edges() > 0:
            is_planar, _ = nx.check_planarity(g)
            if not is_planar:
                problems.append("Optical connectivity graph is non-planar")

        # Placement-aware crossings when coordinates exist
        n_cross = count_aabb_crossings(store)
        if n_cross > 0:
            problems.append(
                f"n_crossings={n_cross} (axis-aligned optical edges with placement)"
            )

        return ExactCritique(ok=not problems, problems=problems, constraint_ids=constraint_ids)
