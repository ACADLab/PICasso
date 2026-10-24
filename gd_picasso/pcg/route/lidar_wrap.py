"""
LiDAR detailed-router wrap — **isolated env** (gf pin mismatch).

Pin check (Phase 2a first-5-min gate)
-------------------------------------
- PICasso gate: ``gdsfactory==9.23.0``
- LiDAR (ScopeX-ASU/LiDAR @ ``4e7004d3…``): ``gdsfactory==8.26.1``

Never import LiDAR into the gate venv. Drive it via subprocess YAML in a
separate interpreter listed by ``PICASSO_LIDAR_PYTHON`` (or
``~/.venvs/lidar/bin/python``).

Claim discipline: cite LiDAR; do **not** claim curvy detailed routing as ours.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from gd_picasso.pcg.backannotate import RouteMetrics, apply_route_metrics
from gd_picasso.pcg.lidar_ir import (
    LIDAR_GITHUB_REPO,
    LIDAR_SCHEMA_COMMIT,
    from_lidar_yaml,
    to_lidar_yaml,
)
from gd_picasso.pcg.store import PCGStore

# Documented pin divergence (do not silent-bump).
PICASSO_GF_PIN = "9.23.0"
LIDAR_GF_PIN = "8.26.1"
LIDAR_PIN_MISMATCH = PICASSO_GF_PIN != LIDAR_GF_PIN


@dataclass
class LidarPinReport:
    picasso_gf: str = PICASSO_GF_PIN
    lidar_gf: str = LIDAR_GF_PIN
    mismatch: bool = LIDAR_PIN_MISMATCH
    lidar_python: Optional[str] = None
    lidar_import_ok: bool = False
    detail: str = ""


@dataclass
class LidarRouteResult:
    """Back-annotated metrics from a LiDAR (or stub) route run."""

    ok: bool
    metrics: Dict[Tuple[str, str, str, str], RouteMetrics] = field(default_factory=dict)
    il_max_db: Optional[float] = None
    wirelength_um: Optional[float] = None
    yaml_out: Optional[str] = None
    gds_path: Optional[str] = None
    banner: str = "LiDAR wrap — cite ScopeX-ASU/LiDAR; not our router"
    detail: str = ""


def check_lidar_gf_pin(
    lidar_python: Optional[str] = None,
) -> LidarPinReport:
    """First-5-min gate: confirm LiDAR env gf pin vs PICasso 9.23."""
    repo_venv = (
        Path(__file__).resolve().parents[3] / ".lidar_env" / "venv" / "bin" / "python"
    )
    py = (
        lidar_python
        or os.environ.get("PICASSO_LIDAR_PYTHON")
        or (str(repo_venv) if repo_venv.is_file() else None)
        or shutil.which("lidar-python")
    )
    report = LidarPinReport(lidar_python=py)
    if not py or not Path(py).exists():
        report.detail = (
            f"LiDAR python not found; expected isolated env with "
            f"gdsfactory=={LIDAR_GF_PIN} (PICasso uses {PICASSO_GF_PIN}). "
            f"Run gd_picasso/pcg/route/setup_lidar_env.sh then "
            f"export PICASSO_LIDAR_PYTHON=..."
        )
        return report
    try:
        out = subprocess.check_output(
            [
                py,
                "-c",
                "import importlib.metadata as m; print(m.version('gdsfactory'))",
            ],
            text=True,
            timeout=30,
            stderr=subprocess.STDOUT,
        ).strip()
        report.lidar_gf = out
        report.mismatch = out != PICASSO_GF_PIN
        report.lidar_import_ok = True
        report.detail = (
            f"LiDAR env gf={out}; PICasso gf={PICASSO_GF_PIN}; "
            f"isolated={'yes' if report.mismatch else 'same-pin'}"
        )
    except Exception as e:
        report.detail = f"LiDAR pin probe failed: {e}"
    return report


def _manhattan_stub_metrics(store: PCGStore) -> Dict[Tuple[str, str, str, str], RouteMetrics]:
    """CPU fallback when LiDAR env is unavailable — ESTIMATOR_ONLY lengths."""
    from gd_picasso.pcg.place.tensors import build_placement_problem, estimated_net_length
    from gd_picasso.pcg.types import EdgeLayer

    problem = build_placement_problem(store)
    optical = [e for e in store.edges if e.layer == EdgeLayer.OPTICAL]
    metrics: Dict[Tuple[str, str, str, str], RouteMetrics] = {}
    for net in problem.nets:
        L = float(estimated_net_length(problem, net))
        e = optical[net.edge_idx]
        metrics[(e.src_node, e.src_port, e.dst_node, e.dst_port)] = RouteMetrics(
            length_um=L
        )
    return metrics


def route_with_lidar(
    store: PCGStore,
    *,
    design: str = "picasso_route",
    lidar_python: Optional[str] = None,
    allow_stub: bool = True,
    try_full_route: bool = False,
    gds_out: Optional[str | Path] = None,
) -> LidarRouteResult:
    """Export PCG→LiDAR YAML, invoke LiDAR driver in isolated env, back-annotate.

    Default driver mode = LiDAR-IR placement Manhattan (cite LiDAR IR).
    Set ``try_full_route=True`` to run gdsfactory 8.26 curvy routing
    (``route_bundle`` / ``route_single`` / ``route_astar``) inside the
    LiDAR env and back-annotate length / bends / crossings.
    When ``gds_out`` is set (with ``try_full_route``), the driver writes the
    routed layout GDS for headless DRC.
    """
    pin = check_lidar_gf_pin(lidar_python)
    export = to_lidar_yaml(store, design=design)
    if pin.lidar_python and pin.lidar_import_ok:
        driver = Path(__file__).resolve().parent / "lidar_driver.py"
        lidar_src = Path(__file__).resolve().parents[3] / ".lidar_env" / "LiDAR" / "src"
        env = os.environ.copy()
        env["PYTHONPATH"] = (
            f"{lidar_src}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
        )
        requested_gds: Optional[Path] = (
            Path(gds_out).resolve() if gds_out is not None else None
        )
        if requested_gds is not None:
            requested_gds.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix="picasso_lidar_") as td:
                ypath = Path(td) / f"{design}.yml"
                ypath.write_text(export.yaml_text)
                # Write into the caller's path when given; else a temp GDS
                # (discarded with the TemporaryDirectory unless copied by caller).
                gds_arg = (
                    str(requested_gds)
                    if requested_gds is not None
                    else (str(Path(td) / f"{design}.gds") if try_full_route else None)
                )
                cmd = [pin.lidar_python, str(driver), str(ypath)]
                if try_full_route:
                    cmd.append("--route")
                if gds_arg is not None:
                    cmd.extend(["--gds-out", gds_arg])
                proc = subprocess.run(
                    cmd,
                    text=True,
                    capture_output=True,
                    timeout=600,
                    env=env,
                    cwd=str(lidar_src.parent) if lidar_src.is_dir() else None,
                )
            # Driver may leak PICRoute banners before JSON; take last JSON object.
            raw_out = (proc.stdout or "").strip()
            payload: Dict[str, Any] = {}
            if raw_out:
                try:
                    payload = json.loads(raw_out)
                except json.JSONDecodeError:
                    # Scan for last line that looks like a JSON object
                    for line in reversed(raw_out.splitlines()):
                        line = line.strip()
                        if line.startswith("{") and line.endswith("}"):
                            try:
                                payload = json.loads(line)
                                break
                            except json.JSONDecodeError:
                                continue
            metrics: Dict[Tuple[str, str, str, str], RouteMetrics] = {}
            for row in payload.get("metrics") or []:
                key = (
                    str(row["src"]),
                    str(row["src_port"]),
                    str(row["dst"]),
                    str(row["dst_port"]),
                )
                n_bends = int(row.get("n_bends") or 0)
                bend_angle = float(row.get("bend_angle_rad") or 0.0)
                if not bend_angle and n_bends:
                    bend_angle = n_bends * (3.141592653589793 / 2.0)
                metrics[key] = RouteMetrics(
                    length_um=float(row.get("length_um", 0.0)),
                    loss_dB=row.get("il_db"),
                    n_crossings=int(row.get("n_crossings") or 0),
                    n_bends=n_bends,
                    bend_angle_rad=bend_angle,
                    bend_radius_um=float(row.get("bend_radius_um") or 0.0),
                )
            mode = str(payload.get("mode") or "lidar")
            resolved_gds: Optional[str] = None
            if requested_gds is not None and requested_gds.is_file():
                resolved_gds = str(requested_gds)
            elif payload.get("gds_path") and Path(str(payload["gds_path"])).is_file():
                resolved_gds = str(payload["gds_path"])
            # Full-route path: require gf_curvy (or picroute) success when
            # allow_stub=False — do not silently accept Manhattan fallback.
            if try_full_route and not allow_stub:
                if mode in ("lidar_ir_manhattan", "lidar_ir_manhattan_after_route_fail"):
                    return LidarRouteResult(
                        ok=False,
                        metrics=metrics,
                        gds_path=resolved_gds,
                        detail=(
                            f"curvy route failed (mode={mode}): "
                            f"{payload.get('route_error') or payload.get('error')}; "
                            f"gf_errors={payload.get('gf_route_errors') or payload.get('route_errors')}"
                        ),
                    )
                if not payload.get("ok", True) or not metrics:
                    return LidarRouteResult(
                        ok=False,
                        gds_path=resolved_gds,
                        detail=f"LiDAR curvy driver failed: {payload}",
                    )
            if metrics:
                apply_route_metrics(store, metrics, agent="lidar_wrap")
                return LidarRouteResult(
                    ok=True,
                    metrics=metrics,
                    il_max_db=payload.get("il_max_db"),
                    wirelength_um=payload.get("wirelength_um"),
                    yaml_out=export.yaml_text,
                    gds_path=resolved_gds,
                    banner=(
                        f"LiDAR wrap ({mode}) — cite ScopeX-ASU/LiDAR; "
                        "not our curvy-router novelty"
                    ),
                    detail=(
                        f"{pin.detail}; mode={mode}; "
                        f"n_bends={sum(m.n_bends for m in metrics.values())}; "
                        f"n_crossings={sum(m.n_crossings for m in metrics.values())}; "
                        f"stderr={(proc.stderr or '')[:200]}"
                    ),
                )
            # Empty metrics but pin ok — fall through with better detail
            if not allow_stub:
                return LidarRouteResult(
                    ok=False,
                    detail=f"LiDAR driver returned no metrics: {payload}",
                )
            stub_detail = f"{pin.detail}; driver={payload}"
        except Exception as e:
            if not allow_stub:
                return LidarRouteResult(ok=False, detail=f"LiDAR invoke failed: {e}")
            stub_detail = f"{pin.detail}; invoke_error={e}"
    else:
        stub_detail = pin.detail or "LiDAR env unavailable"

    if not allow_stub:
        return LidarRouteResult(ok=False, detail=stub_detail)

    metrics = _manhattan_stub_metrics(store)
    apply_route_metrics(store, metrics, agent="lidar_wrap_stub")
    wl = sum(m.length_um for m in metrics.values())
    return LidarRouteResult(
        ok=True,
        metrics=metrics,
        il_max_db=None,
        wirelength_um=wl,
        yaml_out=export.yaml_text,
        banner=(
            "LiDAR wrap STUB (PCG Manhattan estimator) — cite LiDAR when "
            "driver metrics land"
        ),
        detail=stub_detail,
    )


def fidelity_vs_routed(
    predicted_um: Dict[Tuple[str, str, str, str], float],
    routed: Dict[Tuple[str, str, str, str], RouteMetrics],
    *,
    mae_um_threshold: float = 25.0,
) -> Dict[str, Any]:
    """Compare estimator predictions to routed lengths; gate ESTIMATOR_ONLY drop."""
    errs = []
    for key, ref in routed.items():
        pred = predicted_um.get(key) or predicted_um.get(
            (key[2], key[3], key[0], key[1])
        )
        if pred is None:
            continue
        errs.append(abs(float(pred) - float(ref.length_um)))
    mae = float(sum(errs) / len(errs)) if errs else float("inf")
    drop_banner = mae <= mae_um_threshold and len(errs) > 0
    return {
        "mae_um": mae,
        "n": len(errs),
        "threshold_um": mae_um_threshold,
        "drop_estimator_only": drop_banner,
        "lidar_repo": LIDAR_GITHUB_REPO,
        "lidar_commit": LIDAR_SCHEMA_COMMIT,
    }
