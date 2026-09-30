"""Tip-vs-tag guard for ``spa_protocol.py`` freeze constants.

Fails if tip drifts from ``protocol-freeze-n1-spa`` for any constant that
existed at the tag. Post-tag pins are locked to an explicit golden here;
promote them into a new annotated tag before the campaign (do **not** move
``protocol-freeze-n1-spa``).
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import Any, Dict, FrozenSet, Set

import pytest

from gd_picasso.pcg import spa_protocol
from gd_picasso.pcg.spa_protocol import (
    N1_ABLATION_ARMS,
    N1_CRITIC_HOLDOUT_TASK_IDS,
    N1_DRY_RUN_TASK_IDS,
    N1_ERROR_TAXONOMY,
    N1_LLM_MODEL_ID,
    N1_MAX_REPAIR_ROUNDS,
    N1_MAX_TOKENS,
    N1_SAMPLES_PER_TASK,
    N1_TASK_SUBSET,
    N1_TASK_SUBSET_SIZE,
    N1_TEMPERATURE,
    N1_UNPARSEABLE_YAML,
    PROTOCOL_FREEZE_PATH,
    PROTOCOL_FREEZE_TAG,
    SPA_KNOWN_FAILURE_CHECK_TASK_IDS,
    SPA_TOL_PRIMARY_RAD,
    SPA_TOL_RAD,
    SPA_TOL_SWEEP_RAD,
    n1_campaign_ready,
    run_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Names present on protocol-freeze-n1-spa (must match git show exactly).
TAG_ERA_NAMES: FrozenSet[str] = frozenset(
    {
        "SPA_TOL_RAD",
        "N1_ABLATION_ARMS",
        "N1_SAMPLES_PER_TASK",
        "N1_TASK_SUBSET_SIZE",
        "N1_ERROR_TAXONOMY",
    }
)

# Post-tag pins locked by this test (commit + optional follow-on annotated tag).
# Do not change without a disclosed protocol deviation or a new annotated tag.
TIP_LOCKED: Dict[str, Any] = {
    "SPA_TOL_SWEEP_RAD": (0.01, 0.02, 0.05, 0.1),
    "SPA_TOL_PRIMARY_RAD": 0.05,
    "N1_TEMPERATURE": 0.3,
    "N1_MAX_TOKENS": 2048,
    "N1_MAX_REPAIR_ROUNDS": 3,
    "N1_TASK_SUBSET": (1, 2, 9, 10, 11, 19, 20, 26, 29, 30, 34, 36),
    "N1_CRITIC_HOLDOUT_TASK_IDS": (11, 26),
    "N1_DRY_RUN_TASK_IDS": (34, 36),
    "N1_UNPARSEABLE_YAML": "unparseable_yaml",
    "SPA_KNOWN_FAILURE_CHECK_TASK_IDS": (6, 9),
    "PROTOCOL_FREEZE_TAG": "protocol-freeze-n1-spa",
}


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def _module_assignments(source: str) -> Dict[str, Any]:
    """Evaluate module-level assignments (constants only) via AST literals."""
    tree = ast.parse(source)
    out: Dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name):
                out[tgt.id] = ast.literal_eval(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                out[node.target.id] = ast.literal_eval(node.value)
    return out


def _tag_source() -> str:
    return _git("show", f"{PROTOCOL_FREEZE_TAG}:{PROTOCOL_FREEZE_PATH}")


def _tip_source() -> str:
    return (REPO_ROOT / PROTOCOL_FREEZE_PATH).read_text(encoding="utf-8")


def test_freeze_tag_resolves() -> None:
    sha = _git("rev-list", "-n", "1", PROTOCOL_FREEZE_TAG)
    assert len(sha) == 40
    assert _git("cat-file", "-t", PROTOCOL_FREEZE_TAG) == "tag"


def test_tag_era_constants_match_git_show() -> None:
    """Tip must not drift from protocol-freeze-n1-spa for tag-era names."""
    tagged = _module_assignments(_tag_source())
    tip = _module_assignments(_tip_source())
    missing = TAG_ERA_NAMES - set(tagged)
    assert not missing, f"tag missing expected names: {missing}"
    for name in sorted(TAG_ERA_NAMES):
        assert tip[name] == tagged[name], (
            f"{name} drifted from {PROTOCOL_FREEZE_TAG}: "
            f"tip={tip[name]!r} tag={tagged[name]!r}"
        )
        assert getattr(spa_protocol, name) == tagged[name]


def test_tip_extension_pins_locked() -> None:
    """Post-tag pins stay at the committed golden (new tag before campaign)."""
    for name, expected in TIP_LOCKED.items():
        actual = getattr(spa_protocol, name)
        assert actual == expected, f"{name}: tip={actual!r} locked={expected!r}"


def test_primary_tol_in_sweep_and_aliased() -> None:
    assert SPA_TOL_RAD == SPA_TOL_PRIMARY_RAD == 0.05
    assert SPA_TOL_RAD in SPA_TOL_SWEEP_RAD


def test_task_subset_invariants() -> None:
    assert len(N1_TASK_SUBSET) == N1_TASK_SUBSET_SIZE == 12
    assert set(N1_CRITIC_HOLDOUT_TASK_IDS).issubset(N1_TASK_SUBSET)
    assert set(N1_DRY_RUN_TASK_IDS).issubset(N1_TASK_SUBSET)
    # Dry-run must not consume holdout signal tasks.
    assert set(N1_DRY_RUN_TASK_IDS).isdisjoint(N1_CRITIC_HOLDOUT_TASK_IDS)
    assert set(N1_DRY_RUN_TASK_IDS).issubset({30, 34, 35, 36})  # ceiling / trivial class
    assert N1_SAMPLES_PER_TASK == 5
    assert N1_ABLATION_ARMS == (
        "A_yaml_pilot",
        "B_yaml_exact_critic",
        "C_typed_exact_critic",
    )
    assert N1_ERROR_TAXONOMY == (
        "illegal_port",
        "fanout",
        "out_of_bounds_param",
        "non_ascii",
        "unit_mismatch",
        "wrong_connectivity",
    )
    assert N1_UNPARSEABLE_YAML == "unparseable_yaml"
    assert SPA_KNOWN_FAILURE_CHECK_TASK_IDS == (6, 9)


def test_budget_pins() -> None:
    assert N1_TEMPERATURE == 0.3
    assert N1_MAX_TOKENS == 2048
    assert N1_MAX_REPAIR_ROUNDS == 3


def test_run_manifest_includes_shas() -> None:
    tip = _git("rev-parse", "HEAD")
    tag = _git("rev-list", "-n", "1", PROTOCOL_FREEZE_TAG)
    m = run_manifest(tip_sha=tip, tag_sha=tag)
    assert m["tip_commit_sha"] == tip
    assert m["protocol_freeze_tag_sha"] == tag
    assert m["protocol_freeze_tag"] == PROTOCOL_FREEZE_TAG
    assert m["spa_tol_primary_rad"] == 0.05
    assert m["n1_critic_holdout_task_ids"] == [11, 26]
    assert m["n1_dry_run_task_ids"] == [34, 36]


def test_campaign_ready_requires_model_pin() -> None:
    # Sentinel is intentional until the exact API model string is chosen.
    assert N1_LLM_MODEL_ID == "PIN_BEFORE_CAMPAIGN"
    assert n1_campaign_ready() is False


def test_tip_source_parses_cleanly() -> None:
    names: Set[str] = set(_module_assignments(_tip_source()))
    assert TAG_ERA_NAMES.issubset(names)
    assert set(TIP_LOCKED).issubset(names)
