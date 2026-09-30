"""A-priori SPA / ablation protocol freeze — cite this module (and its git tag).

Do **not** retune ``SPA_TOL_RAD`` after seeing routed WNS.
Do **not** reshape the N1 error taxonomy after counting LLM samples.

Tag: ``protocol-freeze-n1-spa`` (created when this file lands on the branch).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# SPA Δφ tolerance (layout-N3 / PIC-Set e2e claims)
# ---------------------------------------------------------------------------
# Frozen before further routed-layout SPA campaigns. Comparator / planted-φ
# unit tests that used 0.01 historically must either migrate here or stay
# labeled SYNTHETIC_NOT_LAYOUT and not cite this constant.
SPA_TOL_RAD: float = 0.05

# ---------------------------------------------------------------------------
# N1 three-arm ablation protocol (typed mutations vs YAML)
# ---------------------------------------------------------------------------
# Same LLM, same 12-task subset, n=5 samples per task per arm.
# Arms isolate representation from critic feedback:
#
#   A — YAML text + PICasso pilot-prompt repair loop (baseline)
#   B — YAML text + ExactCritic feedback on the *parsed* result
#   C — typed mutations + ExactCritic
#
# Comparisons:
#   A vs B → critic alone
#   B vs C → representation (critic held fixed) — this is the N1 claim
#   If B ≈ C, reword N1: gains are from the critic, not unrepresentability.
#
N1_ABLATION_ARMS = ("A_yaml_pilot", "B_yaml_exact_critic", "C_typed_exact_critic")
N1_SAMPLES_PER_TASK: int = 5
N1_TASK_SUBSET_SIZE: int = 12  # PIC-Set 12-task subset; pin IDs when runner lands

# Error taxonomy — fixed a priori; tally only these buckets.
N1_ERROR_TAXONOMY = (
    "illegal_port",
    "fanout",
    "out_of_bounds_param",
    "non_ascii",
    "unit_mismatch",
    "wrong_connectivity",
)
