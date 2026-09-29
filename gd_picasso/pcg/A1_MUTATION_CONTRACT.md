# A1 mutation contract (frozen)

**Owner:** Lane Formal. **Consumers:** Lane Agents (A0/A1/ExactCritic/SM), Lane λλ/Env (lowering→A1 fill).

This document freezes the typed mutation surface Agents and lowering emit into
`PCGStore` / `SchematicAgent.apply_mutations`. **Do not silently change
signatures or payload keys.** Additive reserved ops require a Formal re-freeze
(bump `CONTRACT_VERSION` below and note the date).

```
CONTRACT_VERSION = 1
FROZEN_DATE = 2026-09-29
```

## Batch API (`SchematicAgent.apply_mutations`)

Atomic: snapshot → apply all → on any exception restore + re-raise.
Successful ops journal via the store; rejected ops must leave the store and
journal unchanged for the failed batch.

| `op` | Required keys | Optional keys | Notes |
|---|---|---|---|
| `add_node` | `id`, `component` | `params` (dict) | Maps to `add_component`; `skip_component_check=True` at A1 |
| `connect` | `src`, `src_port`, `dst`, `dst_port` | `bundle` (default `"optical"`) | Optical layer, `ROUTED` attachment |
| `set_param` | `node`, `key`, `value` | — | PDK / static allow-list validated |

Unknown `op` → `PCGMutationError("A1", "Unknown op …")`.

### Agent entry points (frozen behaviour)

| Method | Behaviour |
|---|---|
| `commit_mutations(store, mutations)` | Atomic batch of the three ops; no ExactCritic |
| `apply_mutations(store, mutations)` | `commit_mutations` + ExactCritic |
| `apply_elaboration(store, mutations, exported_ports=…)` | Commit batch, then **store-direct** `set_exported_ports`, then ExactCritic |

### Payload examples

```python
{"op": "add_node", "id": "mmi1", "component": "mmi1x2", "params": {}}
{"op": "connect", "src": "mmi1", "src_port": "o2", "dst": "ps", "dst_port": "o1",
 "bundle": "optical"}
{"op": "set_param", "node": "ps", "key": "length", "value": 320.0}
```

## Store / agent helpers **not** in the A1 batch vocabulary (v1)

Agents may call these on `PCGStore` or as `SchematicAgent` methods directly;
lowering→A1 must **not** invent batch `op` names for them until Formal
re-freezes:

- `SchematicAgent.set_exported_ports` → `PCGStore.set_exported_ports`
  (A0 elaborator already applies ports outside the batch)
- `disconnect`, `remove_node`
- `set_placement` (L2; Place spike / A2)
- `add_constraint`, `set_bundle_settings`
- Journalled `backannotate_edge` (SPA/IR / router harness only)

## Reserved (not implemented — do not emit)

| Future `op` | Intent | Status |
|---|---|---|
| `insert_module` | Expand a hierarchical template (e.g. MZI cell) | reserved |
| `group_constraint` | Attach matched-length / hybrid path group | reserved |
| `set_edge_grade` | Write intentional `(loss_dB, phase_rad)` on an edge | reserved — use `GradedQuantities` on lowering annotations until wired |

Design-note wording that lists these names is aspirational; **v1 Agents must
only emit the three frozen batch ops**.

## Invariants (exact critic + store)

- Optical port degree ≤ 1.
- No self-loop on the same port.
- Port names must exist on the node when the port map is populated.
- `set_param` keys must be in the component signature / `_STATIC_PARAMS`.
- Illegal mutations raise `PCGMutationError`; they do **not** append journal entries.

## Graded annotations (types, not mutations)

Formal grades live in `gd_picasso.pcg.types`:

- `GradedQuantities` — `{loss_dB, phase_rad}` pair
- `PCGEdge.loss_dB` / `PCGEdge.phase_rad` — measured / back-annotated (additive)
- `LoweredMZIAnnotation` / `SpecAnnotation` — intent from λλ→Clements before layout

Lowering emits **A1 mutation batches** for topology/params; grades travel beside
the batch as `LoweredMZIAnnotation` until a future `set_edge_grade` freeze.

## Lowering → A1 join

Stub: `gd_picasso.probes.lowering.to_a1.cells_to_a1_mutations`.
λλ/Env fills real cell→instance expansion; Agents must accept the frozen
payload shape above. See `LL_ANNOTATION_WORKFLOW.md`.

## Change control

1. Propose additive fields only (optional keys with defaults).
2. Update this file + `CONTRACT_VERSION` in the same commit.
3. Ping Lane Agents before merging signature breaks.
