#!/usr/bin/env python3
"""LiDAR-env driver: YAML path → JSON metrics on stdout.

Runs under ``PICASSO_LIDAR_PYTHON`` (gf==8.26.1). Never import into gate venv.

Modes
-----
1. ``--route``: gdsfactory ``route_bundle`` / ``route_single`` / ``route_astar``
   curvy routing inside the LiDAR env; extract length / bends / crossings.
2. default: LiDAR-IR placement Manhattan from YAML nets (cite LiDAR IR;
   not a novelty claim for curvy A*).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _parse_ref(ref: str) -> Tuple[str, str]:
    a, _, b = ref.partition(",")
    return a.strip(), b.strip()


def metrics_from_lidar_yaml(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Manhattan lengths from LiDAR PIC IR placements + 2-pin nets."""
    placements = doc.get("schematic_placements") or {}
    instances = doc.get("instances") or {}
    xy: Dict[str, Tuple[float, float]] = {}
    for name, pl in placements.items():
        if isinstance(pl, dict) and "x" in pl and "y" in pl:
            xy[name] = (float(pl["x"]), float(pl["y"]))
    for name, inst in instances.items():
        if name in xy:
            continue
        settings = (inst or {}).get("settings") or {}
        place = settings.get("placement")
        if isinstance(place, list) and len(place) >= 2 and isinstance(
            place[1], (list, tuple)
        ):
            xy[name] = (float(place[1][0]), float(place[1][1]))

    metrics: List[Dict[str, Any]] = []
    nets = doc.get("nets") or {}
    for _nid, ends in nets.items():
        if not isinstance(ends, (list, tuple)) or len(ends) != 2:
            continue
        s_inst, s_port = _parse_ref(str(ends[0]))
        d_inst, d_port = _parse_ref(str(ends[1]))
        if s_inst not in xy or d_inst not in xy:
            continue
        x0, y0 = xy[s_inst]
        x1, y1 = xy[d_inst]
        L = abs(x1 - x0) + abs(y1 - y0)
        metrics.append(
            {
                "src": s_inst,
                "src_port": s_port,
                "dst": d_inst,
                "dst_port": d_port,
                "length_um": float(L),
                "n_bends": 0,
                "n_crossings": 0,
                "bend_radius_um": 0.0,
            }
        )
    wl = sum(m["length_um"] for m in metrics) if metrics else None
    return {
        "ok": bool(metrics),
        "mode": "lidar_ir_manhattan",
        "metrics": metrics,
        "il_max_db": None,
        "wirelength_um": wl,
    }


def _resolve_lidar_root() -> Path:
    env = os.environ.get("PICASSO_LIDAR_ROOT")
    if env and Path(env).is_dir():
        return Path(env)
    return Path(__file__).resolve().parents[3] / ".lidar_env" / "LiDAR"


def _default_route_config() -> Optional[Path]:
    root = _resolve_lidar_root()
    for rel in (
        "src/picroute/config/comp_LiDAR.yml",
        "src/picroute/config/default_config.yml",
    ):
        cand = root / rel
        if cand.is_file():
            return cand
    return None


_SKIP_SETTINGS = frozenset(
    {
        "placement",
        "macro_type",
        "library",
        "N",
        "W",
        "E",
        "S",
    }
)


def _iter_net_endpoints(doc: Dict[str, Any]) -> List[Tuple[str, str, str, str]]:
    """Collect (src, sport, dst, dport) from LiDAR nets or GF-style routes."""
    out: List[Tuple[str, str, str, str]] = []
    nets = doc.get("nets") or {}
    for _nid, ends in nets.items():
        if not isinstance(ends, (list, tuple)) or len(ends) != 2:
            continue
        s_inst, s_port = _parse_ref(str(ends[0]))
        d_inst, d_port = _parse_ref(str(ends[1]))
        out.append((s_inst, s_port, d_inst, d_port))
    if out:
        return out
    routes = doc.get("routes") or {}
    for _bname, bundle in routes.items():
        if not isinstance(bundle, dict):
            continue
        links = bundle.get("links") or {}
        if isinstance(links, dict):
            for src_ref, dst_ref in links.items():
                s_inst, s_port = _parse_ref(str(src_ref))
                d_inst, d_port = _parse_ref(str(dst_ref))
                out.append((s_inst, s_port, d_inst, d_port))
    return out


def _placement_xy_rot(doc: Dict[str, Any], name: str) -> Tuple[float, float, float]:
    sch = (doc.get("schematic_placements") or {}).get(name) or {}
    if isinstance(sch, dict) and ("x" in sch or "y" in sch):
        return (
            float(sch.get("x") or 0.0),
            float(sch.get("y") or 0.0),
            float(sch.get("rotation") or 0.0),
        )
    placements = doc.get("placements") or {}
    pl = placements.get(name) or {}
    if isinstance(pl, dict):
        return (
            float(pl.get("x") or 0.0),
            float(pl.get("y") or 0.0),
            float(pl.get("rotation") or 0.0),
        )
    inst = (doc.get("instances") or {}).get(name) or {}
    settings = (inst.get("settings") or {}) if isinstance(inst, dict) else {}
    place = settings.get("placement")
    if isinstance(place, list) and len(place) >= 2 and isinstance(
        place[1], (list, tuple)
    ):
        return float(place[1][0]), float(place[1][1]), 0.0
    return 0.0, 0.0, 0.0


# SiEPIC / ubcpdk cells are not in bare gf.components inside the LiDAR env.
# Port layouts (name, dx_um, dy_um, orient_deg, width_um) are routing stubs
# so Multi-PDK nets (and intermediate tapers) get real ComponentReferences.
_SIEPIC_ROUTING_STUBS: Dict[str, List[Tuple[str, float, float, float, float]]] = {
    "ebeam_y_adiabatic": [
        ("o1", -25.0, 0.0, 180.0, 0.45),
        ("o2", 25.0, 1.25, 0.0, 0.45),
        ("o3", 25.0, -1.25, 0.0, 0.45),
    ],
    "ebeam_YBranch_895": [
        ("o1", -20.0, 0.0, 180.0, 0.45),
        ("o2", 20.0, 1.25, 0.0, 0.45),
        ("o3", 20.0, -1.25, 0.0, 0.45),
    ],
    "ebeam_DC_te895": [
        ("o1", -20.0, 5.0, 180.0, 0.45),
        ("o2", -20.0, -5.0, 180.0, 0.45),
        ("o3", 20.0, 5.0, 0.0, 0.45),
        ("o4", 20.0, -5.0, 0.0, 0.45),
    ],
    "ebeam_gc_te895": [
        ("o1", -10.0, 0.0, 180.0, 0.45),
    ],
    "crossing_horizontal": [
        ("o1", -15.0, 0.0, 180.0, 0.5),
        ("o2", 15.0, 0.0, 0.0, 0.5),
        ("o3", 0.0, 15.0, 90.0, 0.5),
        ("o4", 0.0, -15.0, 270.0, 0.5),
    ],
    "ANT_MMI_1x2_te1550_3dB_BB": [
        ("o1", -30.0, 0.0, 180.0, 0.75),
        ("o2", 30.0, 8.0, 0.0, 0.75),
        ("o3", 30.0, -8.0, 0.0, 0.75),
    ],
    "ebeam_Polarizer_TM_1550_UQAM": [
        ("o1", -25.0, 0.0, 180.0, 1.04),
        ("o2", 25.0, 0.0, 0.0, 0.924),
    ],
}


# Cache routing stubs by component name so multi-instance Multi-PDK nets
# (e.g. two ebeam_YBranch_895) share one cell and add_ref cleanly.
_STUB_CACHE: Dict[str, Any] = {}


def _routing_stub_component(
    gf: Any,
    comp_name: str,
    ports: Sequence[Tuple[str, float, float, float, float]],
) -> Any:
    """Build a minimal gf Component with named optical ports for routing."""
    cached = _STUB_CACHE.get(comp_name)
    if cached is not None:
        return cached
    c = gf.Component(f"stub_{comp_name}")
    # Body bbox covering all port centers (+ margin) so keep-outs have area.
    xs = [p[1] for p in ports] or [0.0]
    ys = [p[2] for p in ports] or [0.0]
    pad = 5.0
    xmin, xmax = min(xs) - pad, max(xs) + pad
    ymin, ymax = min(ys) - pad, max(ys) + pad
    try:
        c.add_polygon(
            [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)],
            layer=(1, 0),
        )
    except Exception:
        pass
    for name, dx, dy, orient, width in ports:
        try:
            c.add_port(
                name=name,
                center=(dx, dy),
                width=float(width),
                orientation=float(orient),
                layer=(1, 0),
                port_type="optical",
            )
        except TypeError:
            # gf 8.x alternate signature
            c.add_port(
                name=name,
                center=(dx, dy),
                width=float(width),
                orientation=float(orient),
                layer=(1, 0),
            )
    _STUB_CACHE[comp_name] = c
    return c


def _make_component(gf: Any, comp_name: str, settings: Dict[str, Any]) -> Any:
    """Resolve a cell factory: gf.components → ubcpdk.cells → routing stub."""
    kwargs = {
        k: v
        for k, v in settings.items()
        if k not in _SKIP_SETTINGS and not str(k).startswith("_")
    }
    clean: Dict[str, Any] = {}
    for k, v in kwargs.items():
        if isinstance(v, (list, dict)) and k not in ("cross_section",):
            continue
        clean[k] = v

    factory = getattr(gf.components, comp_name, None)
    if factory is not None:
        try:
            return factory(**clean)
        except TypeError:
            return factory()

    # Optional ubcpdk (usually absent in the isolated LiDAR env).
    try:
        import ubcpdk  # type: ignore

        cells = getattr(ubcpdk, "cells", None)
        ubc_factory = getattr(cells, comp_name, None) if cells is not None else None
        if ubc_factory is not None:
            try:
                return ubc_factory(**clean)
            except TypeError:
                return ubc_factory()
    except Exception:
        pass

    stub_ports = _SIEPIC_ROUTING_STUBS.get(comp_name)
    if stub_ports is not None:
        return _routing_stub_component(gf, comp_name, stub_ports)

    raise KeyError(f"unknown component {comp_name!r}")


def _route_length_um(route: Any, dbu: float) -> float:
    L = getattr(route, "length", None)
    if L is None:
        return 0.0
    return float(L) * float(dbu)


def _route_n_bends(route: Any) -> int:
    for attr in ("n_bend90", "n_bends", "n_bend"):
        v = getattr(route, attr, None)
        if v is not None:
            return int(v)
    # Count bend instances as fallback
    n = 0
    for inst in getattr(route, "instances", None) or []:
        name = str(getattr(inst, "cell_name", None) or getattr(inst, "name", "") or inst)
        if "bend" in name.lower():
            n += 1
    return n


def _route_bend_radius_um(route: Any, dbu: float) -> float:
    r = getattr(route, "bend90_radius", None)
    if r is None:
        return 0.0
    return float(r) * float(dbu)


def _count_crossings_in_component(component: Any) -> int:
    n = 0
    try:
        insts = component.insts if hasattr(component, "insts") else []
        for inst in insts:
            name = str(
                getattr(inst, "cell", None)
                or getattr(inst, "cell_name", None)
                or getattr(inst, "name", "")
                or ""
            ).lower()
            if "crossing" in name:
                n += 1
    except Exception:
        pass
    # Also scan route instance names already counted above; keep net-local below.
    return n


# Static keep-outs + bundle pitch so routes clear the 2.0 µm DRC spacing rule.
KEEP_OUT_BUFFER_UM: float = 3.0
BUNDLE_SEPARATION_UM: float = 4.0
# A* clearance around avoid-layer keep-outs (µm).
ASTAR_AVOID_DISTANCE_UM: float = 2.5
# Dedicated layer for painted keep-out rectangles (not in strip cross-section).
_KEEPOUT_LAYER: Tuple[int, int] = (99, 0)


def _ref_dbbox(ref: Any) -> Optional[Any]:
    """Return a DBox for a placed instance, or None."""
    try:
        db = getattr(ref, "dbbox", None)
        if callable(db):
            return db()
        if db is not None:
            return db
    except Exception:
        pass
    try:
        return ref.bbox() if callable(getattr(ref, "bbox", None)) else ref.bbox
    except Exception:
        return None


def _component_keepout_bboxes(
    gf: Any,
    refs: Dict[str, Any],
    *,
    buffer_um: float = KEEP_OUT_BUFFER_UM,
    exclude: Optional[Sequence[str]] = None,
) -> List[Any]:
    """Integer ``kdb.Box`` keep-outs = component bbox + ``buffer_um`` padding.

    Endpoint instances listed in ``exclude`` are omitted so ports stay
    reachable; all other bodies become static obstacles for ``route_bundle``.
    """
    skip = set(exclude or ())
    dbu = float(getattr(getattr(gf, "kcl", None), "dbu", None) or 0.001)
    pad_dbu = max(1, int(round(float(buffer_um) / dbu)))
    boxes: List[Any] = []
    for name, ref in refs.items():
        if name in skip:
            continue
        dbox = _ref_dbbox(ref)
        if dbox is None:
            continue
        try:
            ibox = dbox.to_itype(dbu)
            boxes.append(ibox.enlarged(pad_dbu))
        except Exception:
            try:
                # Manual DBox → Box conversion.
                import kfactory as kf

                left = int((float(dbox.left) - buffer_um) / dbu)
                bottom = int((float(dbox.bottom) - buffer_um) / dbu)
                right = int((float(dbox.right) + buffer_um) / dbu)
                top = int((float(dbox.top) + buffer_um) / dbu)
                boxes.append(kf.kdb.Box(left, bottom, right, top))
            except Exception:
                continue
    return boxes


def _paint_keepout_layer(
    component: Any,
    refs: Dict[str, Any],
    *,
    buffer_um: float = KEEP_OUT_BUFFER_UM,
    exclude: Optional[Sequence[str]] = None,
    layer: Tuple[int, int] = _KEEPOUT_LAYER,
) -> None:
    """Draw keep-out rectangles on ``layer`` for A* ``avoid_layers``."""
    skip = set(exclude or ())
    for name, ref in refs.items():
        if name in skip:
            continue
        dbox = _ref_dbbox(ref)
        if dbox is None:
            continue
        try:
            component.add_polygon(
                [
                    (float(dbox.left) - buffer_um, float(dbox.bottom) - buffer_um),
                    (float(dbox.right) + buffer_um, float(dbox.bottom) - buffer_um),
                    (float(dbox.right) + buffer_um, float(dbox.top) + buffer_um),
                    (float(dbox.left) - buffer_um, float(dbox.top) + buffer_um),
                ],
                layer=layer,
            )
        except Exception:
            continue


def _try_route_pair(
    gf: Any,
    component: Any,
    port1: Any,
    port2: Any,
    *,
    radius: float,
    cross_section: str = "strip",
    bboxes: Optional[Sequence[Any]] = None,
) -> Tuple[Optional[Any], Optional[str]]:
    """Route one net, preferring ``route_bundle`` so ``bboxes`` keep-outs apply.

    ``route_single`` ignores obstacles; A* uses a painted keep-out layer when
    present. Order: bundle(bboxes) → astar(avoid_layers) → single.
    """
    errors: List[str] = []
    # 1-net bundle inherits bboxes / separation (clears foreign component bodies).
    try:
        routes = gf.routing.route_bundle(
            component,
            [port1],
            [port2],
            cross_section=cross_section,
            radius=radius,
            separation=BUNDLE_SEPARATION_UM,
            bboxes=list(bboxes) if bboxes else None,
            start_straight_length=BUNDLE_SEPARATION_UM,
            end_straight_length=BUNDLE_SEPARATION_UM,
        )
        if routes:
            return routes[0], None
    except Exception as e:
        errors.append(f"route_bundle1:{type(e).__name__}:{e}")
    try:
        astar_kwargs: Dict[str, Any] = {
            "cross_section": cross_section,
            "bend": "bend_euler",
            "radius": radius,
            "resolution": 1.0,
            "distance": ASTAR_AVOID_DISTANCE_UM,
        }
        # Keep-out layer may be empty; still pass avoid_layers for consistency.
        astar_kwargs["avoid_layers"] = [_KEEPOUT_LAYER]
        rt = gf.routing.route_astar(component, port1, port2, **astar_kwargs)
        return rt, None
    except Exception as e:
        errors.append(f"route_astar:{type(e).__name__}:{e}")
    try:
        rt = gf.routing.route_single(
            component,
            port1,
            port2,
            cross_section=cross_section,
            radius=radius,
        )
        return rt, None
    except Exception as e:
        errors.append(f"route_single:{type(e).__name__}:{e}")
    return None, " | ".join(errors)

def try_gf_curvy_route(
    doc: Dict[str, Any],
    *,
    radius: float = 10.0,
    gds_out: Optional[str] = None,
) -> Dict[str, Any]:
    """Curvy route via gdsfactory 8.26 ``route_bundle`` / ``route_single`` / A*.

    Extracts ``length_um``, ``n_bends``, Euler ``bend_radius_um``, and
    ``n_crossings`` from generated route references. When ``gds_out`` is set,
    writes the routed component GDS for headless DRC.
    """
    try:
        import gdsfactory as gf
    except Exception as e:
        return {
            "ok": False,
            "error": f"import gdsfactory failed: {e}",
            "metrics": [],
            "mode": "gf_curvy_failed",
        }

    instances = doc.get("instances") or {}
    if not instances:
        return {
            "ok": False,
            "error": "no instances in YAML",
            "metrics": [],
            "mode": "gf_curvy_failed",
        }

    endpoints = _iter_net_endpoints(doc)
    if not endpoints:
        return {
            "ok": False,
            "error": "no nets/routes to route",
            "metrics": [],
            "mode": "gf_curvy_failed",
        }

    # Prefer GF routes-bundle radius when present
    routes_block = doc.get("routes") or {}
    for bundle in routes_block.values():
        if isinstance(bundle, dict):
            settings = bundle.get("settings") or {}
            if settings.get("radius") is not None:
                try:
                    radius = float(settings["radius"])
                except (TypeError, ValueError):
                    pass
                break

    component = gf.Component("picasso_gf_curvy")
    refs: Dict[str, Any] = {}
    place_errors: List[str] = []
    for name, inst in instances.items():
        if isinstance(inst, str):
            comp_name, settings = inst, {}
        else:
            comp_name = str((inst or {}).get("component") or "")
            settings = dict((inst or {}).get("settings") or {})
        try:
            cell = _make_component(gf, comp_name, settings)
            # Explicit ComponentReference so dynamically inserted tapers /
            # SiEPIC stubs are in the top-level layout before route_bundle.
            ref = component.add_ref(cell) if hasattr(component, "add_ref") else (
                component << cell
            )
            x, y, rot = _placement_xy_rot(doc, name)
            if rot:
                # gf8: prefer drotate/dmove when present
                if hasattr(ref, "drotate"):
                    ref.drotate(rot)
                else:
                    ref.rotate(rot)
            if hasattr(ref, "dmove"):
                ref.dmove((x, y))
            else:
                ref.move((x, y))
            refs[name] = ref
        except Exception as e:
            place_errors.append(f"{name}:{type(e).__name__}:{e}")

    if place_errors and len(refs) < 2:
        return {
            "ok": False,
            "error": "placement failed: " + "; ".join(place_errors[:4]),
            "metrics": [],
            "mode": "gf_curvy_failed",
            "place_errors": place_errors,
        }
    # Keep going when only some cells failed — missing_ref below names them.
    if place_errors:
        route_errors_seed = [
            f"place:{e}" for e in place_errors[:8]
        ]
    else:
        route_errors_seed = []

    dbu = float(gf.kcl.dbu)
    metrics: List[Dict[str, Any]] = []
    route_errors: List[str] = list(route_errors_seed)

    # Paint keep-outs for A* avoid_layers. Endpoints are still painted; A* is
    # a fallback after route_bundle (which strips endpoint bboxes). The keep-out
    # layer is not part of the strip cross-section, so it won't appear in GDS
    # WG DRC.
    _paint_keepout_layer(
        component, refs, buffer_um=KEEP_OUT_BUFFER_UM, exclude=None
    )

    # Group endpoints that share a common source instance for route_bundle attempts
    by_src: Dict[str, List[Tuple[str, str, str, str]]] = {}
    for ep in endpoints:
        by_src.setdefault(ep[0], []).append(ep)

    routed_keys: set = set()
    for src_inst, group in by_src.items():
        if src_inst not in refs:
            continue
        if len(group) >= 2 and all(g[2] in refs for g in group):
            try:
                ports1 = [refs[s].ports[sp] for s, sp, _d, _dp in group]
                ports2 = [refs[d].ports[dp] for _s, _sp, d, dp in group]
                # Exclude this bundle's own endpoints so ports stay open;
                # every other body (+3 µm) is a hard obstacle.
                ep_names = {s for s, _sp, d, _dp in group} | {
                    d for _s, _sp, d, _dp in group
                }
                bboxes = _component_keepout_bboxes(
                    gf,
                    refs,
                    buffer_um=KEEP_OUT_BUFFER_UM,
                    exclude=sorted(ep_names),
                )
                routes = gf.routing.route_bundle(
                    component,
                    ports1,
                    ports2,
                    cross_section="strip",
                    radius=radius,
                    separation=BUNDLE_SEPARATION_UM,
                    bboxes=bboxes or None,
                    start_straight_length=BUNDLE_SEPARATION_UM,
                    end_straight_length=BUNDLE_SEPARATION_UM,
                )
                for ep, rt in zip(group, routes):
                    key = ep
                    routed_keys.add(key)
                    n_bends = _route_n_bends(rt)
                    metrics.append(
                        {
                            "src": ep[0],
                            "src_port": ep[1],
                            "dst": ep[2],
                            "dst_port": ep[3],
                            "length_um": _route_length_um(rt, dbu),
                            "n_bends": n_bends,
                            "n_crossings": 0,
                            "bend_radius_um": _route_bend_radius_um(rt, dbu),
                            "bend_angle_rad": n_bends * (math.pi / 2.0),
                        }
                    )
                continue
            except Exception as e:
                route_errors.append(
                    f"route_bundle[{src_inst}]:{type(e).__name__}:{e}"
                )

        for ep in group:
            if ep in routed_keys:
                continue
            s, sp, d, dp = ep
            if s not in refs or d not in refs:
                route_errors.append(f"missing_ref:{s}->{d}")
                continue
            try:
                p1 = refs[s].ports[sp]
                p2 = refs[d].ports[dp]
            except Exception as e:
                route_errors.append(f"port:{s},{sp}->{d},{dp}:{e}")
                continue
            pair_bboxes = _component_keepout_bboxes(
                gf,
                refs,
                buffer_um=KEEP_OUT_BUFFER_UM,
                exclude=(s, d),
            )
            rt, err = _try_route_pair(
                gf,
                component,
                p1,
                p2,
                radius=radius,
                cross_section="strip",
                bboxes=pair_bboxes,
            )
            if rt is None:
                route_errors.append(f"{s},{sp}->{d},{dp}:{err}")
                continue
            routed_keys.add(ep)
            n_bends = _route_n_bends(rt)
            # Per-route crossing cells among this route's instances
            n_cross = 0
            for inst in getattr(rt, "instances", None) or []:
                nm = str(
                    getattr(inst, "cell_name", None)
                    or getattr(inst, "name", "")
                    or inst
                ).lower()
                if "crossing" in nm:
                    n_cross += 1
            metrics.append(
                {
                    "src": s,
                    "src_port": sp,
                    "dst": d,
                    "dst_port": dp,
                    "length_um": _route_length_um(rt, dbu),
                    "n_bends": n_bends,
                    "n_crossings": n_cross,
                    "bend_radius_um": _route_bend_radius_um(rt, dbu),
                    "bend_angle_rad": n_bends * (math.pi / 2.0),
                }
            )

    # Component-level crossing cells distributed as residual (rare for river)
    total_cross = _count_crossings_in_component(component)
    if total_cross and metrics:
        # If routes didn't attribute crossings, put residual on first metric
        attributed = sum(m["n_crossings"] for m in metrics)
        if attributed == 0:
            metrics[0]["n_crossings"] = int(total_cross)

    if not metrics:
        return {
            "ok": False,
            "error": "gf curvy route produced no metrics: "
            + "; ".join(route_errors[:6]),
            "metrics": [],
            "mode": "gf_curvy_failed",
            "route_errors": route_errors,
        }

    wl = sum(m["length_um"] for m in metrics)
    incomplete = len(metrics) < len(endpoints)
    gds_path = None
    if gds_out:
        try:
            Path(gds_out).parent.mkdir(parents=True, exist_ok=True)
            component.write_gds(str(gds_out))
            gds_path = str(gds_out)
        except Exception as e:
            route_errors.append(f"write_gds:{type(e).__name__}:{e}")
    return {
        "ok": not incomplete,
        "mode": "gf_curvy",
        "metrics": metrics,
        "il_max_db": None,
        "wirelength_um": wl,
        "n_bends_total": sum(m["n_bends"] for m in metrics),
        "n_crossings_total": sum(m["n_crossings"] for m in metrics),
        "route_errors": route_errors if incomplete or route_errors else [],
        "gds_path": gds_path,
        "error": (
            f"partial route {len(metrics)}/{len(endpoints)}: "
            + "; ".join(route_errors[:4])
            if incomplete
            else None
        ),
    }


def _extract_net_metrics(router: Any) -> Tuple[List[Dict[str, Any]], float, Optional[float]]:
    """Best-effort port-aware metrics from PICRoute cirdb / evaluation."""
    metrics: List[Dict[str, Any]] = []
    wl_total = 0.0
    il_max: Optional[float] = None

    db = getattr(router, "cirdb", None)
    if db is None:
        return metrics, wl_total, il_max

    for attr in ("net_wirelength", "wirelengths", "net_wl"):
        table = getattr(db, attr, None)
        if isinstance(table, dict) and table:
            for name, L in table.items():
                try:
                    Lf = float(L)
                except (TypeError, ValueError):
                    continue
                wl_total += Lf
                metrics.append(
                    {
                        "src": str(name),
                        "src_port": "o1",
                        "dst": str(name),
                        "dst_port": "o2",
                        "length_um": Lf,
                        "n_bends": 0,
                        "n_crossings": 0,
                    }
                )
            if metrics:
                return metrics, wl_total, il_max

    nets = getattr(db, "nets", None) or getattr(db, "dbNets", None) or {}
    if isinstance(nets, dict):
        for name, net in nets.items():
            L = float(
                getattr(net, "wirelength", None)
                or getattr(net, "wl", None)
                or getattr(net, "length", None)
                or 0
            )
            if L <= 0:
                continue
            wl_total += L
            src = getattr(net, "src", None) or getattr(net, "source", None)
            dst = getattr(net, "dst", None) or getattr(net, "sink", None)
            s_inst = s_port = d_inst = d_port = None
            if isinstance(src, str) and "," in src:
                s_inst, s_port = _parse_ref(src)
            if isinstance(dst, str) and "," in dst:
                d_inst, d_port = _parse_ref(dst)
            if s_inst and d_inst:
                metrics.append(
                    {
                        "src": s_inst,
                        "src_port": s_port or "o1",
                        "dst": d_inst,
                        "dst_port": d_port or "o2",
                        "length_um": L,
                        "n_bends": int(getattr(net, "n_bends", 0) or 0),
                        "n_crossings": int(getattr(net, "n_crossings", 0) or 0),
                    }
                )
            else:
                metrics.append(
                    {
                        "src": str(name),
                        "src_port": "o1",
                        "dst": str(name),
                        "dst_port": "o2",
                        "length_um": L,
                        "n_bends": 0,
                        "n_crossings": 0,
                    }
                )

    for attr in ("il_max", "IL_max", "max_il"):
        v = getattr(db, attr, None)
        if v is not None:
            try:
                il_max = float(v)
                break
            except (TypeError, ValueError):
                pass

    return metrics, wl_total, il_max


def try_picroute(yaml_path: Path, config_path: Optional[Path]) -> Dict[str, Any]:
    """Best-effort full PICRoute; returns empty metrics on failure."""
    try:
        from picroute.config.config import configs
        from picroute.main.picroute import PICRoute
    except Exception as e:
        return {"ok": False, "error": f"import PICRoute failed: {e}", "metrics": []}

    cfg: Optional[Path] = None
    for cand in (
        config_path,
        _default_route_config(),
        Path(os.environ.get("PICASSO_LIDAR_ROOT", ""))
        / "src/picroute/config/comp_LiDAR.yml",
        Path(__file__).resolve().parents[3]
        / ".lidar_env/LiDAR/src/picroute/config/comp_LiDAR.yml",
    ):
        if cand and Path(cand).is_file():
            cfg = Path(cand)
            break
    if cfg is None:
        return {
            "ok": False,
            "error": "no LiDAR config found (expected comp_LiDAR.yml)",
            "metrics": [],
            "mode": "picroute_failed",
        }

    try:
        configs.load(str(cfg), recursive=False)
        out_gds = tempfile.mktemp(suffix=".gds")
        configs.update([f"--run.output_layout_gds_path={out_gds}"])
        if not hasattr(configs, "il_cross"):
            try:
                configs.update(["--il_cross=0.5"])
            except Exception:
                pass
        with open(os.devnull, "w") as devnull:
            old_out, old_err = os.dup(1), os.dup(2)
            try:
                os.dup2(devnull.fileno(), 1)
                os.dup2(devnull.fileno(), 2)
                router = PICRoute(str(yaml_path), configs)
                router.run()
            finally:
                os.dup2(old_out, 1)
                os.dup2(old_err, 2)
                os.close(old_out)
                os.close(old_err)
        metrics, wl_total, il_max = _extract_net_metrics(router)
        return {
            "ok": True,
            "mode": "picroute",
            "metrics": metrics,
            "il_max_db": il_max,
            "wirelength_um": wl_total if metrics else None,
            "gds_path": out_gds,
            "config": str(cfg),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "metrics": [],
            "mode": "picroute_failed",
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("yaml", type=Path)
    ap.add_argument(
        "--route",
        action="store_true",
        help="Attempt gf curvy route (bundle/single/A*), then PICRoute fallback",
    )
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--radius", type=float, default=10.0)
    ap.add_argument(
        "--gds-out",
        type=Path,
        default=None,
        help="Write routed layout GDS (gf_curvy or PICRoute) to this path",
    )
    args = ap.parse_args()
    doc = None
    try:
        import yaml

        doc = yaml.safe_load(args.yaml.read_text())
    except Exception as e:
        json.dump({"ok": False, "error": f"yaml load: {e}", "metrics": []}, sys.stdout)
        return 0

    gds_out = str(args.gds_out) if args.gds_out else None
    if args.route:
        payload = try_gf_curvy_route(
            doc or {}, radius=args.radius, gds_out=gds_out
        )
        if payload.get("ok") and payload.get("metrics"):
            json.dump(payload, sys.stdout)
            return 0
        # Optional PICRoute fallback (LiDAR native)
        pico = try_picroute(args.yaml, args.config)
        if pico.get("metrics"):
            pico["gf_route_error"] = payload.get("error")
            # Copy PICRoute GDS to requested path when possible.
            if gds_out and pico.get("gds_path"):
                try:
                    import shutil

                    Path(gds_out).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(pico["gds_path"]), gds_out)
                    pico["gds_path"] = gds_out
                except Exception as e:
                    pico["gds_copy_error"] = str(e)
            json.dump(pico, sys.stdout)
            return 0
        base = metrics_from_lidar_yaml(doc or {})
        base["route_error"] = payload.get("error") or pico.get("error")
        base["mode"] = "lidar_ir_manhattan_after_route_fail"
        base["gf_route_errors"] = payload.get("route_errors")
        json.dump(base, sys.stdout)
        return 0

    json.dump(metrics_from_lidar_yaml(doc or {}), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
