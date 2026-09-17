# Spec → unitary → Clements → Cornerstone probes

Math half of the NL → spec → PCG pipeline, plus Cornerstone heater / FoM
re-baseline scripts.

**Dependencies**
- Math stack: `numpy`, `scipy`, `sympy`, plus lambda-lambda
  (`unitary_inference.py`, `optical_compiler/ast.py`) on `PYTHONPATH`
- Cornerstone stage (`cs_*.py`): `gdsfactory` + `cspdk` (tested w/ gf 9.45.0)

**Run order (math)**
1. `recon_check.py` — pin Clements reconstruction convention
2. `mzi_conventions.py` — sweep MZI conventions
3. `mzi_extract.py` — closed-form `(θ,φ,a,b)` extraction
4. `lower.py` — end-to-end spec → U → cells → rebuild
5. `psd_gate.py` — Algorithm-1 feasibility guard
6. `picset_specs.py` — PIC-Set linear-spec expressibility

**Cornerstone / heater**
- `cs_mzi.py`, `cs_full.py` — `ARM_L=320 µm`, `loss_dB_cm=0.7`, loss-balancing dummy
- `merge_phases.py`, `heater_count.py` — phase-layer merge (little savings; ~4 heaters/MZI)

**Measured results** — `FINDINGS.md`. Every number in it is currently
UNVERIFIED: the math probes need lambda-lambda on `PYTHONPATH`, and the
Cornerstone numbers were taken on gf 9.45.0 while the repo pins 9.23.0.

**Running** — either `python gd_picasso/probes/lowering/<script>.py` or
`python -m gd_picasso.probes.lowering.<script>`; `__init__.py` makes the flat
cross-imports resolve in both modes.

See `PICasso_plus_design_note.md` §5.2–5.3 for how these land in the FoM path and PCG.
