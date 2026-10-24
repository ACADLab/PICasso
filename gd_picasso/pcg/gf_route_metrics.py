"""Extract routed lengths from a gdsfactory ``get_netlist()`` into RouteMetrics.

Used for layout-N3 SPA without LiDAR: GF routes → edge lengths → SPA WNS.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Tuple

from .backannotate import RouteMetrics, apply_route_metrics
from .store import PCGStore
from .types import EdgeLayer

Pin = Tuple[str, str]  # (instance, port)


def _inst_length_um(inst: Dict[str, Any], *, default_bend_um: float = 15.7) -> float:
    settings = inst.get("settings") or {}
    if isinstance(settings, dict):
        for key in ("length", "length_um", "L"):
            if key in settings and settings[key] is not None:
                try:
                    return float(settings[key])
                except (TypeError, ValueError):
                    pass
    info = inst.get("info") or {}
    if isinstance(info, dict):
        for key in ("length", "route_info_length", "route_info_strip_length"):
            if key in info and info[key] is not None:
                try:
                    return float(info[key])
                except (TypeError, ValueError):
                    pass
    comp = str(inst.get("component", "")).lower()
    if "bend" in comp:
        return float(default_bend_um)
    return 0.0


def _parse_ref(ref: str) -> Pin:
    a, _, b = ref.partition(",")
    return a.strip(), b.strip()


def _iter_netlist_links(netlist: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Yield (src_ref, dst_ref) pairs from ``connections`` or gf9 ``nets``."""
    items: List[Tuple[Any, Any]] = []
    connections = netlist.get("connections") or {}
    if isinstance(connections, dict):
        items = list(connections.items())
    elif isinstance(connections, list):
        for row in connections:
            if isinstance(row, (list, tuple)) and len(row) == 2:
                items.append((row[0], row[1]))

    nets = netlist.get("nets") or ()
    if not items and nets:
        for row in nets:
            if isinstance(row, dict) and "p1" in row and "p2" in row:
                items.append((row["p1"], row["p2"]))
            elif isinstance(row, (list, tuple)) and len(row) == 2:
                items.append((row[0], row[1]))
    out: List[Tuple[str, str]] = []
    for a, b in items:
        if isinstance(a, str) and isinstance(b, str):
            out.append((a, b))
    return out


def route_metrics_from_gf_netlist(
    netlist: Dict[str, Any],
    *,
    default_bend_um: float = 15.7,
) -> Dict[Tuple[str, str, str, str], RouteMetrics]:
    """Per-link metrics from a routed GF netlist (flat expanded graph).

    Keys are individual netlist hops (may be auto-generated bend/straight
    names). Prefer ``route_metrics_for_store`` to map onto PCG topology edges.
    """
    instances = netlist.get("instances") or {}
    metrics: Dict[Tuple[str, str, str, str], RouteMetrics] = {}
    for src_ref, dst_ref in _iter_netlist_links(netlist):
        s_inst, s_port = _parse_ref(src_ref)
        d_inst, d_port = _parse_ref(dst_ref)
        L = 0.0
        for nid in (s_inst, d_inst):
            L += _inst_length_um(
                instances.get(nid) or {}, default_bend_um=default_bend_um
            )
        if L <= 0:
            L = 1.0
        metrics[(s_inst, s_port, d_inst, d_port)] = RouteMetrics(length_um=L)
    return metrics


def _build_pin_graph(
    netlist: Dict[str, Any],
) -> Dict[Pin, List[Pin]]:
    """Undirected adjacency over pins: net hops + intra-instance port bridges."""
    instances = netlist.get("instances") or {}
    adj: Dict[Pin, List[Pin]] = defaultdict(list)

    def link(a: Pin, b: Pin) -> None:
        adj[a].append(b)
        adj[b].append(a)

    for src_ref, dst_ref in _iter_netlist_links(netlist):
        link(_parse_ref(src_ref), _parse_ref(dst_ref))

    # Bridge all ports of the same instance so BFS can traverse through cells
    ports_by_inst: Dict[str, List[str]] = defaultdict(list)
    for pin in list(adj.keys()):
        ports_by_inst[pin[0]].append(pin[1])
    for inst, ports in ports_by_inst.items():
        uniq = sorted(set(ports))
        for i, p0 in enumerate(uniq):
            for p1 in uniq[i + 1 :]:
                link((inst, p0), (inst, p1))
    # Ensure named instances with no nets still appear (noop)
    for inst in instances:
        _ = ports_by_inst[inst]
    return adj


def _path_length_um(
    adj: Dict[Pin, List[Pin]],
    instances: Dict[str, Any],
    start: Pin,
    goal: Pin,
    *,
    default_bend_um: float = 15.7,
) -> Optional[float]:
    """BFS pin path; sum instance lengths when entering→leaving same cell."""
    if start == goal:
        return 0.0
    if start not in adj or goal not in adj:
        return None
    prev: Dict[Pin, Optional[Pin]] = {start: None}
    q: deque[Pin] = deque([start])
    found = False
    while q:
        cur = q.popleft()
        if cur == goal:
            found = True
            break
        for nxt in adj.get(cur, ()):
            if nxt not in prev:
                prev[nxt] = cur
                q.append(nxt)
    if not found:
        return None
    # Reconstruct pin path
    path: List[Pin] = []
    cur2: Optional[Pin] = goal
    while cur2 is not None:
        path.append(cur2)
        cur2 = prev[cur2]
    path.reverse()
    # Charge instance length once per traversed cell (excluding endpoints'
    # functional cells is wrong for arms that ARE straights — charge all
    # intermediate cells; also charge endpoint if it is a waveguide).
    L = 0.0
    charged: set[str] = set()
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        if a[0] == b[0] and a[0] not in charged:
            # Traversing through instance a[0]
            charged.add(a[0])
            Li = _inst_length_um(
                instances.get(a[0]) or {}, default_bend_um=default_bend_um
            )
            L += Li if Li > 0 else 0.0
    return L if L > 0 else 1.0


def route_metrics_for_store(
    store: PCGStore,
    netlist: Dict[str, Any],
    *,
    default_bend_um: float = 15.7,
) -> Dict[Tuple[str, str, str, str], RouteMetrics]:
    """Map expanded GF netlist routes onto PCG optical topology edges."""
    instances = netlist.get("instances") or {}
    adj = _build_pin_graph(netlist)
    metrics: Dict[Tuple[str, str, str, str], RouteMetrics] = {}
    for e in store.edges:
        if e.layer != EdgeLayer.OPTICAL:
            continue
        start = (e.src_node, e.src_port)
        goal = (e.dst_node, e.dst_port)
        L = _path_length_um(
            adj, instances, start, goal, default_bend_um=default_bend_um
        )
        if L is None:
            # Try swapped orientation
            L = _path_length_um(
                adj, instances, goal, start, default_bend_um=default_bend_um
            )
        if L is None:
            continue
        metrics[(e.src_node, e.src_port, e.dst_node, e.dst_port)] = RouteMetrics(
            length_um=float(L)
        )
    return metrics


def backannotate_from_component(
    store: PCGStore,
    component: Any,
    *,
    agent: str = "gf_netlist",
) -> int:
    """``component.get_netlist()`` → ``apply_route_metrics`` on ``store``."""
    nl = component.get_netlist()
    metrics = route_metrics_for_store(store, nl)
    if not metrics:
        # Flat hop metrics (rarely match store keys) then param fallback
        metrics = route_metrics_from_gf_netlist(nl)
        n = apply_route_metrics(store, metrics, agent=agent)
        if n > 0:
            return n
        metrics = {}
        for e in store.edges:
            if e.layer != EdgeLayer.OPTICAL:
                continue
            src = store.nodes[e.src_node]
            L = float((src.params or {}).get("length") or 0.0)
            if L <= 0:
                dst = store.nodes[e.dst_node]
                L = float((dst.params or {}).get("length") or 50.0)
            metrics[(e.src_node, e.src_port, e.dst_node, e.dst_port)] = RouteMetrics(
                length_um=L
            )
    return apply_route_metrics(store, metrics, agent=agent)


def backannotate_from_yaml(
    store: PCGStore,
    yaml_str: str,
    *,
    agent: str = "gf_netlist",
) -> int:
    """Build GF component from YAML, route via read, back-annotate store."""
    import gdsfactory as gf

    c = gf.read.from_yaml(yaml_str)
    return backannotate_from_component(store, c, agent=agent)
