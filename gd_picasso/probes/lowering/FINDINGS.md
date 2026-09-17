# Probe findings — measured results

Provenance: this is the content of the original `files-2/README.md`, which was
the only record of these measurements. That file was untracked and was deleted
when the tree moved to `gd_picasso/probes/lowering/` (commit `e9c984c`); it
appears nowhere in git history. Restored verbatim below.

**Status of every number here: UNVERIFIED in the current environment.**
- Math findings (1–4) need lambda-lambda (`unitary_inference.py`) on `PYTHONPATH` — not installed, not vendored.
- Cornerstone findings (5–8) and the heater table were measured on **gdsfactory 9.45.0**;
  `pyproject.toml` pins **9.23.0** and `cspdk` is in no dependency file. S-model values
  (notably 0.6831) are version-dependent.

Do not promote these into `sax_models` / the FoM path until re-run under a pinned
environment. See `PICasso_plus_design_note.md` §5.2 item 1.

---

## Original text (verbatim)

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
