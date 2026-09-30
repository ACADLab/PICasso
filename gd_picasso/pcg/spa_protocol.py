"""SPA / N1 ablation protocol freeze — cite this module and its git tags.

Tags
----
- ``protocol-freeze-n1-spa`` — SPA_TOL + N1 taxonomy / arms (constants).
- ``protocol-freeze-n1-prompts`` — ExactCritic + pilot prompt artifact hashes
  (cut after this module locks the artifact list; before dry-run).
- ``protocol-freeze-n1-campaign`` — cut only after ``N1_LLM_MODEL_ID`` is pinned
  to a dated snapshot string (not a floating alias).

Do **not** rewrite ``3dd1fe4`` or move ``protocol-freeze-n1-spa``.
Tip must not drift from tag-era constants (``test_spa_protocol_freeze.py``).
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Tag identity (for run logs)
# ---------------------------------------------------------------------------
PROTOCOL_FREEZE_TAG: str = "protocol-freeze-n1-spa"
PROTOCOL_FREEZE_PROMPTS_TAG: str = "protocol-freeze-n1-prompts"
PROTOCOL_FREEZE_CAMPAIGN_TAG: str = "protocol-freeze-n1-campaign"
PROTOCOL_FREEZE_PATH: str = "gd_picasso/pcg/spa_protocol.py"

# Artifact paths hashed into every run manifest (prompt / critic freeze).
# Arm A = pilot prompt; arms B/C = ExactCritic. Do not edit after prompts tag
# without a new annotated tag or disclosed deviation.
N1_FROZEN_ARTIFACT_PATHS: Tuple[str, ...] = (
    "gd_picasso/agents/exact_critic.py",
    "gd_picasso/pilot/base_pilot_generator.py",
    "gd_picasso/pcg/spa_protocol.py",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# SPA Δφ tolerance (layout / PIC-Set e2e claims AFTER the freeze)
# ---------------------------------------------------------------------------
# Schematic MATCHED_LENGTH intent / synthetic planted-φ: ~0.01 rad (§2.2).
#
# Primary layout tolerance (chosen first; justifications written after):
#   SPA_TOL_RAD = 0.05  ≈  π/64
# Meaning: equal to **one LSB** of an *assumed* 6-bit code over [0, π]
#   (π/2^6 = π/64). This is NOT the worst-case quantization error (½ LSB
#   ≈ 0.025 rad), and the 6-bit DAC is an assumption — not a Cornerstone
#   datasheet fact. Parent RobustPass ``phase_error_std: 0.05`` is a 1σ
#   perturbation scale (corroborating context only — not a yield-grade
#   pass/fail budget; ~⅓ of draws exceed 1σ).
#
# Primary vs sensitivity: SPA_TOL_RAD is the **primary** test;
# SPA_TOL_SWEEP_RAD others are sensitivity only. N3 is counted against if
# any of the 12 confirmatory tasks is misclassified at 0.05 — do not pick
# another sweep point post hoc to recover 12/12.
SPA_TOL_RAD: float = 0.05
SPA_TOL_SWEEP_RAD: Tuple[float, ...] = (0.01, 0.02, 0.05, 0.1)
SPA_TOL_PRIMARY_RAD: float = 0.05  # primary test; sweep others = sensitivity only

# ---------------------------------------------------------------------------
# N1 three-arm ablation protocol (typed mutations vs YAML)
# ---------------------------------------------------------------------------
# Same LLM model ID + version, same temperature, same max repair rounds,
# same token cap. Log API-reported model ID per call; abort on mismatch.
#
#   A — YAML text + PICasso pilot-prompt repair loop (baseline)
#   B — YAML text + ExactCritic feedback on the *parsed* result
#   C — typed mutations + ExactCritic
#
N1_ABLATION_ARMS = ("A_yaml_pilot", "B_yaml_exact_critic", "C_typed_exact_critic")
N1_SAMPLES_PER_TASK: int = 5
N1_TASK_SUBSET_SIZE: int = 12

# Campaign set — NOT ICLAD / parent Table V's 12. Task 6 (64-QAM) is absent
# on purpose (non_expressible / not the structural-N1 claim). Parent Table V
# numbers are not directly comparable to this campaign; say so in the paper.
N1_TASK_SUBSET: Tuple[int, ...] = (1, 2, 9, 10, 11, 19, 20, 26, 29, 30, 34, 36)
N1_TASK_SUBSET_NOTE: str = (
    "Not parent ICLAD Table V's 12; Task 6 (64-QAM) absent by design; "
    "do not compare campaign rates directly to Table V."
)

# Critic leakage check — WEAK, not a proven holdout.
# ExactCritic (d852424) is task-agnostic and landed with only linear/mzi/mzm/
# ring_bus fixtures; task_11/26 YAML were never in that commit. But the full
# 36-task corpus and rejection/e2e suites exercise the same primitives, and
# git log cannot prove no critic edit was made with 11/26 in view. Report
# subset descriptively (10 samples/arm); no significance claim. Prefer
# parametric variants (arm lengths / stage counts) the critic never saw.
N1_CRITIC_LEAKAGE_CHECK_TASK_IDS: Tuple[int, ...] = (11, 26)
N1_CRITIC_LEAKAGE_STATUS: str = "weak_unproven_holdout"
# Alias — same IDs; do not treat as a clean holdout in the paper.
N1_CRITIC_HOLDOUT_TASK_IDS: Tuple[int, ...] = (11, 26)

# Dry-run ceiling tasks — justified BEFORE any N1 dry-run from earlier logs:
# BENCHMARK_FINAL_RESULTS.md "Successful Circuits (100% Pass@k)":
#   34 Simple MMI 1x2 Splitter  3/3 (100%)
#   36 Straight + Phase Shifter 3/3 (100%)
# Not derived by running arm A in the N1 dry-run. Samples excluded from
# campaign data; still in the campaign set → also record that prompts/critic
# were untouched after the dry run (artifact hashes must match prompts tag).
N1_DRY_RUN_TASK_IDS: Tuple[int, ...] = (34, 36)
N1_DRY_RUN_CEILING_CITATION: str = (
    "BENCHMARK_FINAL_RESULTS.md §Successful Circuits (100% Pass@k): "
    "tasks 34 and 36 at 3/3 — not from N1 dry-run / arm A"
)

N1_MAX_REPAIR_ROUNDS: int = 3
N1_TEMPERATURE: float = 0.3
N1_MAX_TOKENS: int = 2048
# Dated snapshot string (e.g. "gpt-4o-2024-08-06"), never a floating alias.
# PIN_BEFORE_CAMPAIGN until campaign tag; changing this requires updating the
# tip-vs-tag golden and cutting protocol-freeze-n1-campaign.
N1_LLM_MODEL_ID: str = "PIN_BEFORE_CAMPAIGN"

N1_ERROR_TAXONOMY = (
    "illegal_port",
    "fanout",
    "out_of_bounds_param",
    "non_ascii",
    "unit_mismatch",
    "wrong_connectivity",
)
N1_UNPARSEABLE_YAML = "unparseable_yaml"

SPA_KNOWN_FAILURE_CHECK_TASK_IDS: Tuple[int, ...] = (6, 9)


class DirtyWorktreeError(RuntimeError):
    """Raised when a run is attempted on a dirty git worktree."""


class ModelIdMismatchError(RuntimeError):
    """Raised when the API-reported model ID differs from N1_LLM_MODEL_ID."""


def n1_campaign_ready() -> bool:
    """True iff LLM model ID is pinned to a non-sentinel dated snapshot."""
    return bool(N1_LLM_MODEL_ID) and N1_LLM_MODEL_ID != "PIN_BEFORE_CAMPAIGN"


def assert_api_model_matches_pin(api_reported_model_id: str) -> None:
    """Abort a call if the provider's reported model ID ≠ frozen pin."""
    if not n1_campaign_ready():
        raise ModelIdMismatchError(
            "N1_LLM_MODEL_ID is still PIN_BEFORE_CAMPAIGN; "
            "pin a dated snapshot and cut protocol-freeze-n1-campaign first"
        )
    if api_reported_model_id != N1_LLM_MODEL_ID:
        raise ModelIdMismatchError(
            f"API reported model {api_reported_model_id!r} != "
            f"pinned N1_LLM_MODEL_ID {N1_LLM_MODEL_ID!r}; aborting call"
        )


def _git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=_REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f"git {' '.join(args)} failed")
    return (proc.stdout or "").strip()


def worktree_is_clean() -> bool:
    """True iff ``git status --porcelain`` is empty."""
    return _git("status", "--porcelain") == ""


def require_clean_worktree() -> None:
    """Refuse runs on a dirty worktree — 'frozen' must be checkable."""
    porcelain = _git("status", "--porcelain")
    if porcelain:
        raise DirtyWorktreeError(
            "Refusing run on dirty worktree. Commit or stash first.\n" + porcelain
        )


def hash_file(rel_path: str) -> str:
    data = (_REPO_ROOT / rel_path).read_bytes()
    return hashlib.sha256(data).hexdigest()


def frozen_artifact_hashes(
    paths: Sequence[str] = N1_FROZEN_ARTIFACT_PATHS,
) -> Dict[str, str]:
    """SHA-256 of each prompt/critic freeze artifact (repo-relative path → hex)."""
    return {p: hash_file(p) for p in paths}


def combined_artifacts_hash(
    paths: Sequence[str] = N1_FROZEN_ARTIFACT_PATHS,
) -> str:
    """Single digest over sorted path:hash lines (stable across machines)."""
    lines = [f"{p}:{h}" for p, h in sorted(frozen_artifact_hashes(paths).items())]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def resolve_tag_sha(tag_name: str) -> Optional[str]:
    try:
        return _git("rev-list", "-n", "1", tag_name)
    except RuntimeError:
        return None


def run_manifest(
    *,
    tip_sha: Optional[str] = None,
    tag_sha: Optional[str] = None,
    tag_name: str = PROTOCOL_FREEZE_TAG,
    prompts_tag_sha: Optional[str] = None,
    campaign_tag_sha: Optional[str] = None,
    require_clean: bool = True,
    prompts_untouched_after_dry_run: Optional[bool] = None,
) -> Dict[str, Any]:
    """Fields every run log must include (dry-run and campaign).

    Refuses a dirty worktree by default so "frozen" is checkable, not aspirational.
    """
    if require_clean:
        require_clean_worktree()
    tip = tip_sha or _git("rev-parse", "HEAD")
    spa_tag = tag_sha or resolve_tag_sha(tag_name) or ""
    prompts_sha = prompts_tag_sha or resolve_tag_sha(PROTOCOL_FREEZE_PROMPTS_TAG) or ""
    campaign_sha = campaign_tag_sha or resolve_tag_sha(PROTOCOL_FREEZE_CAMPAIGN_TAG) or ""
    artifacts = frozen_artifact_hashes()
    return {
        "protocol_freeze_tag": tag_name,
        "protocol_freeze_tag_sha": spa_tag,
        "protocol_freeze_prompts_tag": PROTOCOL_FREEZE_PROMPTS_TAG,
        "protocol_freeze_prompts_tag_sha": prompts_sha,
        "protocol_freeze_campaign_tag": PROTOCOL_FREEZE_CAMPAIGN_TAG,
        "protocol_freeze_campaign_tag_sha": campaign_sha,
        "tip_commit_sha": tip,
        "worktree_clean": worktree_is_clean(),
        "frozen_artifact_hashes": artifacts,
        "frozen_artifacts_combined_sha256": combined_artifacts_hash(),
        "spa_tol_primary_rad": SPA_TOL_PRIMARY_RAD,
        "spa_tol_sweep_rad": list(SPA_TOL_SWEEP_RAD),
        "n1_llm_model_id": N1_LLM_MODEL_ID,
        "n1_temperature": N1_TEMPERATURE,
        "n1_max_tokens": N1_MAX_TOKENS,
        "n1_max_repair_rounds": N1_MAX_REPAIR_ROUNDS,
        "n1_task_subset": list(N1_TASK_SUBSET),
        "n1_task_subset_note": N1_TASK_SUBSET_NOTE,
        "n1_critic_leakage_check_task_ids": list(N1_CRITIC_LEAKAGE_CHECK_TASK_IDS),
        "n1_critic_leakage_status": N1_CRITIC_LEAKAGE_STATUS,
        "n1_critic_holdout_task_ids": list(N1_CRITIC_HOLDOUT_TASK_IDS),  # alias
        "n1_dry_run_task_ids": list(N1_DRY_RUN_TASK_IDS),
        "n1_dry_run_ceiling_citation": N1_DRY_RUN_CEILING_CITATION,
        "prompts_untouched_after_dry_run": prompts_untouched_after_dry_run,
        "n1_error_taxonomy": list(N1_ERROR_TAXONOMY),
    }


def verify_artifacts_match_mapping(expected: Mapping[str, str]) -> None:
    """Fail if on-disk artifact hashes drifted from a recorded freeze mapping."""
    actual = frozen_artifact_hashes()
    if actual != dict(expected):
        raise RuntimeError(
            f"Frozen artifact hash drift.\nexpected={dict(expected)}\nactual={actual}"
        )
