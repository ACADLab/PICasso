"""
Photonic Circuit Graph — Store.

NetworkX-backed mutable graph with checked mutations, append-only journal,
dual hashing, bundle-settings registry, constraint ledger, and exported-port map.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import math
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

from .journal import MutationJournal
from .pdk_ports import COMPONENT_PORT_MAP
from .types import (
    AttachmentKind,
    BundleSettings,
    ConstraintEntry,
    ConstraintKind,
    ConstraintStatus,
    EdgeLayer,
    PCGEdge,
    PCGNode,
    PCGPort,
    PortKind,
)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class PCGMutationError(Exception):
    """Raised when a graph mutation violates an invariant."""

    def __init__(self, op: str, reason: str) -> None:
        self.op = op
        self.reason = reason
        super().__init__(f"[{op}] {reason}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _round_float(v: Any) -> Any:
    """Round floats to 6 decimal places for canonical hashing."""
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return v
        return round(v, 6)
    if isinstance(v, dict):
        return {k: _round_float(val) for k, val in sorted(v.items())}
    if isinstance(v, (list, tuple)):
        return [_round_float(i) for i in v]
    return v


def _canonical_json(obj: Any) -> str:
    return json.dumps(_round_float(obj), sort_keys=True, separators=(",", ":"))


# Minimal param allow-lists when gdsfactory is not importable (unit tests / CI smoke).
_STATIC_PARAMS = {
    "straight": {"length", "npoints", "cross_section", "width", "layer"},
    "bend_euler": {"radius", "angle", "p", "with_arc_floorplan", "npoints", "cross_section"},
    "mmi1x2": {"width", "width_taper", "length_taper", "length_mmi", "width_mmi", "gap_mmi", "cross_section"},
    "mmi2x2": {"width", "width_taper", "length_taper", "length_mmi", "width_mmi", "gap_mmi", "cross_section"},
    "coupler": {"gap", "length", "dx", "dy", "cross_section"},
    "straight_heater_metal": {"length", "length_straight_input", "heater_width", "layer_heater"},
    "ring_single": {"gap", "radius", "length_x", "length_y", "cross_section"},
    "terminator": set(),
}


def _validate_param(component: str, key: str) -> None:
    try:
        import gdsfactory as gf
        comp_func = getattr(gf.components, component, None)
        if comp_func is not None:
            sig = inspect.signature(comp_func)
            valid_params = set(sig.parameters.keys())
            if key not in valid_params and "kwargs" not in str(sig):
                raise PCGMutationError(
                    "set_param",
                    f"Parameter '{key}' not in signature of '{component}'",
                )
            return
    except ImportError:
        pass
    allowed = _STATIC_PARAMS.get(component)
    if allowed is not None:
        if key not in allowed:
            raise PCGMutationError(
                "set_param",
                f"Parameter '{key}' not in signature of '{component}'",
            )
        return
    # Unknown component / no signature source — do not silently accept keys.
    raise PCGMutationError(
        "set_param",
        f"Cannot validate parameter '{key}' for unknown component '{component}'",
    )


def _validate_component(component: str) -> None:
    """Check component exists in gdsfactory — same as yaml_pilot_validator."""
    try:
        import gdsfactory as gf
        if not hasattr(gf.components, component):
            raise PCGMutationError(
                "add_node",
                f"Component '{component}' not found in gf.components",
            )
    except ImportError:
        pass  # allow store to work without gdsfactory for unit tests


def default_ports_for(component: str) -> Dict[str, PCGPort]:
    """Build optical PCGPort map from the static PDK port table."""
    names = COMPONENT_PORT_MAP.get(component, [])
    return {n: PCGPort(name=n, kind=PortKind.OPTICAL) for n in names}


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class PCGStore:
    """Mutable photonic circuit graph with checked mutations + journal."""

    def __init__(self, *, default_agent: Optional[str] = None) -> None:
        self._graph = nx.MultiDiGraph()
        self._nodes: Dict[str, PCGNode] = {}
        self._edges: List[PCGEdge] = []
        self._bundles: Dict[str, BundleSettings] = {}
        self._constraints: List[ConstraintEntry] = []
        self._exported_ports: Dict[str, str] = {}  # name -> "inst,port"
        self.journal = MutationJournal()
        self.default_agent = default_agent

    # -- read accessors -----------------------------------------------------

    @property
    def nodes(self) -> Dict[str, PCGNode]:
        return dict(self._nodes)

    @property
    def edges(self) -> List[PCGEdge]:
        return list(self._edges)

    @property
    def bundles(self) -> Dict[str, BundleSettings]:
        return dict(self._bundles)

    @property
    def constraints(self) -> List[ConstraintEntry]:
        return list(self._constraints)

    @property
    def exported_ports(self) -> Dict[str, str]:
        return dict(self._exported_ports)

    def _record(self, op: str, payload: Dict[str, Any], agent: Optional[str]) -> None:
        self.journal.append(
            op,
            payload,
            agent=agent if agent is not None else self.default_agent,
            topology_hash_after=self.topology_hash() if self._nodes else None,
        )

    # -- mutations ----------------------------------------------------------

    def add_node(
        self,
        node: PCGNode,
        *,
        skip_component_check: bool = False,
        agent: Optional[str] = None,
    ) -> None:
        if node.id in self._nodes:
            raise PCGMutationError("add_node", f"Duplicate node id '{node.id}'")
        if not skip_component_check:
            _validate_component(node.component)
        if not node.ports:
            node.ports = default_ports_for(node.component)
        self._nodes[node.id] = node
        self._graph.add_node(node.id)
        self._record(
            "add_node",
            {"id": node.id, "component": node.component, "params": dict(node.params)},
            agent,
        )

    def connect(
        self,
        src_node: str,
        src_port: str,
        dst_node: str,
        dst_port: str,
        layer: EdgeLayer = EdgeLayer.OPTICAL,
        bundle: Optional[str] = None,
        attachment: AttachmentKind = AttachmentKind.ROUTED,
        *,
        agent: Optional[str] = None,
    ) -> PCGEdge:
        # Existence
        if src_node not in self._nodes:
            raise PCGMutationError("connect", f"Source node '{src_node}' not found")
        if dst_node not in self._nodes:
            raise PCGMutationError("connect", f"Destination node '{dst_node}' not found")

        src = self._nodes[src_node]
        dst = self._nodes[dst_node]
        # Port-name membership when the node has a populated port map
        if src.ports and src_port not in src.ports:
            raise PCGMutationError(
                "connect",
                f"Port '{src_port}' not on node '{src_node}' "
                f"(have {sorted(src.ports)})",
            )
        if dst.ports and dst_port not in dst.ports:
            raise PCGMutationError(
                "connect",
                f"Port '{dst_port}' not on node '{dst_node}' "
                f"(have {sorted(dst.ports)})",
            )

        # No self-loop on same port
        if src_node == dst_node and src_port == dst_port:
            raise PCGMutationError("connect", "Self-loop on same port")

        # Port-degree <= 1 on optical ports
        if layer == EdgeLayer.OPTICAL:
            for e in self._edges:
                if e.layer != EdgeLayer.OPTICAL:
                    continue
                if (e.src_node == src_node and e.src_port == src_port) or \
                   (e.dst_node == src_node and e.dst_port == src_port):
                    raise PCGMutationError(
                        "connect",
                        f"Optical port '{src_node}.{src_port}' already connected",
                    )
                if (e.src_node == dst_node and e.src_port == dst_port) or \
                   (e.dst_node == dst_node and e.dst_port == dst_port):
                    raise PCGMutationError(
                        "connect",
                        f"Optical port '{dst_node}.{dst_port}' already connected",
                    )

        edge = PCGEdge(
            src_node=src_node,
            src_port=src_port,
            dst_node=dst_node,
            dst_port=dst_port,
            layer=layer,
            bundle=bundle,
            attachment=attachment,
        )
        self._edges.append(edge)
        self._graph.add_edge(src_node, dst_node)
        self._record(
            "connect",
            {
                "src": f"{src_node},{src_port}",
                "dst": f"{dst_node},{dst_port}",
                "layer": layer.value,
                "bundle": bundle,
                "attachment": attachment.value,
            },
            agent,
        )
        return edge

    def disconnect(
        self,
        src_node: str,
        src_port: str,
        dst_node: str,
        dst_port: str,
        *,
        agent: Optional[str] = None,
    ) -> None:
        before = len(self._edges)
        self._edges = [
            e for e in self._edges
            if not (
                e.src_node == src_node and e.src_port == src_port
                and e.dst_node == dst_node and e.dst_port == dst_port
            )
            and not (
                e.src_node == dst_node and e.src_port == dst_port
                and e.dst_node == src_node and e.dst_port == src_port
            )
        ]
        if len(self._edges) == before:
            raise PCGMutationError(
                "disconnect",
                f"No edge {src_node},{src_port} ↔ {dst_node},{dst_port}",
            )
        self._record(
            "disconnect",
            {"src": f"{src_node},{src_port}", "dst": f"{dst_node},{dst_port}"},
            agent,
        )

    def set_param(
        self,
        node_id: str,
        key: str,
        value: Any,
        *,
        agent: Optional[str] = None,
    ) -> None:
        if node_id not in self._nodes:
            raise PCGMutationError("set_param", f"Node '{node_id}' not found")
        node = self._nodes[node_id]
        _validate_param(node.component, key)
        node.params[key] = value
        self._record(
            "set_param",
            {"node": node_id, "key": key, "value": value},
            agent,
        )

    def set_placement(
        self,
        node_id: str,
        *,
        x: Optional[float] = None,
        y: Optional[float] = None,
        rotation: Optional[int] = None,
        mirror: Optional[bool] = None,
        agent: Optional[str] = None,
    ) -> None:
        """Update placement and mark dirty so to_gf_yaml emits live fields."""
        if node_id not in self._nodes:
            raise PCGMutationError("set_placement", f"Node '{node_id}' not found")
        node = self._nodes[node_id]
        if x is not None:
            node.x = x
        if y is not None:
            node.y = y
        if rotation is not None:
            node.rotation = rotation
        if mirror is not None:
            node.mirror = mirror
        node._placement_dirty = True
        self._record(
            "set_placement",
            {
                "node": node_id,
                "x": node.x,
                "y": node.y,
                "rotation": node.rotation,
                "mirror": node.mirror,
            },
            agent,
        )

    def remove_node(self, node_id: str, *, agent: Optional[str] = None) -> None:
        if node_id not in self._nodes:
            raise PCGMutationError("remove_node", f"Node '{node_id}' not found")
        self._edges = [
            e for e in self._edges
            if e.src_node != node_id and e.dst_node != node_id
        ]
        del self._nodes[node_id]
        if self._graph.has_node(node_id):
            self._graph.remove_node(node_id)
        self._record("remove_node", {"id": node_id}, agent)

    def add_constraint(
        self, entry: ConstraintEntry, *, agent: Optional[str] = None
    ) -> None:
        self._constraints.append(entry)
        self._record(
            "add_constraint",
            {"id": entry.id, "kind": entry.kind.value, "elements": list(entry.elements)},
            agent,
        )

    def set_bundle_settings(
        self, name: str, settings: BundleSettings, *, agent: Optional[str] = None
    ) -> None:
        self._bundles[name] = settings
        self._record("set_bundle_settings", {"name": name}, agent)

    def set_exported_ports(
        self, ports: Dict[str, str], *, agent: Optional[str] = None
    ) -> None:
        self._exported_ports = dict(ports)
        self._record("set_exported_ports", {"ports": dict(ports)}, agent)

    # -- snapshot / restore (atomic agent batches) ---------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Deep-ish snapshot of graph state + journal length for rollback."""
        return {
            "nodes": {k: v.model_copy(deep=True) for k, v in self._nodes.items()},
            "edges": [e.model_copy(deep=True) for e in self._edges],
            "bundles": {k: v.model_copy(deep=True) for k, v in self._bundles.items()},
            "constraints": [c.model_copy(deep=True) for c in self._constraints],
            "exported_ports": dict(self._exported_ports),
            "journal_len": len(self.journal),
        }

    def restore(self, snap: Dict[str, Any]) -> None:
        """Restore a snapshot from ``snapshot()``; truncates journal."""
        self._nodes = {k: v.model_copy(deep=True) for k, v in snap["nodes"].items()}
        self._edges = [e.model_copy(deep=True) for e in snap["edges"]]
        self._bundles = {k: v.model_copy(deep=True) for k, v in snap["bundles"].items()}
        self._constraints = [c.model_copy(deep=True) for c in snap["constraints"]]
        self._exported_ports = dict(snap["exported_ports"])
        self._graph = nx.MultiDiGraph()
        for nid in self._nodes:
            self._graph.add_node(nid)
        for e in self._edges:
            self._graph.add_edge(e.src_node, e.dst_node)
        # Truncate journal in place
        keep = int(snap["journal_len"])
        self.journal._entries = self.journal._entries[:keep]

    # -- hashing ------------------------------------------------------------

    def topology_hash(self) -> str:
        """SHA-256 over nodes (id, component, params) + edges (topology only).
        Geometry excluded — L1 and L2 of the same circuit share this hash."""
        node_data = []
        for nid in sorted(self._nodes):
            n = self._nodes[nid]
            node_data.append({
                "id": n.id,
                "component": n.component,
                "params": n.params,
            })
        edge_data = []
        for e in sorted(self._edges, key=lambda e: (e.src_node, e.src_port, e.dst_node, e.dst_port)):
            edge_data.append({
                "src": f"{e.src_node},{e.src_port}",
                "dst": f"{e.dst_node},{e.dst_port}",
                "layer": e.layer.value,
                "attachment": e.attachment.value,
                "bundle": e.bundle,
            })
        blob = _canonical_json({"nodes": node_data, "edges": edge_data})
        return hashlib.sha256(blob.encode()).hexdigest()

    def layout_hash(self) -> Optional[str]:
        """SHA-256 including placement geometry + back-annotated edge fields.
        Returns None if any node lacks geometry (i.e. store is L1)."""
        for n in self._nodes.values():
            if n.x is None or n.y is None:
                return None

        node_data = []
        for nid in sorted(self._nodes):
            n = self._nodes[nid]
            node_data.append({
                "id": n.id,
                "component": n.component,
                "params": n.params,
                "x": n.x,
                "y": n.y,
                "rotation": n.rotation,
                "mirror": n.mirror,
            })
        edge_data = []
        for e in sorted(self._edges, key=lambda e: (e.src_node, e.src_port, e.dst_node, e.dst_port)):
            edge_data.append({
                "src": f"{e.src_node},{e.src_port}",
                "dst": f"{e.dst_node},{e.dst_port}",
                "layer": e.layer.value,
                "attachment": e.attachment.value,
                "bundle": e.bundle,
                "length_um": e.length_um,
                "phase_rad": e.phase_rad,
                "n_crossings": e.n_crossings,
            })
        blob = _canonical_json({"nodes": node_data, "edges": edge_data})
        return hashlib.sha256(blob.encode()).hexdigest()
