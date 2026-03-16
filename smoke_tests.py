"""
Smoke test suite: runs multiple problems x samples to verify stochastic variance.
Shows pass/fail per sample so you can see LLM randomness clearly.

Usage (in picasso env, from PICasso dir):
    python smoke_tests.py
"""

import subprocess
import json
import os
import sys
import shutil
from pathlib import Path

MODEL = "claude-sonnet-4-5"
SAMPLES = 3

OUTPUT_DIR      = Path("gd_picasso/output") / f"{MODEL}_results"
TEST_RESULTS_DIR = Path("gd_picasso/output/test_results")

# (problem_number, label, complexity_tier)
TEST_PROBLEMS = [
    (1,  "MZI",              "C1"),
    (2,  "MZM",              "C1"),
    (3,  "Direct Modulator", "C1"),
    (4,  "QPSK Modulator",   "C2"),
    (5,  "8-QAM Modulator",  "C2"),
]

PHASES = ["vanilla", "picasso"]


def clear_cache():
    """Remove cached run results so we always run fresh."""
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)


def latest_json() -> Path | None:
    jsons = sorted(TEST_RESULTS_DIR.glob(f"results_{MODEL}_*.json"))
    return jsons[-1] if jsons else None


def run_and_read(problem_num: int, phase: str, samples: int) -> list[dict]:
    """
    Run a single problem/phase and return per-sample result dicts.
    The result JSON is a flat list; find the entry matching problem_id and phase.
    """
    clear_cache()

    flag = "--picasso-only" if phase == "picasso" else "--vanilla-only"
    cmd = [
        sys.executable, "gd_picasso/test_with_llm.py",
        "--model", MODEL,
        "--num-problems", str(problem_num),
        "--samples", str(samples),
        flag,
    ]
    subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)

    path = latest_json()
    if not path:
        return []

    with open(path) as f:
        data = json.load(f)  # flat list of problem result dicts

    # The last entry is the problem we just ran (num-problems runs 1..N, we want N)
    for entry in reversed(data):
        if str(entry.get("problem_id")) == str(problem_num) and entry.get("phase") == phase:
            return entry.get("samples", [])

    # Fallback: just take the last entry's samples if IDs don't align
    return data[-1].get("samples", []) if data else []


def bar(passed: int, total: int, width: int = 20) -> str:
    filled = int(width * passed / total) if total > 0 else 0
    return f"[{'█' * filled}{'░' * (width - filled)}] {passed}/{total}"


def failure_reason(s: dict) -> str:
    if not s.get("component_built", True):
        err = s.get("errors", [""])
        # shorten the routing angle error to something readable
        msg = err[0] if err else "build failed"
        if "same angle" in msg:
            return "routing angle mismatch"
        if "build" in msg.lower():
            return "build failed"
        return msg[:60]
    vr = s.get("validation_reports", {})
    if not s.get("drc_passed", True):
        return "DRC fail"
    if not vr.get("functional", {}).get("passed", True):
        return "SAX fail"
    return "unknown"


def main():
    print("=" * 70)
    print(f"  PICasso Smoke Tests  |  model={MODEL}  |  {SAMPLES} samples each")
    print("=" * 70)

    summary = []

    for prob_num, label, tier in TEST_PROBLEMS:
        print(f"\n{'─' * 70}")
        print(f"  Problem {prob_num}: {label}  (Complexity {tier})")
        print(f"{'─' * 70}")

        row = {"label": label, "tier": tier}

        for phase in PHASES:
            print(f"\n  ▶ {phase.upper()}")
            samples = run_and_read(prob_num, phase, SAMPLES)

            if not samples:
                print("    ⚠️  No data returned — check API key / errors above")
                row[f"{phase}_passed"] = 0
                row[f"{phase}_total"] = SAMPLES
                continue

            passed = sum(1 for s in samples if s.get("passed", False))
            total  = len(samples)
            row[f"{phase}_passed"] = passed
            row[f"{phase}_total"]  = total

            for i, s in enumerate(samples, 1):
                ok   = s.get("passed", False)
                icon = "✅" if ok else "❌"
                note = "" if ok else f"  ({failure_reason(s)})"
                print(f"    Sample {i}: {icon}{note}")

            spec1 = passed / total if total > 0 else 0.0
            spec_k = "100%" if passed > 0 else "0%"
            print(f"    {bar(passed, total)}  Spec@1≈{spec1:.0%}  Spec@{total}≈{spec_k}")

        summary.append(row)

    # ── Summary table ────────────────────────────────────────────────────────
    print(f"\n\n{'=' * 70}")
    print("  SUMMARY  (Vanilla vs PICasso, Spec@1 over 3 samples)")
    print(f"{'=' * 70}")
    print(f"  {'Problem':<22} {'Tier':<5} {'Vanilla':>9}  {'PICasso':>9}  {'Δ':>6}")
    print(f"  {'-'*22} {'-'*5} {'-'*9}  {'-'*9}  {'-'*6}")

    for row in summary:
        vp = row.get("vanilla_passed", 0)
        vt = row.get("vanilla_total", SAMPLES)
        pp = row.get("picasso_passed", 0)
        pt = row.get("picasso_total", SAMPLES)
        vr = vp / vt if vt else 0
        pr = pp / pt if pt else 0
        delta = pr - vr
        sign = "+" if delta >= 0 else ""
        print(f"  {row['label']:<22} {row['tier']:<5} {vr:>8.0%}  {pr:>9.0%}  {sign}{delta:.0%}")

    print(f"{'=' * 70}")
    print("\nStochastic note: 3 samples gives some variance. Paper used n=5.")
    print("Spec@3 = 100% means at least 1 of 3 passed (not that all passed).")


if __name__ == "__main__":
    main()
