"""
PIC-Set 36 end-to-end + agent triage + DRC/LVS + φ ablation.

Pipeline per task
-----------------
1. A0 IntentAgent on Pic_set / fixture name
2. Load GF YAML (prefer) or LiDAR IR → PCGStore
3. A1 ExactCritic → A4 TriageAgent on failures
4. Route / back-annotate lengths
5. DRC (generic_tech KLayout batch) on GF builds
6. Connectivity check (PCG ↔ GF netlist; not device-level foundry LVS)
6b. SiEPIC report column = SKIP(no emitter); sky130 dropped from PIC gate
7. SPA when reconvergent groups exist
8. φ ablation (W_cos+D vs +λ_φ) when phase groups eligible

**Important — use the gate venv (gdsfactory 9.23), not LiDAR's venv:**

.. code-block:: bash

   # deactivate LiDAR / .lidar_env/venv first if prompt shows (venv)
   source .venv/bin/activate          # prompt should be (.venv) — gf 9.23.0
   export PICASSO_LIDAR_PYTHON=$PWD/.lidar_env/venv/bin/python
   export PYTHONPATH=$PWD/.lidar_env/LiDAR/src:$PYTHONPATH
   python -m gd_picasso.pcg.test_picset36_e2e

``.lidar_env/venv`` is gf **8.26.1** and raises ``Routing collision`` on these
fixtures. LiDAR is only invoked via ``PICASSO_LIDAR_PYTHON`` subprocess.
"""

from __future__ import annotations

import os
import re
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gdsfactory as gf
import pytest
import yaml

# Suppress klive show() spam during batch builds (same as test_with_llm.py)
try:
    import kfactory
    import kfactory.kcell as _kc

    kfactory.show = lambda *a, **kw: None  # type: ignore[assignment]
    _kc.show = lambda *a, **kw: None  # type: ignore[assignment]
except Exception:
    pass

from gd_picasso.agents.exact_critic import ExactCritic
from gd_picasso.agents.intent_agent import IntentAgent
from gd_picasso.agents.state_machine import AgentStateMachine
from gd_picasso.agents.triage_agent import TriageAgent
from gd_picasso.pcg import from_gf_yaml
from gd_picasso.pcg.gf_route_metrics import backannotate_from_yaml
from gd_picasso.pcg.lidar_ir import from_lidar_yaml
from gd_picasso.pcg.place.estimator_fidelity import phi_ablation_eligible
from gd_picasso.pcg.place.objective import ObjectiveWeights, evaluate_objective
from gd_picasso.pcg.place.tensors import build_placement_problem
from gd_picasso.pcg.route import check_lidar_gf_pin, route_with_lidar
from gd_picasso.pcg.spa import spa_analyze
from gd_picasso.pcg.spa_protocol import SPA_TOL_RAD
from gd_picasso.pcg.store import PCGStore
from gd_picasso.pcg.types import EdgeLayer
from gd_picasso.validators.drc_validator import DRCValidator
from gd_picasso.validators.lvs_validator import LVSValidator

PICSET = Path(__file__).resolve().parent / "fixtures" / "picset"
PIC_SET_TXT = Path(__file__).resolve().parents[2] / "Pic_set.txt"
TOL_RAD = SPA_TOL_RAD
GATE_GF_PIN = "9.23.0"


def _assert_gate_gdsfactory() -> None:
    """Fail fast if someone activated ``.lidar_env/venv`` (gf 8.26.1)."""
    ver = getattr(gf, "__version__", "?")
    if ver != GATE_GF_PIN:
        raise RuntimeError(
            f"Wrong Python/gdsfactory for PIC-Set e2e: got gdsfactory=={ver} "
            f"(exe={sys.executable}). Need the gate env with "
            f"gdsfactory=={GATE_GF_PIN}.\n"
            f"  deactivate   # if prompt is (venv) from .lidar_env/venv\n"
            f"  source .venv/bin/activate   # expect (.venv)\n"
            f"  python -c \"import gdsfactory as gf; print(gf.__version__)\"  "
            f"# → {GATE_GF_PIN}\n"
            f"LiDAR stays isolated via PICASSO_LIDAR_PYTHON only."
        )

PARTITION: Dict[int, str] = {
    1: "expressible",
    2: "expressible",
    3: "expressible",
    4: "partial",
    5: "non_expressible",
    6: "non_expressible",
    7: "non_expressible",
    8: "non_expressible",
    9: "expressible",
    10: "expressible",
    11: "expressible",
    12: "expressible",
    13: "expressible",
    14: "expressible",
    15: "expressible",
    16: "expressible",
    17: "expressible",
    18: "expressible",
    19: "expressible",
    20: "expressible",
    21: "expressible",
    22: "expressible",
    23: "non_expressible",
    24: "non_expressible",
    25: "non_expressible",
    26: "expressible",
    27: "expressible",
    28: "non_expressible",
    29: "expressible",
    30: "expressible_trivial",
    31: "non_expressible",
    32: "expressible",
    33: "partial",
    34: "expressible_trivial",
    35: "expressible_trivial",
    36: "expressible_trivial",
}


def _load_problem_texts() -> Dict[int, str]:
    texts: Dict[int, str] = {}
    if not PIC_SET_TXT.is_file():
        return texts
    raw = PIC_SET_TXT.read_text(encoding="utf-8")
    parts = re.split(r"(?=^Problem \d+)", raw, flags=re.M)
    for block in parts:
        m = re.match(r"Problem (\d+)", block.strip())
        if m:
            texts[int(m.group(1))] = block.strip()[:4000]
    return texts


PROBLEM_TEXTS = _load_problem_texts()


@dataclass
class TaskResult:
    task_id: int
    partition: str
    source: str
    ok: bool
    n_nodes: int = 0
    n_edges: int = 0
    n_routed: int = 0
    wirelength_um: Optional[float] = None
    spa_wns: Optional[float] = None
    spa_groups: int = 0
    intent_program: str = ""
    critic_ok: Optional[bool] = None
    triage_next: str = ""
    drc_pass: Optional[bool] = None
    drc_mode: str = ""
    drc_violations: int = 0
    lvs_pass: Optional[bool] = None
    lvs_mode: str = ""
    # Report-only PDK deck probes (not gate)
    siepic_drc: str = ""  # SKIP(no emitter) | n/a
    siepic_markers: int = 0
    ablation: str = ""  # n/a | pass | fail | skip
    phi_geo: Optional[float] = None
    phi_with: Optional[float] = None
    detail: str = ""
    error: str = ""


def _optical_edges(store: PCGStore):
    return [e for e in store.edges if e.layer == EdgeLayer.OPTICAL]


def _spa_from_inferred(store: PCGStore) -> Tuple[Optional[float], int, str]:
    problem = build_placement_problem(store)
    groups: Dict[str, List[List[str]]] = {}
    for g in problem.phase_groups:
        if g.arm_paths and len(g.arm_paths) >= 2:
            groups[g.group_id] = [list(p) for p in g.arm_paths]
    if not groups:
        return None, 0, "no_reconvergent_groups"
    report = spa_analyze(store, groups, tolerance_rad=TOL_RAD)
    return float(report.wns_rad), len(report.groups), "spa_ok"


def _run_agents(store: PCGStore, task_id: int, name: str) -> Dict[str, Any]:
    """A0 intent → ExactCritic → A4 triage (plus DRC/LVS failures later)."""
    sm = AgentStateMachine(store=store)
    problem = PROBLEM_TEXTS.get(task_id) or f"{name} photonic circuit task {task_id}"
    intent = sm.run_intent(problem)
    critic = ExactCritic().review(store)
    failures = sm.critique_to_failures(critic)
    triage = sm.triage_failures(failures)
    return {
        "intent": intent,
        "critic": critic,
        "triage": triage,
        "failures": failures,
    }


def _run_phi_ablation(store: PCGStore) -> Dict[str, Any]:
    """Compare W_cos+D vs +λ_φ from the *same* skewed seed (clean ablation)."""
    from copy import deepcopy

    from gd_picasso.pcg.place.optimize import _gd_one

    st = deepcopy(store)
    problem0 = build_placement_problem(st)
    if not phi_ablation_eligible(problem0):
        return {"status": "n/a", "reason": "no_phase_groups"}

    # Asymmetric X/Y like mzi_unbalanced.yaml (pure ±Y cancels in estimator)
    for g in problem0.phase_groups:
        if not g.arm_paths or len(g.arm_paths) < 2:
            continue
        for k, path in enumerate(g.arm_paths[:2]):
            if len(path) < 2:
                continue
            node = st.nodes.get(path[1])
            if node is None:
                continue
            if node.x is not None:
                node.x = float(node.x) + (40.0 if k == 0 else -20.0)
            if node.y is not None:
                node.y = float(node.y) + (45.0 if k == 0 else -15.0)

    problem = build_placement_problem(st)
    start = evaluate_objective(problem)
    if start.phi_sq < 1e-3:
        return {
            "status": "skip",
            "reason": "cannot_unbalance",
            "phi_geo": float(start.phi_sq),
        }

    xy0 = problem.xy.copy()
    theta = problem.theta_rad.copy()
    w_geo = ObjectiveWeights(lambda_D=0.05, lambda_phi=0.0, alpha=1.4)
    w_phi = ObjectiveWeights(lambda_D=0.05, lambda_phi=5e-4, alpha=1.4)
    xy_geo, _ = _gd_one(problem, xy0, theta, w_geo, steps=40, lr=1.5)
    xy_phi, _ = _gd_one(problem, xy0, theta, w_phi, steps=40, lr=1.5)
    # Report φ under identical weights (φ term itself is weight-independent)
    t_geo = evaluate_objective(problem, xy_geo, theta, w_geo)
    t_phi = evaluate_objective(problem, xy_phi, theta, w_geo)
    ok = t_phi.phi_sq <= t_geo.phi_sq + 1e-6
    return {
        "status": "pass" if ok else "fail",
        "phi_geo": float(t_geo.phi_sq),
        "phi_with": float(t_phi.phi_sq),
        "phi_start": float(start.phi_sq),
    }


def _pdk_status(res: Any) -> str:
    if res is None:
        return "n/a"
    st = getattr(res, "status", None)
    if st:
        return str(st)
    if not getattr(res, "ran", False):
        return "n/a"
    if res.passed is True:
        return "PASS"
    if res.passed is False:
        return "FAIL"
    return "n/a"


def _drc_lvs_gf(yaml_text: str, store: PCGStore) -> Dict[str, Any]:
    import tempfile

    import gdsfactory as gf

    from gd_picasso.validators.pdk_deck_runner import pic_gate_pdk_probes

    out: Dict[str, Any] = {
        "drc_pass": None,
        "drc_mode": "skip",
        "drc_violations": 0,
        "lvs_pass": None,
        "lvs_mode": "skip",
        "siepic_drc": "skip",
        "siepic_markers": 0,
        "failures": [],
    }
    try:
        c = gf.read.from_yaml(yaml_text)
    except Exception as e:
        out["drc_pass"] = False
        out["lvs_pass"] = False
        out["failures"].append(
            {
                "kind": "drc",
                "elements": [],
                "evidence": {"build_error": str(e)},
            }
        )
        return out

    with tempfile.NamedTemporaryFile(suffix=".gds", delete=False) as tmp:
        gds_path = tmp.name
    try:
        c.write_gds(gds_path)
        drc = DRCValidator()
        drc_ok, drc_rep = drc.validate(c, gds_path=gds_path)
        out["drc_pass"] = bool(drc_ok)
        out["drc_mode"] = str(
            drc_rep.get("drc_mode") or ("klayout" if drc_ok else "fail")
        )
        out["drc_violations"] = int(drc_rep.get("violations") or 0)
        if not drc_ok:
            out["failures"].append(
                {
                    "kind": "drc",
                    "elements": [],
                    "evidence": {
                        "violations": out["drc_violations"],
                        "errors": drc_rep.get("errors"),
                    },
                }
            )

        # Four-state: SiEPIC SKIP(no emitter); sky130 dropped from PIC gate
        if os.environ.get("PICASSO_PDK_PROBE", "1") != "0":
            sie = pic_gate_pdk_probes().get("siepic_ebeam")
            out["siepic_drc"] = _pdk_status(sie)
            out["siepic_markers"] = 0
    finally:
        try:
            os.unlink(gds_path)
        except OSError:
            pass

    lvs = LVSValidator(enabled=True)
    lvs_ok, lvs_rep = lvs.validate_connectivity(store, c)
    out["lvs_pass"] = bool(lvs_ok)
    out["lvs_mode"] = str(lvs_rep.get("lvs_mode") or "connectivity")
    if not lvs_ok:
        out["failures"].append(
            {
                "kind": "port",
                "elements": list(
                    lvs_rep.get("mismatches", {}).get("missing_in_layout") or []
                ),
                "evidence": {"lvs": lvs_rep.get("errors")},
            }
        )
    return out


def _fixture_name(path: Path) -> str:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        info = doc.get("info") or {}
        return str(info.get("picset_name") or path.stem)
    except Exception:
        return path.stem


def run_gf_task(task_id: int, path: Path) -> TaskResult:
    _assert_gate_gdsfactory()
    part = PARTITION[task_id]
    text = path.read_text(encoding="utf-8")
    name = _fixture_name(path)
    store = from_gf_yaml(text)
    edges = _optical_edges(store)

    agent = _run_agents(store, task_id, name)
    try:
        n = backannotate_from_yaml(store, text)
    except RuntimeError as e:
        if "routing collision" in str(e).lower():
            raise RuntimeError(
                f"{e}\nHint: this usually means gdsfactory!=9.23.0 "
                f"(got {gf.__version__} at {sys.executable}). "
                f"Use `source .venv/bin/activate`, not `.lidar_env/venv`."
            ) from e
        raise
    routed = [e for e in edges if e.length_um is not None and float(e.length_um) > 0]
    wl = sum(float(e.length_um or 0) for e in routed) or None
    wns, ng, spa_detail = _spa_from_inferred(store)

    phys = _drc_lvs_gf(text, store)
    # Re-triage with DRC/LVS failures
    if phys["failures"]:
        triage2 = TriageAgent().triage(store, phys["failures"])
        triage_next = triage2.reinvoke
        triage_summary = triage2.summary
    else:
        triage_next = agent["triage"].reinvoke
        triage_summary = agent["triage"].summary

    abl = _run_phi_ablation(store)
    if abl.get("status") == "fail":
        phys["failures"].append(
            {
                "kind": "phase",
                "elements": [],
                "evidence": {
                    "phi_geo": abl.get("phi_geo"),
                    "phi_with": abl.get("phi_with"),
                },
            }
        )
        triage2 = TriageAgent().triage(store, phys["failures"])
        triage_next = triage2.reinvoke
        triage_summary = triage2.summary

    # ExactCritic dangling on exported I/O is expected for incomplete PDK maps;
    # hard-fail only on unknown components / degree errors / DRC / LVS.
    # φ ablation fail is reported + A4→A3, but does not fail the layout gate.
    critic = agent["critic"]
    hard_critic = [
        p
        for p in critic.problems
        if "Unknown component" in p or "has degree" in p
    ]
    ok = (
        not hard_critic
        and phys["drc_pass"] is not False
        and phys["lvs_pass"] is not False
    )
    if edges and n == 0 and not routed and len(store.nodes) > 1:
        ok = False

    return TaskResult(
        task_id=task_id,
        partition=part,
        source="gf",
        ok=ok,
        n_nodes=len(store.nodes),
        n_edges=len(edges),
        n_routed=len(routed),
        wirelength_um=wl,
        spa_wns=wns,
        spa_groups=ng,
        intent_program=str(agent["intent"].topology_program or "none"),
        critic_ok=bool(critic.ok),
        triage_next=triage_next,
        drc_pass=phys["drc_pass"],
        drc_mode=phys["drc_mode"],
        drc_violations=phys["drc_violations"],
        lvs_pass=phys["lvs_pass"],
        lvs_mode=phys["lvs_mode"],
        siepic_drc=str(phys.get("siepic_drc") or "skip"),
        siepic_markers=int(phys.get("siepic_markers") or 0),
        ablation=str(abl.get("status")),
        phi_geo=abl.get("phi_geo"),
        phi_with=abl.get("phi_with"),
        detail=f"backannot={n}; {spa_detail}; triage={triage_summary}",
    )


def run_lidar_task(task_id: int, path: Path) -> TaskResult:
    part = PARTITION[task_id]
    pin = check_lidar_gf_pin()
    text = path.read_text(encoding="utf-8")
    name = _fixture_name(path)
    store = from_lidar_yaml(text)
    edges = _optical_edges(store)
    agent = _run_agents(store, task_id, name)

    routed = route_with_lidar(
        store,
        design=f"picset_{task_id:02d}",
        allow_stub=not pin.lidar_import_ok,
    )
    wl = routed.wirelength_um
    n_routed = len(routed.metrics)
    wns, ng, spa_detail = _spa_from_inferred(store)
    abl = _run_phi_ablation(store)

    # LiDAR stubs: no GF GDS → DRC/LVS soft-skip (not claimed)
    critic = agent["critic"]
    hard_critic = [
        p
        for p in critic.problems
        if "Unknown component" in p or "has degree" in p
    ]
    ok = (
        routed.ok
        and not hard_critic
    )
    return TaskResult(
        task_id=task_id,
        partition=part,
        source="lidar",
        ok=ok,
        n_nodes=len(store.nodes),
        n_edges=len(edges),
        n_routed=n_routed,
        wirelength_um=wl,
        spa_wns=wns,
        spa_groups=ng,
        intent_program=str(agent["intent"].topology_program or "none"),
        critic_ok=bool(critic.ok),
        triage_next=agent["triage"].reinvoke,
        drc_pass=None,
        drc_mode="n/a_lidar_stub",
        drc_violations=0,
        lvs_pass=None,
        lvs_mode="n/a_lidar_stub",
        siepic_drc="SKIP",
        siepic_markers=0,
        ablation=str(abl.get("status")),
        phi_geo=abl.get("phi_geo"),
        phi_with=abl.get("phi_with"),
        detail=f"{routed.banner}; {spa_detail}",
    )


def run_task(task_id: int) -> TaskResult:
    gf = PICSET / f"task_{task_id:02d}.yaml"
    lid = PICSET / f"task_{task_id:02d}_lidar.yaml"
    try:
        if gf.is_file():
            return run_gf_task(task_id, gf)
        if lid.is_file():
            return run_lidar_task(task_id, lid)
        return TaskResult(
            task_id=task_id,
            partition=PARTITION.get(task_id, "?"),
            source="missing",
            ok=False,
            error="no fixture",
        )
    except Exception as e:
        return TaskResult(
            task_id=task_id,
            partition=PARTITION.get(task_id, "?"),
            source="gf" if gf.is_file() else "lidar",
            ok=False,
            error=f"{type(e).__name__}: {e}",
            detail=traceback.format_exc(limit=4),
        )


def run_all() -> List[TaskResult]:
    _assert_gate_gdsfactory()
    return [run_task(i) for i in range(1, 37)]


def format_report(results: List[TaskResult]) -> str:
    lines = [
        f"{'#':>2} {'part':<18} {'src':<5} {'ok':<4} "
        f"{'A0':<18} {'crit':<4} {'A4':<4} "
        f"{'DRC':<4} {'LVS':<4} {'SiEPIC':<7} {'abl':<5} "
        f"{'WNS':>8} detail"
    ]
    lines.append("-" * 120)
    for r in results:
        wns = f"{r.spa_wns:.3g}" if r.spa_wns is not None else "-"
        drc = (
            "PASS"
            if r.drc_pass is True
            else ("FAIL" if r.drc_pass is False else "n/a")
        )
        lvs = (
            "PASS"
            if r.lvs_pass is True
            else ("FAIL" if r.lvs_pass is False else "n/a")
        )
        crit = (
            "ok"
            if r.critic_ok is True
            else ("bad" if r.critic_ok is False else "-")
        )
        prog = (r.intent_program or "-")[:18]
        det = (r.error or r.detail)[:40]
        sie = (r.siepic_drc or "n/a")[:7]
        lines.append(
            f"{r.task_id:02d} {r.partition:<18} {r.source:<5} "
            f"{'PASS' if r.ok else 'FAIL':<4} "
            f"{prog:<18} {crit:<4} {(r.triage_next or '-'):<4} "
            f"{drc:<4} {lvs:<4} {sie:<7} {r.ablation:<5} "
            f"{wns:>8} {det}"
        )
    n_ok = sum(1 for r in results if r.ok)
    lines.append("-" * 120)
    lines.append(f"TOTAL {n_ok}/{len(results)} PASS")
    n_drc = sum(1 for r in results if r.drc_pass is True)
    n_drc_run = sum(1 for r in results if r.drc_pass is not None)
    n_lvs = sum(1 for r in results if r.lvs_pass is True)
    n_lvs_run = sum(1 for r in results if r.lvs_pass is not None)
    n_abl = sum(1 for r in results if r.ablation == "pass")
    n_abl_fail = sum(1 for r in results if r.ablation == "fail")
    lines.append(f"DRC PASS {n_drc}/{n_drc_run} (generic_tech; LiDAR stubs n/a)")
    lines.append(
        f"LVS PASS {n_lvs}/{n_lvs_run} (connectivity check; not device-level LVS)"
    )
    gf_r = [r for r in results if r.source == "gf"]
    n_sie_skip = sum(1 for r in gf_r if str(r.siepic_drc).startswith("SKIP"))
    lines.append(
        f"SiEPIC {n_sie_skip}/{len(gf_r)} SKIP(no emitter) — not a regression; "
        f"sky130 dropped from PIC gate"
    )
    lines.append("N6: NO EVIDENCE — gate emit is generic_tech only")
    lines.append(f"φ ablation pass={n_abl} fail={n_abl_fail}")
    return "\n".join(lines)


@pytest.fixture(scope="session", autouse=True)
def _gate_gf_pin() -> None:
    _assert_gate_gdsfactory()


@pytest.mark.parametrize("task_id", list(range(1, 37)))
def test_picset_task_e2e(task_id: int) -> None:
    r = run_task(task_id)
    assert r.ok, f"task {task_id:02d} failed: {r.error or r.detail}"


def test_picset36_summary(capsys) -> None:
    results = run_all()
    print("\n" + format_report(results))
    fails = [r for r in results if not r.ok]
    assert not fails, f"{len(fails)} failures: {[r.task_id for r in fails]}"


def test_picset36_drc_lvs_ablation_gates() -> None:
    """GF subset: DRC+LVS hard-pass; φ ablation ≥80% of eligible."""
    results = run_all()
    gf = [r for r in results if r.source == "gf"]
    assert gf, "expected GF fixtures"
    for r in gf:
        assert r.drc_pass is True, f"task {r.task_id} DRC fail mode={r.drc_mode}"
        assert r.lvs_pass is True, f"task {r.task_id} LVS fail mode={r.lvs_mode}"
    eligible = [r for r in results if r.ablation in ("pass", "fail")]
    assert eligible, "expected at least one φ-ablation-eligible task"
    n_pass = sum(1 for r in eligible if r.ablation == "pass")
    rate = n_pass / len(eligible)
    assert rate >= 0.80, (
        f"φ ablation pass-rate {rate:.0%} < 80% "
        f"(pass={n_pass}/{len(eligible)}; fails="
        f"{[r.task_id for r in eligible if r.ablation == 'fail']})"
    )


if __name__ == "__main__":
    results = run_all()
    print(format_report(results))
    raise SystemExit(0 if all(r.ok for r in results) else 1)
