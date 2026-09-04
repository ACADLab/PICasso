"""
Photonic Circuit Graph — Bridge to/from GDSFactory YAML and SAX.

Lossless round-trip: from_gf_yaml(to_gf_yaml(store)) preserves topology
and layout, including bundles, raw_placement stash, mirror, and attachment.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

import yaml

from .store import PCGStore
from .types import (
    AttachmentKind,
    BundleSettings,
    EdgeLayer,
    PCGEdge,
    PCGNode,
    PCGPort,
    PortKind,
    RefLevel,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GDSFactory YAML → PCGStore
# ---------------------------------------------------------------------------

def from_gf_yaml(yaml_str: str) -> PCGStore:
    """Parse a GDSFactory-compatible YAML netlist into a PCGStore.

    Handles both ``routes:<bundle>:links`` (ROUTED) and ``connections:``
    dict (BUTT_JOINT) connectivity syntaxes.
    """
    data = yaml.safe_load(yaml_str)
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")

    store = PCGStore()

    instances: Dict[str, Any] = data.get("instances", {}) or {}
    placements: Dict[str, Any] = data.get("placements", {}) or {}
    routes: Dict[str, Any] = data.get("routes", {}) or {}
    connections: Dict[str, str] = data.get("connections", {}) or {}
    ports: Dict[str, str] = data.get("ports", {}) or {}

    # --- nodes ---
    for inst_id, inst_spec in instances.items():
        if isinstance(inst_spec, str):
            comp_name = inst_spec
            settings: Dict[str, Any] = {}
        else:
            comp_name = inst_spec.get("component", "")
            settings = dict(inst_spec.get("settings", {}) or {})

        placement = placements.get(inst_id, {}) or {}

        node = PCGNode(
            id=inst_id,
            component=comp_name,
            params=settings,
            level=RefLevel.L2_PLACED if placement else RefLevel.L1_CIRCUIT,
            x=_to_float(placement.get("x")),
            y=_to_float(placement.get("y")),
            rotation=_to_int(placement.get("rotation")),
            mirror=bool(placement.get("mirror", False)),
            raw_placement=dict(placement) if placement else None,
        )
        store.add_node(node, skip_component_check=True)

    # --- routes (ROUTED edges) ---
    for bundle_name, bundle_spec in routes.items():
        if not isinstance(bundle_spec, dict):
            continue

        # Bundle settings
        raw_settings = dict(bundle_spec.get("settings", {}) or {})
        bs = BundleSettings(
            routing_strategy=raw_settings.pop("routing_strategy", None),
            radius=_to_float(raw_settings.pop("radius", None)),
            separation=_to_float(raw_settings.pop("separation", None)),
            cross_section=raw_settings.pop("cross_section", None),
            extra=raw_settings,
        )
        store.set_bundle_settings(bundle_name, bs)

        links: Dict[str, str] = bundle_spec.get("links", {}) or {}
        for src_str, dst_str in links.items():
            sn, sp = _parse_port_ref(src_str)
            dn, dp = _parse_port_ref(dst_str)
            if sn and dn:
                store.connect(
                    sn, sp, dn, dp,
                    layer=EdgeLayer.OPTICAL,
                    bundle=bundle_name,
                    attachment=AttachmentKind.ROUTED,
                )

    # --- connections (BUTT_JOINT edges) ---
    if isinstance(connections, dict):
        for src_str, dst_str in connections.items():
            sn, sp = _parse_port_ref(src_str)
            dn, dp = _parse_port_ref(dst_str)
            if sn and dn:
                store.connect(
                    sn, sp, dn, dp,
                    layer=EdgeLayer.OPTICAL,
                    bundle=None,
                    attachment=AttachmentKind.BUTT_JOINT,
                )

    # --- exported ports ---
    if isinstance(ports, dict):
        store.set_exported_ports(ports)

    return store


# ---------------------------------------------------------------------------
# PCGStore → GDSFactory YAML
# ---------------------------------------------------------------------------

def to_gf_yaml(store: PCGStore) -> str:
    """Serialize a PCGStore back to GDSFactory-compatible YAML.

    Preserves raw_placement verbatim when untouched, regroups edges by
    bundle, and emits BUTT_JOINT edges under ``connections:``.
    """
    data: Dict[str, Any] = {}

    # --- instances ---
    instances: Dict[str, Any] = {}
    for nid in sorted(store.nodes):
        n = store.nodes[nid]
        inst: Dict[str, Any] = {"component": n.component}
        if n.params:
            inst["settings"] = dict(n.params)
        else:
            inst["settings"] = {}
        instances[nid] = inst
    data["instances"] = instances

    # --- placements ---
    placements: Dict[str, Any] = {}
    for nid in sorted(store.nodes):
        n = store.nodes[nid]
        if n.raw_placement is not None and not n._placement_dirty:
            placements[nid] = dict(n.raw_placement)
        else:
            p: Dict[str, Any] = {}
            if n.x is not None:
                p["x"] = n.x
            if n.y is not None:
                p["y"] = n.y
            if n.rotation is not None:
                p["rotation"] = n.rotation
            p["mirror"] = n.mirror
            placements[nid] = p
    data["placements"] = placements

    # --- routes (ROUTED edges grouped by bundle) ---
    bundle_edges: Dict[str, List[PCGEdge]] = defaultdict(list)
    butt_edges: List[PCGEdge] = []
    for e in store.edges:
        if e.attachment == AttachmentKind.BUTT_JOINT:
            butt_edges.append(e)
        else:
            bname = e.bundle or "optical"
            bundle_edges[bname].append(e)

    if bundle_edges:
        routes: Dict[str, Any] = {}
        for bname in sorted(bundle_edges):
            bundle_spec: Dict[str, Any] = {}
            # settings
            bs = store.bundles.get(bname)
            settings: Dict[str, Any] = {}
            if bs:
                if bs.cross_section is not None:
                    settings["cross_section"] = bs.cross_section
                if bs.radius is not None:
                    settings["radius"] = bs.radius
                if bs.separation is not None:
                    settings["separation"] = bs.separation
                if bs.routing_strategy is not None:
                    settings["routing_strategy"] = bs.routing_strategy
                settings.update(bs.extra)
            bundle_spec["settings"] = settings
            # links
            links: Dict[str, str] = {}
            for e in bundle_edges[bname]:
                links[f"{e.src_node},{e.src_port}"] = f"{e.dst_node},{e.dst_port}"
            bundle_spec["links"] = links
            routes[bname] = bundle_spec
        data["routes"] = routes

    # --- connections (BUTT_JOINT) ---
    if butt_edges:
        conns: Dict[str, str] = {}
        for e in butt_edges:
            conns[f"{e.src_node},{e.src_port}"] = f"{e.dst_node},{e.dst_port}"
        data["connections"] = conns

    # --- ports ---
    if store.exported_ports:
        data["ports"] = dict(store.exported_ports)

    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=False)


# ---------------------------------------------------------------------------
# PCGStore → SAX netlist
# ---------------------------------------------------------------------------

def to_sax_netlist(store: PCGStore) -> Dict[str, Any]:
    """Emit a schematic-ideal SAX-compatible netlist dict.

    Edges are zero-length ideal connections — no router-inserted
    bends/straights. This is the "before" side of the delta-IL comparison;
    the "after" side comes from ``component.get_netlist()`` on a built
    GDSFactory component.
    """
    instances: Dict[str, Any] = {}
    for nid, n in store.nodes.items():
        instances[nid] = {
            "component": n.component,
            "settings": dict(n.params),
        }

    # SAX / gdsfactory expect connections as a dict of port refs, not a list
    connections: Dict[str, str] = {}
    for e in store.edges:
        connections[f"{e.src_node},{e.src_port}"] = f"{e.dst_node},{e.dst_port}"

    ports: Dict[str, str] = dict(store.exported_ports)

    return {
        "instances": instances,
        "connections": connections,
        "ports": ports,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_port_ref(ref: str) -> Tuple[str, str]:
    """Parse 'instance,port' into (instance, port). Returns ('','') on failure."""
    parts = ref.split(",", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", ""


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        # Port-anchored placement like "instance,port" — keep as-is in raw_placement
        return None


def _to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
