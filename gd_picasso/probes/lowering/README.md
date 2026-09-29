# Spec → unitary → Clements → Cornerstone probes

Math half of the NL → spec → PCG pipeline, plus Cornerstone heater / FoM
re-baseline scripts.

**Lane Formal docs (Paper A)**
- `PICSET_PARTITION.md` — expressible / non-expressible table for all 36
- `LL_ANNOTATION_WORKFLOW.md` — how specs map once patched λλ lands
- `to_a1.py` — lowering→A1 stub (frozen contract; Env fills expansion)
- `psd_numpy.py` — pure-numpy PSD matrix check (no λλ)
- `test_formal_acceptance_stubs.py` — numpy PSD green now; λλ reject / 1e-13 SKIP
- A1 freeze: `gd_picasso/pcg/A1_MUTATION_CONTRACT.md`

**Dependencies**
- Math stack: `numpy`, `scipy`, `sympy`, plus lambda-lambda
  (`unitary_inference.py`, `optical_compiler/ast.py`) on `PYTHONPATH`
- Cornerstone stage (`cs_*.py`): `gdsfactory==9.23.0` + **`cspdk==1.3.2`**
  (re-measured 2026-09-29; see FINDINGS header). λλ vendor still missing —
  `gd_picasso/vendor/lambda_lambda/SEARCH_LOG.md`

**Run order (math)**
1. `recon_check.py` — pin Clements reconstruction convention
2. `mzi_conventions.py` — sweep MZI conventions
3. `mzi_extract.py` — closed-form `(θ,φ,a,b)` extraction
4. `lower.py` — end-to-end spec → U → cells → rebuild
5. `psd_gate.py` — Algorithm-1 feasibility guard (needs λλ)
6. `psd_numpy.py` / `test_formal_acceptance_stubs.py` — λλ-free PSD + stubs
7. `picset_specs.py` — PIC-Set linear-spec expressibility (probe subset)
8. See `PICSET_PARTITION.md` for the full 36-row partition

**Cornerstone / heater**
- `cs_mzi.py`, `cs_full.py` — `ARM_L=320 µm`, `loss_dB_cm=0.7`, loss-balancing dummy
- `merge_phases.py`, `heater_count.py` — phase-layer merge (little savings; ~4 heaters/MZI)

**Measured results** — `FINDINGS.md`. Cornerstone rows (5–8) + heater L /
mmi2x2 loss **re-confirmed** under gf 9.23.0 + cspdk 1.3.2 (`‖T−αU‖~1e-13`).
Math rows (1–4) still need λλ on `PYTHONPATH`. PSD matrix reject:
`tests/test_psd_reject.py`.

**Running** — either `python gd_picasso/probes/lowering/<script>.py` or
`python -m gd_picasso.probes.lowering.<script>`; `__init__.py` makes the flat
cross-imports resolve in both modes.

See `PICasso_plus_design_note.md` §5.2–5.3 for how these land in the FoM path and PCG.
