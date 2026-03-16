"""
Ablation Study for PICasso Framework

Evaluates five progressively richer pipeline configurations to quantify
the contribution of each major component:

  V1  Vanilla LLM           – basic prompt, single attempt, no validation
  V2  + Structured YAML     – rich prompt with knowledge injection, no validation
  V3  + Pilot Validation    – V2 + pilot pre-check + retry with feedback
  V4  + Physical Checks     – V3 + DRC/LVS/SAX post-build validation
  V5  Full PICasso          – V4 + device/circuit optimization

Usage (from PICasso dir, in picasso conda env):
    python ablation_study.py                        # Phase 1: quick sanity (MZI only)
    python ablation_study.py --phase 2              # Phase 2: pilot (3 designs, 1/tier)
    python ablation_study.py --phase 3              # Phase 3: full (12 designs)
    python ablation_study.py --problems 1 4 6       # custom problem selection
    python ablation_study.py --variants V1 V5       # only specific variants
    python ablation_study.py --samples 5            # 5 samples per problem
"""

import sys
import os
import json
import shutil
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

framework_dir = Path(__file__).parent
if str(framework_dir) not in sys.path:
    sys.path.insert(0, str(framework_dir))

import gd_picasso.test_with_llm as twl
import gd_picasso.config as cfg
from gd_picasso.test_with_llm import (
    load_problems, create_agent, run_single_problem,
    YAMLPilotValidator, DRCValidator, LVSValidator, SAXValidator,
    SiliconEfficiencyValidator, PortConnectionValidator,
    OptimizationIntegration, ComponentSpecLoader, BasePilotGenerator,
)
from gd_picasso.config import SYSTEM_PROMPT, VANILLA_PROMPT_TEMPLATE, YAML_DSL_PROMPT_TEMPLATE
from gd_picasso.metrics import estimate_pass_at_k

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("ablation_study.log"), logging.StreamHandler()],
)
logger = logging.getLogger("ablation")
logger.setLevel(logging.INFO)

# ── Variant Definitions ─────────────────────────────────────────────────

VARIANTS = {
    "V1": {
        "label": "Vanilla LLM",
        "prompt": "vanilla",       # uses VANILLA_PROMPT_TEMPLATE
        "phase": "vanilla",        # single attempt, no retry
        "enable_validation": False,
        "enable_optimization": False,
        "pilot": False, "drc": False, "lvs": False, "sax": False,
    },
    "V2": {
        "label": "+ Structured YAML",
        "prompt": "picasso",       # uses YAML_DSL_PROMPT_TEMPLATE (with injection)
        "phase": "vanilla",        # single attempt, no retry
        "enable_validation": False,
        "enable_optimization": False,
        "pilot": False, "drc": False, "lvs": False, "sax": False,
    },
    "V3": {
        "label": "+ Pilot Validation",
        "prompt": "picasso",
        "phase": "picasso",        # retry with feedback
        "enable_validation": True,
        "enable_optimization": False,
        "pilot": True, "drc": False, "lvs": False, "sax": False,
    },
    "V4": {
        "label": "+ Physical Checks",
        "prompt": "picasso",
        "phase": "picasso",
        "enable_validation": True,
        "enable_optimization": False,
        "pilot": True, "drc": True, "lvs": False, "sax": True,
    },
    "V5": {
        "label": "Full PICasso",
        "prompt": "picasso",
        "phase": "picasso",
        "enable_validation": True,
        "enable_optimization": True,
        "pilot": True, "drc": True, "lvs": False, "sax": True,
    },
}

# ── Design Selection ────────────────────────────────────────────────────

PHASE1_PROBLEMS = [1]                          # quick sanity
PHASE2_PROBLEMS = [1, 4, 6]                    # 1/tier pilot (C1, C2, C3)
PHASE3_PROBLEMS = [1, 2, 10, 34,               # C1 x 4
                   4, 9, 23, 26,               # C2 x 4
                   6, 11, 20, 25]              # C3 x 4

TIER_MAP = {
    1: "C1", 2: "C1", 3: "C1", 10: "C1", 19: "C1", 30: "C1", 34: "C1", 35: "C1", 36: "C1",
    4: "C2", 5: "C2", 7: "C2", 8: "C2", 9: "C2", 23: "C2", 24: "C2", 26: "C2", 27: "C2",
    29: "C2", 32: "C2", 33: "C2",
    6: "C3", 11: "C3", 12: "C3", 13: "C3", 14: "C3", 15: "C3", 16: "C3", 17: "C3",
    18: "C3", 20: "C3", 21: "C3", 22: "C3", 25: "C3", 28: "C3", 31: "C3",
}

DEFAULT_MODEL = "claude-sonnet-4-5"

# ── Helpers ──────────────────────────────────────────────────────────────

def patch_config(variant: dict):
    """Monkeypatch the config flags on the test_with_llm module."""
    twl.ENABLE_YAML_PILOT_VALIDATION = variant["pilot"]
    twl.ENABLE_DRC_CHECK = variant["drc"]
    twl.ENABLE_LVS_CHECK = variant["lvs"]
    twl.ENABLE_SAX_CHECK = variant["sax"]


def clear_output(model_name: str):
    """Remove cached results so each variant runs fresh."""
    results_dir = Path("gd_picasso/output") / f"{model_name}_results"
    if results_dir.exists():
        shutil.rmtree(results_dir)
    test_results = Path("gd_picasso/output/test_results")
    if test_results.exists():
        shutil.rmtree(test_results)


def build_prompts():
    """Build both prompt templates (vanilla + structured)."""
    loader = ComponentSpecLoader()
    component_injection = loader.generate_yaml_dsl_injection(
        include_examples=True, include_error_patterns=True
    )
    pilot_gen = BasePilotGenerator()
    pilot_prompt = pilot_gen.generate_base_pilot_prompt()

    vanilla_prompt = VANILLA_PROMPT_TEMPLATE.format(system_prompt=SYSTEM_PROMPT)
    picasso_prompt = YAML_DSL_PROMPT_TEMPLATE.format(
        system_prompt=SYSTEM_PROMPT,
        component_injection=component_injection,
        pilot_prompt=pilot_prompt,
    )
    return vanilla_prompt, picasso_prompt


def run_variant(
    variant_name: str,
    variant: dict,
    problems: List[Dict],
    agent,
    prompts: dict,
    validators: dict,
    optimizer,
    samples: int,
    model_name: str = DEFAULT_MODEL,
) -> List[Dict]:
    """Run all problems for a single ablation variant."""
    patch_config(variant)
    prompt_tpl = prompts["vanilla"] if variant["prompt"] == "vanilla" else prompts["picasso"]

    results = []
    for prob in problems:
        clear_output(model_name)
        result = run_single_problem(
            problem=prob,
            agent=agent,
            prompt_template=prompt_tpl,
            pilot_validator=validators["pilot"],
            drc_validator=validators["drc"],
            lvs_validator=validators["lvs"],
            sax_validator=validators["sax"],
            silicon_validator=validators["silicon"],
            port_connection_validator=validators["port"],
            optimizer=optimizer,
            model_name=model_name,
            phase=variant["phase"],
            samples_per_problem=samples,
            enable_validation=variant["enable_validation"],
            enable_optimization=variant["enable_optimization"],
        )
        results.append(result)
    return results


def spec_at_k_structural(samples: List[dict], k: int = 3) -> float:
    """Probabilistic Spec@k_structural: 1 - C(n-c_s,k)/C(n,k).

    Structural pass = yaml_valid AND component_built AND drc_passed.
    """
    n = len(samples)
    c = sum(1 for s in samples if s.get("passed", False))
    return estimate_pass_at_k(n, c, k)


def spec_at_k_full(samples: List[dict], k: int = 3) -> float:
    """Probabilistic Spec@k_full: 1 - C(n-c_f,k)/C(n,k).

    Full pass = structural pass AND functional_pass.
    """
    n = len(samples)
    c = sum(1 for s in samples
            if s.get("passed", False) and s.get("functional_pass", False))
    return estimate_pass_at_k(n, c, k)


# ── Display helpers (smoke-tests style) ──────────────────────────────────

def bar(passed: int, total: int, width: int = 20) -> str:
    filled = int(width * passed / total) if total > 0 else 0
    return f"[{'█' * filled}{'░' * (width - filled)}] {passed}/{total}"


def failure_reason(s: dict) -> str:
    """Extract a short, readable failure reason from a sample dict."""
    if not s.get("yaml_valid", True):
        errs = s.get("errors", [""])
        msg = errs[0] if errs else "YAML invalid"
        if "truncat" in msg.lower():
            return "YAML truncated"
        if "missing routes" in msg.lower():
            return "missing routes"
        if "spacing" in msg.lower():
            return "spacing violation"
        if "port" in msg.lower():
            return "invalid port"
        return msg[:50]
    if not s.get("component_built", True):
        errs = s.get("errors", [""])
        msg = errs[0] if errs else "build failed"
        if "same angle" in msg:
            return "routing angle mismatch"
        if "routing collision" in msg.lower():
            return "routing collision"
        if "invalid literal" in msg:
            return "arithmetic in YAML"
        if "could not find expected" in msg:
            return "YAML syntax error"
        if "validation error" in msg.lower():
            return "YAML schema error"
        return msg[:50]
    if not s.get("drc_passed", True):
        return "DRC fail"
    vr = s.get("validation_reports", {})
    if not vr.get("functional", {}).get("passed", True):
        return "SAX fail"
    return "unknown"


_ERROR_CATEGORIES = [
    ("YAML truncated",        lambda e: "truncat" in e.lower()),
    ("Missing routes",        lambda e: "missing routes" in e.lower()),
    ("Spacing violation",     lambda e: "spacing" in e.lower() and "too close" in e.lower()),
    ("Invalid port",          lambda e: "port" in e.lower() and ("invalid" in e.lower() or "not found" in e.lower())),
    ("Arithmetic in YAML",    lambda e: "arithmetic" in e.lower() or "invalid literal" in e.lower()),
    ("YAML schema error",     lambda e: "schema" in e.lower() or "validation error" in e.lower() or "extra inputs" in e.lower()),
    ("YAML syntax error",     lambda e: "yaml syntax" in e.lower() or "could not find expected" in e.lower()),
    ("Routing angle mismatch",lambda e: "same angle" in e.lower() or "ports at the target" in e.lower()),
    ("Routing collision",     lambda e: "routing collision" in e.lower()),
    ("DRC fail",              lambda e: "drc" in e.lower()),
    ("SAX fail",              lambda e: "sax" in e.lower()),
    ("Component not found",   lambda e: "not found" in e.lower() and "component" in e.lower()),
    ("Build failed (other)",  lambda e: True),  # catch-all – must be last
]


def categorize_error(sample: dict) -> Optional[str]:
    """Return the primary error category string for a failed sample, or None if passed."""
    if sample.get("passed", False):
        return None
    errors = sample.get("errors", [])
    combined = " ".join(errors).lower()
    if not combined:
        if not sample.get("yaml_valid", True):
            combined = "yaml invalid"
        elif not sample.get("component_built", True):
            combined = "build failed"
        elif not sample.get("drc_passed", True):
            combined = "drc fail"
        else:
            combined = "unknown"
    for label, test in _ERROR_CATEGORIES:
        if test(combined):
            return label
    return "unknown"


def collect_error_patterns(all_variant_results: Dict[str, List[Dict]]) -> Dict[str, Dict[str, int]]:
    """
    Collect error frequency per variant across all problems and samples.

    Returns: {variant_name: {error_category: count}}
    """
    pattern_counts: Dict[str, Dict[str, int]] = {}
    for vname, variant_results in all_variant_results.items():
        counts: Dict[str, int] = {}
        for prob_result in variant_results:
            for s in prob_result.get("samples", []):
                cat = categorize_error(s)
                if cat is not None:
                    counts[cat] = counts.get(cat, 0) + 1
        pattern_counts[vname] = counts
    return pattern_counts


def print_error_pattern_report(
    pattern_counts: Dict[str, Dict[str, int]],
    vanilla_variants: List[str],
    picasso_variants: List[str],
):
    """Print a side-by-side error breakdown: vanilla variants vs PICasso variants."""
    all_cats = set()
    for counts in pattern_counts.values():
        all_cats.update(counts.keys())
    all_cats = sorted(all_cats)

    col_w = 10
    cat_w = 26
    print(f"\n{'=' * (cat_w + (col_w + 1) * len(pattern_counts) + 4)}")
    print("  ERROR PATTERN ANALYSIS")
    print(f"  Vanilla variants: {vanilla_variants}    PICasso variants: {picasso_variants}")
    print(f"  {'Category':<{cat_w}}", end="")
    for vn in list(pattern_counts.keys()):
        marker = "▶" if vn in picasso_variants else " "
        print(f" {marker}{vn:<{col_w-1}}", end="")
    print()
    print(f"  {'-' * (cat_w + (col_w + 1) * len(pattern_counts))}")

    for cat in all_cats:
        row = f"  {cat:<{cat_w}}"
        for vn, counts in pattern_counts.items():
            n = counts.get(cat, 0)
            row += f" {n:>{col_w}}" if n else f" {'·':>{col_w}}"
        print(row)

    # totals
    print(f"  {'-' * (cat_w + (col_w + 1) * len(pattern_counts))}")
    row = f"  {'TOTAL FAILURES':<{cat_w}}"
    for vn, counts in pattern_counts.items():
        row += f" {sum(counts.values()):>{col_w}}"
    print(row)
    print(f"{'=' * (cat_w + (col_w + 1) * len(pattern_counts) + 4)}")

    # Narrative summary
    print("\n  KEY OBSERVATIONS:")
    for cat in all_cats:
        v_total = sum(pattern_counts.get(vn, {}).get(cat, 0) for vn in vanilla_variants)
        p_total = sum(pattern_counts.get(vn, {}).get(cat, 0) for vn in picasso_variants)
        if v_total > 0 and p_total == 0:
            print(f"    ✅ '{cat}' eliminated in PICasso variants (was {v_total}x in vanilla)")
        elif v_total > 0 and p_total < v_total:
            reduction = (v_total - p_total) / v_total * 100
            print(f"    🔧 '{cat}' reduced by {reduction:.0f}% in PICasso ({v_total}→{p_total})")
        elif v_total == 0 and p_total > 0:
            print(f"    ⚠️  '{cat}' appears only in PICasso ({p_total}x) — check if over-strict")
    print()


def print_variant_detail(variant_name: str, results: List[Dict], samples: int):
    """Print per-sample pass/fail detail with progress bars (smoke-tests style)."""
    for r in results:
        pid = r.get("problem_id", "?")
        pname = r.get("problem_name", f"Problem {pid}")
        tier = TIER_MAP.get(int(pid), "?")
        sample_list = r.get("samples", [])

        s_pass = sum(1 for s in sample_list if s.get("passed", False))
        f_pass = sum(1 for s in sample_list
                     if s.get("passed", False) and s.get("functional_pass", False))
        total = len(sample_list)

        print(f"\n    Problem {pid}: {pname}  ({tier})")
        for i, s in enumerate(sample_list, 1):
            ok_s = s.get("passed", False)
            ok_f = ok_s and s.get("functional_pass", False)
            if ok_f:
                icon = "✅"
                note = ""
            elif ok_s:
                icon = "🔧"
                note = "  (structural OK, functional fail)"
            else:
                icon = "❌"
                note = f"  ({failure_reason(s)})"
            print(f"      Sample {i}: {icon}{note}")

        sk_s = spec_at_k_structural(sample_list, k=total)
        sk_f = spec_at_k_full(sample_list, k=total)
        print(f"      {bar(s_pass, total)}  Struct={s_pass}/{total} (Spec@{total}_S={sk_s:.0%})")
        print(f"      {bar(f_pass, total)}  Full  ={f_pass}/{total} (Spec@{total}_F={sk_f:.0%})")


def print_results(all_variant_results: Dict[str, List[Dict]], problems: List[Dict], samples: int, model_name: str = DEFAULT_MODEL):
    """Print comparison table with Structural (S) and Full (F) Spec@k per variant."""
    variant_names = list(all_variant_results.keys())
    col_per_v = 2  # S and F
    col_w = 6
    name_w = 26
    tier_w = 5
    W = name_w + tier_w + len(variant_names) * col_per_v * (col_w + 1) + 12

    print(f"\n{'=' * W}")
    print(f"  ABLATION STUDY RESULTS  (Spec@{samples}, probabilistic)")
    print(f"  Model: {model_name}  |  Samples/problem: {samples}")
    print(f"  S = Spec@k_structural   F = Spec@k_full (structural + functional)")
    print(f"{'=' * W}")

    # Two-row header: variant names, then S/F sub-columns
    h1 = f"  {'Problem':<{name_w}} {'Tier':<{tier_w}}"
    h2 = f"  {'':<{name_w}} {'':<{tier_w}}"
    for vn in variant_names:
        span = col_per_v * (col_w + 1)
        h1 += f" {vn:^{span}}"
        h2 += f" {'S':>{col_w}} {'F':>{col_w}}"
    h1 += f" {'Delta-S':>{col_w+1}} {'Delta-F':>{col_w+1}}"
    h2 += f" {'':>{col_w+1}} {'':>{col_w+1}}"
    print(h1)
    print(h2)
    print(f"  {'-' * (W - 4)}")

    tier_s = {}
    tier_f = {}

    for prob in problems:
        pid = int(prob["id"])
        name = prob.get("name", f"Problem {pid}")[:24]
        tier = TIER_MAP.get(pid, "?")
        row = f"  {name:<{name_w}} {tier:<{tier_w}}"

        scores_s = {}
        scores_f = {}
        for vn in variant_names:
            vr = all_variant_results[vn]
            prob_result = next((r for r in vr if str(r.get("problem_id")) == str(pid)), None)
            if prob_result:
                sl = prob_result.get("samples", [])
                s_val = spec_at_k_structural(sl, k=samples)
                f_val = spec_at_k_full(sl, k=samples)
            else:
                s_val = f_val = 0.0

            scores_s[vn] = s_val
            scores_f[vn] = f_val
            row += f" {s_val:>{col_w}.0%} {f_val:>{col_w}.0%}"

            tier_s.setdefault(tier, {}).setdefault(vn, []).append(s_val)
            tier_f.setdefault(tier, {}).setdefault(vn, []).append(f_val)

        d_s = scores_s.get(variant_names[-1], 0) - scores_s.get(variant_names[0], 0)
        d_f = scores_f.get(variant_names[-1], 0) - scores_f.get(variant_names[0], 0)
        row += f" {'+' if d_s >= 0 else ''}{d_s:>{col_w}.0%}"
        row += f" {'+' if d_f >= 0 else ''}{d_f:>{col_w}.0%}"
        print(row)

        # Mini progress bars per variant
        for vn in variant_names:
            vr = all_variant_results[vn]
            prob_result = next((r for r in vr if str(r.get("problem_id")) == str(pid)), None)
            if prob_result:
                sl = prob_result.get("samples", [])
                sp = sum(1 for s in sl if s.get("passed", False))
                fp = sum(1 for s in sl if s.get("passed", False) and s.get("functional_pass", False))
                icons = ""
                for s in sl:
                    ok_s = s.get("passed", False)
                    ok_f = ok_s and s.get("functional_pass", False)
                    icons += "✅" if ok_f else ("🔧" if ok_s else "❌")
                print(f"      {vn}: S={sp}/{len(sl)} F={fp}/{len(sl)}  {icons}")
        print()

    # Per-tier averages
    print(f"  {'-' * (W - 4)}")
    for tier in sorted(tier_s.keys()):
        row = f"  {'Avg ' + tier:<{name_w}} {'':<{tier_w}}"
        for vn in variant_names:
            vs = tier_s[tier].get(vn, [])
            vf = tier_f[tier].get(vn, [])
            avg_s = sum(vs) / len(vs) if vs else 0.0
            avg_f = sum(vf) / len(vf) if vf else 0.0
            row += f" {avg_s:>{col_w}.0%} {avg_f:>{col_w}.0%}"
        print(row)

    # Grand average
    print(f"  {'-' * (W - 4)}")
    row = f"  {'OVERALL AVERAGE':<{name_w}} {'':<{tier_w}}"
    for vn in variant_names:
        all_s = [v for ts in tier_s.values() for v in ts.get(vn, [])]
        all_f = [v for tf in tier_f.values() for v in tf.get(vn, [])]
        avg_s = sum(all_s) / len(all_s) if all_s else 0.0
        avg_f = sum(all_f) / len(all_f) if all_f else 0.0
        row += f" {avg_s:>{col_w}.0%} {avg_f:>{col_w}.0%}"
    print(row)

    print(f"{'=' * W}")


# ── LaTeX generation ──────────────────────────────────────────────────────

LATEX_DIR = Path(__file__).parent.parent / "ICLAD2026_PICasso_March_9"


def _pct(v: float) -> str:
    """Format a 0-1 probability as a percentage string for LaTeX."""
    return f"{v * 100:.1f}"


def save_latex_ablation_table(
    all_variant_results: Dict[str, List[Dict]],
    problems: List[Dict],
    samples: int,
    model_name: str,
    output_dir: Optional[Path] = None,
):
    """Generate a standalone LaTeX file with the ablation table and explanation."""
    output_dir = output_dir or LATEX_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    variant_names = list(all_variant_results.keys())
    n_variants = len(variant_names)

    # -- collect per-problem scores ----------------------------------------
    rows = []
    tier_s: Dict[str, Dict[str, List[float]]] = {}
    tier_f: Dict[str, Dict[str, List[float]]] = {}

    for prob in problems:
        pid = int(prob["id"])
        name = prob.get("name", f"Problem {pid}")
        tier = TIER_MAP.get(pid, "?")
        scores_s = {}
        scores_f = {}
        for vn in variant_names:
            vr = all_variant_results[vn]
            pr = next((r for r in vr if str(r.get("problem_id")) == str(pid)), None)
            if pr:
                sl = pr.get("samples", [])
                scores_s[vn] = spec_at_k_structural(sl, k=samples)
                scores_f[vn] = spec_at_k_full(sl, k=samples)
            else:
                scores_s[vn] = scores_f[vn] = 0.0
            tier_s.setdefault(tier, {}).setdefault(vn, []).append(scores_s[vn])
            tier_f.setdefault(tier, {}).setdefault(vn, []).append(scores_f[vn])
        rows.append((pid, name, tier, scores_s, scores_f))

    # -- build LaTeX body --------------------------------------------------
    col_spec = "l l " + " ".join(["r r"] * n_variants)  # Problem, Tier, then S F per variant
    cmidrule_parts = []
    for i, vn in enumerate(variant_names):
        start = 3 + i * 2
        end = start + 1
        cmidrule_parts.append(f"\\cmidrule(lr){{{start}-{end}}}")
    cmidrules = " ".join(cmidrule_parts)

    header_top = " & ".join(
        [f"\\multicolumn{{2}}{{c}}{{\\textbf{{{vn}}}}}" for vn in variant_names]
    )
    header_sub = " & ".join(["\\textbf{S} & \\textbf{F}"] * n_variants)

    table_rows = []
    for pid, name, tier, sc_s, sc_f in rows:
        tex_name = name.replace("&", "\\&").replace("_", "\\_")
        cells = f"{tex_name} & {tier}"
        for vn in variant_names:
            cells += f" & {_pct(sc_s[vn])} & {_pct(sc_f[vn])}"
        table_rows.append(cells + " \\\\")

    # tier averages
    tier_avg_rows = []
    for tier in sorted(tier_s.keys()):
        cells = f"\\textit{{Avg {tier}}} & "
        for vn in variant_names:
            vs = tier_s[tier].get(vn, [])
            vf = tier_f[tier].get(vn, [])
            avg_s = sum(vs) / len(vs) if vs else 0.0
            avg_f = sum(vf) / len(vf) if vf else 0.0
            cells += f" & {_pct(avg_s)} & {_pct(avg_f)}"
        tier_avg_rows.append(cells + " \\\\")

    # grand average
    grand_cells = "\\textbf{Overall Average} & "
    for vn in variant_names:
        all_s = [v for ts in tier_s.values() for v in ts.get(vn, [])]
        all_f = [v for tf in tier_f.values() for v in tf.get(vn, [])]
        avg_s = sum(all_s) / len(all_s) if all_s else 0.0
        avg_f = sum(all_f) / len(all_f) if all_f else 0.0
        grand_cells += f" & \\textbf{{{_pct(avg_s)}}} & \\textbf{{{_pct(avg_f)}}}"
    grand_row = grand_cells + " \\\\"

    # variant labels for the caption
    v_desc = {
        "V1": "Vanilla LLM generation",
        "V2": "V1 + structured YAML with knowledge injection",
        "V3": "V2 + pilot validation with feedback loop",
        "V4": "V3 + DRC/LVS/SAX physical checks",
        "V5": "V4 + device- and circuit-level optimization (Full PICasso)",
    }
    variant_legend = "; ".join(
        f"\\textbf{{{vn}}}: {v_desc.get(vn, VARIANTS.get(vn, {}).get('label', vn))}"
        for vn in variant_names
    )

    tex = rf"""%% Auto-generated by ablation_study.py — {datetime.now():%Y-%m-%d %H:%M}
%% Model: {model_name}   Samples per problem: {samples}   Metric: Spec@{samples}
%%
%% To include in Main.tex:  \input{{ablation_table.tex}}
%%
\begin{{table*}}[t]
\centering
\caption{{Ablation study of PICasso pipeline components ({model_name}, Spec@{samples}).
Each column pair reports structural (S) and full-specification (F) Spec@$k$
(\%).  {variant_legend}.
Spec@$k$ uses the probabilistic formula
$\mathrm{{Spec}}@k = 1 - \binom{{n-c}}{{k}}/\binom{{n}}{{k}}$
where $n$ is the number of samples and $c$ the number of passing samples.
``Structural'' counts designs that compile, route, and pass DRC;
``Full'' additionally requires SAX-based functional correctness.}}
\label{{tab:ablation}}
\renewcommand{{\arraystretch}}{{1.1}}
\setlength{{\tabcolsep}}{{4pt}}
\scalebox{{0.78}}{{
\begin{{tabular}}{{{col_spec}}}
\toprule
\multirow{{2}}{{*}}{{\textbf{{Problem}}}} & \multirow{{2}}{{*}}{{\textbf{{Tier}}}}
  & {header_top} \\
{cmidrules}
 & & {header_sub} \\
\midrule
{chr(10).join(table_rows)}
\midrule
{chr(10).join(tier_avg_rows)}
\midrule
{grand_row}
\bottomrule
\end{{tabular}}}}
\end{{table*}}
"""

    out_path = output_dir / "ablation_table.tex"
    out_path.write_text(tex)
    print(f"\nLaTeX ablation table saved to: {out_path}")
    return out_path


def save_latex_table1(
    merged_json_path: Path,
    output_dir: Optional[Path] = None,
    k_values: tuple = (1, 3),
):
    """Generate a standalone LaTeX file reproducing Table 1 from a merged-metrics JSON.

    The JSON is produced by merge_metrics.py and has structure:
      {model: {phase: {problem_id: {summary: {...}, samples: [...]}}}}
    """
    output_dir = output_dir or LATEX_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(merged_json_path) as f:
        data = json.load(f)

    # Collect per-model, per-tier averages for each (phase, metric, k)
    model_results: Dict[str, Dict] = {}

    for model, phases in data.items():
        model_results[model] = {}
        for phase in ("vanilla", "picasso"):
            phase_data = phases.get(phase, {})
            tier_scores: Dict[str, Dict[str, List[float]]] = {}
            for pid_str, pdata in phase_data.items():
                pid = int(pid_str)
                tier = TIER_MAP.get(pid, "?")
                samples_list = pdata.get("samples", [])
                n = len(samples_list)
                c_s = sum(1 for s in samples_list
                          if s.get("structural_pass", s.get("component_built", False))
                          and s.get("drc_passed", True))
                c_f = sum(1 for s in samples_list
                          if s.get("structural_pass", s.get("component_built", False))
                          and s.get("drc_passed", True)
                          and s.get("functional_pass", False))
                for k in k_values:
                    sk_s = estimate_pass_at_k(n, c_s, k) if n > 0 else 0.0
                    sk_f = estimate_pass_at_k(n, c_f, k) if n > 0 else 0.0
                    tier_scores.setdefault(tier, {}).setdefault(f"s@{k}", []).append(sk_s)
                    tier_scores[tier].setdefault(f"f@{k}", []).append(sk_f)

            avgs: Dict[str, Dict[str, float]] = {}
            for tier, metrics in tier_scores.items():
                avgs[tier] = {}
                for mk, vals in metrics.items():
                    avgs[tier][mk] = sum(vals) / len(vals) if vals else 0.0
            model_results[model][phase] = avgs

    # Build LaTeX
    tiers_ordered = ["C1", "C2", "C3"]
    n_tiers = len(tiers_ordered)
    cols_per_tier = len(k_values) * 2  # S@1 S@3 F@1 F@3

    col_spec = "c" + ("c" * cols_per_tier) * n_tiers
    tier_headers = []
    sub_headers = []
    for ti, tier in enumerate(tiers_ordered):
        start = 2 + ti * cols_per_tier
        end = start + cols_per_tier - 1
        tier_headers.append(f"\\multicolumn{{{cols_per_tier}}}{{c}}{{\\textbf{{{tier}}}}}")
        for k in k_values:
            sub_headers.extend([f"\\textbf{{S@{k}}}", f"\\textbf{{F@{k}}}"])

    cmidrules_t1 = []
    for ti in range(n_tiers):
        s = 2 + ti * cols_per_tier
        e = s + cols_per_tier - 1
        cmidrules_t1.append(f"\\cmidrule(lr){{{s}-{e}}}")

    model_rows = []
    for model in sorted(model_results.keys()):
        for phase in ("vanilla", "picasso"):
            label = model if phase == "vanilla" else f"\\quad PICasso w/ {model}"
            avgs = model_results[model].get(phase, {})
            cells = label
            for tier in tiers_ordered:
                tavg = avgs.get(tier, {})
                for k in k_values:
                    cells += f" & {_pct(tavg.get(f's@{k}', 0))}"
                    cells += f" & {_pct(tavg.get(f'f@{k}', 0))}"
            model_rows.append(cells + " \\\\")
            if phase == "picasso":
                model_rows.append("")  # blank line between model groups

    tex = rf"""%% Auto-generated by ablation_study.py — {datetime.now():%Y-%m-%d %H:%M}
%% Source: {merged_json_path.name}
%%
%% To include in Main.tex:  \input{{table1_updated.tex}}
%%
\begin{{table*}}[t]
\centering
\caption{{Aggregate Spec@$k$ performance across PIC-Set tasks (updated).
Each block reports structural correctness (S@1, S@3) and
full-specification correctness (F@1, F@3).
Values are percentages averaged over problems in each complexity tier.
Spec@$k = 1 - \binom{{n-c}}{{k}}/\binom{{n}}{{k}}$.}}
\label{{tab:picasso_all36_updated}}
\renewcommand{{\arraystretch}}{{1.05}}
\setlength{{\tabcolsep}}{{3pt}}
\scalebox{{0.84}}{{
\begin{{tabular}}{{{col_spec}}}
\toprule
\multirow{{3}}{{*}}{{\textbf{{Model / Setting}}}}
  & {' & '.join(tier_headers)} \\
{' '.join(cmidrules_t1)}
 & {' & '.join(sub_headers)} \\
\midrule
{chr(10).join(model_rows)}
\bottomrule
\end{{tabular}}}}
\end{{table*}}
"""

    out_path = output_dir / "table1_updated.tex"
    out_path.write_text(tex)
    print(f"\nLaTeX Table 1 (updated) saved to: {out_path}")
    return out_path


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="PICasso Ablation Study")
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2, 3],
                        help="1=quick sanity, 2=pilot (3 designs), 3=full (12 designs)")
    parser.add_argument("--problems", type=int, nargs="+", default=None,
                        help="Custom problem numbers (overrides --phase)")
    parser.add_argument("--variants", nargs="+", default=None,
                        help="Specific variants to run (e.g., V1 V3 V5)")
    parser.add_argument("--samples", type=int, default=3,
                        help="Samples per problem (default: 3)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help=f"LLM model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    model_name = args.model

    # Select problems
    if args.problems:
        problem_nums = args.problems
    elif args.phase == 1:
        problem_nums = PHASE1_PROBLEMS
    elif args.phase == 2:
        problem_nums = PHASE2_PROBLEMS
    else:
        problem_nums = PHASE3_PROBLEMS

    # Select variants
    if args.variants:
        selected_variants = {k: VARIANTS[k] for k in args.variants if k in VARIANTS}
    else:
        selected_variants = VARIANTS

    # Load problems
    all_problems = load_problems(str(framework_dir / "Pic_set.txt"))
    problems = [p for p in all_problems if int(p["id"]) in problem_nums]

    if not problems:
        print(f"ERROR: No problems found for IDs {problem_nums}")
        return

    n_calls = len(problems) * len(selected_variants) * args.samples
    retry_factor = 1.8  # avg retries in picasso mode
    n_picasso_variants = sum(1 for v in selected_variants.values() if v["phase"] == "picasso")
    n_vanilla_variants = len(selected_variants) - n_picasso_variants
    est_calls = (n_vanilla_variants * len(problems) * args.samples +
                 n_picasso_variants * len(problems) * args.samples * retry_factor)
    est_minutes = est_calls * 25 / 60  # ~25s per LLM call on average

    print("=" * 70)
    print(f"  PICasso Ablation Study")
    print(f"  Model: {model_name}")
    print(f"  Problems: {[int(p['id']) for p in problems]} ({len(problems)} designs)")
    print(f"  Variants: {list(selected_variants.keys())}")
    print(f"  Samples: {args.samples}")
    print(f"  Est. LLM calls: ~{est_calls:.0f}")
    print(f"  Est. time: ~{est_minutes:.0f} minutes")
    print("=" * 70)

    # Create agent
    agent = create_agent(model_name)
    if agent is None:
        print(f"ERROR: Failed to create agent for model '{model_name}'")
        print("Check that ANTHROPIC_API_KEY is exported.")
        return

    # Build prompts
    vanilla_prompt, picasso_prompt = build_prompts()
    prompts = {"vanilla": vanilla_prompt, "picasso": picasso_prompt}

    # Initialize validators (once, reused across variants)
    validators = {
        "pilot": YAMLPilotValidator(),
        "drc": DRCValidator(),
        "lvs": LVSValidator(enabled=False),
        "sax": SAXValidator(),
        "silicon": SiliconEfficiencyValidator(),
        "port": PortConnectionValidator(),
    }
    optimizer = OptimizationIntegration()

    # Run ablation
    all_variant_results = {}
    start_time = time.time()

    for vname, vdef in selected_variants.items():
        print(f"\n{'─' * 70}")
        print(f"  Running {vname}: {vdef['label']}")
        print(f"  Prompt: {vdef['prompt']}  |  Phase: {vdef['phase']}  |  Pilot: {vdef['pilot']}  |  DRC: {vdef['drc']}  |  SAX: {vdef['sax']}  |  Opt: {vdef['enable_optimization']}")
        print(f"{'─' * 70}")

        variant_start = time.time()
        results = run_variant(
            vname, vdef, problems, agent, prompts, validators, optimizer, args.samples,
            model_name=model_name,
        )
        variant_elapsed = time.time() - variant_start

        all_variant_results[vname] = results

        print_variant_detail(vname, results, args.samples)

        print(f"\n  [{vname} done in {variant_elapsed:.0f}s]")

    total_elapsed = time.time() - start_time

    # Display results
    print_results(all_variant_results, problems, args.samples, model_name=model_name)
    print(f"\nTotal wall time: {total_elapsed / 60:.1f} minutes")

    # Error pattern analysis
    vanilla_vs = [vn for vn, vd in selected_variants.items() if vd["phase"] == "vanilla"]
    picasso_vs  = [vn for vn, vd in selected_variants.items() if vd["phase"] == "picasso"]
    pattern_counts = collect_error_patterns(all_variant_results)
    print_error_pattern_report(pattern_counts, vanilla_vs, picasso_vs)

    # Save raw results JSON
    output_path = Path("gd_picasso/output") / f"ablation_{model_name}_{datetime.now():%Y%m%d_%H%M}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {}
    for vname, results in all_variant_results.items():
        serializable[vname] = []
        for r in results:
            sl = r.get("samples", [])
            n = len(sl)
            c_s = sum(1 for s in sl if s.get("passed", False))
            c_f = sum(1 for s in sl if s.get("passed", False) and s.get("functional_pass", False))
            sr = {
                "problem_id": r.get("problem_id"),
                "problem_name": r.get("problem_name"),
                "structural_pass_count": c_s,
                "functional_pass_count": c_f,
                "total_samples": n,
                "spec_at_k_structural": spec_at_k_structural(sl, k=args.samples),
                "spec_at_k_full": spec_at_k_full(sl, k=args.samples),
                "samples": [
                    {
                        "passed": s.get("passed", False),
                        "yaml_valid": s.get("yaml_valid", False),
                        "component_built": s.get("component_built", False),
                        "drc_passed": s.get("drc_passed", False),
                        "functional_pass": s.get("functional_pass", False),
                        "errors": s.get("errors", []),
                    }
                    for s in sl
                ],
            }
            serializable[vname].append(sr)

    output_data = {
        "meta": {
            "model": model_name,
            "samples": args.samples,
            "problems": [int(p["id"]) for p in problems],
            "variants": list(selected_variants.keys()),
            "timestamp": datetime.now().isoformat(),
        },
        "results": serializable,
        "error_patterns": pattern_counts,
    }
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"\nJSON results saved to: {output_path}")

    # Save LaTeX ablation table
    try:
        save_latex_ablation_table(
            all_variant_results, problems, args.samples, model_name=model_name,
        )
    except Exception as e:
        logger.warning(f"Failed to save LaTeX ablation table: {e}")


if __name__ == "__main__":
    main()
