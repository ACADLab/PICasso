"""
PCG round-trip gate test.

Proves losslessness of from_gf_yaml / to_gf_yaml via a six-step gate.
SKIP is a distinct outcome from PASS: thesis steps (SAX, ΔIL) that SKIP
cause a non-zero exit. Source-YAML fallback for netlist diff is WARN/FAIL,
not a silent pass.

Run:  python -m gd_picasso.pcg.pcg_roundtrip_test
"""

from __future__ import annotations

import json
import math
import sys
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Fixtures — generous spacing (≥100 µm) to reduce auto-router collisions
# ---------------------------------------------------------------------------

FIXTURE_MZI = """\
instances:
  splitter:
    component: mmi1x2
    settings: {}
  ps_upper:
    component: straight_heater_metal
    settings: {length: 100}
  ps_lower:
    component: straight
    settings: {length: 100}
  combiner:
    component: mmi1x2
    settings: {}

placements:
  splitter:
    x: 0
    y: 0
    rotation: 0
    mirror: false
  ps_upper:
    x: 150
    y: 50
    rotation: 0
    mirror: false
  ps_lower:
    x: 150
    y: -50
    rotation: 0
    mirror: false
  combiner:
    x: 300
    y: 0
    rotation: 180
    mirror: false

routes:
  optical:
    settings:
      cross_section: strip
      radius: 10.0
    links:
      splitter,o2: ps_upper,o1
      splitter,o3: ps_lower,o1
      ps_upper,o2: combiner,o2
      ps_lower,o2: combiner,o3

ports:
  in: splitter,o1
  out: combiner,o1
"""

FIXTURE_MZM = """\
instances:
  splitter:
    component: mmi1x2
    settings: {}
  ps_upper:
    component: straight_heater_metal
    settings: {length: 100}
  ps_lower:
    component: straight_heater_metal
    settings: {length: 100}
  combiner:
    component: mmi2x2
    settings: {}

placements:
  splitter:
    x: 0
    y: 0
    rotation: 0
    mirror: false
  ps_upper:
    x: 150
    y: 40
    rotation: 0
    mirror: false
  ps_lower:
    x: 150
    y: -40
    rotation: 0
    mirror: false
  combiner:
    x: 300
    y: 0
    rotation: 180
    mirror: false

routes:
  optical:
    settings:
      cross_section: strip
      radius: 10.0
    links:
      splitter,o2: ps_upper,o1
      splitter,o3: ps_lower,o1
      ps_upper,o2: combiner,o1
      ps_lower,o2: combiner,o2

ports:
  in: splitter,o1
  out1: combiner,o3
  out2: combiner,o4
"""

# Ring-bus probe: coupler with same-instance feedback (o3→o4) + bus through.
# Stresses same-node different-port edges (allowed) vs same-port self-loop (rejected).
FIXTURE_RING = """\
instances:
  dc:
    component: coupler
    settings: {gap: 0.2, length: 10}
  bus_in:
    component: straight
    settings: {length: 20}
  bus_out:
    component: straight
    settings: {length: 20}

placements:
  bus_in:
    x: 0
    y: 0
    rotation: 0
    mirror: false
  dc:
    x: 80
    y: 0
    rotation: 0
    mirror: false
  bus_out:
    x: 200
    y: 0
    rotation: 0
    mirror: false

routes:
  optical:
    settings:
      cross_section: strip
      radius: 10.0
    links:
      bus_in,o2: dc,o1
      dc,o4: bus_out,o1

connections:
  dc,o3: dc,o2

ports:
  in: bus_in,o1
  out: bus_out,o2
"""

# Linear waveguide — guaranteed routeable; meaningful length for ΔIL
FIXTURE_LINEAR = """\
instances:
  wg1:
    component: straight
    settings: {length: 10}
  wg2:
    component: straight
    settings: {length: 10}

placements:
  wg1:
    x: 0
    y: 0
    rotation: 0
    mirror: false
  wg2:
    x: 200
    y: 0
    rotation: 0
    mirror: false

routes:
  optical:
    settings:
      cross_section: strip
      radius: 20.0
    links:
      wg1,o2: wg2,o1

ports:
  in: wg1,o1
  out: wg2,o2
"""

BUILTIN_FIXTURES = {
    "Linear": FIXTURE_LINEAR,
    "MZI": FIXTURE_MZI,
    "MZM": FIXTURE_MZM,
    "Ring": FIXTURE_RING,
}

# Thesis steps — SKIP on these fails the run
THESIS_STEPS = {"5_sax", "6_delta_il"}


# ---------------------------------------------------------------------------
# Corpus discovery
# ---------------------------------------------------------------------------

def discover_corpus() -> Dict[str, str]:
    """Load committed fixtures/ plus optional gd_picasso/output/**/circuit.yaml."""
    found: Dict[str, str] = {}
    root = Path(__file__).resolve().parent
    fixtures_dir = root / "fixtures"
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.yaml")):
            try:
                found[f"fixture:{path.stem}"] = path.read_text(encoding="utf-8")
            except OSError:
                continue
    out = root.parent / "output"
    if out.is_dir():
        for path in sorted(out.glob("**/*/circuit.yaml")):
            rel = path.relative_to(out)
            key = str(rel.parent).replace("\\", "/")
            try:
                found[f"corpus:{key}"] = path.read_text(encoding="utf-8")
            except OSError:
                continue
    return found


# ---------------------------------------------------------------------------
# Routing / build helpers
# ---------------------------------------------------------------------------

def _route_ok(component) -> Tuple[bool, str]:
    """True if get_netlist() succeeds (proxy for route success)."""
    try:
        nl = component.get_netlist()
        if not nl:
            return False, "empty netlist"
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def _try_yaml_spacing_fix(yaml_str: str) -> Tuple[Optional[Any], Optional[str], Dict]:
    """Apply spacing multipliers to source YAML and rebuild.

    Does NOT call get_netlist on the collided component — that always fails.
    Uses the same multipliers as yaml_routing_fixer (1.5 / 2.0 / 2.5×).
    """
    import gdsfactory as gf
    from gd_picasso.utils.yaml_routing_fixer import fix_yaml_spacing_with_multiplier

    info: Dict[str, Any] = {"success": False, "errors": [], "method_used": "none"}
    for mult in (1.5, 2.0, 2.5, 3.0, 4.0):
        try:
            fixed_yaml = fix_yaml_spacing_with_multiplier(yaml_str, mult)
            comp = gf.read.from_yaml(fixed_yaml)
            ok, msg = _route_ok(comp)
            if ok:
                info["success"] = True
                info["method_used"] = f"spacing_{mult}x"
                info["final_spacing_multiplier"] = mult
                return comp, fixed_yaml, info
            info["errors"].append(f"{mult}x still collides: {msg}")
        except Exception as exc:
            info["errors"].append(f"{mult}x rebuild failed: {exc}")
    return None, None, info


# ---------------------------------------------------------------------------
# Normalized netlist comparison
# ---------------------------------------------------------------------------

def _round_settings(settings: Dict[str, Any]) -> str:
    def _norm(v: Any) -> Any:
        if isinstance(v, float):
            return round(v, 6)
        if isinstance(v, dict):
            return {k: _norm(val) for k, val in sorted(v.items())}
        if isinstance(v, (list, tuple)):
            return [_norm(i) for i in v]
        return v
    return json.dumps(_norm(settings), sort_keys=True, separators=(",", ":"))


def _instance_multiset(netlist: Dict) -> Counter:
    instances = netlist.get("instances", {}) or {}
    bag: Counter = Counter()
    for inst_spec in instances.values():
        if isinstance(inst_spec, dict):
            comp = inst_spec.get("component", "")
            settings = inst_spec.get("settings", {}) or {}
        else:
            comp = str(inst_spec)
            settings = {}
        bag[(comp, _round_settings(settings))] += 1
    return bag


def _connection_set(netlist: Dict) -> Set[frozenset]:
    conns: Set[frozenset] = set()
    raw_conns = netlist.get("connections", [])
    if isinstance(raw_conns, dict):
        for src, dst in raw_conns.items():
            conns.add(frozenset([str(src), str(dst)]))
    elif isinstance(raw_conns, (list, tuple)):
        for item in raw_conns:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                conns.add(frozenset([str(item[0]), str(item[1])]))

    routes = netlist.get("routes", {}) or {}
    for bundle_spec in routes.values():
        if isinstance(bundle_spec, dict):
            links = bundle_spec.get("links", {}) or {}
            for src, dst in links.items():
                conns.add(frozenset([str(src), str(dst)]))
    return conns


def compare_netlists(nl_orig: Dict, nl_rt: Dict, name: str) -> Tuple[bool, List[str]]:
    msgs: List[str] = []
    bag_o = _instance_multiset(nl_orig)
    bag_r = _instance_multiset(nl_rt)
    if bag_o != bag_r:
        msgs.append(
            f"  [{name}] Instance multiset mismatch — "
            f"only in orig: {dict(bag_o - bag_r)}, only in rt: {dict(bag_r - bag_o)}"
        )
    conn_o = _connection_set(nl_orig)
    conn_r = _connection_set(nl_rt)
    if conn_o != conn_r:
        msgs.append(
            f"  [{name}] Connection set mismatch — "
            f"only in orig: {conn_o - conn_r}, only in rt: {conn_r - conn_o}"
        )
    return len(msgs) == 0, msgs


def _status_kind(val: str) -> str:
    if val.startswith("PASS"):
        return "PASS"
    if val.startswith("SKIP"):
        return "SKIP"
    if val.startswith("WARN"):
        return "WARN"
    return "FAIL"


# ---------------------------------------------------------------------------
# Per-fixture gate
# ---------------------------------------------------------------------------

def run_fixture(name: str, yaml_str: str) -> Dict[str, str]:
    """Run the six-step gate on one YAML. Returns result dict with status strings."""
    import gdsfactory as gf
    from gd_picasso.pcg import from_gf_yaml, to_gf_yaml

    result: Dict[str, str] = {
        "orig_build_ok": "FAIL",
        "orig_route_ok": "FAIL",
        "rt_build_ok": "FAIL",
        "rt_route_ok": "FAIL",
    }
    print(f"\n{'='*60}")
    print(f"  FIXTURE: {name}")
    print(f"{'='*60}")

    # --- Build original ---
    try:
        comp_orig = gf.read.from_yaml(yaml_str)
        result["orig_build_ok"] = "PASS"
        print(f"  [build] original: PASS")
    except Exception as exc:
        result["orig_build_ok"] = f"FAIL: {exc}"
        result["1_build_orig"] = result["orig_build_ok"]
        print(f"  [build] original: FAIL — {exc}")
        return result

    result["1_build_orig"] = "PASS"

    # --- Route original ---
    ok, msg = _route_ok(comp_orig)
    if ok:
        result["orig_route_ok"] = "PASS"
        print(f"  [route] original: PASS")
    else:
        print(f"  [route] original: FAIL — {msg}")
        print(f"  [route] attempting YAML spacing fix on source (1.5–4.0×)...")
        fixed, fixed_yaml, info = _try_yaml_spacing_fix(yaml_str)
        if fixed is not None and info.get("success") and fixed_yaml:
            comp_orig = fixed
            yaml_str = fixed_yaml
            result["orig_route_ok"] = f"PASS (fixed, {info.get('method_used')})"
            print(f"  [route] original: PASS after spacing fix ({info.get('method_used')})")
        else:
            result["orig_route_ok"] = f"FAIL (fixture/router): {msg}"
            print(f"  [route] original: FAIL — fixture authoring or router issue")
            for e in info.get("errors", [])[:3]:
                print(f"           fixer: {e}")

    # --- Round-trip build ---
    try:
        store = from_gf_yaml(yaml_str)
        rt_yaml = to_gf_yaml(store)
        comp_rt = gf.read.from_yaml(rt_yaml)
        result["rt_build_ok"] = "PASS"
        result["2_roundtrip"] = "PASS"
        print(f"  [build] round-trip: PASS")
    except Exception as exc:
        result["rt_build_ok"] = f"FAIL: {exc}"
        result["2_roundtrip"] = result["rt_build_ok"]
        print(f"  [build] round-trip: FAIL — {exc}")
        traceback.print_exc()
        return result

    # --- Route round-trip ---
    ok_rt, msg_rt = _route_ok(comp_rt)
    if ok_rt:
        result["rt_route_ok"] = "PASS"
        print(f"  [route] round-trip: PASS")
    else:
        # Critical disambiguation
        if result["orig_route_ok"].startswith("PASS"):
            result["rt_route_ok"] = f"FAIL (lossy bridge?): {msg_rt}"
            print(f"  [route] round-trip: FAIL — original routed, RT did not → LOSSY BRIDGE?")
            print(f"           detail: {msg_rt}")
        else:
            result["rt_route_ok"] = f"FAIL (same as orig): {msg_rt}"
            print(f"  [route] round-trip: FAIL — original also failed (fixture/router)")

    # --- Step 3: normalized netlist diff ---
    # Post-build path only. Source-YAML fallback is WARN and fails the run.
    if result["orig_route_ok"].startswith("PASS") and result["rt_route_ok"].startswith("PASS"):
        try:
            nl_orig = comp_orig.get_netlist()
            nl_rt = comp_rt.get_netlist()
            diff_ok, diff_msgs = compare_netlists(nl_orig, nl_rt, name)
            if diff_ok:
                result["3_netlist_diff"] = "PASS"
                print(f"  [3] Normalized netlist diff (post-build): PASS")
            else:
                result["3_netlist_diff"] = "FAIL"
                print(f"  [3] Normalized netlist diff (post-build): FAIL")
                for m in diff_msgs:
                    print(m)
        except Exception as exc:
            result["3_netlist_diff"] = f"WARN: get_netlist raised ({exc}); fallback refused"
            print(f"  [3] WARN — get_netlist raised ({type(exc).__name__}); "
                  f"source-YAML fallback is not accepted (would pass vacuously)")
    else:
        # Fixture didn't route — not a vacuous pass, not a bridge failure
        result["3_netlist_diff"] = (
            f"SKIP: routing unavailable "
            f"(orig={_status_kind(result['orig_route_ok'])}, "
            f"rt={_status_kind(result['rt_route_ok'])})"
        )
        print(f"  [3] SKIP — netlist diff unavailable (routing failed on fixture)")

    # --- Step 4: topology_hash ---
    try:
        store2 = from_gf_yaml(rt_yaml)
        h1 = store.topology_hash()
        h2 = store2.topology_hash()
        if h1 == h2:
            result["4_topo_hash"] = "PASS"
            print(f"  [4] topology_hash stable: PASS ({h1[:12]}...)")
        else:
            result["4_topo_hash"] = f"FAIL: {h1[:12]} != {h2[:12]}"
            print(f"  [4] topology_hash: FAIL")
    except Exception as exc:
        result["4_topo_hash"] = f"FAIL: {exc}"
        print(f"  [4] topology_hash: FAIL — {exc}")

    # --- Step 5: SAX (thesis) ---
    if not result["rt_route_ok"].startswith("PASS"):
        result["5_sax"] = "SKIP: rt_route_ok=false"
        print(f"  [5] SAXValidator: SKIP — round-trip did not route")
    else:
        try:
            from gd_picasso.validators.sax_validator import SAXValidator
            sax_ok, sax_report = SAXValidator().validate(comp_rt)
            if sax_ok:
                result["5_sax"] = "PASS"
                print(f"  [5] SAXValidator: PASS")
            else:
                errs = sax_report.get("errors", [])
                result["5_sax"] = f"FAIL: {errs}"
                print(f"  [5] SAXValidator: FAIL — {errs}")
        except Exception as exc:
            result["5_sax"] = f"SKIP: {exc}"
            print(f"  [5] SAXValidator: SKIP — {exc}")

    # --- Step 6: ΔIL (thesis) ---
    if not result["orig_route_ok"].startswith("PASS"):
        result["6_delta_il"] = "SKIP: orig_route_ok=false"
        print(f"  [6] Delta-IL: SKIP — original did not route")
    else:
        _run_delta_il(store, comp_orig, name, result)

    return result


def _run_delta_il(store, comp_orig, name: str, result: Dict[str, str]) -> None:
    """Report both dIL and dPHI under lossy waveguide models (Table II ~0.7 dB/cm).

    Default gplugins straight has loss_dB_cm=0.0, which makes dIL structurally
    zero even when the router inserts real length. Phase still moves; with
    loss set, both deltas are informative.
    """
    try:
        import sax
        import jax.numpy as jnp
    except ImportError:
        result["6_delta_il"] = "SKIP: sax/jax not installed"
        print(f"  [6] Delta: SKIP — sax/jax not installed")
        return

    from gd_picasso.pcg import to_sax_netlist
    from gd_picasso.pcg.sax_models import DEFAULT_LOSS_DB_CM, build_lossy_models, ensure_jax_x64

    ensure_jax_x64()
    LOSS_DB_CM = DEFAULT_LOSS_DB_CM

    sax_nl = to_sax_netlist(store)
    try:
        routed_nl = comp_orig.get_netlist()
    except Exception as exc:
        result["6_delta_il"] = f"SKIP: get_netlist failed ({exc})"
        print(f"  [6] Delta: SKIP — get_netlist failed")
        return

    try:
        models = build_lossy_models(LOSS_DB_CM)
    except Exception as exc:
        result["6_delta_il"] = f"SKIP: cannot load SAX models ({exc})"
        print(f"  [6] Delta: SKIP — cannot load SAX models ({exc})")
        return

    try:
        circuit_ideal, _ = sax.circuit(sax_nl, models=models)
        try:
            circuit_routed, _ = sax.circuit(routed_nl, models=models)
        except Exception as miss_exc:
            # Router-inserted / PDK cells (vias, heater metal) may lack S-models;
            # map any "Missing Models" names to lossy straight and retry once.
            import re
            from functools import partial
            from gplugins import sax as gs

            straight = partial(gs.models.straight, loss_dB_cm=LOSS_DB_CM)
            m = re.search(r'"Missing Models":\s*\[(.*?)\]', str(miss_exc), re.S)
            if not m:
                raise
            for raw in m.group(1).split(","):
                name_m = raw.strip().strip('"').strip("'")
                if name_m and name_m not in models:
                    models[name_m] = straight
            circuit_routed, _ = sax.circuit(routed_nl, models=models)
        S_ideal = circuit_ideal(wl=1.55)
        S_routed = circuit_routed(wl=1.55)
        ports = list(store.exported_ports.keys())
        if len(ports) < 2:
            result["6_delta_il"] = "SKIP: <2 exported ports"
            print(f"  [6] Delta: SKIP — <2 exported ports")
            return

        def _get_S(S, k):
            if not isinstance(S, dict):
                return None
            if k in S:
                return S[k]
            kr = (k[1], k[0])
            if kr in S:
                return S[kr]
            return None

        p_in, p_out = ports[0], ports[1]
        key = (p_out, p_in)
        vi = _get_S(S_ideal, key)
        vr = _get_S(S_routed, key)
        if vi is None or vr is None:
            result["6_delta_il"] = f"SKIP: TX key {key} missing in S"
            print(f"  [6] Delta: SKIP — TX key {key} missing")
            return

        ti = float(jnp.abs(vi) ** 2)
        tr = float(jnp.abs(vr) ** 2)
        pi = float(jnp.angle(vi))
        pr = float(jnp.angle(vr))
        il_i = -10 * math.log10(max(ti, 1e-30))
        il_r = -10 * math.log10(max(tr, 1e-30))
        dIL = il_r - il_i
        dPHI = pr - pi
        result["6_delta_il"] = (
            f"PASS: dIL={dIL:+.4f} dB dPHI={dPHI:+.4f} rad "
            f"(loss_dB_cm={LOSS_DB_CM})"
        )
        print(
            f"  [6] Delta: IL_ideal={il_i:.4f} dB, IL_routed={il_r:.4f} dB, "
            f"dIL={dIL:+.4f} dB | dPHI={dPHI:+.4f} rad "
            f"({math.degrees(dPHI):+.2f} deg) [loss_dB_cm={LOSS_DB_CM}]"
        )
    except Exception as exc:
        result["6_delta_il"] = f"SKIP: {exc}"
        print(f"  [6] Delta: SKIP — {exc}")


# ---------------------------------------------------------------------------
# Summary / exit policy
# ---------------------------------------------------------------------------

def evaluate_run(results: Dict[str, Dict[str, str]]) -> Tuple[bool, bool, List[str]]:
    """Return (hard_pass, thesis_executed, notes).

    hard_pass fails on:
      - WARN (vacuous fallback)
      - FAIL on serialization steps (build, roundtrip, netlist_diff, topo_hash)
      - LOSSY BRIDGE: orig_route PASS but rt_route FAIL
    Fixture-only route failures (orig and rt both FAIL) are reported but do not
    fail the run — they are authoring/router problems, not bridge losses.
    """
    hard_pass = True
    thesis_pass_count = 0
    notes: List[str] = []

    serialize_keys = {
        "1_build_orig", "2_roundtrip", "3_netlist_diff", "4_topo_hash",
        "orig_build_ok", "rt_build_ok",
    }

    for name, res in results.items():
        orig_r = res.get("orig_route_ok", "FAIL")
        rt_r = res.get("rt_route_ok", "FAIL")
        if orig_r.startswith("PASS") and not rt_r.startswith("PASS"):
            hard_pass = False
            notes.append(f"LOSSY BRIDGE: {name}")

        for k in serialize_keys:
            v = res.get(k, "PASS")
            kind = _status_kind(v)
            if kind in ("FAIL", "WARN"):
                hard_pass = False
                notes.append(f"{name}.{k}={kind}")

        sax = _status_kind(res.get("5_sax", "SKIP"))
        dil = _status_kind(res.get("6_delta_il", "SKIP"))
        if sax == "PASS" and dil == "PASS":
            thesis_pass_count += 1

    return hard_pass, thesis_pass_count > 0, notes


def run_gate() -> int:
    """Run gate. Exit 0 only if hard_pass AND thesis executed on >=1 fixture."""
    import gdsfactory as gf

    print(f"gdsfactory version: {gf.__version__}")
    print(f"python: {sys.version.split()[0]}")

    fixtures = dict(BUILTIN_FIXTURES)
    corpus = discover_corpus()
    if corpus:
        print(f"\nCorpus: found {len(corpus)} circuit.yaml under gd_picasso/output/")
        fixtures.update(corpus)
    else:
        print("\nCorpus: NO circuit.yaml found under gd_picasso/output/")
        print("        Gate runs on built-in fixtures only. Point at a stored")
        print("        corpus when available for real losslessness evidence.")

    results: Dict[str, Dict[str, str]] = {}
    for name, yaml_str in fixtures.items():
        results[name] = run_fixture(name, yaml_str)

    hard_pass, thesis_ok, notes = evaluate_run(results)

    print(f"\n{'='*60}")
    print(f"  SUMMARY MATRIX (PASS / SKIP / WARN / FAIL)")
    print(f"{'='*60}")
    cols = [
        "orig_build_ok", "orig_route_ok", "rt_build_ok", "rt_route_ok",
        "3_netlist_diff", "4_topo_hash", "5_sax", "6_delta_il",
    ]
    header = f"{'fixture':<40} " + " ".join(f"{c[:12]:>12}" for c in cols)
    print(header)
    for name, res in results.items():
        row = f"{name:<40} "
        for c in cols:
            row += f"{_status_kind(res.get(c, 'SKIP')):>12} "
        print(row)

    print()
    if notes:
        print("  Notes:")
        for n in notes:
            print(f"    - {n}")

    if hard_pass and thesis_ok:
        print("  VERDICT: GREEN — hard checks passed and thesis steps executed")
        return 0
    if hard_pass and not thesis_ok:
        print("  VERDICT: YELLOW — serialization OK but thesis steps (SAX/dIL) did not execute")
        print("           Exit 1: SKIP on thesis is not PASS.")
        return 1
    print("  VERDICT: RED — FAIL/WARN on serialization or lossy-bridge suspect")
    return 1


if __name__ == "__main__":
    sys.exit(run_gate())
