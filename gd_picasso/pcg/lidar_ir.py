"""
LiDAR PIC IR ↔ PCG adapter.

Schema inference pin
--------------------
Upstream: https://github.com/ScopeX-ASU/LiDAR
Commit:   ``4e7004d32b0b80d959553797fb30f0737513de0c`` (2026-01-13 tip)
Evidence: ``src/picroute/database/schematic.py``
          (``CustomSchematicConfiguration``, ``Settings``, ``Macro``, ``Instance``)
          and benchmark YAML under ``src/picroute/benchmarks/``
          (``nets: {n_i: [inst,port, inst,port]}``, ``library``, ``schematic_placements``).

Semantics
---------
- **LiDAR → PCG → LiDAR** = identity (structured equality on the supported IR).
- **PCG → LiDAR** = **projection**: optical 2-port nets emit; ELECTRICAL /
  THERMAL edges/ports and multi-port nets (>2 endpoints) are dropped and
  reported. Does not claim layout N3 or routed geometry fidelity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import yaml

from .store import PCGMutationError, PCGStore, default_ports_for
from .types import (
    AttachmentKind,
    EdgeLayer,
    PCGNode,
    PCGPort,
    PortKind,
    RefLevel,
)

# Pinned LiDAR revision used for schema inference (do not silent-bump).
LIDAR_GITHUB_REPO = "https://github.com/ScopeX-ASU/LiDAR"
LIDAR_SCHEMA_COMMIT = "4e7004d32b0b80d959553797fb30f0737513de0c"

_LIDAR_META_ATTR = "_lidar_meta"


@dataclass
class DroppedField:
    """One field/edge/port omitted by the PCG→LiDAR projection."""

    category: str  # ELECTRICAL | THERMAL | MULTI_PORT | OTHER
    detail: str


@dataclass
class LidarExportResult:
    """YAML text plus projection diagnostics."""

    yaml_text: str
    dropped: List[DroppedField] = field(default_factory=list)

    @property
    def is_identity_capable(self) -> bool:
        """True when nothing PCG-only was discarded (pure optical 2-port)."""
        return not self.dropped


def _parse_port_ref(ref: str) -> Tuple[str, str]:
    if not isinstance(ref, str) or "," not in ref:
        raise PCGMutationError(
            "from_lidar_yaml",
            f"Malformed LiDAR port ref '{ref}' (expected 'inst,port')",
        )
    inst, port = ref.split(",", 1)
    inst, port = inst.strip(), port.strip()
    if not inst or not port:
        raise PCGMutationError(
            "from_lidar_yaml",
            f"Malformed LiDAR port ref '{ref}'",
        )
    return inst, port


def _iter_nets(nets_raw: Any) -> List[Tuple[str, List[str]]]:
    """Normalize LiDAR ``nets`` (dict or list-of-lists) → (name, endpoints)."""
    out: List[Tuple[str, List[str]]] = []
    if nets_raw is None:
        return out
    if isinstance(nets_raw, dict):
        for name, endpoints in nets_raw.items():
            if not isinstance(endpoints, (list, tuple)):
                raise PCGMutationError(
                    "from_lidar_yaml",
                    f"Net '{name}' endpoints must be a list, got {type(endpoints)}",
                )
            out.append((str(name), [str(e) for e in endpoints]))
        return out
    if isinstance(nets_raw, list):
        for i, endpoints in enumerate(nets_raw):
            if not isinstance(endpoints, (list, tuple)):
                raise PCGMutationError(
                    "from_lidar_yaml",
                    f"Net index {i} endpoints must be a list",
                )
            out.append((f"n_{i}", [str(e) for e in endpoints]))
        return out
    raise PCGMutationError(
        "from_lidar_yaml",
        f"Unsupported nets type {type(nets_raw)}; expected dict or list",
    )


def _stash_meta(store: PCGStore, meta: Dict[str, Any]) -> None:
    setattr(store, _LIDAR_META_ATTR, meta)


def _get_meta(store: PCGStore) -> Dict[str, Any]:
    return dict(getattr(store, _LIDAR_META_ATTR, {}) or {})


def from_lidar_yaml(yaml_str: str) -> PCGStore:
    """Parse a LiDAR PIC IR YAML document into a ``PCGStore``.

    Stashes LiDAR-only keys (``library``, ``settings``, ``schematic_placements``,
    ``constraints``, net names, ``schema_version``) on the store so
    ``to_lidar_yaml`` can restore them for an identity round-trip.
    """
    data = yaml.safe_load(yaml_str)
    if not isinstance(data, dict):
        raise ValueError("LiDAR YAML root must be a mapping")

    store = PCGStore(default_agent="from_lidar_yaml")
    instances: Dict[str, Any] = data.get("instances") or {}
    if not isinstance(instances, dict):
        raise ValueError("LiDAR 'instances' must be a mapping")

    for inst_id, inst_spec in instances.items():
        if isinstance(inst_spec, str):
            comp_name = inst_spec
            settings: Dict[str, Any] = {}
        elif isinstance(inst_spec, dict):
            comp_name = str(inst_spec.get("component", ""))
            settings = dict(inst_spec.get("settings") or {})
        else:
            raise ValueError(f"Bad instance spec for '{inst_id}'")

        placement_block = settings.get("placement")
        x = y = rotation = None
        mirror = False
        level = RefLevel.L1_CIRCUIT
        raw_pl: Optional[Dict[str, Any]] = None
        if isinstance(placement_block, (list, tuple)) and len(placement_block) >= 2:
            loc = placement_block[1]
            if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                x, y = float(loc[0]), float(loc[1])
                level = RefLevel.L2_PLACED
            orient = placement_block[2] if len(placement_block) > 2 else "N"
            rotation, mirror = _orient_to_rotation_mirror(str(orient))
            raw_pl = {
                "x": x,
                "y": y,
                "rotation": rotation,
                "mirror": mirror,
                "lidar_placement": list(placement_block),
            }

        # Prefer schematic_placements when present (gdsfactory-style).
        sch = (data.get("schematic_placements") or {}).get(inst_id)
        if isinstance(sch, dict):
            if sch.get("x") is not None:
                x = float(sch["x"])
                level = RefLevel.L2_PLACED
            if sch.get("y") is not None:
                y = float(sch["y"])
            if sch.get("rotation") is not None:
                rotation = int(sch["rotation"])
            mirror = bool(sch.get("mirror", mirror))
            raw_pl = dict(sch)

        ports = default_ports_for(comp_name)
        # Ensure ports referenced later exist even for unknown components.
        node = PCGNode(
            id=inst_id,
            component=comp_name,
            params=settings,
            level=level,
            ports=ports,
            x=x,
            y=y,
            rotation=rotation,
            mirror=mirror,
            raw_placement=raw_pl,
        )
        store.add_node(node, skip_component_check=True)

    net_order: List[str] = []
    multiport_nets: List[Dict[str, Any]] = []
    for net_name, endpoints in _iter_nets(data.get("nets")):
        net_order.append(net_name)
        if len(endpoints) == 0:
            continue
        if len(endpoints) == 1:
            raise PCGMutationError(
                "from_lidar_yaml",
                f"Net '{net_name}' has a single endpoint {endpoints}",
            )
        if len(endpoints) > 2:
            # LiDAR IR is strictly 2-port. Keep the first pair as an optical
            # edge; stash the full endpoint list so projection reports
            # MULTI_PORT (identity cannot hold for this net).
            multiport_nets.append({"name": net_name, "endpoints": list(endpoints)})
            endpoints = list(endpoints[:2])

        a, b = endpoints[0], endpoints[1]
        an, ap = _parse_port_ref(a)
        bn, bp = _parse_port_ref(b)
        _ensure_port(store, an, ap)
        _ensure_port(store, bn, bp)
        store.connect(
            an, ap, bn, bp,
            layer=EdgeLayer.OPTICAL,
            attachment=AttachmentKind.ROUTED,
            bundle=net_name,
        )

    ports_map = data.get("ports") or {}
    if ports_map:
        store.set_exported_ports({str(k): str(v) for k, v in ports_map.items()})

    meta = {
        "library": data.get("library") or {},
        "settings": data.get("settings") or {},
        "schematic_placements": data.get("schematic_placements") or {},
        "constraints": data.get("constraints"),
        "schema": data.get("schema"),
        "schema_version": data.get("schema_version", 1),
        "net_order": net_order,
        "instance_order": list(instances.keys()),
        "multiport_nets": multiport_nets,
        "raw_nets": data.get("nets"),
    }
    _stash_meta(store, meta)
    return store


def _ensure_port(store: PCGStore, node_id: str, port_name: str) -> None:
    node = store.nodes.get(node_id)
    if node is None:
        raise PCGMutationError(
            "from_lidar_yaml",
            f"Net references unknown instance '{node_id}'",
        )
    if port_name not in node.ports:
        # Mutate port map in place (node is the live store object).
        live = store._nodes[node_id]  # noqa: SLF001 — ingest bootstrap
        live.ports[port_name] = PCGPort(name=port_name, kind=PortKind.OPTICAL)


def _orient_to_rotation_mirror(orient: str) -> Tuple[Optional[int], bool]:
    table = {
        "N": (0, False),
        "W": (90, False),
        "S": (180, False),
        "E": (270, False),
        "FN": (0, True),
        "FW": (90, True),
        "FS": (180, True),
        "FE": (270, True),
    }
    return table.get(orient, (0, False))


def _rotation_mirror_to_orient(rotation: Optional[int], mirror: bool) -> str:
    r = int(rotation or 0) % 360
    base = {0: "N", 90: "W", 180: "S", 270: "E"}.get(r, "N")
    if not mirror:
        return base
    return {"N": "FN", "W": "FW", "S": "FS", "E": "FE"}[base]


def to_lidar_yaml(
    store: PCGStore,
    *,
    design: Optional[str] = None,
) -> LidarExportResult:
    """Project a ``PCGStore`` to LiDAR PIC IR YAML.

    When the store was produced by ``from_lidar_yaml``, LiDAR-only metadata is
    restored so LiDAR→PCG→LiDAR is identity. Otherwise a minimal document is
    synthesized and non-LiDAR fields are reported in ``dropped``.
    """
    dropped: List[DroppedField] = []
    meta = _get_meta(store)

    # --- instances ---
    instance_order: Sequence[str] = meta.get("instance_order") or list(store.nodes.keys())
    # Include any nodes added after ingest.
    seen = set(instance_order)
    inst_ids = list(instance_order) + [n for n in store.nodes if n not in seen]

    instances: Dict[str, Any] = {}
    meta_placements = meta.get("schematic_placements")
    schematic_placements: Dict[str, Any] = (
        dict(meta_placements) if meta_placements is not None else {}
    )
    # When meta came from LiDAR ingest, preserve schematic_placements exactly
    # (even if partial / empty) so identity holds.
    preserve_placements = bool(meta)

    for nid in inst_ids:
        node = store.nodes[nid]
        settings = dict(node.params)

        # Drop non-optical ports from the projected view (report).
        for pname, pobj in node.ports.items():
            if pobj.kind == PortKind.ELECTRICAL:
                dropped.append(
                    DroppedField("ELECTRICAL", f"port {nid},{pname}")
                )
            elif pobj.kind == PortKind.THERMAL:
                dropped.append(
                    DroppedField("THERMAL", f"port {nid},{pname}")
                )

        if "placement" not in settings:
            orient = _rotation_mirror_to_orient(node.rotation, node.mirror)
            status = "PLACED" if node.x is not None else "UNPLACED"
            xy = [float(node.x or 0.0), float(node.y or 0.0)]
            settings["placement"] = [status, xy, orient, [0, 0, 0, 0]]

        instances[nid] = {"component": node.component, "settings": settings}

        if not preserve_placements and nid not in schematic_placements:
            if node.x is not None or node.raw_placement:
                if isinstance(node.raw_placement, dict) and "lidar_placement" not in (
                    node.raw_placement or {}
                ):
                    schematic_placements[nid] = dict(node.raw_placement)
                else:
                    schematic_placements[nid] = {
                        "x": float(node.x or 0.0),
                        "y": float(node.y or 0.0),
                        "port": None,
                        "rotation": int(node.rotation or 0),
                        "dx": 0,
                        "dy": 0,
                        "mirror": bool(node.mirror),
                    }

    # --- nets (optical 2-port only) ---
    raw_nets = meta.get("raw_nets")
    multiport_meta = list(meta.get("multiport_nets") or [])
    for mp in multiport_meta:
        dropped.append(
            DroppedField(
                "MULTI_PORT",
                f"net {mp.get('name')} endpoints={mp.get('endpoints')}",
            )
        )

    for e in store.edges:
        if e.layer == EdgeLayer.ELECTRICAL:
            dropped.append(
                DroppedField(
                    "ELECTRICAL",
                    f"edge {e.src_node},{e.src_port} → "
                    f"{e.dst_node},{e.dst_port}",
                )
            )
        elif e.layer == EdgeLayer.THERMAL:
            dropped.append(
                DroppedField(
                    "THERMAL",
                    f"edge {e.src_node},{e.src_port} → "
                    f"{e.dst_node},{e.dst_port}",
                )
            )

    has_non_optical = any(e.layer != EdgeLayer.OPTICAL for e in store.edges)
    use_raw = (
        isinstance(raw_nets, dict)
        and not multiport_meta
        and not has_non_optical
        and _optical_edge_count_matches(store, raw_nets)
    )

    nets: Dict[str, List[str]] = {}
    if use_raw:
        nets = {str(k): list(v) for k, v in raw_nets.items()}
    else:
        net_order = list(meta.get("net_order") or [])
        used_names: set[str] = set()
        optical_edges = [e for e in store.edges if e.layer == EdgeLayer.OPTICAL]
        for i, e in enumerate(optical_edges):
            name = (
                e.bundle
                if e.bundle
                else (net_order[i] if i < len(net_order) else f"n_{i}")
            )
            base = name
            suffix = 0
            while name in used_names:
                suffix += 1
                name = f"{base}_{suffix}"
            used_names.add(name)
            nets[name] = [
                f"{e.src_node},{e.src_port}",
                f"{e.dst_node},{e.dst_port}",
            ]

        # Back-annotation is PCG-only (LiDAR netlist IR has no phase/length).
        for e in optical_edges:
            if e.phase_rad is not None or e.length_um is not None:
                dropped.append(
                    DroppedField(
                        "OTHER",
                        "back-annot phase_rad/length_um not in LiDAR PIC IR",
                    )
                )
                break

    settings = dict(meta.get("settings") or {})
    if design is not None:
        settings["design"] = design
    if "version" not in settings:
        settings["version"] = "1.0"
    if "design" not in settings:
        settings["design"] = design or "pcg_export"
    if "units_distance_microns" not in settings:
        settings["units_distance_microns"] = 1
    if "die_area" not in settings:
        settings["die_area"] = [[0, 0], [100, 100]]
    if "wg_radius" not in settings:
        settings["wg_radius"] = 5
    settings["num_instances"] = len(instances)
    settings["num_nets"] = len(nets)
    settings["num_ports"] = len(store.exported_ports)

    doc: Dict[str, Any] = {
        "schema": meta.get("schema", None),
        "instances": instances,
        "schematic_placements": schematic_placements,
        "nets": nets,
        "ports": dict(store.exported_ports),
        "schema_version": meta.get("schema_version", 1),
        "settings": settings,
        "library": meta.get("library") or {},
    }
    if meta.get("constraints") is not None:
        doc["constraints"] = meta["constraints"]

    text = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)
    return LidarExportResult(yaml_text=text, dropped=dropped)


def _optical_edge_count_matches(store: PCGStore, raw_nets: Dict[str, Any]) -> bool:
    n_optical = sum(1 for e in store.edges if e.layer == EdgeLayer.OPTICAL)
    n_nets = 0
    for endpoints in raw_nets.values():
        if isinstance(endpoints, (list, tuple)) and len(endpoints) == 2:
            n_nets += 1
        elif isinstance(endpoints, (list, tuple)) and len(endpoints) > 2:
            return False
    return n_optical == n_nets


def lidar_docs_equal(a: Union[str, Dict[str, Any]], b: Union[str, Dict[str, Any]]) -> bool:
    """Structured equality for LiDAR IR docs (ignore YAML key order / style)."""

    def _load(x: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        if isinstance(x, dict):
            return x
        d = yaml.safe_load(x)
        if not isinstance(d, dict):
            raise ValueError("expected mapping")
        return d

    da, db = _load(a), _load(b)
    keys = (
        "instances",
        "nets",
        "ports",
        "settings",
        "library",
        "schematic_placements",
        "constraints",
        "schema_version",
    )
    for k in keys:
        if da.get(k) != db.get(k):
            return False
    return True
