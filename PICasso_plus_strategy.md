# PICasso+ Strategy Lock

**Branch:** `dev/picplus`  
**Env stack:** `gdsfactory==9.23.0`, `gplugins~=2.0`, SAX/JAX OK  
**Companion scoping note:** [`PICasso_plus_design_note.md`](PICasso_plus_design_note.md)  
**One copy only** — do not duplicate this file under `docs/` or `gd_picasso/`.

---

## 1. Gate status (hard prerequisite)

| Item | Status |
|---|---|
| PCG round-trip gate (`pcg_roundtrip_test.py`) | **GREEN** under gf **9.23.0** |
| Linear / MZI / MZM | PASS incl. SAX / ΔIL |
| Ring bus | build + route + SAX PASS; ΔIL soft-SKIP (singular KLU when ideal SAX includes IR feedback absent from layout) — plan-aligned, non-blocking |
| Parallel lanes | **GO** |

Activate env before any lane pass command:

```bash
source .venv/bin/activate   # or: uv run …
```

---

## 2. Locked §7 decisions

Answers to open questions in design-note §7. Do not reopen casually.

| # | Question | Decision |
|---|---|---|
| 1 | Router baseline | **Wrap LiDAR** (open CPU A\* baseline + credibility). Do not reimplement the A\* core in-house for Tier-1/early Tier-2. |
| 2 | Placement baseline | **Apollo-style via DREAMPlace** (cite Apollo; adopt DREAMPlace lineage / photonic corrections). Near-term in-tree Place work is an **estimator-only spike**, not a competing GPU placer claim. |
| 3 | Benchmarks | **PIC-Set 36 first** (continuity with parent paper), **then Clements** (and LiDAR TeMPO/GWOR/Benes) for the scaling curve. Headline scaling → Clements 16×16+. |
| 4 | Venue / scope | **Two-paper sequence:** Paper A = IR + agents + Formal/λλ (Tier-1); Paper B = GPU P&R + SPA (Tier-2). Four thrusts in one paper is out. |

Later Tier-2 (after Paper A spine): LiDAR wrap integration + DREAMPlace adoption + GPU min-plus; RL only after GNN + hard router.

---

## 3. Claim discipline

Required banners / labels:

- **`SYNTHETIC_NOT_LAYOUT`** — SPA Task-6/9 synthetic harnesses, planted lengths, or any WNS/IL number not from routed L3 geometry.
- **`ESTIMATOR_ONLY`** — all Place-spike results until routed geometry exists (predicted vs planted or vs routed when available).

**Do not claim** (unchanged from design-note §6):

- GPU PIC placement (Apollo)
- Curvy detailed routing (LiDAR)
- NL→layout agentic synthesis (PhIDO)
- Agent-driven router selection (Flexcompute)
- GPU maze routing as a technique (GAMER / FastGR / InstantGR)

RL = Thrust 2 **after** GNN + hard router; discrete actions ≠ router picking.

---

## 4. Environment pins (Lane λλ/Env)

| Pin | Rule |
|---|---|
| **`cspdk==1.3.2`** | Only. Pins `gdsfactory~=9.23.0`, `gplugins[sax,tidy3d]~=2.0.0`. Add to `[full]` extra in `pyproject.toml`. **Never** bare `uv pip install cspdk` (1.4.5 pulls gf≈9.45). |
| **λλ (`unitary_inference`)** | Vendor as **upstream SHA + explicit patch**, not bare SHA. Preserve Algorithm-1 PSD fix (`psd_gate.py`) and `embedding.py` workaround. Acceptance: PSD reject regression + recover **1e-13** spec→SAX slice. |
| Cornerstone FINDINGS | Measured under 9.45-era stack → **re-confirm under cspdk==1.3.2** before promoting heater L / `mmi2x2` loss into FoM constants. |

---

## 5. Shared-file owners

| Surface | Owner | Rule |
|---|---|---|
| `gd_picasso/pcg/types.py` + A1 mutation contract | **Lane Formal** (freeze); Agents consumes | No silent signature changes |
| `gd_picasso/pcg/fixtures/` | **Lane SPA/IR** | **Append-only** — new files only; Place/Formal do not rewrite existing YAMLs |
| GF YAML bridge `pcg/bridge.py` + roundtrip gate | **Lane FoM** | Gate red under 9.23 → FoM owns the fix |
| LVS gf9 soft-break | **Lane FoM** | Document or `importorskip` |
| Missing `netlist_optimize` (ICLAD Table III/V) | **Lane FoM** | Recover or rewrite + document |
| `gd_picasso/agents/` | **Lane Agents** | Consumes frozen A1 API from Formal |
| `gd_picasso/pcg/place/` | **Lane Place** (spike) | Estimator-only; no DREAMPlace/GPU router here |
| `pcg/lidar_ir.py`, synthetic SPA | **Lane SPA/IR** | Pin LiDAR commit used for schema inference |
| λλ vendor tree + `cspdk` pin | **Lane λλ/Env** | SHA+patch; FINDINGS rewrite under 1.3.2 |
| This strategy doc | **Lane Ops** | One copy at repo root |

**Do not cross-edit** another lane’s owned surfaces without an explicit handoff.

---

## 6. Parallel lane map + pass commands

Run from repo root with `.venv` active (or `uv run`). Gate is green; lanes may proceed in parallel subject to join points in §7.

| Lane | Owns | Pass command | Pass criteria |
|---|---|---|---|
| **Ops** | This file; push tip; design-note §5.1 sync | `test -f PICasso_plus_strategy.md && rg -n "Pass command" PICasso_plus_strategy.md` | Strategy present with pass-command table; `origin/dev/picplus` updated |
| **FoM** | `sax_validator`, `sax_models`, bridge/gate, LVS note, `netlist_optimize` | `python -m gd_picasso.pcg.pcg_roundtrip_test && pytest gd_picasso/pcg/test_pcg_sax_il.py -q` | Gate stays GREEN; behavioral IL test green (straight of length `L` → `0.7 dB/cm × L`, nonzero); validator shares `build_lossy_models` with PCG |
| **Formal** (Paper A) | PIC-Set partition 36, λλ annotations, graded `loss_dB`/`phase_rad`, lowering→A1 contract | `pytest gd_picasso/probes/lowering/ -q -k "psd or picset or lower" 2>/dev/null; python -m gd_picasso.probes.lowering.psd_gate` *(adjust once suite lands)* | Partition table complete; PSD reject regression green; expressible subset documented |
| **Agents** | `gd_picasso/agents/` (A0–A4, SM) | `pytest gd_picasso/pcg/test_pcg_rejection.py gd_picasso/pcg/test_pcg_invariants.py -q` *(extend with SM/elaborator tests when added)* | Elaborator output accepted by ExactCritic on MZI/MZM; SM A0→A1→critique→A4 path green. Defer A2/A3 fake-metric busywork |
| **SPA/IR** | `lidar_ir`, synthetic SPA Task-6/9, append-only fixtures | `pytest gd_picasso/pcg/test_pcg_extensions.py -q -k "spa"` *(+ lidar roundtrip tests when added)* | LiDAR→PCG→LiDAR identity; PCG→LiDAR projection reports drops; synthetic WNS goldens bannered `SYNTHETIC_NOT_LAYOUT` |
| **Place** (timeboxed spike) | `gd_picasso/pcg/place/` only | `pytest gd_picasso/pcg/place/ -q` *(or demo script once landed)* | `W_cos+D+λ_φ` runs; `estimator_fidelity` present; results bannered `ESTIMATOR_ONLY`; φ ablation only if arms can unbalance |
| **λλ/Env** | λλ vendor+patches, `cspdk==1.3.2`, FINDINGS | `python -c "import importlib.metadata as m; assert m.version('cspdk')=='1.3.2'"; python -c "import importlib.metadata as m; print('gf', m.version('gdsfactory'))"` then PSD reject + 1e-13 slice | `cspdk==1.3.2` + gf 9.23.0; PSD reject green; 1e-13 recovered or delta documented; FINDINGS header names both pins |

### Lane Formal note
λλ is off the *throughput* critical path but **on the Paper A critical path**. Place is a timeboxed Tier-2 preview and must not starve Formal.

### Lane SPA/IR LiDAR semantics
- **LiDAR→PCG→LiDAR** = identity roundtrip (must hold).
- **PCG→LiDAR** = **projection** that reports dropped fields (multi-port / ELECTRICAL / THERMAL).

---

## 7. Join points

1. Gate GREEN before Place / SPA-IR / Formal fixture branching — **met**.
2. FoM behavioral IL test green before quoting validator IL/WNS.
3. `cspdk==1.3.2` + re-measure before promoting Cornerstone numbers / heater audit finalization.
4. Patched λλ + PSD reject + 1e-13 before lowering→A1 and Formal Clements claims.
5. Place spike stays `ESTIMATOR_ONLY` until routed N3 exists.
6. RL / GNN / GPU router remain later (Paper B / Tier-2).

---

## 8. Paper sequence (locked)

| Paper | Scope | Primary lanes |
|---|---|---|
| **A (Tier-1)** | PCG IR, agents (A0/ExactCritic/SM), Formal PIC-Set partition, patched λλ → A1, honest FoM | Formal, Agents, FoM, λλ/Env, SPA/IR (IR half) |
| **B (Tier-2)** | Apollo/DREAMPlace placement, LiDAR wrap, GPU min-plus router, SPA on routed geometry | Place (beyond spike), SPA/IR (N3), later RL |

---

*Last locked by Lane Ops. Update this file when gate status, pins, or §7 decisions change — not for routine lane progress (use design-note §5.1 for status).*
