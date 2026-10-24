"""L3 physical-closure harness for PIC-Bench-48 (DAC paper table).

For every golden ``fixtures/picset/task_XX.yaml``:

1. Baseline: layout-blind placer (λ_F=0, λ_φ=0) → LiDAR curvy route → SPA WNS
2. Optimized: torch placer (λ_F>0, λ_φ>0) → LiDAR curvy route → SPA WNS

WNS uses inferred reconvergent path groups at ``SPA_TOL_RAD = 0.05``.

Placement budgets scale with ``n_nodes`` so O(n²) density / FD grads finish
on large Clements meshes; each arm is wall-clock capped.

CLI::

    python -m gd_picasso.pcg.run_dac_harness
    python -m gd_picasso.pcg.run_dac_harness --out dac_physical_results.csv
"""

from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
import os
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from gd_picasso.pcg.bridge import from_gf_yaml
from gd_picasso.pcg.place.objective import ObjectiveWeights
from gd_picasso.pcg.place.optimize import place_multistart
from gd_picasso.pcg.place.tensors import build_placement_problem
from gd_picasso.pcg.place.torch_placer import place_torch
from gd_picasso.pcg.route.lidar_wrap import route_with_lidar
from gd_picasso.pcg.spa import spa_analyze
from gd_picasso.pcg.spa_protocol import SPA_TOL_RAD
from gd_picasso.pcg.store import PCGStore

_REPO = Path(__file__).resolve().parents[2]
PICSET = Path(__file__).resolve().parent / "fixtures" / "picset"
DEFAULT_OUT = _REPO / "dac_physical_results.csv"

# Baseline: layout-blind (no phase / FoM pressure).
W_BASELINE = ObjectiveWeights(lambda_D=0.05, lambda_phi=0.0, lambda_F=0.0, alpha=1.4)
# Optimized: differentiable torch FoM + phase matching + X-stage runway.
W_OPTIMIZED = ObjectiveWeights(
    lambda_D=0.05,
    lambda_phi=1.0,
    lambda_F=1.0,
    lambda_x_stage=25.0,
    x_stage_gap_um=150.0,
    alpha=1.4,
)

# Soft wall-clock per place+route arm (seconds).
ARM_TIMEOUT_S = 240


@dataclass
class HarnessRow:
    task_id: int
    n_nodes: int
    n_groups: int
    baseline_ok: bool
    baseline_wns: Optional[float]
    baseline_detail: str
    optimized_ok: bool
    optimized_wns: Optional[float]
    optimized_detail: str
    delta_wns: Optional[float]

    def to_csv_row(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "n_nodes": self.n_nodes,
            "n_groups": self.n_groups,
            "baseline_ok": int(self.baseline_ok),
            "baseline_wns": "" if self.baseline_wns is None else f"{self.baseline_wns:.6g}",
            "baseline_detail": self.baseline_detail,
            "optimized_ok": int(self.optimized_ok),
            "optimized_wns": "" if self.optimized_wns is None else f"{self.optimized_wns:.6g}",
            "optimized_detail": self.optimized_detail,
            "delta_wns": "" if self.delta_wns is None else f"{self.delta_wns:.6g}",
        }


def _placement_budget(n_nodes: int) -> Tuple[int, int, int]:
    """Return (n_starts, baseline_steps, torch_steps) scaled by circuit size."""
    if n_nodes <= 40:
        return 3, 30, 40
    if n_nodes <= 80:
        return 2, 20, 25
    if n_nodes <= 160:
        return 1, 12, 15
    return 1, 6, 8


def _spa_wns(store: PCGStore) -> Tuple[Optional[float], int, str]:
    problem = build_placement_problem(store)
    groups: Dict[str, List[List[str]]] = {}
    for g in problem.phase_groups:
        if g.arm_paths and len(g.arm_paths) >= 2:
            groups[g.group_id] = [list(p) for p in g.arm_paths]
    if not groups:
        return None, 0, "no_reconvergent_groups"
    try:
        report = spa_analyze(store, groups, tolerance_rad=SPA_TOL_RAD)
        return float(report.wns_rad), len(report.groups), "spa_ok"
    except Exception as exc:  # noqa: BLE001
        return None, len(groups), f"spa_error:{type(exc).__name__}:{exc}"


def _place_and_route(
    store: PCGStore,
    *,
    weights: ObjectiveWeights,
    use_torch: bool,
    design: str,
    n_starts: int,
    steps: int,
) -> Tuple[bool, Optional[float], int, str]:
    """Place → LiDAR full route → SPA WNS. Mutates ``store`` in place."""
    try:
        if use_torch:
            place_torch(store, weights=weights, steps=steps, lr=2.0, write_back=True)
        else:
            place_multistart(
                store,
                weights=weights,
                n_starts=n_starts,
                steps=steps,
                lr=1.5,
                write_back=True,
            )
    except Exception as exc:  # noqa: BLE001
        return False, None, 0, f"place_error:{type(exc).__name__}:{exc}"

    try:
        routed = route_with_lidar(
            store,
            design=design,
            try_full_route=True,
            allow_stub=False,
        )
    except Exception as exc:  # noqa: BLE001
        return False, None, 0, f"route_exc:{type(exc).__name__}:{exc}"

    if not routed.ok:
        return False, None, 0, f"route_fail:{routed.detail}"

    wns, n_groups, detail = _spa_wns(store)
    return True, wns, n_groups, detail


def _arm_worker(
    yaml_text: str,
    *,
    use_torch: bool,
    design: str,
    n_starts: int,
    steps: int,
    q: "mp.Queue[Tuple[bool, Optional[float], int, str]]",
) -> None:
    lidar_py = _REPO / ".lidar_env" / "venv" / "bin" / "python"
    if lidar_py.is_file() and not os.environ.get("PICASSO_LIDAR_PYTHON"):
        os.environ["PICASSO_LIDAR_PYTHON"] = str(lidar_py)
    try:
        store = from_gf_yaml(yaml_text)
        weights = W_OPTIMIZED if use_torch else W_BASELINE
        result = _place_and_route(
            store,
            weights=weights,
            use_torch=use_torch,
            design=design,
            n_starts=n_starts,
            steps=steps,
        )
        q.put(result)
    except Exception as exc:  # noqa: BLE001
        q.put((False, None, 0, f"worker_exc:{type(exc).__name__}:{exc}"))


def _run_arm_with_timeout(
    yaml_text: str,
    *,
    use_torch: bool,
    design: str,
    n_starts: int,
    steps: int,
    timeout_s: int = ARM_TIMEOUT_S,
) -> Tuple[bool, Optional[float], int, str]:
    ctx = mp.get_context("spawn")
    q: mp.Queue = ctx.Queue()
    proc = ctx.Process(
        target=_arm_worker,
        args=(yaml_text,),
        kwargs={
            "use_torch": use_torch,
            "design": design,
            "n_starts": n_starts,
            "steps": steps,
            "q": q,
        },
    )
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(10)
        if proc.is_alive():
            proc.kill()
            proc.join(5)
        return False, None, 0, f"timeout:{timeout_s}s"
    if not q.empty():
        return q.get()
    code = proc.exitcode
    return False, None, 0, f"worker_exit:{code}"


def golden_task_ids() -> List[int]:
    ids = []
    for path in sorted(PICSET.glob("task_*.yaml")):
        if path.name.endswith("_lidar.yaml"):
            continue
        try:
            tid = int(path.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        ids.append(tid)
    return ids


def _load_done(path: Path) -> Dict[int, HarnessRow]:
    done: Dict[int, HarnessRow] = {}
    if not path.is_file():
        return done
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            tid = int(row["task_id"])
            def _f(key: str) -> Optional[float]:
                v = row.get(key, "")
                return None if v in ("", None) else float(v)

            done[tid] = HarnessRow(
                task_id=tid,
                n_nodes=int(row.get("n_nodes") or 0),
                n_groups=int(row.get("n_groups") or 0),
                baseline_ok=bool(int(row.get("baseline_ok") or 0)),
                baseline_wns=_f("baseline_wns"),
                baseline_detail=row.get("baseline_detail") or "",
                optimized_ok=bool(int(row.get("optimized_ok") or 0)),
                optimized_wns=_f("optimized_wns"),
                optimized_detail=row.get("optimized_detail") or "",
                delta_wns=_f("delta_wns"),
            )
    return done


def _write_csv(path: Path, rows: Sequence[HarnessRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].to_csv_row().keys()) if rows else [
        "task_id",
        "n_nodes",
        "n_groups",
        "baseline_ok",
        "baseline_wns",
        "baseline_detail",
        "optimized_ok",
        "optimized_wns",
        "optimized_detail",
        "delta_wns",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r.to_csv_row())


def run_harness(
    *,
    task_ids: Optional[Sequence[int]] = None,
    out_path: Path = DEFAULT_OUT,
    resume: bool = True,
) -> List[HarnessRow]:
    # Prefer dedicated LiDAR env python when present.
    lidar_py = _REPO / ".lidar_env" / "venv" / "bin" / "python"
    if lidar_py.is_file() and not os.environ.get("PICASSO_LIDAR_PYTHON"):
        os.environ["PICASSO_LIDAR_PYTHON"] = str(lidar_py)

    ids = list(task_ids) if task_ids is not None else golden_task_ids()
    done = _load_done(out_path) if resume else {}
    rows_by_id: Dict[int, HarnessRow] = dict(done)

    for tid in ids:
        if tid in rows_by_id and rows_by_id[tid].baseline_detail != "incomplete":
            # Skip finished rows; re-run timeouts / incomplete.
            det = rows_by_id[tid]
            if "timeout" not in det.baseline_detail and "timeout" not in det.optimized_detail:
                print(f"[dac] task {tid:02d} skip (cached)", flush=True)
                continue
        path = PICSET / f"task_{tid:02d}.yaml"
        if not path.is_file():
            rows_by_id[tid] = HarnessRow(
                task_id=tid,
                n_nodes=0,
                n_groups=0,
                baseline_ok=False,
                baseline_wns=None,
                baseline_detail="missing_fixture",
                optimized_ok=False,
                optimized_wns=None,
                optimized_detail="missing_fixture",
                delta_wns=None,
            )
            continue
        text = path.read_text(encoding="utf-8")
        n_nodes = len(from_gf_yaml(text).nodes)
        n_starts, base_steps, torch_steps = _placement_budget(n_nodes)
        print(
            f"[dac] task {tid:02d} n={n_nodes} "
            f"budget=({n_starts},{base_steps},{torch_steps}) …",
            flush=True,
        )

        b_ok, b_wns, b_ng, b_det = _run_arm_with_timeout(
            text,
            use_torch=False,
            design=f"dac_base_{tid:02d}",
            n_starts=n_starts,
            steps=base_steps,
        )
        o_ok, o_wns, o_ng, o_det = _run_arm_with_timeout(
            text,
            use_torch=True,
            design=f"dac_opt_{tid:02d}",
            n_starts=1,
            steps=torch_steps,
        )
        n_groups = max(b_ng, o_ng)
        delta = None
        if b_wns is not None and o_wns is not None:
            delta = o_wns - b_wns  # positive ⇒ optimized improved slack
        rows_by_id[tid] = HarnessRow(
            task_id=tid,
            n_nodes=n_nodes,
            n_groups=n_groups,
            baseline_ok=b_ok,
            baseline_wns=b_wns,
            baseline_detail=b_det,
            optimized_ok=o_ok,
            optimized_wns=o_wns,
            optimized_detail=o_det,
            delta_wns=delta,
        )
        print(
            f"  base_wns={b_wns} opt_wns={o_wns} Δ={delta} "
            f"base_ok={b_ok} opt_ok={o_ok}",
            flush=True,
        )
        # Checkpoint after every task.
        ordered = [rows_by_id[i] for i in ids if i in rows_by_id]
        _write_csv(out_path, ordered)

    rows = [rows_by_id[i] for i in ids if i in rows_by_id]
    _write_csv(out_path, rows)
    _print_wns_summary(rows)
    print(f"wrote {out_path}")
    return rows


def _print_wns_summary(rows: Sequence[HarnessRow]) -> None:
    deltas = [r.delta_wns for r in rows if r.delta_wns is not None]
    print("=== DAC physical WNS summary ===")
    print(f"  tasks_total={len(rows)}")
    print(f"  tasks_with_both_wns={len(deltas)}")
    if deltas:
        mean_delta = sum(deltas) / len(deltas)
        print(f"  mean_delta_wns (opt − base) = {mean_delta:.6g} rad")
        print(f"  (positive ⇒ torch placer improved slack vs baseline)")
        improved = sum(1 for d in deltas if d > 0)
        print(f"  improved_count={improved}/{len(deltas)}")
    else:
        print("  mean_delta_wns = n/a (no paired WNS)")


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="DAC L3 physical-closure harness")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument(
        "--tasks",
        type=str,
        default=None,
        help="Comma-separated task ids (default: all golden GF fixtures)",
    )
    p.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore existing CSV and recompute all tasks",
    )
    args = p.parse_args(argv)
    task_ids = None
    if args.tasks:
        task_ids = [int(x) for x in args.tasks.split(",") if x.strip()]
    try:
        run_harness(
            task_ids=task_ids,
            out_path=args.out,
            resume=not args.no_resume,
        )
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
