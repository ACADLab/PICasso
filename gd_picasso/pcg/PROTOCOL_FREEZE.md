# Protocol freeze — SPA Δφ + N1 three-arm ablation

**Status:** frozen a priori in code (`gd_picasso/pcg/spa_protocol.py`).
**Git tag (cite in paper):** `protocol-freeze-n1-spa`

Do not retune tolerances or reshape the error taxonomy after seeing routed WNS
or LLM sample tallies.

## SPA Δφ tolerance

| Constant | Value | Scope |
|---|---|---|
| `SPA_TOL_RAD` | **0.05 rad** | Layout-N3, PIC-Set e2e SPA claims |

Planted-φ / comparator tests historically used `0.01`; those remain
`SYNTHETIC_NOT_LAYOUT` unless migrated to this constant.

## N1 ablation — three arms (not two)

Same LLM, same 12-task subset, **n = 5** samples per task per arm.

| Arm | Representation | Feedback |
|---|---|---|
| **A** | YAML text | PICasso pilot-prompt repair loop (baseline) |
| **B** | YAML text | ExactCritic on the **parsed** result |
| **C** | Typed mutations | ExactCritic |

- **A vs B** → critic alone  
- **B vs C** → representation with critic held fixed (**N1 claim**)  
- If **B ≈ C**, honest claim is about the critic; reword N1.

### Error taxonomy (fixed a priori)

1. `illegal_port`
2. `fanout`
3. `out_of_bounds_param`
4. `non_ascii`
5. `unit_mismatch`
6. `wrong_connectivity`

## Hash naming (related honesty)

| Hash | Includes settings? | Claim |
|---|---|---|
| `connectivity_hash` | no | topology preserved under lowering |
| `circuit_hash` | **yes** | circuit identity incl. PCell params (`topology_hash` deprecated alias) |
| `layout_hash` | yes + geometry | layout changed under lowering / P&R |

## RL reward (sanity)

`SYNTHETIC_ENV` reward is `−(IL̂ + 0.5|Δφ̂| + 0.1·density)` — **not** `−|WNS|`.
Positive phase slack is not penalized via WNS absolute value.
