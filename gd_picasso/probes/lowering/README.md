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

See `PICasso_plus_design_note.md` §5.2–5.3 for how these land in the FoM path and PCG.
