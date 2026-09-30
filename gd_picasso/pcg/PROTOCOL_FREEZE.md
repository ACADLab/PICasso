# Protocol freeze — SPA Δφ + N1 three-arm ablation

**Status:** frozen in code (`gd_picasso/pcg/spa_protocol.py`).

| Tag | Covers | Notes |
|---|---|---|
| `protocol-freeze-n1-spa` | SPA_TOL + N1 arms/taxonomy/budgets | Annotated; on `origin`; **do not move** (incl. trailers on `3dd1fe4`) |
| `protocol-freeze-n1-prompts` | ExactCritic + pilot prompt artifact hashes | Cut **before** dry-run; after tip locks `N1_FROZEN_ARTIFACT_PATHS` |
| `protocol-freeze-n1-campaign` | Dated `N1_LLM_MODEL_ID` pin | Cut **after** model pin, **before** first campaign call |

Tag-era constants are guarded by `test_spa_protocol_freeze.py` via
`git show protocol-freeze-n1-spa:…`. Post-tag pins use an explicit golden in
that test. **`run_manifest(require_clean=True)` refuses a dirty worktree.**

**Verifiability.** Prefer SSH-signed annotated tags (`git config gpg.format ssh`
then `git tag -s`) if GPG is unavailable. `protocol-freeze-n1-spa` may remain
unsigned — say so in the paper. Before the campaign, archive the repo **at the
prompts (and then campaign) tag** on [Software Heritage](https://www.softwareheritage.org/)
or Zenodo for an independent timestamp.

Every run log must include tip SHA, spa/prompts/(campaign) tag SHAs, and
`frozen_artifact_hashes` via `spa_protocol.run_manifest(...)`.

---

## Order of operations

1. Tip honesty commit pushed (done: tip-vs-tag guard).
2. Commit prompt/critic freeze helpers → cut **`protocol-freeze-n1-prompts`** → push tag.
3. Dry-run A/B/C on logging only (ceiling tasks; clean worktree; prompts tag present).
4. Record `prompts_untouched_after_dry_run=true` (artifact hashes still match).
5. Pin `N1_LLM_MODEL_ID` to a **dated snapshot** (not a floating alias); update tip golden in the same commit → cut **`protocol-freeze-n1-campaign`** → push.
6. Archive at campaign tag (SWH / Zenodo).
7. Campaign — abort any call if API-reported model ID ≠ pin (`assert_api_model_matches_pin`).

Ring ΔIL SKIP stays in **limitations** until `ring_single` / regularization yields a real ΔIL.

---

## SPA Δφ tolerance

| Constant | Value | Role |
|---|---|---|
| `SPA_TOL_PRIMARY_RAD` / `SPA_TOL_RAD` | **0.05 rad** | **Primary** layout / PIC-Set e2e test |
| `SPA_TOL_SWEEP_RAD` | `{0.01, 0.02, 0.05, 0.1}` | **Sensitivity only** — not a forking path |
| Historical / schematic | **0.01 rad** | Synthetic planted-φ; early layout-N3; §2.2 `MATCHED_LENGTH` intent |

### Primary vs sensitivity (no post-hoc tolerance picking)

- Declare **0.05** the primary test **before** looking at confirmatory results.
- Sweep points other than 0.05 are sensitivity; report them, but **do not**
  choose whichever tolerance yields 12/12 after the fact.
- **Counts against N3:** misclassification of **any** of the 12 confirmatory
  tasks at primary `0.05` rad. Sensitivity flips at 0.01/0.02/0.1 are discussed,
  not used to rescue the primary claim.

### Honesty — why 0.01 → 0.05 (word carefully)

Synthetic probe slack and §2.2 both point at ~**0.01 rad**. Layout SPA uses a
looser budget. **`0.05` was chosen first; the following justifications were
written afterward — say so in the paper.**

- **`0.05 ≈ π/64`:** equal to **one LSB** of an *assumed* 6-bit code over
  `[0, π]` (`π/2^6`). This is **not** the worst-case quantization error
  (½ LSB ≈ 0.025 rad). Say which you mean: **tolerance = one LSB**.
- **6-bit DAC:** an **assumption**, not a Cornerstone datasheet fact — mark it.
- **Parent `phase_error_std: 0.05`:** a **1σ** perturbation scale. Using 1σ as
  a hard pass/fail tolerance would let ~⅓ of fabricated devices exceed it — it
  is **not** a yield-grade budget. Cite only as corroborating context, or use a
  stated multiple of σ.
- Do **not** justify 0.05 from observed router WNS.

### Exploratory vs confirmatory SPA

| Status | What | Paper treatment |
|---|---|---|
| **Exploratory** | Pre-tag synthetic; layout-N3 @ 0.01; pre-tag routed Tasks 6 & 9 | Label exploratory; **not** confirmatory evidence |
| **Confirmatory** | Fresh routed-SPA campaign **after** the tag | Primary claim; report alongside exploratory |

Tasks **6 and 9** motivated the method → **known-failure checks**, not blind
predictions (`SPA_KNOWN_FAILURE_CHECK_TASK_IDS`).

---

## Prompt / critic freeze (second anchor)

`protocol-freeze-n1-spa` covers **constants only**. Prompts and ExactCritic need
their own anchor:

| Path | Role |
|---|---|
| `gd_picasso/agents/exact_critic.py` | Arms B/C critic |
| `gd_picasso/pilot/base_pilot_generator.py` | Arm A pilot prompt |
| `gd_picasso/pcg/spa_protocol.py` | Protocol pins + this list |

`run_manifest()` embeds per-file SHA-256 and `frozen_artifacts_combined_sha256`.
After dry-run, campaign logs must set `prompts_untouched_after_dry_run=true`
only if those hashes still match the prompts-tag tree.

---

## N1 ablation — three arms

| Arm | Representation | Feedback |
|---|---|---|
| **A** | YAML text | PICasso pilot-prompt repair loop (baseline) |
| **B** | YAML text | ExactCritic on the **parsed** result |
| **C** | Typed mutations | ExactCritic |

### Campaign set ≠ parent Table V

`N1_TASK_SUBSET = (1, 2, 9, 10, 11, 19, 20, 26, 29, 30, 34, 36)`.

This is **not** ICLAD / parent Table V’s 12. **Task 6 (64-QAM) is absent** by
design. Parent Table V rates are **not directly comparable** to this campaign —
state that in the paper.

### Critic leakage check (weak — not a proven holdout)

| IDs | Status |
|---|---|
| `11, 26` | `weak_unproven_holdout` |

**Provenance check (`git log`):** ExactCritic landed in `d852424` with only
`linear` / `mzi` / `mzm` / `ring_bus` fixtures — **no** `task_11` / `task_26`.
The critic is task-agnostic. That still does **not** prove those two were unseen
during later rejection/e2e work on the 36-task corpus (fixtures may be local /
uncommitted). **Do not call this a clean holdout.** Report the subset
**descriptively** (2×5 = 10 samples/arm); **no significance claim**. Prefer
parametric variants (arm lengths / stage counts) the critic never saw for a
stronger leakage check.

### Dry-run ceiling tasks (justified before N1)

| IDs | Prior evidence (not from N1 dry-run) |
|---|---|
| `34, 36` | `BENCHMARK_FINAL_RESULTS.md` §Successful Circuits: **3/3 (100%) Pass@k** |

Rules:

1. Prompts/critic frozen (`protocol-freeze-n1-prompts`) **before** dry-run.
2. Dry-run = **logging only** (`error_class`, `repair_round`, tokens, model ID, SHAs, artifact hashes).
3. Any prompt/critic change afterward → new annotated tag or disclosed deviation.
4. Dry-run samples **excluded** from campaign data.
5. Because 34/36 remain in the campaign set, also record that prompts/critic
   were **untouched after** the dry-run (hash match).

### Equal budgets

| Knob | Rule |
|---|---|
| Model | Dated snapshot in `N1_LLM_MODEL_ID` (campaign tag); log API-reported ID; **abort on mismatch** |
| Temperature | `0.3` |
| Max repair rounds | `3` |
| Token cap | `2048` |

Pinning the model ID **is** a frozen-constant change: update the tip golden in
the same commit, then cut `protocol-freeze-n1-campaign` before the first call.

### Denominator / power

- Unparseable YAML in arm B = failure (in denominator).
- Wilson 95% intervals; overlapping → no win claim.
- Per-task + A-fail subset.

### Error taxonomy

`illegal_port`, `fanout`, `out_of_bounds_param`, `non_ascii`, `unit_mismatch`,
`wrong_connectivity`, plus `unparseable_yaml` (arm B).

---

## Hash naming

| Hash | Claim |
|---|---|
| `connectivity_hash` | Wiring-only (types + ports; no settings/geometry) |
| `circuit_hash` | Wiring + PCell params (`topology_hash` → `DeprecationWarning`) |
| `layout_hash` | + geometry |

## RL reward

`−(IL̂ + 0.5|Δφ̂| + 0.1·density)` — chosen weights; `ESTIMATOR_ONLY` until fidelity gate.

## Ring ΔIL SKIP (limitations)

Singular KLU on IR feedback. Keep in limitations until `ring_single` / regularization produces a real ΔIL.
