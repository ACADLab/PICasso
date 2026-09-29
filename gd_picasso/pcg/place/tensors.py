"""
PCG L1/L2 → placement tensors: (x, y, θ), port orientation vectors,
2-pin nets, and phase-critical groups.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..store import PCGStore
from ..types import EdgeLayer, PCGEdge, PCGNode

# ---------------------------------------------------------------------------
# Approximate local port geometry (µm, degrees) at rotation=0, mirror=False.
# Orientations are outward-facing. Offsets are intentionally coarse —
# ESTIMATOR_ONLY spike, not PDK-accurate.
# ---------------------------------------------------------------------------

_DEFAULT_HALF_L = 50.0  # fallback half-length when params lack length


def _port_table(component: str, params: Dict) -> Dict[str, Tuple[float, float, float]]:
    """Return {port: (dx, dy, orient_deg)} in the cell local frame."""
    length = float(params.get("length", 2.0 * _DEFAULT_HALF_L))
    half = 0.5 * length

    if component in ("straight", "straight_heater_metal", "straight_heater_metal_undercut", "taper"):
        return {
            "o1": (-half, 0.0, 180.0),
            "o2": (half, 0.0, 0.0),
        }
    if component == "mmi1x2":
        # Input west; outputs east (split vertically).
        return {
            "o1": (-20.0, 0.0, 180.0),
            "o2": (20.0, 8.0, 0.0),
            "o3": (20.0, -8.0, 0.0),
        }
    if component == "mmi2x2":
        return {
            "o1": (-20.0, 8.0, 180.0),
            "o2": (-20.0, -8.0, 180.0),
            "o3": (20.0, 8.0, 0.0),
            "o4": (20.0, -8.0, 0.0),
        }
    if component == "coupler":
        return {
            "o1": (-15.0, 5.0, 180.0),
            "o2": (-15.0, -5.0, 180.0),
            "o3": (15.0, 5.0, 0.0),
            "o4": (15.0, -5.0, 0.0),
        }
    if component == "bend_euler":
        r = float(params.get("radius", 10.0))
        return {"o1": (0.0, 0.0, 180.0), "o2": (r, r, 90.0)}
    # Generic 2-port fallback
    return {"o1": (-half, 0.0, 180.0), "o2": (half, 0.0, 0.0)}


def _cell_half_extents(component: str, params: Dict) -> Tuple[float, float]:
    """Axis-aligned half-width / half-height for density proxy."""
    length = float(params.get("length", 2.0 * _DEFAULT_HALF_L))
    if component.startswith("mmi"):
        return (25.0, 15.0)
    if component == "coupler":
        return (20.0, 12.0)
    if "heater" in component or component == "straight":
        return (0.5 * length, 5.0)
    return (0.5 * max(length, 20.0), 8.0)


@dataclass
class PortRef:
    """One optical port on a placed instance."""

    node_idx: int
    node_id: str
    port: str
    local_xy: np.ndarray  # (2,)
    local_orient_rad: float


@dataclass
class Net2Pin:
    """Optical 2-pin net (PCG edge)."""

    edge_idx: int
    src: PortRef
    dst: PortRef
    constraint_group: Optional[str] = None


@dataclass
class PhaseGroup:
    """Reconvergent arm group for Δφ̂."""

    group_id: str
    # Each arm is a list of net indices into PlacementProblem.nets
    arm_net_indices: List[List[int]] = field(default_factory=list)
    # Optional node sequences (for SPA / fidelity reporting)
    arm_paths: List[List[str]] = field(default_factory=list)


@dataclass
class PlacementProblem:
    """Tensorized placement view of a PCGStore."""

    node_ids: List[str]
    xy: np.ndarray  # (N, 2) float64
    theta_rad: np.ndarray  # (N,) cell rotation
    mirror: np.ndarray  # (N,) bool
    half_extents: np.ndarray  # (N, 2)
    nets: List[Net2Pin]
    phase_groups: List[PhaseGroup]
    # Fixed mask: True → do not optimize (e.g. no seed geometry → still free)
    movable: np.ndarray  # (N,) bool

    @property
    def n_nodes(self) -> int:
        return len(self.node_ids)

    def node_index(self) -> Dict[str, int]:
        return {nid: i for i, nid in enumerate(self.node_ids)}


def _world_port(
    xy: np.ndarray,
    theta: float,
    mirror: bool,
    local_xy: np.ndarray,
    local_orient: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Map local port offset/orient → world position + unit orientation vector."""
    lx, ly = float(local_xy[0]), float(local_xy[1])
    if mirror:
        ly = -ly
        # Mirror across x-axis: orientation reflects
        local_orient = -local_orient
    c, s = math.cos(theta), math.sin(theta)
    wx = xy[0] + c * lx - s * ly
    wy = xy[1] + s * lx + c * ly
    o = local_orient + theta
    u = np.array([math.cos(o), math.sin(o)], dtype=np.float64)
    return np.array([wx, wy], dtype=np.float64), u


def port_world(
    problem: PlacementProblem,
    pref: PortRef,
    xy: Optional[np.ndarray] = None,
    theta: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """World (position, unit orientation) for a port under current/override state."""
    xy_arr = problem.xy if xy is None else xy
    th_arr = problem.theta_rad if theta is None else theta
    i = pref.node_idx
    return _world_port(
        xy_arr[i],
        float(th_arr[i]),
        bool(problem.mirror[i]),
        pref.local_xy,
        pref.local_orient_rad,
    )


def estimated_net_length(
    problem: PlacementProblem,
    net: Net2Pin,
    xy: Optional[np.ndarray] = None,
    theta: Optional[np.ndarray] = None,
) -> float:
    """Manhattan port-to-port length (pre-route estimator)."""
    p_s, _ = port_world(problem, net.src, xy=xy, theta=theta)
    p_d, _ = port_world(problem, net.dst, xy=xy, theta=theta)
    return float(abs(p_s[0] - p_d[0]) + abs(p_s[1] - p_d[1]))


def arm_length_estimate(
    problem: PlacementProblem,
    net_indices: Sequence[int],
    xy: Optional[np.ndarray] = None,
    theta: Optional[np.ndarray] = None,
) -> float:
    return sum(
        estimated_net_length(problem, problem.nets[i], xy=xy, theta=theta)
        for i in net_indices
    )


def _make_port_ref(
    node: PCGNode, node_idx: int, port_name: str
) -> PortRef:
    table = _port_table(node.component, node.params or {})
    if port_name in table:
        dx, dy, odeg = table[port_name]
    else:
        dx, dy, odeg = (0.0, 0.0, 0.0)
    return PortRef(
        node_idx=node_idx,
        node_id=node.id,
        port=port_name,
        local_xy=np.array([dx, dy], dtype=np.float64),
        local_orient_rad=math.radians(odeg),
    )


def _seed_xy_theta(node: PCGNode, fallback_idx: int) -> Tuple[np.ndarray, float, bool]:
    """Initial (x,y), θ_rad, mirror from L2 placement or a coarse L1 seed."""
    if node.x is not None and node.y is not None:
        xy = np.array([float(node.x), float(node.y)], dtype=np.float64)
    else:
        # Spread along x so L1 graphs are not degenerate
        xy = np.array([float(fallback_idx) * 80.0, 0.0], dtype=np.float64)
    rot = int(node.rotation or 0)
    theta = math.radians(float(rot))
    return xy, theta, bool(node.mirror)


def _infer_two_arm_groups(
    store: PCGStore,
    nets: List[Net2Pin],
    id_to_idx: Dict[str, int],
) -> List[PhaseGroup]:
    """Infer reconvergent 2-arm groups (MZI/MZM-style) from optical topology.

    Prefer edges tagged with ``constraint_group``; else find a splitter with
    two outgoing optical edges that reconverge at a common combiner.
    """
    # Tagged groups first
    by_group: Dict[str, List[int]] = {}
    for i, net in enumerate(nets):
        if net.constraint_group:
            by_group.setdefault(net.constraint_group, []).append(i)
    if by_group:
        groups: List[PhaseGroup] = []
        for gid, idxs in sorted(by_group.items()):
            # Split evenly into two arms if even count; else one bag (Δφ=0)
            if len(idxs) >= 2 and len(idxs) % 2 == 0:
                mid = len(idxs) // 2
                groups.append(
                    PhaseGroup(
                        group_id=gid,
                        arm_net_indices=[idxs[:mid], idxs[mid:]],
                    )
                )
            else:
                groups.append(PhaseGroup(group_id=gid, arm_net_indices=[idxs, idxs]))
        return groups

    # Topology: undirected adjacency via optical nets
    adj: Dict[str, List[Tuple[str, int]]] = {n: [] for n in id_to_idx}
    for i, net in enumerate(nets):
        a, b = net.src.node_id, net.dst.node_id
        adj[a].append((b, i))
        adj[b].append((a, i))

    groups: List[PhaseGroup] = []
    seen_pairs: set = set()
    for src, nbrs in adj.items():
        if len(nbrs) < 2:
            continue
        # Try every pair of neighbors as arm midpoints that share a far node
        for i in range(len(nbrs)):
            for j in range(i + 1, len(nbrs)):
                mid_a, e_sa = nbrs[i]
                mid_b, e_sb = nbrs[j]
                # Far neighbors of midpoints excluding src
                far_a = [(n, e) for n, e in adj[mid_a] if n != src]
                far_b = [(n, e) for n, e in adj[mid_b] if n != src]
                for comb_a, e_ac in far_a:
                    for comb_b, e_bc in far_b:
                        if comb_a != comb_b:
                            continue
                        key = tuple(sorted((src, mid_a, mid_b, comb_a)))
                        if key in seen_pairs:
                            continue
                        seen_pairs.add(key)
                        groups.append(
                            PhaseGroup(
                                group_id=f"arms:{src}->{comb_a}",
                                arm_net_indices=[[e_sa, e_ac], [e_sb, e_bc]],
                                arm_paths=[
                                    [src, mid_a, comb_a],
                                    [src, mid_b, comb_b],
                                ],
                            )
                        )
    return groups


def build_placement_problem(store: PCGStore) -> PlacementProblem:
    """Build placement tensors from a PCG store (L1 or L2)."""
    nodes = list(store.nodes.values())
    node_ids = [n.id for n in nodes]
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}

    xy = np.zeros((len(nodes), 2), dtype=np.float64)
    theta = np.zeros(len(nodes), dtype=np.float64)
    mirror = np.zeros(len(nodes), dtype=bool)
    half = np.zeros((len(nodes), 2), dtype=np.float64)
    movable = np.ones(len(nodes), dtype=bool)

    for i, n in enumerate(nodes):
        xy[i], theta[i], mirror[i] = _seed_xy_theta(n, i)
        half[i] = _cell_half_extents(n.component, n.params or {})

    optical_edges: List[PCGEdge] = [
        e for e in store.edges if e.layer == EdgeLayer.OPTICAL
    ]
    nets: List[Net2Pin] = []
    for ei, e in enumerate(optical_edges):
        if e.src_node not in id_to_idx or e.dst_node not in id_to_idx:
            continue
        src_node = store.nodes[e.src_node]
        dst_node = store.nodes[e.dst_node]
        nets.append(
            Net2Pin(
                edge_idx=ei,
                src=_make_port_ref(src_node, id_to_idx[e.src_node], e.src_port),
                dst=_make_port_ref(dst_node, id_to_idx[e.dst_node], e.dst_port),
                constraint_group=e.constraint_group,
            )
        )

    phase_groups = _infer_two_arm_groups(store, nets, id_to_idx)
    return PlacementProblem(
        node_ids=node_ids,
        xy=xy,
        theta_rad=theta,
        mirror=mirror,
        half_extents=half,
        nets=nets,
        phase_groups=phase_groups,
        movable=movable,
    )
