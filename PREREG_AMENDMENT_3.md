# Pre-registration amendment 3 (`n1-confirm-v3`)

Frozen before any payload-saving mini-campaign. No API calls in this amendment.
Parent freeze: `n1-confirm-v2` / `PREREG_AMENDMENT_2.md`.

## Applicable functional-oracle tasks (9)

Dropped from the v2 list because the golden fixtures fail the frozen
permutation rule at stored/zero heater phases (strongest exported-port
`|S|^2` well below 0.5):

- **13** Spanke 4×4 (was `|S|^2` ≈ 0.062 on the strongest output)
- **17** Spanke–Beneš 4×4 (was `|S|^2` ≈ 0.250 on the strongest output)

Remaining applicable tasks:

| Kind | Task ids | Pass rule (unchanged) |
|---|---|---|
| Equal split | **26, 30, 34** | Each output within **0.5 dB** of ideal `1/N`. Row sum of `|S|^2` ≤ `1+1e-3`. |
| Mesh permutation | **11, 15, 20, 21, 37, 38** | At stored heater phases (missing = 0): claimed entry ≥ **0.5**, every other entry in that row ≤ **0.1**, row sums ≤ `1+1e-3`. Not all-to-all. |

Hard stop unchanged: if any of these 9 goldens fails the oracle, stop and do not grade campaigns. Thresholds were not retuned to recover 13/17.

## Crossing convention (verified)

gdsfactory `crossing` ports: o1 west, o2 north, o3 east, o4 south.
`gplugins.sax.models.crossing_ideal` nonzero S is **o1↔o3** and **o2↔o4**.

The oracle ideal crossing matches that. Note: `mesh_builders._insert_crossing`
still wires o1→o2 and o3→o4 (builder bug relative to gdsfactory); that is not
used to retune the oracle model.

### Golden re-validation after the crossing fix

On the 9 remaining goldens with the verified o1↔o3 / o2↔o4 model: **8 pass, 1 fail**.

- Pass: 26, 30, 34, 11, 20, 21, 37, 38
- Fail: **15** (Beneš). Exported-port `|S|^2` is ≈ 0 on every in→out under the
  verified crossing. Cause: the golden / `mesh_builders._insert_crossing` links
  o1→o2 and o3→o4, which is a turn under gdsfactory’s port layout, so the ideal
  straight-through S has no path. The model was **not** retuned. Hard stop:
  do not grade campaign stores with this oracle until task 15 is removed or the
  golden wiring is fixed (wiring fix is out of scope for this amendment).

## Campaign CLI

`--tasks` selects an explicit task list (used by the prepared mini-campaign).
Does not change default A/B/C PIC-Bench-48 behaviour.

## Mini-campaign (prepared, not launched)

Arms **B_parity** and **C** only, on the 9 applicable tasks, 5 samples each,
payload sidecar on. Cost estimate from R1 tokens on those tasks (B as proxy for
B_parity; campaign blend ≈ $6.399 / MTok): B_parity ≈ $4.06, C ≈ $3.52,
total ≈ **$7.58**. Remaining under the $60 cap after R1 (~$47.57) ≈ **$12.43**;
after the mini ≈ **$4.85**. Wait for Deepak's budget decision.
