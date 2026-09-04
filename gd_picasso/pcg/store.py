"""
Photonic Circuit Graph — Store.

NetworkX-backed mutable graph with checked mutations, dual hashing,
bundle-settings registry, constraint ledger, and exported-port map.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import math
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

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


def _validate_component(component: str) -> None:
    """Check component exists in gdsfactory — same as yaml_pilot_validator line 179."""
    try:
        import gdsfactory as gf
        if not hasattr(gf.components, component):
            raise PCGMutationError(
                "add_node",
                f"Component '{component}' not found in gf.components",
            )
    except ImportError:
        pass  # allow store to work without gdsfactory for unit tests


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class PCGStore:
    """Mutable photonic circuit graph with checked mutations."""

    def __init__(self) -> None:
        self._graph = nx.MultiDiGraph()
        self._nodes: Dict[str, PCGNode] = {}
        self._edges: List[PCGEdge] = []
        self._bundles: Dict[str, BundleSettings] = {}
        self._constraints: List[ConstraintEntry] = []
        self._exported_ports: Dict[str, str] = {}  # name -> "inst,port"

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

    # -- mutations ----------------------------------------------------------

    def add_node(self, node: PCGNode, *, skip_component_check: bool = False) -> None:
        if node.id in self._nodes:
            raise PCGMutationError("add_node", f"Duplicate node id '{node.id}'")
        if not skip_component_check:
            _validate_component(node.component)
        self._nodes[node.id] = node
        self._graph.add_node(node.id)

    def connect(
        self,
        src_node: str,
        src_port: str,
        dst_node: str,
        dst_port: str,
        layer: EdgeLayer = EdgeLayer.OPTICAL,
        bundle: Optional[str] = None,
        attachment: AttachmentKind = AttachmentKind.ROUTED,
    ) -> PCGEdge:
        # Existence
        if src_node not in self._nodes:
            raise PCGMutationError("connect", f"Source node '{src_node}' not found")
        if dst_node not in self._nodes:
            raise PCGMutationError("connect", f"Destination node '{dst_node}' not found")

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
        return edge

    def set_param(self, node_id: str, key: str, value: Any) -> None:
        if node_id not in self._nodes:
            raise PCGMutationError("set_param", f"Node '{node_id}' not found")
        node = self._nodes[node_id]
        # Validate key against component signature when gdsfactory available
        try:
            import gdsfactory as gf
            comp_func = getattr(gf.components, node.component, None)
            if comp_func is not None:
                sig = inspect.signature(comp_func)
                valid_params = set(sig.parameters.keys())
                if key not in valid_params and "kwargs" not in str(sig):
                    raise PCGMutationError(
                        "set_param",
                        f"Parameter '{key}' not in signature of '{node.component}'",
                    )
        except ImportError:
            pass
        node.params[key] = value

    def remove_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise PCGMutationError("remove_node", f"Node '{node_id}' not found")
        self._edges = [
            e for e in self._edges
            if e.src_node != node_id and e.dst_node != node_id
        ]
        del self._nodes[node_id]
        if self._graph.has_node(node_id):
            self._graph.remove_node(node_id)

    def add_constraint(self, entry: ConstraintEntry) -> None:
        self._constraints.append(entry)

    def set_bundle_settings(self, name: str, settings: BundleSettings) -> None:
        self._bundles[name] = settings

    def set_exported_ports(self, ports: Dict[str, str]) -> None:
        self._exported_ports = dict(ports)

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
