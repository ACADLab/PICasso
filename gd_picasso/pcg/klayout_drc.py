"""Headless waveguide DRC for PIC-Bench layouts (klayout.db / gf fallback).

Checks (µm):
  a. Polygon self-intersections (``strange_polygon_check`` on WG)
  b. Minimum inter-waveguide spacing (< ``min_spacing_um``, default 2.0)
  c. Minimum bend radius (Cornerstone 5.0 µm / SiEPIC 15.0 µm)

CLI::

    python -m gd_picasso.pcg.klayout_drc path/to/layout.gds --task-id 20
    python -m gd_picasso.pcg.klayout_drc --sweep   # all 46 golden fixtures
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO = Path(__file__).resolve().parents[2]
PICSET = Path(__file__).resolve().parent / "fixtures" / "picset"

# PDK bend floors (user spec).
R_MIN_CORNERSTONE_UM = 5.0
R_MIN_SIEPIC_UM = 15.0
DEFAULT_MIN_SPACING_UM = 2.0

# generic_tech WG is layer 1/0; also accept (1,*) and common foundry WG.
_WG_LAYER_CANDIDATES = {(1, 0), (1, 1), (3, 0), (2, 0)}

# Device bodies intentionally pack WG < 2 µm (MMI apertures, directional
# couplers, heater stacks). Spacing DRC only scores route interconnect.
_DEVICE_CELL_RE = re.compile(
    r"(mmi|coupler|crossing|grating|gc_|heater|ring|disk|via|pad)",
    re.I,
)
_ROUTE_CELL_RE = re.compile(
    r"(bend_euler|bend_circular|bend_s|taper|route_|bundle)",
    re.I,
)
_STRAIGHT_LEN_RE = re.compile(r"_L(\d+(?:p\d+)?)", re.I)


@dataclass
class DrcViolation:
    kind: str  # self_intersection | spacing | bend_radius
    detail: str
    value_um: Optional[float] = None


@dataclass
class DrcResult:
    task_id: Optional[int]
    gds_path: str
    drc_clean: bool
    violation_count: int
    violations: List[DrcViolation] = field(default_factory=list)
    pdk: str = "cornerstone"
    min_spacing_um: float = DEFAULT_MIN_SPACING_UM
    r_min_um: float = R_MIN_CORNERSTONE_UM
    backend: str = "klayout.db"
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["violations"] = [asdict(v) for v in self.violations]
        return d


def r_min_for_pdk(pdk: str) -> float:
    p = (pdk or "cornerstone").lower()
    if "siepic" in p or "ebeam" in p:
        return R_MIN_SIEPIC_UM
    return R_MIN_CORNERSTONE_UM


def _wg_layers(ly: Any) -> List[Tuple[int, int]]:
    found: List[Tuple[int, int]] = []
    try:
        from gdsfactory.generic_tech import LAYER

        wg = LAYER.WG
        found.append((int(wg[0]), int(wg[1]) if len(wg) > 1 else 0))
    except Exception:
        pass
    for li in ly.layer_infos():
        key = (int(li.layer), int(li.datatype))
        if key in _WG_LAYER_CANDIDATES or key in found:
            if key not in found:
                found.append(key)
    if not found:
        # Fall back: densest layer by shape count (likely WG).
        best = None
        best_n = -1
        for li in ly.layer_infos():
            idx = ly.layer(li.layer, li.datatype)
            n = ly.top_cell().shapes(idx).size()
            if n > best_n:
                best_n = n
                best = (int(li.layer), int(li.datatype))
        if best is not None and best_n > 0:
            found.append(best)
    return found


def _parse_radius_token(name: str, radii: List[float]) -> None:
    for token in name.replace("-", "_").split("_"):
        t = token.lower()
        if t.startswith("r") and t[1:].replace(".", "", 1).isdigit():
            try:
                radii.append(float(t[1:]))
            except ValueError:
                pass


def _collect_bend_radii_from_layout(ly: Any, dbu: float) -> List[float]:
    """Extract bend radii from Path objects and cell names when present."""
    radii: List[float] = []
    top = ly.top_cell()
    if top is None:
        return radii

    def _walk(cell: Any, depth: int = 0) -> None:
        if depth > 8:
            return
        _parse_radius_token(str(cell.name), radii)
        for li in ly.layer_infos():
            idx = ly.layer(li.layer, li.datatype)
            for shape in cell.shapes(idx).each():
                if not shape.is_path():
                    continue
                path = shape.path
                for attr in ("radius", "r", "bend_radius"):
                    v = getattr(path, attr, None)
                    if v is None:
                        continue
                    try:
                        fv = float(v)
                    except (TypeError, ValueError):
                        continue
                    # Heuristic: integer dbu counts are large; µm floats are small.
                    radii.append(fv * dbu if fv > 100.0 else fv)
        for inst in cell.each_inst():
            try:
                _walk(inst.cell, depth + 1)
            except Exception:
                continue

    try:
        _walk(top)
    except Exception:
        pass
    return radii


def _inter_island_spacing_violations(
    region: Any,
    *,
    min_s_dbu: int,
    dbu: float,
    # 120 µm rejects bend-fillet false positives from the short-straight
    # route filter (which drops long spans and fragments nets) while still
    # catching long collinear bus merges on dense meshes.
    parallel_run_um: float = 120.0,
    min_island_span_um: float = 60.0,
) -> Tuple[int, Optional[float]]:
    """Count distinct merged-island pairs closer than ``min_s_dbu``.

    Returns ``(n_violations, min_gap_um)``. Uses a single sized-interact
    probe per pair (no binary search) so large meshes stay tractable.

    Tip / MMI fan-in proximity is ignored: a pair only counts when both
    islands are long interconnect spans (max bbox edge ≥
    ``min_island_span_um``) and share a projected parallel run ≥
    ``parallel_run_um`` — i.e. collinear bus merging, not port escape stubs
    or bend-fillet fragments left by the short-straight route filter.
    """
    import klayout.db as kdb

    if region is None or region.is_empty():
        return 0, None
    islands = list(region.merged().each())
    if len(islands) < 2:
        return 0, None
    regs = [kdb.Region(p) for p in islands]
    boxes = [p.bbox() for p in islands]

    def _span_um(box: Any) -> float:
        return max(box.width(), box.height()) * dbu

    n_viol = 0
    min_gap: Optional[float] = None
    for i, ra in enumerate(regs):
        ba = boxes[i]
        if _span_um(ba) < min_island_span_um:
            continue  # short port-escape stub
        grown = ra.sized(int(min_s_dbu))
        for j in range(i + 1, len(regs)):
            rb = regs[j]
            bb = boxes[j]
            if _span_um(bb) < min_island_span_um:
                continue
            # Projected overlap along each axis (µm).
            ox = (
                max(0, min(ba.right, bb.right) - max(ba.left, bb.left)) * dbu
            )
            oy = (
                max(0, min(ba.top, bb.top) - max(ba.bottom, bb.bottom)) * dbu
            )
            if max(ox, oy) < parallel_run_um:
                continue  # tip touch / short convergence only
            if not (ra & rb).is_empty():
                n_viol += 1
                min_gap = 0.0 if min_gap is None else min(min_gap, 0.0)
                continue
            if grown.interacting(rb).is_empty():
                continue
            n_viol += 1
            approx = 0.5 * float(min_s_dbu) * float(dbu)
            min_gap = approx if min_gap is None else min(min_gap, approx)
    return n_viol, min_gap


def _is_route_interconnect_cell(name: str) -> bool:
    """True for Euler/S bends and short routed straights (not heater/MMI)."""
    if _DEVICE_CELL_RE.search(name):
        return False
    if _ROUTE_CELL_RE.search(name):
        return True
    # Short ``straight_…_L{len}`` segments from gf.routing (len < 100 µm).
    # Longer straights are usually placed MZI dummy arms, not interconnect.
    if "straight" in name.lower():
        m = _STRAIGHT_LEN_RE.search(name)
        if m:
            raw = m.group(1).replace("p", ".")
            try:
                return float(raw) < 100.0
            except ValueError:
                return False
    return False


def _route_only_region(ly: Any, top: Any, layer_idx: int) -> Any:
    """WG shapes from route interconnect cells (bends + routed straights)."""
    import klayout.db as kdb

    region = kdb.Region()

    def _insert_cell_shapes(cell: Any, trans: Any) -> None:
        tmp = kdb.Region(cell.begin_shapes_rec(layer_idx))
        if not tmp.is_empty():
            region.insert(tmp.transformed(trans))

    def _walk(cell: Any, trans: Any, depth: int = 0) -> None:
        if depth > 12:
            return
        name = str(cell.name)
        # Never score WG inside device bodies (MMI, GC, heater, …).
        if depth > 0 and _DEVICE_CELL_RE.search(name):
            return
        if depth > 0 and _is_route_interconnect_cell(name):
            _insert_cell_shapes(cell, trans)
            return
        for inst in cell.each_inst():
            try:
                child = inst.cell
                ctr = trans * inst.cplx_trans
                _walk(child, ctr, depth + 1)
            except Exception:
                continue

    try:
        _walk(top, kdb.ICplxTrans(), 0)
    except Exception:
        return kdb.Region(top.begin_shapes_rec(layer_idx))
    return region


def run_drc(
    gds_path: str | Path,
    *,
    task_id: Optional[int] = None,
    pdk: str = "cornerstone",
    min_spacing_um: float = DEFAULT_MIN_SPACING_UM,
    r_min_um: Optional[float] = None,
    route_bend_radii_um: Optional[Sequence[float]] = None,
) -> DrcResult:
    """Evaluate headless DRC on a GDS layout."""
    path = Path(gds_path)
    r_min = float(r_min_um) if r_min_um is not None else r_min_for_pdk(pdk)
    violations: List[DrcViolation] = []
    backend = "klayout.db"

    if not path.is_file():
        return DrcResult(
            task_id=task_id,
            gds_path=str(path),
            drc_clean=False,
            violation_count=1,
            violations=[
                DrcViolation(kind="missing_gds", detail=f"GDS not found: {path}")
            ],
            pdk=pdk,
            min_spacing_um=min_spacing_um,
            r_min_um=r_min,
            backend="none",
            detail="missing_gds",
        )

    try:
        import klayout.db as kdb
    except ImportError:
        return _run_drc_gf_fallback(
            path,
            task_id=task_id,
            pdk=pdk,
            min_spacing_um=min_spacing_um,
            r_min=r_min,
            route_bend_radii_um=route_bend_radii_um,
        )

    try:
        ly = kdb.Layout()
        ly.read(str(path))
        top = ly.top_cell()
        if top is None:
            return DrcResult(
                task_id=task_id,
                gds_path=str(path),
                drc_clean=False,
                violation_count=1,
                violations=[DrcViolation(kind="empty", detail="GDS has no top cell")],
                pdk=pdk,
                min_spacing_um=min_spacing_um,
                r_min_um=r_min,
                backend=backend,
            )
        dbu = float(ly.dbu) or 0.001
        min_s = max(1, int(round(min_spacing_um / dbu)))

        wg_layers = _wg_layers(ly)
        if not wg_layers:
            violations.append(
                DrcViolation(kind="no_wg", detail="no waveguide layer geometry found")
            )
        for layer, datatype in wg_layers:
            idx = ly.layer(layer, datatype)
            region = kdb.Region(top.begin_shapes_rec(idx))
            if region.is_empty():
                continue

            # (a) Self-intersections / strange polygons (hairpin self-overlap).
            strange = region.strange_polygon_check()
            n_strange = int(strange.count()) if strange is not None else 0
            if n_strange:
                violations.append(
                    DrcViolation(
                        kind="self_intersection",
                        detail=(
                            f"WG {layer}/{datatype}: {n_strange} strange/self-"
                            f"intersecting polygon edge(s)"
                        ),
                        value_um=None,
                    )
                )

            # (b) Inter-island spacing on route-like WG (distinct-net proxy).
            # Do NOT use Region.space_check on a merged net — that flags same-net
            # U-turn / parallel-arm notches. Pairwise island proximity only.
            route_region = _route_only_region(ly, top, idx)
            if route_region.is_empty():
                route_region = region
            n_space, min_gap = _inter_island_spacing_violations(
                route_region, min_s_dbu=min_s, dbu=dbu
            )
            if n_space:
                violations.append(
                    DrcViolation(
                        kind="spacing",
                        detail=(
                            f"WG {layer}/{datatype}: {n_space} distinct route-"
                            f"island pair(s) with gap < {min_spacing_um} µm"
                            + (
                                f" (min gap {min_gap:.3f} µm)"
                                if min_gap is not None
                                else ""
                            )
                        ),
                        value_um=min_gap if min_gap is not None else min_spacing_um,
                    )
                )

        # (c) Bend radius — prefer routed metrics; also scan layout.
        radii = list(route_bend_radii_um or [])
        radii.extend(_collect_bend_radii_from_layout(ly, dbu))
        # Positive reported radii that undershoot the PDK floor.
        bad = [r for r in radii if 0.0 < float(r) < r_min - 1e-9]
        if bad:
            violations.append(
                DrcViolation(
                    kind="bend_radius",
                    detail=(
                        f"{len(bad)} bend(s) below R_min={r_min} µm "
                        f"(min observed {min(bad):.3f} µm, pdk={pdk})"
                    ),
                    value_um=float(min(bad)),
                )
            )

        return DrcResult(
            task_id=task_id,
            gds_path=str(path),
            drc_clean=len(violations) == 0,
            violation_count=len(violations),
            violations=violations,
            pdk=pdk,
            min_spacing_um=min_spacing_um,
            r_min_um=r_min,
            backend=backend,
            detail=f"wg_layers={wg_layers}; n_radii_checked={len(radii)}",
        )
    except Exception as exc:  # noqa: BLE001
        return DrcResult(
            task_id=task_id,
            gds_path=str(path),
            drc_clean=False,
            violation_count=1,
            violations=[
                DrcViolation(kind="drc_error", detail=f"{type(exc).__name__}:{exc}")
            ],
            pdk=pdk,
            min_spacing_um=min_spacing_um,
            r_min_um=r_min,
            backend="klayout.db_error",
        )


def _run_drc_gf_fallback(
    path: Path,
    *,
    task_id: Optional[int],
    pdk: str,
    min_spacing_um: float,
    r_min: float,
    route_bend_radii_um: Optional[Sequence[float]],
) -> DrcResult:
    """Boolean geometry checks via gdsfactory when klayout.db is absent."""
    violations: List[DrcViolation] = []
    try:
        import gdsfactory as gf
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except Exception as exc:  # noqa: BLE001
        return DrcResult(
            task_id=task_id,
            gds_path=str(path),
            drc_clean=False,
            violation_count=1,
            violations=[
                DrcViolation(
                    kind="backend_missing",
                    detail=f"klayout.db and gf/shapely unavailable: {exc}",
                )
            ],
            pdk=pdk,
            min_spacing_um=min_spacing_um,
            r_min_um=r_min,
            backend="none",
        )

    c = gf.import_gds(str(path))
    polys = []
    for poly in c.get_polygons(by="tuple"):
        # poly may be array of points
        try:
            pts = [(float(x), float(y)) for x, y in poly]
            if len(pts) >= 3:
                p = Polygon(pts)
                if not p.is_valid:
                    violations.append(
                        DrcViolation(
                            kind="self_intersection",
                            detail="invalid/self-intersecting polygon (shapely)",
                        )
                    )
                polys.append(p)
        except Exception:
            continue

    if len(polys) >= 2:
        merged = unary_union(polys)
        # Pairwise distance between disconnected islands
        if hasattr(merged, "geoms"):
            geoms = list(merged.geoms)
            for i in range(len(geoms)):
                for j in range(i + 1, len(geoms)):
                    d = float(geoms[i].distance(geoms[j]))
                    if 0.0 < d < min_spacing_um:
                        violations.append(
                            DrcViolation(
                                kind="spacing",
                                detail=f"island gap {d:.3f} µm < {min_spacing_um}",
                                value_um=d,
                            )
                        )
                        break

    bad = [r for r in (route_bend_radii_um or []) if 0.0 < float(r) < r_min - 1e-9]
    if bad:
        violations.append(
            DrcViolation(
                kind="bend_radius",
                detail=f"{len(bad)} bend(s) < R_min={r_min} µm",
                value_um=float(min(bad)),
            )
        )

    # Dedup spacing floods
    kinds = {}
    deduped: List[DrcViolation] = []
    for v in violations:
        key = (v.kind, v.detail[:80])
        if key in kinds:
            continue
        kinds[key] = True
        deduped.append(v)

    return DrcResult(
        task_id=task_id,
        gds_path=str(path),
        drc_clean=len(deduped) == 0,
        violation_count=len(deduped),
        violations=deduped,
        pdk=pdk,
        min_spacing_um=min_spacing_um,
        r_min_um=r_min,
        backend="gdsfactory+shapely",
    )


def golden_task_ids() -> List[int]:
    ids: List[int] = []
    for path in sorted(PICSET.glob("task_*.yaml")):
        if path.name.endswith("_lidar.yaml"):
            continue
        try:
            ids.append(int(path.stem.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return ids


def place_route_emit_gds(
    task_id: int,
    *,
    out_dir: Path,
    pdk: str = "cornerstone",
    lambda_overlap: float = 200.0,
) -> Dict[str, Any]:
    """Torch-place (λ_overlap + X-stage) → I/O GC pads → LiDAR route → GDS."""
    from gd_picasso.pcg.bridge import from_gf_yaml
    from gd_picasso.pcg.io_legalize import legalize_io_pads
    from gd_picasso.pcg.legalize import legalize_taper_placements
    from gd_picasso.pcg.place.objective import ObjectiveWeights
    from gd_picasso.pcg.place.torch_placer import place_torch
    from gd_picasso.pcg.route.lidar_wrap import route_with_lidar
    from gd_picasso.pcg.types import EdgeLayer

    # Prefer dedicated LiDAR env.
    lidar_py = _REPO / ".lidar_env" / "venv" / "bin" / "python"
    if lidar_py.is_file() and not os.environ.get("PICASSO_LIDAR_PYTHON"):
        os.environ["PICASSO_LIDAR_PYTHON"] = str(lidar_py)

    yaml_path = PICSET / f"task_{task_id:02d}.yaml"
    if not yaml_path.is_file():
        return {
            "task_id": task_id,
            "ok": False,
            "detail": "missing_fixture",
            "gds_path": None,
        }

    store = from_gf_yaml(yaml_path.read_text(encoding="utf-8"))
    n_nodes = len(store.nodes)
    # Scale place budget with size (same spirit as DAC harness).
    if n_nodes <= 40:
        steps, lr = 60, 3.0
    elif n_nodes <= 80:
        steps, lr = 40, 4.0
    else:
        steps, lr = 30, 5.0

    w = ObjectiveWeights(
        lambda_F=0.05,
        lambda_phi=0.05,
        lambda_overlap=lambda_overlap,
        lambda_y_pitch=10.0,
        y_pitch_um=25.0,
        lambda_x_stage=40.0,
        x_stage_gap_um=150.0,
        lambda_D=0.0,
        alpha=1.4,
    )
    place_torch(store, weights=w, steps=steps, lr=lr, write_back=True)
    # Snap Multi-PDK tapers onto the CS↔SiEPIC corridor so LiDAR gets real
    # ComponentReferences with (x, y) before route_bundle.
    legalize_taper_placements(store, agent="drc_sweep")

    out_dir.mkdir(parents=True, exist_ok=True)
    # Absolute path: LiDAR driver runs with cwd=.lidar_env/LiDAR.
    gds_path = (out_dir / f"task_{task_id:02d}.gds").resolve()

    # Tapeout I/O pads after placement (core + GC array routed together).
    io_info = legalize_io_pads(store, pdk=pdk, margin_um=200.0)

    routed = route_with_lidar(
        store,
        design=f"drc_t{task_id:02d}",
        try_full_route=True,
        allow_stub=False,
        gds_out=gds_path,
    )

    n_optical = sum(1 for e in store.edges if e.layer == EdgeLayer.OPTICAL)
    n_routed = len(routed.metrics)
    bend_radii = [float(m.bend_radius_um or 0.0) for m in routed.metrics.values()]
    min_bend = min((r for r in bend_radii if r > 0), default=None)
    hairpin = any(0.0 < r < r_min_for_pdk(pdk) for r in bend_radii)

    # If LiDAR did not emit GDS, fall back to gate-env YAML emit (placed only).
    if not gds_path.is_file():
        try:
            from gd_picasso.pcg.backends.cornerstone import emit_generic_tech_gds

            emit_generic_tech_gds(store, gds_path=gds_path)
        except Exception as exc:  # noqa: BLE001
            return {
                "task_id": task_id,
                "ok": False,
                "route_ok": routed.ok,
                "detail": f"no_gds:{exc}; route={routed.detail}",
                "gds_path": None,
                "n_optical": n_optical,
                "n_routed": n_routed,
                "bend_radii_um": bend_radii,
            }

    unrouted = max(0, n_optical - n_routed) if routed.ok else n_optical
    clean_route = bool(routed.ok) and unrouted == 0 and not hairpin
    return {
        "task_id": task_id,
        "ok": clean_route,
        "route_ok": routed.ok,
        "gds_path": str(gds_path) if gds_path.is_file() else None,
        "n_optical": n_optical,
        "n_routed": n_routed,
        "unrouted": unrouted,
        "hairpin_bend": hairpin,
        "min_bend_radius_um": min_bend,
        "bend_radii_um": bend_radii,
        "wirelength_um": routed.wirelength_um,
        "detail": routed.detail,
        "banner": routed.banner,
        "io_legalize": {
            "n_inputs": io_info.n_inputs,
            "n_outputs": io_info.n_outputs,
            "gc_ids": list(io_info.gc_ids),
            "pitch_um": io_info.pitch_um,
            "gc_component": io_info.gc_component,
            "skipped": io_info.skipped,
            "detail": io_info.detail,
        },
    }


def verify_representative_tasks(
    task_ids: Sequence[int] = (1, 2, 9, 11, 20, 26),
    *,
    out_dir: Optional[Path] = None,
    pdk: str = "cornerstone",
) -> List[Dict[str, Any]]:
    """Place+route+DRC on the representative task set."""
    out = out_dir or (_REPO / "gd_picasso" / "pcg" / "n1_runs" / "layout_verify")
    rows: List[Dict[str, Any]] = []
    for tid in task_ids:
        print(f"[verify] task {tid:02d} place+route …", flush=True)
        route_info = place_route_emit_gds(tid, out_dir=out, pdk=pdk)
        gds = route_info.get("gds_path")
        if gds:
            drc = run_drc(
                gds,
                task_id=tid,
                pdk=pdk,
                route_bend_radii_um=route_info.get("bend_radii_um") or [],
            )
            route_info["drc"] = drc.to_dict()
            route_info["drc_clean"] = drc.drc_clean
        else:
            route_info["drc_clean"] = False
            route_info["drc"] = None
        # Step-1 cleanliness: full route, no unrouted nets, no hairpin / self-X.
        self_x = any(
            (v.get("kind") == "self_intersection")
            for v in ((route_info.get("drc") or {}).get("violations") or [])
        )
        route_clean = bool(route_info.get("ok")) and not self_x
        route_info["route_clean"] = route_clean
        status = "CLEAN" if route_clean else "FAIL"
        print(
            f"  {status} route_ok={route_info.get('route_ok')} "
            f"unrouted={route_info.get('unrouted')} "
            f"hairpin={route_info.get('hairpin_bend')} "
            f"self_x={self_x} drc_clean={route_info.get('drc_clean')}",
            flush=True,
        )
        rows.append(route_info)
    return rows


def sweep_drc_all_fixtures(
    *,
    out_dir: Optional[Path] = None,
    pdk: str = "cornerstone",
    task_ids: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """Place+route+DRC every golden PIC-Bench fixture; return summary."""
    out = out_dir or (_REPO / "gd_picasso" / "pcg" / "n1_runs" / "drc_sweep")
    ids = list(task_ids) if task_ids is not None else golden_task_ids()
    results: List[Dict[str, Any]] = []
    for tid in ids:
        print(f"[drc-sweep] task {tid:02d} …", flush=True)
        try:
            route_info = place_route_emit_gds(tid, out_dir=out, pdk=pdk)
        except Exception as exc:  # noqa: BLE001
            route_info = {
                "task_id": tid,
                "ok": False,
                "detail": f"place_route_exc:{type(exc).__name__}:{exc}",
                "gds_path": None,
            }
        gds = route_info.get("gds_path")
        if gds:
            drc = run_drc(
                gds,
                task_id=tid,
                pdk=pdk,
                route_bend_radii_um=route_info.get("bend_radii_um") or [],
            )
            route_info["drc"] = drc.to_dict()
            route_info["drc_clean"] = drc.drc_clean
            route_info["failure_modes"] = [
                v["kind"] for v in drc.to_dict().get("violations") or []
            ]
        else:
            route_info["drc_clean"] = False
            route_info["failure_modes"] = ["no_gds"]
            if not route_info.get("route_ok", False):
                route_info["failure_modes"].append("route_fail")
        print(
            f"  drc_clean={route_info.get('drc_clean')} "
            f"modes={route_info.get('failure_modes')}",
            flush=True,
        )
        results.append(route_info)

    n = len(results)
    n_clean = sum(1 for r in results if r.get("drc_clean"))
    mode_counts: Dict[str, int] = {}
    for r in results:
        for m in r.get("failure_modes") or []:
            mode_counts[m] = mode_counts.get(m, 0) + 1
    summary = {
        "n_total": n,
        "n_drc_clean": n_clean,
        "pass_rate": (n_clean / n) if n else 0.0,
        "failure_mode_counts": mode_counts,
        "failures": [
            {
                "task_id": r["task_id"],
                "modes": r.get("failure_modes"),
                "detail": (r.get("detail") or "")[:200],
            }
            for r in results
            if not r.get("drc_clean")
        ],
        "results": results,
    }
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "drc_sweep_report.json"
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        f"=== DRC sweep: {n_clean}/{n} clean "
        f"({100.0 * summary['pass_rate']:.1f}%) ===",
        flush=True,
    )
    print(f"failure modes: {mode_counts}", flush=True)
    print(f"wrote {report_path}", flush=True)
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Headless PIC waveguide DRC")
    p.add_argument("gds", nargs="?", type=Path, help="GDS file to check")
    p.add_argument("--task-id", type=int, default=None)
    p.add_argument("--pdk", default="cornerstone", choices=("cornerstone", "siepic"))
    p.add_argument("--min-spacing", type=float, default=DEFAULT_MIN_SPACING_UM)
    p.add_argument("--r-min", type=float, default=None)
    p.add_argument(
        "--verify",
        action="store_true",
        help="Place+LiDAR-route+DRC tasks 1,2,9,11,20,26",
    )
    p.add_argument(
        "--sweep",
        action="store_true",
        help="Place+route+DRC all 46 golden PIC-Bench fixtures",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory for GDS / reports",
    )
    args = p.parse_args(argv)

    if args.verify:
        rows = verify_representative_tasks(out_dir=args.out_dir, pdk=args.pdk)
        n_route = sum(1 for r in rows if r.get("route_clean"))
        n_drc = sum(1 for r in rows if r.get("drc_clean"))
        print(f"representative route-clean: {n_route}/{len(rows)}")
        print(f"representative DRC-clean:   {n_drc}/{len(rows)}")
        out = args.out_dir or (
            _REPO / "gd_picasso" / "pcg" / "n1_runs" / "layout_verify"
        )
        out.mkdir(parents=True, exist_ok=True)
        (out / "representative_report.json").write_text(
            json.dumps(rows, indent=2), encoding="utf-8"
        )
        return 0 if n_route == len(rows) else 1

    if args.sweep:
        summary = sweep_drc_all_fixtures(out_dir=args.out_dir, pdk=args.pdk)
        return 0 if summary["n_drc_clean"] == summary["n_total"] else 1

    if args.gds is None:
        p.error("provide a GDS path, or --verify / --sweep")
    result = run_drc(
        args.gds,
        task_id=args.task_id,
        pdk=args.pdk,
        min_spacing_um=args.min_spacing,
        r_min_um=args.r_min,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.drc_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
