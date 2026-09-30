# PICasso+ — Scoping Note: Agents, the Photonic Circuit Graph, Graph-Native P&R, and the GPU Formulation

Working document. Four thrusts, in dependency order. Each section states what is claimed, what is borrowed, and what the ablation is.

---

## 0. Positioning: does this collide with PhIDO?

PhIDO (Sharma et al., *APL Machine Learning* 3, 046113, 2025; arXiv:2508.14123) is the closest agentic work. Read carefully, it does **not** collide — and more usefully, it names most of PICasso+ as its own future work. Concretely, PhIDO is:

- **Four modules, two of them agents.** Interpreter (LLM: entity extraction + retrieval of literature templates) → Designer (LLM: component selection from a 34-PCell generic C-band PDK, PCell parameter config, port-level schematic generation) → Layout (**algorithmic**: Graphviz `dot` for placement with nodes scaled to component size, gdsfactory **river router** for waveguides) → Circuit verification (**algorithmic**: SAX, reported to the user).
- **A text DSL, not a graph engine.** YAML/DOT, nodes = components, edges = links. It is a prompt-and-parse intermediate representation. There is no mutable typed state, no constraint object, no back-annotation from layout into the simulation model.
- **Structural validity as the endpoint, explicitly not performance.** Their words. No optimization stage at all; DRC results are surfaced, not repaired.
- **Human-in-the-loop at every stage boundary**, and a second LLM used to check schematic planarity, followed by a crossing-detection algorithm and re-prompting.
- **Reported failure profile**: entity extraction (EE) dominates at every complexity level — hierarchy misreads, mis-enumeration (missing/duplicated components), wrong connectivity. Level 4 (16–112 components) mostly dies before it reaches layout. Layout stage benchmarked standalone: 74/118 circuits routed with gdsfactory v8.16 defaults.
- **Stated next steps**: standardized knowledge representations, extended verification, coupling simulators/optimizers so designs are qualified on figures of merit before being called successful, and better routing/placement (they name A* explicitly).

So the non-conflict is structural, not cosmetic:

| Axis | PhIDO | PICasso+ |
|---|---|---|
| Agent output | YAML/DOT **text** | **typed graph mutations** through an API; text is only a view |
| Critic | second LLM + crossing detector | exact checkers (port-degree, planarity, DRC/LVS) + differentiable FoM |
| Placement | Graphviz `dot` (aesthetic hierarchical drawing) | analytical, constraint-projected, **function-aware**, **phase-constrained** |
| Routing | gdsfactory river router (crossing-free bundles) | curvy-aware search (LiDAR wrap primary) with priced crossings + **phase-matched groups** |
| Simulation | SAX on the schematic-ideal netlist | SAX on the **routed** netlist (back-annotated L, Σ\|θ\|, n_cross) |
| Endpoint | structural validity | functional Spec@k + IL/ER closure |
| Autonomy | user inspects each stage | closed loop; agents consume machine-actionable constraint entries |

Two newer papers matter more for positioning than PhIDO does, and both post-date the PICasso submission:

1. **Gu/ScopeX (ASU) line — this is the real overlap risk on Thrust 3/4.** Apollo (ICCAD'25, arXiv:2504.18813) is already *"the first GPU-accelerated, routing-informed placement framework"* for PICs, built on DREAMPlace, with an asymmetric bending-aware wirelength (cosWA) capturing port orientation, a routing-informed net-spacing model, constraint handling via conditional projection and cell inflation, and >1000 components in ~100 s. LiDAR 1.0/2.0 (ISPD'25, TCAD'25, arXiv:2505.17239) is a curvy-aware **A\* CPU** detailed router with adaptive crossing insertion, group-based net ordering, critical-path IL minimization, hierarchical reuse, and an open YAML **PIC IR**. LiDAR 3.0 (ISPD'26) adds photonics-aware electrical routing. PoLaRIS = Apollo + LiDAR + inverse design. **Consequence: "GPU placement for PICs" is taken.** Do not claim it. What is not taken: (a) any *functional/spectral* term in the placement objective — theirs are geometric and loss-proxy; (b) differential **phase** as a first-class constrained objective; (c) ~~a GPU router~~ *(N5 demoted — see §4.2 / §6; LiDAR wrap is the shipped router)*; (d) any LLM/agent layer; (e) simulation and layout in one autodiff graph. **Citation check:** Apollo/LiDAR detail numbers above must be re-verified against the source PDFs before camera-ready — they post-date casual verification.
2. **Flexcompute (arXiv:2606.00915, 30 May 2026).** Agentic loops for passives, MRM junctions, RF electrodes, and — relevant here — **chip-level electrical routing**: the draft cites an agent driving **192 DRC violations → 0 in 27 iterations** with 12 routing algorithms + bondpad freedom. **Unverified here** — confirm against the paper before §0 ships. This is still the strongest *class* of evidence that an LLM belongs *above* the P&R engine as a controller, and a warning that "agent picks a router" is published. Our version has to be distinguished by *what the agent controls* (weights on a differentiable objective, net grouping, hierarchy cuts) and *what signal closes the loop* (IL/Δφ/spectrum, not DRV count alone).

**Net framing for the paper.** PICasso+ is not "another agentic PIC flow." It is: *the intermediate representation and the solver formulation that let agents, physical design, and circuit simulation share one differentiable state on one device.* PhIDO gave agents a text DSL; ScopeX gave PIC physical design real solvers; nobody has connected the two, and nobody has closed the loop on function rather than structure.

---

## 1. The agent layer

Five agents, one shared state, no free-form file editing. The design rule: **an LLM is allowed to propose structure and to set knobs; it is never allowed to compute a quantity a program can compute exactly.**

### 1.1 A0 — Intent agent (NL → L0 typed intent)
Emits a typed intent object: role, boundary ports (count/type/polarization), targets (IL, ER, FSR, splitting ratio, bandwidth), platform/PDK, and — critically — **a topology *program*, not a node list**.

This is the direct counter to PhIDO's dominant failure mode. Their EE errors are hierarchy misreads and mis-enumeration, and they explode at 16–112 components because the model is asked to *enumerate*. If A0 instead emits `mzi_tree(stages=6, coupler="mmi1x2", ps="heater")` and a deterministic elaborator expands it, the enumeration error class stops existing at any n. Free-form node lists remain allowed only for irregular circuits.

Tools: PDK retrieval (docstring/embedding search over components), topology template library (PIC-Set + literature), unit parser. Output validated by Pydantic-style schema; ambiguity is either resolved by a single clarification turn or recorded as an explicit assumption in the journal (never silently defaulted).

### 1.2 A1 — Schematic agent (generator/critic pair)
Generator proposes graph mutations: `add_node`, `connect(port,port)`, `set_param`, `insert_module`, `group_constraint`. Critic is **not** an LLM: port-degree ≤ 1 on optical ports, type/width/polarization compatibility at each link, parameter bounds from `inspect.signature` + PDK, planarity test and exact crossing count, dangling-port terminator insertion, unit consistency. Only *semantic* judgments (is this topology actually a QPSK modulator?) go to the GNN surrogate or, as a last resort, an LLM reviewer.

Rationale for the split: PhIDO asks an LLM to check planarity, then runs a crossing detector anyway. Counting crossings is `O(E log E)`; spending tokens on it is strictly worse.

### 1.3 A2 — Physical-design agent (controller, not solver)
Reads the placed/routed graph + metric vector; writes only *hyper-parameters*: objective weights (λ_D, λ_F, λ_φ, λ_T), target density and aspect ratio, alignment/regularity constraint groups, net groups and routing order policy, hierarchy cut points, whether to inflate or re-place. The solvers stay deterministic. Loop closes on (ILmax, Δφ per critical group, #DRV, #crossings, area), not on DRV count alone.

This is the honest scope for an LLM in P&R, it is where Flexcompute got real gains, and it is defensible under review because the agent's action space is small, typed, and auditable.

### 1.4 A3 — Optimization agent
Selects the objective and constraint weights, chooses restart strategy and budget, decides when to stop. The optimizer itself is gradient descent on the JAX/SAX FoM (multi-start, x64). Nelder–Mead is retained only as a baseline. RL is explicitly **out of scope for Thrust 1** — reserved for discrete P&R decisions later.

### 1.5 A4 — Verification/triage agent
Converts DRC/LVS/SAX failures into *constraint-ledger entries attached to specific graph elements*, plus a routing decision: which agent gets re-invoked and with what added constraint. This replaces PICasso's "append the error text to the pilot prompt" loop. The claim is localization: a violation becomes `constraint(id=c7, kind=SPACING, elements=[n3,n4], evidence={achieved:1.8µm, required:2.0µm})`, not a sentence.

### 1.6 Implementation shape
- Single graph store (NetworkX-backed, Pydantic-typed nodes/edges) + append-only **journal** of validated mutations. Every mutation is checked before commit; illegal mutations are rejected with a typed reason, not accepted-then-diagnosed.
- Agents receive *views* (a serialized text projection, a metric vector, a subgraph) — never the raw store.
- Per-agent budgets and a top-level state machine with explicit termination; canonical graph hash + seed logged for reproducibility. (A text-artifact pipeline cannot make this claim; a hashed graph can.)
- The journal gives per-iteration graph diffs — a strong paper figure, and the mechanism for "which agent fixed what."

---

## 2. The Photonic Circuit Graph (PCG)

### 2.1 Why (four arguments, in order of strength)
1. **Error elimination vs error detection.** Invariants make failure classes *unrepresentable*: optical fanout, illegal port names, out-of-bounds parameters, non-ASCII, unit mismatch. PICasso's Table V shows V1–V2 stalling at 25–42% structural correctness; those failures are almost entirely representational.
2. **It is the only object all four consumers can share.** LLM (text view), placer (node geometry + port orientation tensors), router (edge demands + constraint groups), simulator (S-matrix netlist). One state, four projections — so information can flow *backwards*.
3. **Back-annotation is the actual scientific claim.** On export, every optical net materializes as a parametric `waveguide_phys` instance whose settings are physical-design quantities written back by the router: length, cumulative bend angle, crossing count; router-inserted crossings become first-class 4-port vertices with crosstalk-bearing S-models. The simulated circuit is then *the routed circuit*. PICasso today (and PhIDO) simulate the schematic-ideal netlist and trim phases on a layout-blind model. This single change is what converts "optimization" into "closure."
4. **Differentiability.** Graph → parameter vector → SAX/JAX FoM with exact gradients (verified against central differences to <1e-4 relative in x64 in the existing prototype). Nelder–Mead's failure on the 64-QAM modulator and 90° hybrid in Table V is a high-dimensional-convergence failure; gradients are the direct fix.

### 2.2 How (settled design)
Heterogeneous, **ported**, hierarchical. Instances are vertices, nets are typed edges. (Devices-on-edges was refuted early: an edge joins exactly two endpoints, so MMIs and other multi-port devices are unrepresentable.) Three edge layers — optical, electrical, and a **derived thermal** layer whose coupling coefficients are emitted by the placer from achieved separations. Four-level refinement lattice: **L0 intent → L1 circuit → L2 placed → L3 routed**, with a constraint ledger carrying status and evidence at every level, and a canonical hash per subgraph enabling reuse and caching.

Phase is an edge attribute, which makes phase-matching a *correctness* property of routing rather than a post-hoc optimization. Constraint tension becomes explicit: `MATCHED_LENGTH` (schematic intent: arms equal to **0.01 rad**) versus `THERMAL_KEEPAWAY` (heaters ≥ 25 µm apart) are in direct conflict, and the placer resolves them under a stated cost instead of the conflict surfacing later as an unexplained functional failure. Layout SPA after tag `protocol-freeze-n1-spa` uses **primary** `SPA_TOL_RAD = 0.05` (≈ π/64 = one LSB of an *assumed* 6-bit code over `[0, π]` — not ½-LSB quantization error; justifications written after the choice, disclose). Sweep `{0.01,0.02,0.05,0.1}` is sensitivity only; misclassification of any confirmatory task at 0.05 counts against N3. Pre-tag routed/layout runs are **exploratory**; a fresh post-tag campaign is **confirmatory**. Tasks 6 & 9 are known-failure checks, not blind predictions. See `PROTOCOL_FREEZE.md`.

### 2.3 When to use which level

| Stage | Level read | Level written | Who |
|---|---|---|---|
| intent capture | — | L0 | A0 |
| elaborate + legalize | L0 | L1 | deterministic |
| topology critique | L1 | L1 | A1 + GNN/exact checks |
| placement | L1 | L2 (+thermal edges, est. lengths) | GPU placer, A2 controls |
| routing | L2 | L3 (+crossing vertices, phase, L/θ) | router, A2 controls |
| simulation/optimization | L3 | L3 params | JAX/SAX, A3 controls |
| DRC/LVS + triage | L3 | ledger | KLayout + A4 |

### 2.4 Prior art — honest accounting
- **PhIDO DSL**: nodes/edges in YAML, but text, no constraints, no back-annotation, no levels.
- **LiDAR PIC IR** (open, YAML): physical/hierarchical, built for routing; carries no intent level, no functional targets, no S-model semantics.
- **gdsfactory netlist**: layout-oriented, flat, no constraint or intent semantics. **SAX netlist**: simulation-only, no geometry.
- **Analog EDA precedent** (this is the methodological cover story): ParaGraph (DAC'20) for layout parasitics via GNN, GANA for netlist annotation, parasitic-aware sizing with GNN+BO. Graph-IR-plus-GNN is standard practice in analog physical design; photonics simply has no equivalent. Say it that way — it is both true and reviewer-friendly.
- **Design decision**: make the PCG a strict **superset of LiDAR's PIC IR ∪ SAX netlist**, so round-trip serialization is free in both directions. This is the cheapest possible credibility gate: if the IR loses nothing relative to the two existing representations, the "why a new IR" question answers itself, and PICasso+ can run against the existing PIC-Set harness unchanged.

**Ablation that carries the thrust**: agents emit YAML text instead of typed mutations → the representational error classes reappear. That is the headline row. **Status: protocol frozen, not yet run** — three arms A/B/C in [`PROTOCOL_FREEZE.md`](gd_picasso/pcg/PROTOCOL_FREEZE.md) / tag `protocol-freeze-n1-spa` (see §5.1 N1).

---

## 3. Placement and routing on the graph

Borrow the VLSI machinery wholesale; add exactly one thing (function) and one thing (phase).

### 3.1 Placement
Analytical/electrostatic lineage (RePlAce → elfPlace → DREAMPlace), with Apollo's photonic corrections adopted and cited rather than reinvented: orientation-aware asymmetric bending wirelength, routing-informed net spacing that reserves whitespace for crossings and port access, constraint enforcement by conditional projection + cell inflation, PIC-appropriate filler geometry.

The added objective:

```
min_x  W_cos(x) + λ_D·D(x) + λ_F·F̂(x) + λ_φ·Σ_g (Δφ̂_g)² + λ_T·T(x)
```

- `W_cos` — orientation-aware wirelength (Apollo-style)
- `D` — density/overlap (FFT Poisson solve)
- `F̂` — **SAX figure of merit through pre-route geometric estimators**: differentiable estimates of per-net length, cumulative bend angle, and a *soft* crossing count feed the S-matrix; ∂F̂/∂x flows back to positions. This is the term nobody has.
- `Δφ̂_g` — estimated differential phase per phase-critical group; makes arm balance a placement-time objective
- `T` — thermal keepaway / crosstalk from derived thermal edges

Legalization: Abacus-style minimal movement, extended to the discrete orientation set (0/90/180/270 + mirror) with port-access feasibility as a hard filter.

**Load-bearing caveat**: the gradient w.r.t. position is only as good as the pre-route estimator. Estimator fidelity (predicted vs routed L, Σ\|θ\|, #crossings) must be validated as its own experiment — it underpins the entire differentiable claim, and Apollo's own analysis gives the template.

### 3.2 Routing
Keep a curvy-aware exact search as the feasibility engine (LiDAR-class: bend-radius-respecting non-Manhattan A*, port-access assignment, adaptive crossing insertion, rip-up/reroute). Three additions:

1. **Phase-critical groups routed first**, under a matched-length budget with deliberate detour (meander/serpentine) insertion. Δφ is a routing constraint with a tolerance in radians, not a downstream surprise.
2. **Crossings priced by their S-model**, not a flat dB penalty — the crossing vertex carries transmission and crosstalk, so the router's cost and the simulator's model are the same object.
3. **Back-annotation contract**: the router writes (L, Σ\|θ\|, n_cross, φ) onto every edge and returns ledger evidence per constraint.

### 3.3 The VLSI mapping — and the framing that sells it

| VLSI | PICasso+ photonic analogue |
|---|---|
| floorplanning | module/block hierarchy from PCG subgraphs (canonical-hash reuse) |
| global routing | coarse-grid congestion + **crossing budget** allocation |
| detailed routing | curvy A* / GPU sweep router |
| parasitic extraction | **back-annotation** of L, bends, crossings into S-models |
| STA | **static phase-and-loss analysis (SPA)** |
| timing-driven placement | **phase-driven placement** |

Define the photonic STA properly, because it is the most quotable contribution of this thrust: arrival time → accumulated optical phase and loss along a path; setup/hold slack → **phase slack** against a group tolerance; critical path → worst-case IL path. LiDAR already minimizes critical-path IL — that is the loss half of SPA. The phase half is missing from every published PIC router, and it is exactly what Table V's 64-QAM and 90°-hybrid failures are made of.

---

## 4. Formulating the whole thing for the GPU

Principle: **one tensor program, one device, one autodiff graph.** The reason the current PICasso loop costs 4–8 minutes per task is not FLOPs — it is Python/gdsfactory/KLayout round-trips per candidate. Three kernels.

### 4.1 Placement — already solved, adopt it
DREAMPlace/Apollo territory: wirelength and density kernels + FFT-based Poisson solve, Nesterov/BNAG optimization in PyTorch. Free extra parallelism: batch over **multi-start restarts** and over **candidate topologies** in the population dimension. No novelty claim here; cite Apollo and move on.

### 4.2 Routing — formulation sketch (N5 demoted → appendix / future work)

**Status (locked with `ROUTER_STATUS.md`):** Paper B ships a **LiDAR wrap** as the primary detailed router. Hard/soft GPU min-plus kernels exist as CPU smoke (`pcg/route/minplus.py`) but are **not** a novelty claim — GAMER-as-technique is taken; do not claim "GPU-native curvy routing" or soft/hard duality as delivered evidence.

Historical formulation (kept for Paper B appendix / future work only):

**State tensor.** Bend-radius and port-orientation constraints mean the state is not just position. Use

```
C ∈ R^{N × H × W × Θ × K}        (nets × grid × orientation × curvature class)
```

Feasible transitions are a sparse stencil in (Θ, K). Shortest path over this state space is a **min-plus (tropical) fixed point** with sweep structure related to GAMER's Manhattan maze routing. Generalizing that sweep to an orientation-and-curvature-augmented lattice was the *intended* technical claim; it is **demoted** pending a real LiDAR IL/WL match and an explicit decision to reopen N5.

**Multi-net / soft-hard duality.** Negotiated congestion and soft (`−τ·logsumexp`) vs hard (`min`) twins remain interesting for ∂F̂/∂x through the router — but **no implementation backs the soft path in the shipped loop**. Soft/hard duality belongs under future work until a kernel is wired into placement.

Shipped path today: LiDAR wrap (or GF-routed metrics) → back-annotation → SPA.

### 4.3 Simulation — batch the axes that are already independent
SAX/JAX circuit solve batches naturally over (a) wavelength — embarrassingly parallel, (b) design candidates, (c) restarts, (d) corner/Monte-Carlo samples for yield. `jit` + `vmap`, x64 enabled. S-matrix assembly is a block-sparse solve; at PIC-Set scale, batched dense on GPU beats sparse-on-CPU comfortably, and the λ axis is what makes spectral objectives (FSR, ER, bandwidth) affordable inside the loop rather than after it.

### 4.4 What stays on the CPU, stated honestly
GDS write and KLayout DRC/LVS. Therefore: **DRC leaves the inner loop.** It runs once per accepted candidate, at the end, and the inner loop is guarded by differentiable spacing/keepaway penalties that make DRC-clean the likely outcome rather than a checked one. This is a design decision to defend explicitly, not paper over.

Other pitfalls to pre-empt:
- float32 is unusable near interference nulls (already observed) → x64 throughout the FoM path;
- memory for `C` is `N·H·W·Θ·K` — give the arithmetic, and provide hierarchical/tiled fallback for large dies (LiDAR 2.0's hierarchical reuse is the model);
- PyTorch (placement) ↔ JAX (SAX) bridge: keep the interface tensor small — per-net geometry `G ∈ R^{|E|×3}` plus the actuation vector — and move it via DLPack with a `torch.autograd.Function` wrapping `jax.value_and_grad`. Already prototyped and gradient-checked.

### 4.5 The metric that connects Thrust 4 back to Thrust 1
Not wall-clock alone. Report **candidates evaluated per second** and the **runtime scaling exponent vs component count**. The agentic argument depends on it: an agent with 1000 evaluations per design problem beats one with 10, and Flexcompute-class results lean on precisely that (GPU cluster budget). **Batched SAX + fast detailed routing** (LiDAR wrap today; GPU kernels only if N5 is reopened) is what makes the agent layer's search budget non-trivial. That is the sentence that makes the thrusts one paper instead of four.

---

## 5. Build order

1. PCG types + store + `canonical_hash`; mutation API enforcing the invariants. No agents yet.
2. `to_yaml`/`from_yaml` round-trip against all 36 PIC-Set tasks **and** LiDAR's PIC IR. **Gate: must pass before anything else.**
3. `legalize` (terminators, tapers) + `to_sax`; reproduce current PICasso numbers exactly. Steps 1–3 give a drop-in replacement with identical outputs, which de-risks everything after.
4. Constraint ledger + A4 triage; then A0/A1 with the exact critic.
5. Placement against the read/write contract; validate the pre-route estimators (their own experiment).
6. Router: **LiDAR wrap primary** (N5 GPU min-plus demoted to appendix — see §4.2). Soft twin = future work.
7. Close the loop: differentiable optimizer over L3 params; A2/A3 as controllers.
8. GNN surrogate, then RL for discrete decisions — Thrust 2 / Paper B territory (smoke only until topology-split eval).
9. **Headline ablation (N1):** typed mutations vs YAML-text agents on ≥12-task subset — required before Paper A writeup.

### 5.1 Status on `dev/picplus` (30 Sep 2026)

Strategy lock (decisions, lanes, pass commands, pins): [`PICasso_plus_strategy.md`](PICasso_plus_strategy.md). Parallel lanes **GO** after gate GREEN.

**How far vs the four thrusts / build order (§5).** The IR spine is real: build-order steps **1–4 are largely landed**. Thrust-3/4 are **honest preview** (place spike + LiDAR wrap; **N5 cut**). **Paper A blockers, in order:** (1) run the **three-arm** N1 ablation under the frozen protocol; (2) finish foundry emit (MZM/Ring maps landed; second foundry still open). GNN ~0.12 dB stays **out of Paper A** until a topology-held-out split. Cite tag `protocol-freeze-n1-spa` for a-priori SPA tol + ablation protocol.

| Build-order / board item | Status |
|---|---|
| PCG store, dual hash, journal | **Done** — hashes renamed for honesty: ``connectivity_hash`` = SHA-256 of sorted component types + port edges (**no** settings/geometry — wiring-only “topology preserved”); ``circuit_hash`` = wiring+**params** (``topology_hash`` deprecated alias emits ``DeprecationWarning``); ``layout_hash`` (geometry). Paper uses new names only |
| gdsfactory YAML round-trip gate | **Mostly GREEN** under gf **9.23.0** (Linear/MZI/MZM PASS incl. SAX/ΔIL). **Ring ΔIL = soft-SKIP** — singular KLU on IR-only ``dc,o3↔dc,o2`` feedback (**not** a silent ΔIL≈0 bridge bug). Unverified N2 path for resonant topologies; fix via regularization / ``ring_single``-style solver to drop SKIP |
| **LiDAR PIC IR round-trip (build-order step 2)** | **Done** (stub corpus) |
| Legalize dangling detect + terminators; A0–A4 stubs; ExactCritic | **Done** (ledger dedupe with A4) |
| **N1 ablation (three arms)** | **Protocol frozen, not run.** Subset ≠ Table V (Task 6 absent). Leakage check `11,26` = **weak_unproven_holdout** (descriptive only). Dry-run `34,36` cited from `BENCHMARK_FINAL_RESULTS.md` 100% Pass@k. Prompt/critic tag `protocol-freeze-n1-prompts`; dirty worktree refused; model pin → `protocol-freeze-n1-campaign`. **Blocker for Paper A** |
| SPA N-path WNS | **Exploratory** pre-tag layout/routed Task-6/9. **Primary** post-tag confirmatory at `SPA_TOL_RAD=0.05` (one assumed 6-bit LSB over `[0,π]`; justifications post-hoc — disclose). Sweep = sensitivity only; **N3 fails if any of 12 misclassified at 0.05**. Tasks 6&9 = known-failure checks, not blind |
| SAX silent-default audit / FoM split-brain | **Closed** (validator); emit split-brain gated in CS MZI smoke |
| Heater / Cornerstone re-baseline | **Promoted**; IL 0.622 = **`CS_MODEL_SAX`** (not `MEASURED_CS`) |
| Spec→unitary→Clements / PIC-Set 36 / Route Tasks 6&9 | **Done** (as before) |
| Placement / router | Place cosWA green; **N5 cut** — LiDAR wrap primary |
| GNN / RL | **Smoke only** — drop GNN MAE from Paper A until topology-held-out. RL = `SYNTHETIC_ENV`; reward `−(IL̂+0.5|Δφ̂|+0.1·density)` **not** `−|WNS|`; weights **chosen** (not tuned); `ESTIMATOR_ONLY` until `fidelity_vs_routed` |
| DRC/LVS / PDK probes / N6 | DRC+connectivity LVS honest; SiEPIC SKIP; sky130 dropped; **N6 = NO EVIDENCE** |
| **`PDKBackend` Cornerstone emit** | **MZI + MZM + Ring-bus maps landed.** Smoke: `connectivity_hash` stable; `circuit_hash` + `layout_hash` move on heater adapt; WG (3,0)/not (1,0); `to_gf_yaml` path. **Not yet:** second foundry; CS DRC deck; gate off `generic_tech` |

### 5.2 Immediate ordered plan (do not reorder casually)

**Done recently:** hash rename (`circuit_hash` / `connectivity_hash`); Cornerstone MZM + Ring-bus `component_map`; protocol freeze (`SPA_TOL_RAD`, three-arm N1) under tag `protocol-freeze-n1-spa`.

**Next:**

1. **Prompt/critic tag** `protocol-freeze-n1-prompts` (artifact hashes in `run_manifest`; clean worktree) → dry-run logging only on `34,36` → record prompts untouched.
2. **Pin dated `N1_LLM_MODEL_ID`** + update tip golden → cut `protocol-freeze-n1-campaign` → archive (SWH/Zenodo) → campaign (abort on API model mismatch).
3. **Confirmatory routed-SPA** after spa tag (exploratory 6/9 stay labeled); primary verdict at 0.05 only.
4. **Second foundry emit** — only then can N6 leave `NO EVIDENCE`.
5. **Ring ΔIL** — limitations until `ring_single` / regularization yields real ΔIL.
4. **Independent CS validation** (optional) — published loss figures / closed-form budget.
5. **Gate migration** to CS emit when fixture-complete.
6. **Paper B depth** — Apollo baseline; LiDAR at scale. No N5 reopen. GNN only with topology-held-out split.

### 5.3 Probe tree: `gd_picasso/probes/lowering/`

Committed probe tree for spec→layout math + Cornerstone FoM.
(Older root `files/` / `files-2/` trees were removed; this directory replaces them. They were
byte-identical to each other for all six shared math files.)

`FINDINGS.md` holds the measured results (restored from the deleted `files-2/README.md`, which was never committed — `git log -S` finds those numbers nowhere in history).

**Math (numpy/scipy/sympy + lambda-lambda)**
- `recon_check.py` — pins Clements rebuild (`G1ᴴ…Gkᴴ @ D`)
- `mzi_conventions.py` / `mzi_extract.py` — SU(2) convention + closed-form `(θ,φ,a,b)`
- `lower.py` — spec → U → Clements cells → rebuild (~1e-15)
- `psd_gate.py` — Algorithm-1 feasibility (`I−AAᴴ` ≱ 0 ⇒ reject gain specs)
- `picset_specs.py` — which PIC-Set tasks are linear-spec expressible (incl. 90° hybrid 4×4)

**Cornerstone (`gdsfactory` + `cspdk`)**
- `cs_mzi.py` / `cs_full.py` — heater re-baseline: `L=320 µm`, `loss_dB_cm=0.7`; `mmi2x2` 50:50 cell; loss-balancing dummy; sub-unitary `T=αU`
- `merge_phases.py` / `heater_count.py` — adjacent-layer merge barely helps (~0–20%); budget ≈ **4 heaters per MZI**
- Emit path (not a hand netlist): `pcg/backends/cornerstone.py` — PCG → `to_gf_yaml` under `cspdk.si220.cband`; MZI smoke green. MZI IL 0.622 dB = **`CS_MODEL_SAX`** (model-derived; not foundry-measured)

## 6. Claim discipline

**Claim (Paper A / shipped evidence bar):** typed graph IR as shared agent/solver state; layout-faithful back-annotated simulation; phase as a first-class routing constraint and the static-phase-analysis framing; ExactCritic + typed mutation API (ablation pending — see §5.1 N1).

**Claim (Paper B / only with evidence):** LiDAR-wrap detailed routing + SPA on routed geometry; function-aware / phase-constrained placement spike (cite Apollo for GPU placement — do not claim GPU placement ourselves).

**Future work / demoted (N5 — do not claim until reopened):** GPU-native curvy routing via orientation-augmented min-plus sweeps; soft/hard router duality giving gradients through routing; “the whole loop on one device” as a delivered system claim.

**Do not claim:** GPU placement for PICs (Apollo), curvy detailed routing as our invention (LiDAR), NL→layout agentic synthesis (PhIDO), agent-driven router selection (Flexcompute), GPU maze routing as a technique (GAMER/FastGR/InstantGR), GNN/RL layout gains from `SYNTHETIC_ENV` / random-split smoke, `CS_MODEL_SAX` IL as foundry measurement.

## 7. Open questions for you

**Locked** in [`PICasso_plus_strategy.md`](PICasso_plus_strategy.md) §2: (1) wrap LiDAR; (2) Apollo-style via DREAMPlace; (3) PIC-Set then Clements; (4) two-paper sequence (IR+agents, then GPU P&R+SPA). Historical wording retained below for context.

1. Router baseline: wrap LiDAR (open source, gives an honest apples-to-apples CPU baseline and instant credibility) or reimplement the A* core to keep everything in one framework?
2. Do we take Apollo as the placement baseline *and* the starting codebase (it is DREAMPlace-based, so the PyTorch↔JAX bridge already fits), or keep placement in-house to avoid a dependency on a competing group's tool?
3. Benchmark strategy: PIC-Set 36 for continuity with the parent paper, plus LiDAR's TeMPO/GWOR/Benes/Clements for the scaling curve? The headline scaling result probably has to be Clements 16×16 or larger — BO/GA will be competitive below ~20 knobs.
4. Venue and scope: is this one paper (all four thrusts, IR as the spine) or two (IR+agents; then GPU P&R+SPA)? Four thrusts in one paper risks the reviewer complaint that no single one is evaluated deeply.
