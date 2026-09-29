# Committed gate fixtures

YAML topologies checked into the repo so `python -m gd_picasso.pcg.pcg_roundtrip_test`
does not shrink to built-ins-only on a clean clone.

| file | intent |
|---|---|
| `linear.yaml` | guaranteed-routeable waveguide pair; ΔIL thesis |
| `mzi.yaml` | dual-arm MZI; combiner rot 180°; **west/east split bundles** (gf 9.23 angle rule) |
| `mzm.yaml` | dual-drive MZM; combiner rot 0; **west/east split bundles** |
| `ring_bus.yaml` | coupler + bus; same-instance feedback under `info.pcg_ir_connections` (GF rejects cyclical `connections:`) |

## Why fixture edits (FoM / gf 9.23 gate)

- **Ring:** `connections: dc,o3: dc,o2` crashes `gf.read.from_yaml` (`Cyclical references`). Feedback is PCG IR-only via `info.pcg_ir_connections` (GF allows `info`; top-level extras are pydantic-forbidden); bus Y aligned to coupler o1/o4.
- **MZM/MZI:** a single `routes.optical.links` mixing west-bound and east-bound targets fails (`All ports at the target must have the same angle` / multi-port collisions). Split into `west` + `east` bundles.

PIC-Set 36 freeze: add `task_XX.yaml` here as they are curated; `discover_corpus()`
loads every `*.yaml` in this directory automatically.
