"""SPA / N1 ablation protocol freeze — cite this module and its git tag.

Tag: ``protocol-freeze-n1-spa`` (annotated, on ``origin``).

Covers **future** SPA campaigns and the N1 three-arm ablation. Synthetic /
early layout-N3 / pre-tag routed Task-6/9 runs are **exploratory** — see
``PROTOCOL_FREEZE.md``. Do **not** rewrite ``3dd1fe4`` or move the tag
(including to strip commit trailers).

Do **not** retune ``SPA_TOL_RAD`` after seeing post-freeze routed WNS.
Do **not** reshape the N1 error taxonomy after counting LLM samples.
Tip must not drift from tag-era constants (enforced by
``test_spa_protocol_freeze.py``).
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

# ---------------------------------------------------------------------------
# Tag identity (for run logs)
# ---------------------------------------------------------------------------
PROTOCOL_FREEZE_TAG: str = "protocol-freeze-n1-spa"
PROTOCOL_FREEZE_PATH: str = "gd_picasso/pcg/spa_protocol.py"

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
# same token cap. Log API-reported model ID per call.
#
#   A — YAML text + PICasso pilot-prompt repair loop (baseline)
#   B — YAML text + ExactCritic feedback on the *parsed* result
#   C — typed mutations + ExactCritic
#
# A vs B → critic alone; B vs C → representation (N1 claim).
# If B ≈ C, reword N1.
#
N1_ABLATION_ARMS = ("A_yaml_pilot", "B_yaml_exact_critic", "C_typed_exact_critic")
N1_SAMPLES_PER_TASK: int = 5
N1_TASK_SUBSET_SIZE: int = 12

# Named before any dry run / campaign. Stratified PIC-Set IDs.
N1_TASK_SUBSET: Tuple[int, ...] = (1, 2, 9, 10, 11, 19, 20, 26, 29, 30, 34, 36)
# Critic-leakage holdout (within the 12): not used to develop ExactCritic rules.
N1_CRITIC_HOLDOUT_TASK_IDS: Tuple[int, ...] = (11, 26)
# Dry-run = ceiling tasks only (arm A already ~100% in parent Table V / benchmarks).
# Logging check only; samples excluded from campaign; prompts/critic frozen first.
N1_DRY_RUN_TASK_IDS: Tuple[int, ...] = (34, 36)

N1_MAX_REPAIR_ROUNDS: int = 3
N1_TEMPERATURE: float = 0.3
N1_MAX_TOKENS: int = 2048
# Exact provider model string — must be pinned before campaign (not dry-run OK to leave sentinel).
N1_LLM_MODEL_ID: str = "PIN_BEFORE_CAMPAIGN"

# Error taxonomy — fixed a priori; tally only these buckets (+ unparseable_yaml).
N1_ERROR_TAXONOMY = (
    "illegal_port",
    "fanout",
    "out_of_bounds_param",
    "non_ascii",
    "unit_mismatch",
    "wrong_connectivity",
)
N1_UNPARSEABLE_YAML = "unparseable_yaml"  # arm B only; counts in denominator

# SPA Tasks 6 & 9: method-motivating known-failure checks — not blind predictions.
SPA_KNOWN_FAILURE_CHECK_TASK_IDS: Tuple[int, ...] = (6, 9)


def n1_campaign_ready() -> bool:
    """True iff LLM model ID is pinned (required before real campaign, not dry-run)."""
    return bool(N1_LLM_MODEL_ID) and N1_LLM_MODEL_ID != "PIN_BEFORE_CAMPAIGN"


def run_manifest(*, tip_sha: str, tag_sha: str, tag_name: str = PROTOCOL_FREEZE_TAG) -> Dict[str, Any]:
    """Fields every run log must include (dry-run and campaign)."""
    return {
        "protocol_freeze_tag": tag_name,
        "protocol_freeze_tag_sha": tag_sha,
        "tip_commit_sha": tip_sha,
        "spa_tol_primary_rad": SPA_TOL_PRIMARY_RAD,
        "spa_tol_sweep_rad": list(SPA_TOL_SWEEP_RAD),
        "n1_llm_model_id": N1_LLM_MODEL_ID,
        "n1_temperature": N1_TEMPERATURE,
        "n1_max_tokens": N1_MAX_TOKENS,
        "n1_max_repair_rounds": N1_MAX_REPAIR_ROUNDS,
        "n1_task_subset": list(N1_TASK_SUBSET),
        "n1_critic_holdout_task_ids": list(N1_CRITIC_HOLDOUT_TASK_IDS),
        "n1_dry_run_task_ids": list(N1_DRY_RUN_TASK_IDS),
        "n1_error_taxonomy": list(N1_ERROR_TAXONOMY),
    }
