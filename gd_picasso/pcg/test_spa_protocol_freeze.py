"""Tip-vs-tag guard + prompt/critic freeze checks for ``spa_protocol.py``."""

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
    N1_CRITIC_LEAKAGE_CHECK_TASK_IDS,
    N1_CRITIC_LEAKAGE_STATUS,
    N1_DRY_RUN_CEILING_CITATION,
    N1_DRY_RUN_TASK_IDS,
    N1_ERROR_TAXONOMY,
    N1_FROZEN_ARTIFACT_PATHS,
    N1_LLM_MODEL_ID,
    N1_MAX_REPAIR_ROUNDS,
    N1_MAX_TOKENS,
    N1_SAMPLES_PER_TASK,
    N1_TASK_SUBSET,
    N1_TASK_SUBSET_NOTE,
    N1_TASK_SUBSET_SIZE,
    N1_TEMPERATURE,
    N1_UNPARSEABLE_YAML,
    PROTOCOL_FREEZE_CAMPAIGN_TAG,
    PROTOCOL_FREEZE_PATH,
    PROTOCOL_FREEZE_PROMPTS_TAG,
    PROTOCOL_FREEZE_TAG,
    SPA_KNOWN_FAILURE_CHECK_TASK_IDS,
    SPA_TOL_PRIMARY_RAD,
    SPA_TOL_RAD,
    SPA_TOL_SWEEP_RAD,
    DirtyWorktreeError,
    ModelIdMismatchError,
    assert_api_model_matches_pin,
    combined_artifacts_hash,
    frozen_artifact_hashes,
    n1_campaign_ready,
    require_clean_worktree,
    run_manifest,
    worktree_is_clean,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

TAG_ERA_NAMES: FrozenSet[str] = frozenset(
    {
        "SPA_TOL_RAD",
        "N1_ABLATION_ARMS",
        "N1_SAMPLES_PER_TASK",
        "N1_TASK_SUBSET_SIZE",
        "N1_ERROR_TAXONOMY",
    }
)

TIP_LOCKED: Dict[str, Any] = {
    "SPA_TOL_SWEEP_RAD": (0.01, 0.02, 0.05, 0.1),
    "SPA_TOL_PRIMARY_RAD": 0.05,
    "N1_TEMPERATURE": 0.3,
    "N1_MAX_TOKENS": 2048,
    "N1_MAX_REPAIR_ROUNDS": 3,
    "N1_TASK_SUBSET": (1, 2, 9, 10, 11, 19, 20, 26, 29, 30, 34, 36),
    "N1_CRITIC_HOLDOUT_TASK_IDS": (11, 26),
    "N1_CRITIC_LEAKAGE_CHECK_TASK_IDS": (11, 26),
    "N1_CRITIC_LEAKAGE_STATUS": "weak_unproven_holdout",
    "N1_DRY_RUN_TASK_IDS": (34, 36),
    "N1_UNPARSEABLE_YAML": "unparseable_yaml",
    "SPA_KNOWN_FAILURE_CHECK_TASK_IDS": (6, 9),
    "PROTOCOL_FREEZE_TAG": "protocol-freeze-n1-spa",
    "PROTOCOL_FREEZE_PROMPTS_TAG": "protocol-freeze-n1-prompts",
    "PROTOCOL_FREEZE_CAMPAIGN_TAG": "protocol-freeze-n1-campaign",
    "N1_FROZEN_ARTIFACT_PATHS": (
        "gd_picasso/agents/exact_critic.py",
        "gd_picasso/pilot/base_pilot_generator.py",
        "gd_picasso/pcg/spa_protocol.py",
    ),
    "N1_LLM_MODEL_ID": "PIN_BEFORE_CAMPAIGN",
}


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def _module_assignments(source: str) -> Dict[str, Any]:
    """Module-level literal assignments only (skip Path(...) and other exprs)."""
    tree = ast.parse(source)
    out: Dict[str, Any] = {}
    for node in tree.body:
        target_name: str | None = None
        value_node = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name):
                target_name, value_node = tgt.id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                target_name, value_node = node.target.id, node.value
        if target_name is None or value_node is None:
            continue
        try:
            out[target_name] = ast.literal_eval(value_node)
        except (ValueError, TypeError):
            continue
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
    for name, expected in TIP_LOCKED.items():
        actual = getattr(spa_protocol, name)
        assert actual == expected, f"{name}: tip={actual!r} locked={expected!r}"


def test_primary_tol_in_sweep_and_aliased() -> None:
    assert SPA_TOL_RAD == SPA_TOL_PRIMARY_RAD == 0.05
    assert SPA_TOL_RAD in SPA_TOL_SWEEP_RAD


def test_task_subset_invariants() -> None:
    assert len(N1_TASK_SUBSET) == N1_TASK_SUBSET_SIZE == 12
    assert set(N1_CRITIC_HOLDOUT_TASK_IDS).issubset(N1_TASK_SUBSET)
    assert N1_CRITIC_HOLDOUT_TASK_IDS == N1_CRITIC_LEAKAGE_CHECK_TASK_IDS
    assert N1_CRITIC_LEAKAGE_STATUS == "weak_unproven_holdout"
    assert set(N1_DRY_RUN_TASK_IDS).issubset(N1_TASK_SUBSET)
    assert set(N1_DRY_RUN_TASK_IDS).isdisjoint(N1_CRITIC_LEAKAGE_CHECK_TASK_IDS)
    assert set(N1_DRY_RUN_TASK_IDS).issubset({30, 34, 35, 36})
    assert "BENCHMARK_FINAL_RESULTS.md" in N1_DRY_RUN_CEILING_CITATION
    assert "Table V" in N1_TASK_SUBSET_NOTE
    assert "Task 6" in N1_TASK_SUBSET_NOTE
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


def test_run_manifest_includes_shas_and_artifact_hashes() -> None:
    tip = _git("rev-parse", "HEAD")
    tag = _git("rev-list", "-n", "1", PROTOCOL_FREEZE_TAG)
    # Worktree is often dirty during development; production runs use require_clean=True.
    m = run_manifest(tip_sha=tip, tag_sha=tag, require_clean=False)
    assert m["tip_commit_sha"] == tip
    assert m["protocol_freeze_tag_sha"] == tag
    assert m["protocol_freeze_tag"] == PROTOCOL_FREEZE_TAG
    assert m["protocol_freeze_prompts_tag"] == PROTOCOL_FREEZE_PROMPTS_TAG
    assert m["protocol_freeze_campaign_tag"] == PROTOCOL_FREEZE_CAMPAIGN_TAG
    assert m["spa_tol_primary_rad"] == 0.05
    assert m["n1_critic_holdout_task_ids"] == [11, 26]
    assert m["n1_critic_leakage_status"] == "weak_unproven_holdout"
    assert m["n1_dry_run_task_ids"] == [34, 36]
    assert set(m["frozen_artifact_hashes"]) == set(N1_FROZEN_ARTIFACT_PATHS)
    assert m["frozen_artifacts_combined_sha256"] == combined_artifacts_hash()
    assert len(m["frozen_artifacts_combined_sha256"]) == 64


def test_frozen_artifact_files_exist() -> None:
    hashes = frozen_artifact_hashes()
    for path, digest in hashes.items():
        assert (REPO_ROOT / path).is_file(), path
        assert len(digest) == 64


def test_require_clean_worktree_detects_dirt() -> None:
    if worktree_is_clean():
        pytest.skip("worktree clean — cannot assert DirtyWorktreeError")
    with pytest.raises(DirtyWorktreeError):
        require_clean_worktree()
    with pytest.raises(DirtyWorktreeError):
        run_manifest(require_clean=True)


def test_campaign_ready_requires_model_pin() -> None:
    assert N1_LLM_MODEL_ID == "PIN_BEFORE_CAMPAIGN"
    assert n1_campaign_ready() is False
    with pytest.raises(ModelIdMismatchError):
        assert_api_model_matches_pin("gpt-4o-2024-08-06")


def test_tip_source_parses_cleanly() -> None:
    names: Set[str] = set(_module_assignments(_tip_source()))
    assert TAG_ERA_NAMES.issubset(names)
    assert set(TIP_LOCKED).issubset(names)
