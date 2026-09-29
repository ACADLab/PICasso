# Probe findings — measured results

## Environment pins (Lane λλ/Env, 2026-09-29)

| Package | Version |
|---|---|
| `gdsfactory` | **9.23.0** (unchanged; do not upgrade) |
| `cspdk` | **1.3.2** (`[full]` extra; never bare-install latest) |
| `gplugins` | 2.0.1 (pre-existing) |
| `unitary_inference` (λλ) | **NOT VENDORED** — working copy not on disk; see `gd_picasso/vendor/lambda_lambda/SEARCH_LOG.md` |

**Promotion:** numbers below are re-measured under the pins above. Do **not**
promote heater / MMI constants into `sax_models` / FoM until FoM consumes this
re-baseline explicitly. Heater audit is **not** finalized here.

## Re-measured Cornerstone (cspdk 1.3.2 + gf 9.23.0)

Scripts: `cs_mzi.py`, `cs_full.py`, plus a direct `mmi2x2` S-probe.

| # | Claim | Result under 1.3.2 |
|---|---|---|
| 5 | `mmi2x2` 50:50 cell; `\|S\|≈0.6831` → **0.3 dB** loss, Bᵢ convention | **Confirmed** — element `\|S\|=0.683101`, IL vs lossless `1/√2` = **0.3000 dB** |
| 6 | MZI (`mmi2x2`–heater–`mmi2x2`) IL ≈ **0.622 dB** at `loss_dB_cm=0.7`, `L=320 µm`; flat across states | **Confirmed** — IL=**0.622 dB**, col-norm=0.93085 for vT∈{0,0.5,1,2} |
| 7 | Loss-balancing dummy on parallel path; with dummy `‖T−αU‖~1e-13` | **Confirmed** — Hadamard/cross/bar/AllReduce: `‖T−αU‖` = **1.52e-13 / 6.71e-14 / 1.88e-13 / 1.52e-13**; full-stage IL **0.667 dB** |
| 8 | Realized blocks sub-unitary `T=αU` | **Confirmed** (same fits) |
| — | Heater default length | **`straight_heater_metal` length=320.0 µm** |

**SAX-half 1e-13 slice:** recovered under these pins (`cs_full.py`).  
**Full spec→unitary→Clements→SAX 1e-13 vertical slice:** still blocked on λλ vendor
(math half cannot run). Delta vs prior claim: CS/SAX half matches; math half
unverifiable until `unitary_inference` lands.

## Math findings (1–4) — still blocked on λλ

Need `unitary_inference` + `optical_compiler/ast.py` on `PYTHONPATH`. Locate
pass failed (SEARCH_LOG). Prior unverified claims retained below for continuity;
do not treat as re-confirmed.

## Heater merge table — not re-run

`heater_count.py` / `merge_phases.py` import λλ via `psd_gate`. Table below is
historical only.

---

## Original text (verbatim from files-2/README.md restoration)

```
# Spec-to-layout lowering probe

Closes the math half of the NL -> spec -> PCG pipeline. No SAX, no gdsfactory,
no Gurobi. Needs only numpy, scipy, sympy, plus lambda-lambda's
`unitary_inference.py` and `optical_compiler/ast.py` on the path.

Run order:
  recon_check.py       pins the Clements reconstruction convention
  mzi_conventions.py   sweeps MZI conventions, scores each
  mzi_extract.py       closed-form (theta,phi,a,b) extraction + self-test
  lower.py             end-to-end: spec -> U -> Clements -> cells -> rebuild
  psd_gate.py          the Algorithm-1 feasibility guard (missing upstream)
  picset_specs.py      PIC-Set expressibility probe

Findings:
  1. U = G1^H G2^H ... Gk^H @ D          (residual 1e-16, N=2,3,4)
  2. Coupler sign convention is IRRELEVANT; output diagonal is MANDATORY.
  3. Closed-form extraction, worst 1.07e-15 over 400 random SU(2).
  4. Full lowering closes at ~1e-15 on all six expressible circuits.

Open: heater count is the naive upper bound 3*MZI + N. Adjacent output/input
phases on the same mode across layers should merge; expect a large reduction.

## Cornerstone stage (cs_mzi.py, cs_full.py)
Needs gdsfactory + cspdk in a venv (gdsfactory 9.45.0 tested).

  5. mmi2x2 is the right 50:50 cell, not 2x mmi1x2.
     S = 0.6831 * [[1,i],[i,1]]  -> exactly 0.3 dB loss, B_i convention.
  6. MZI (mmi2x2 - heater - mmi2x2) IL = 0.622 dB at loss_dB_cm=0.7, L=320um.
     = 2*0.3 (MMI) + 0.022 (320um at 0.7 dB/cm).  Flat across all states.
  7. EVERY phase shifter needs a loss-balancing dummy on the parallel path.
     Without it: ||T - alpha*U|| = 2.39e-3 for every target (systematic).
     With it:    ||T - alpha*U|| ~ 1e-13.  Full-stage IL 0.667 dB.
  8. Realized blocks are SUB-unitary: T = alpha * U. Specs are satisfiable
     only up to overall insertion loss -- which is what the grade must track.

## Heater counts (heater_count.py) -- merging does NOT help
  circuit          MZIs  unmerged  merged  saved
  MZI 2x2             1         5       4    20%
  2x2 cross           1         3       3     0%
  4x4 crossbar        4         8       8     0%
  Clements 4x4        6        24      23     4%
  4-pt DFT            6        25      23     8%
  90deg hybrid       10        31      31     0%
Phases on different modes rarely collide, so adjacent-layer merging is a dead end.
Budget ~4 heaters per MZI.
```
