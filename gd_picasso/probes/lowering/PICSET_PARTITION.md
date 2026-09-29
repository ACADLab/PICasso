# PIC-Set expressible / non-expressible partition (36)

**Lane Formal (Paper A / Tier-1).** Source task text: repo-root `Pic_set.txt`.
Formal path this cycle = **λλ linear spec → PSD gate (`I−AAᴴ` ≱ 0 reject) → Clements mesh → A1 mutations**.

Honesty rule: **rings, AWG, and spectral WDM/WSS are out of the formal path this cycle**, even when a topology can be sketched with MMIs. Constellation / multi-level modulators are only *partially* in scope (MZI tree topology yes; symbol mapping no).

Legend

| Tag | Meaning |
|---|---|
| `expressible` | Linear single-λ transfer; PSD + Clements in scope this cycle |
| `expressible_trivial` | Linear, but no Clements mesh (1–2 components / phase-only) |
| `partial` | Topology partly linear; task intent exceeds single-λ unitary |
| `non_expressible` | Spectral / resonator / AWG / out of formal path this cycle |

| # | Task | Cx | Partition | Formal note |
|---|---|---|---|---|
| 1 | MZI | 1 | `expressible` | Balanced / ΔL MZI; probe golden in `picset_specs` / `lower.py` |
| 2 | MZM | 1 | `expressible` | Push–pull bar/cross as 2×2 unitary (+ overall IL grade) |
| 3 | Direct Modulator | 1 | `expressible` | Single-drive MZI + reference arm |
| 4 | QPSK Modulator | 2 | `partial` | Nested MZMs are linear; I/Q constellation mapping is not a single unitary |
| 5 | 8-QAM Modulator | 2 | `non_expressible` | Multi-level constellation; not Clements-target this cycle |
| 6 | 64-QAM Modulator | 3 | `non_expressible` | Same as #5 at larger scale |
| 7 | WDM Multiplexer | 2 | `non_expressible` | Spectral; out of formal path |
| 8 | WDM Demultiplexer | 2 | `non_expressible` | Spectral; out of formal path |
| 9 | 90° Optical Hybrid | 2 | `expressible` | 4×4 linear; probe goldens exist |
| 10 | 2×2 Optical Switch | 1 | `expressible` | Cross / bar permutation |
| 11 | Crossbar 4×4 | 3 | `expressible` | Permutation unitary; probe golden |
| 12 | Crossbar 8×8 | 3 | `expressible` | Larger permutation; same formal path |
| 13 | Spanke 4×4 | 3 | `expressible` | Switching fabric ≡ permutation family |
| 14 | Spanke 8×8 | 3 | `expressible` | Same |
| 15 | Benes 4×4 | 3 | `expressible` | Multi-stage 2×2 MZIs |
| 16 | Benes 8×8 | 3 | `expressible` | Same |
| 17 | Spanke–Benes 4×4 | 3 | `expressible` | Same |
| 18 | Spanke–Benes 8×8 | 3 | `expressible` | Same |
| 19 | U-matrix Block 2×2 | 1 | `expressible` | Arbitrary SU(2) cell — core of Clements |
| 20 | Clements 4×4 | 3 | `expressible` | **Headline formal path** |
| 21 | Reck 4×4 Mesh | 3 | `expressible` | Alt triangular mesh; same linear class |
| 22 | Reck 8×8 Mesh | 3 | `expressible` | Same |
| 23 | Ring Add-Drop | 2 | `non_expressible` | Resonator; **out of formal path this cycle** |
| 24 | Dual-Ring Tunable Filter | 2 | `non_expressible` | Resonator; out of formal path |
| 25 | 4-Channel WDM Cascaded MZI | 3 | `non_expressible` | Task is spectral WDM; cascaded MZI at one λ is not the claim |
| 26 | Tunable 1×4 Optical Switch | 2 | `expressible` | Binary MZI tree / uniform split |
| 27 | Balanced Coherent RX FE | 2 | `expressible` | Builds on 90° hybrid linear block |
| 28 | 16-Channel AWG Demux | 3 | `non_expressible` | AWG; **out of formal path this cycle** |
| 29 | 2×2 Thermo-Optic Switch | 2 | `expressible` | Dual-heater MZI switch |
| 30 | Y-Branch Power Splitter | 1 | `expressible_trivial` | `mmi1x2` only |
| 31 | WSS 1×8 | 3 | `non_expressible` | Wavelength-selective; out of formal path |
| 32 | 2×2 PCM Switch | 2 | `expressible` | Linear 2×2 coupler states (material ≠ spectral) |
| 33 | Optical Delay Line | 1 | `partial` | Fixed delay/phase; coupler+loop is not Clements mesh |
| 34 | Simple MMI 1×2 | 1 | `expressible_trivial` | Splitter cell |
| 35 | Simple MMI 2×1 | 1 | `expressible_trivial` | Combiner (mirrored `mmi1x2`) |
| 36 | Straight + Phase Shifter | 1 | `expressible_trivial` | 1×1 phase (lossy grade via `loss_dB`) |

## Counts (this cycle)

| Partition | Count | Task IDs |
|---|---|---|
| `expressible` | 20 | 1–3, 9–22, 26–27, 29, 32 |
| `expressible_trivial` | 4 | 30, 34–36 |
| `partial` | 2 | 4, 33 |
| `non_expressible` | 10 | 5–8, 23–25, 28, 31 |

**Paper A expressible subset** = `expressible` ∪ `expressible_trivial` = **24 / 36**.
Headline claims should cite the 20 mesh-class tasks (esp. #9, #11, #19–#22) plus trivial cells as smoke; do **not** claim rings/AWG/WDM under the formal lowering path.

## Probe coverage vs partition

Existing `picset_specs.py` / `lower.py` cases map to tasks **1/10/11/20/9** (+ DFT-like / tap probes that are *not* numbered PIC-Set rows). Full 36 classification above is documentation-complete; live λλ inference for every row waits on **Lane λλ/Env** (patched vendor).

## Acceptance (blocked on λλ/Env)

- PSD reject regression (gain-infeasible spec) — stubbed; green when patched λλ lands.
- ~1e-13 / 1e-15 vertical slice (`‖T−αU‖`) — stubbed; green when patched λλ + Cornerstone re-measure land.
