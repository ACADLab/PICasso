# Protocol freeze — SPA Δφ + N1 three-arm ablation

**Status:** frozen in code (`gd_picasso/pcg/spa_protocol.py`).
**Git tag (cite in paper):** `protocol-freeze-n1-spa` (annotated; on `origin`).
**Do not rewrite** commit `3dd1fe4` or move this tag (including to strip
trailers). Tip honesty amendments are separate; tag-era constants are guarded
by `test_spa_protocol_freeze.py` via `git show protocol-freeze-n1-spa:…`.

**What this freeze covers.** Future SPA campaigns and the N1 three-arm ablation.
Pre-tag synthetic / layout-N3 / routed Task-6/9 runs are **exploratory** only.
Do not retune tolerances or reshape the error taxonomy after seeing LLM sample
tallies or post-freeze confirmatory WNS.

**Verifiability.** Prefer SSH-signed annotated tags (`git config gpg.format ssh`
then `git tag -s`) if GPG is unavailable. For an independent timestamp, archive
the repo **at the tag** on [Software Heritage](https://www.softwareheritage.org/)
or Zenodo — stronger than a local clock.

Every run log (dry-run and campaign) must record `tip_commit_sha` and
`protocol_freeze_tag_sha` via `spa_protocol.run_manifest(...)`.

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
  tasks at primary `0.05` rad (wrong pass/fail vs the pre-registered expected
  verdict for that task). Sensitivity flips at 0.01/0.02/0.1 are discussed,
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
| **Confirmatory** | Fresh routed-SPA campaign **after** the tag | Primary claim; report alongside exploratory and state the status difference |

Tasks **6 and 9** motivated the method → present as **known-failure checks**,
not blind predictions (`SPA_KNOWN_FAILURE_CHECK_TASK_IDS`).

Planted-φ / comparator unit tests may keep `0.01` and stay
`SYNTHETIC_NOT_LAYOUT` unless migrated to `SPA_TOL_RAD`.

---

## N1 ablation — three arms (not two)

Same LLM, named 12-task subset, **n = 5** → 60 samples/arm.
**Holdout named before any run. Campaign waits until holdout is named (done)
and tip-vs-tag test is green. Dry-run only after prompts/critic are frozen.**

| Arm | Representation | Feedback |
|---|---|---|
| **A** | YAML text | PICasso pilot-prompt repair loop (baseline) |
| **B** | YAML text | ExactCritic on the **parsed** result |
| **C** | Typed mutations | ExactCritic |

- **A vs B** → critic alone  
- **B vs C** → representation with critic held fixed (**N1 claim**)  
- If **B ≈ C**, honest claim is about the critic; reword N1.

### Named task sets (a priori)

| Set | Task IDs | Rule |
|---|---|---|
| **Campaign 12** | `1, 2, 9, 10, 11, 19, 20, 26, 29, 30, 34, 36` | `N1_TASK_SUBSET` |
| **Critic holdout** | `11, 26` | Within the 12; ExactCritic rules **not** developed on these; report separately |
| **Dry-run (ceiling)** | `34, 36` | Logging only; **excluded** from campaign data; do not burn A-fail signal |

### Equal budgets (mandatory)

| Knob | Rule |
|---|---|
| Model | Exact `N1_LLM_MODEL_ID` string (pinned before campaign); log **API-reported** model ID per call |
| Temperature | `N1_TEMPERATURE = 0.3` |
| Max repair rounds | `N1_MAX_REPAIR_ROUNDS = 3` |
| Token / context cap | `N1_MAX_TOKENS = 2048` |

### Comparable feedback (B vs C)

ExactCritic’s message to the model must carry the **same typed problem fields**
in B and C (code, elements, evidence). No richer rejection text for arm C.

### Denominator rules

- **Unparseable YAML in arm B counts as failure** (stay in the denominator).
- Report success over all `n × |tasks|` attempts per arm.
- Wilson 95% intervals; if intervals overlap, do not claim a win.
- Per-task rates + subset where arm A fails (signal). Ceiling tasks carry little signal — still report them.

### Dry run — logging only (anti-contamination)

1. **Prompts and ExactCritic are frozen before the dry run starts.**
2. Dry run checks **logging only** (`error_class`, `repair_round`, tokens,
   model ID, tip/tag SHAs).
3. Any change to prompts/critic afterward → **new annotated tag** or a
   **disclosed deviation** (do not silently move `protocol-freeze-n1-spa`).
4. Dry-run samples are **excluded** from campaign data.
5. Dry-run tasks = ceiling only (`34`, `36`).

Start dry run only when tip-vs-tag constants test passes. Start campaign only
when holdout is named (**yes**), model ID is pinned (`n1_campaign_ready()`),
and dry-run logging is verified.

### Error taxonomy (fixed a priori)

1. `illegal_port`
2. `fanout`
3. `out_of_bounds_param`
4. `non_ascii`
5. `unit_mismatch`
6. `wrong_connectivity`

Plus denominator-only: `unparseable_yaml` (arm B).

---

## Hash naming (related honesty)

| Hash | Includes settings? | Claim |
|---|---|---|
| `connectivity_hash` | no | **Wiring-only digest** (component types + port-to-port edges; no PCell params, no geometry) — “topology preserved under lowering” |
| `circuit_hash` | **yes** | circuit identity incl. PCell params (`topology_hash` deprecated alias → `DeprecationWarning`) |
| `layout_hash` | yes + geometry | layout changed under lowering / P&R |

Paper text uses only the new names. One-sentence definition: *connectivity_hash
is the SHA-256 of sorted node component types and optical/electrical edges with
ports, excluding all device settings and placement.*

---

## RL reward (sanity)

`SYNTHETIC_ENV` reward is `−(IL̂ + 0.5|Δφ̂| + 0.1·density)` — **not** `−|WNS|`.

- Estimator-built → **`ESTIMATOR_ONLY`** until `fidelity_vs_routed` drops the banner.
- Weights `0.5` / `0.1` are **chosen**, not tuned.

## Ring ΔIL SKIP (limitations)

Singular KLU on IR-only `dc,o3↔dc,o2` feedback. Keep in **limitations** until
`ring_single` or regularization produces a real ΔIL (PASS or honest FAIL).
Unverified N2 path for resonant topologies.
