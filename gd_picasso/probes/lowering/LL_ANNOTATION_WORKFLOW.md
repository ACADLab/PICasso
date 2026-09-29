# λλ annotation workflow (Formal)

**Owner of this doc:** Lane Formal. **Owner of λλ vendor/patch:** Lane λλ/Env.
Formal does **not** vendor `unitary_inference` / `optical_compiler`.

## Goal

Map a PIC-Set (or probe) linear spec into graded annotations and an A1
mutation batch once the patched λλ tree is on `PYTHONPATH`.

```
NL / PIC-Set task
    → SpecAnnotation (n_inputs, spec_lines, partition tag)
    → PSD gate (reject if I−AAᴴ has negative eigenvalue)
    → λλ infer_unitary_from_spec  →  U, ancillas
    → Clements + mzi_extract      →  List[LoweredMZIAnnotation]
    → to_a1.cells_to_a1_mutations →  A1 batch (frozen contract)
    → SchematicAgent.apply_mutations + ExactCritic
```

## SpecAnnotation fields

Defined in `gd_picasso.pcg.types.SpecAnnotation`:

| Field | Role |
|---|---|
| `task_id` | PIC-Set 1..36 (0 / None for ad-hoc probes) |
| `n_inputs` | Modes entering the linear map |
| `spec_lines` | λλ `output(i) = …` equations |
| `partition` | From `PICSET_PARTITION.md` |
| `ancillas` | Filled after inference |
| `notes` | Honesty / caveats |

Only tasks tagged `expressible` or `expressible_trivial` should enter the
PSD→Clements path. `partial` / `non_expressible` stop at the partition table
(Agents may still build YAML topologies outside Formal).

## Graded quantities

Every lowered cell and every optical edge may carry:

```text
GradedQuantities(loss_dB=…, phase_rad=…)
```

- **Intent (pre-layout):** phases from `(θ, φ, a, b)` heaters; `loss_dB` may be
  `None` until Cornerstone / FoM constants are re-confirmed under `cspdk==1.3.2`.
- **Measured (post-route):** `PCGEdge.phase_rad` / `PCGEdge.loss_dB` via
  back-annotation (`RouteMetrics`); SPA consumes these.

Sub-unitary reality (`T = αU`) means Formal grades track **‖T−αU‖ + IL**, not
lossless unitarity alone (`FINDINGS.md`).

## PSD gate

- Sympy + λλ path: `psd_gate.infer_guarded` (needs patched λλ).
- Pure-numpy matrix check (no λλ): `psd_numpy.is_transfer_psd_feasible(A)`.

Docs + numpy helper ship now; **reject-regression acceptance waits on λλ/Env**.

## A1 emission

`to_a1.cells_to_a1_mutations(annotations, …)` is a **stub** until Env lands:

1. Expand each `LoweredMZIAnnotation` into `mmi2x2` / heater / dummy-arm
   instances (Cornerstone cell choices are FoM/Env, not Formal).
2. Emit only frozen ops: `add_node` / `connect` / `set_param`
   (`A1_MUTATION_CONTRACT.md` v1).
3. Return `(mutations, annotations)` so Agents can critique topology while
   grades remain sidecar data.

## Acceptance stubs (blocked)

| Check | Status |
|---|---|
| PSD reject of gain-infeasible spec | Stub / skip without λλ |
| ~1e-13 vertical slice ‖T−αU‖ | Stub / skip without λλ + CS re-measure |
| Partition table 36/36 | **Done** (`PICSET_PARTITION.md`) |
| A1 contract freeze | **Done** (`A1_MUTATION_CONTRACT.md`) |
