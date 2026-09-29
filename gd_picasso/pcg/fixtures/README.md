# Committed gate fixtures

YAML topologies checked into the repo so `python -m gd_picasso.pcg.pcg_roundtrip_test`
does not shrink to built-ins-only on a clean clone.

| file | intent |
|---|---|
| `linear.yaml` | guaranteed-routeable waveguide pair; ΔIL thesis |
| `mzi.yaml` | dual-arm MZI; combiner rot 180°; **west/east split bundles** (gf 9.23 angle rule) |
| `mzi_unbalanced.yaml` | Place-spike append-only: same MZI topology, **skewed arm placements** so λ_φ ablation is meaningful (stock `mzi.yaml` is too symmetric) |
| `mzm.yaml` | dual-drive MZM; combiner rot 0; **west/east split bundles** |
| `ring_bus.yaml` | coupler + bus; same-instance feedback under `info.pcg_ir_connections` (GF rejects cyclical `connections:`) |

## Why fixture edits (FoM / gf 9.23 gate)

- **Ring:** `connections: dc,o3: dc,o2` crashes `gf.read.from_yaml` (`Cyclical references`). Feedback is PCG IR-only via `info.pcg_ir_connections` (GF allows `info`; top-level extras are pydantic-forbidden); bus Y aligned to coupler o1/o4.
- **MZM/MZI:** a single `routes.optical.links` mixing west-bound and east-bound targets fails (`All ports at the target must have the same angle` / multi-port collisions). Split into `west` + `east` bundles.

PIC-Set 36 freeze: add `task_XX.yaml` here as they are curated; `discover_corpus()`
loads every `*.yaml` in this directory automatically.

## Append-only SPA/IR stubs (do not rewrite rows above)

LiDAR / PIC-Set IR stubs live under ``fixtures/lidar/`` so
``discover_corpus()`` (top-level ``*.yaml`` only) does not feed them into
the GF roundtrip gate.

| file | intent |
|---|---|
| `lidar/lidar_mzi_stub.yaml` | LiDAR PIC IR shaped MZI; identity round-trip (`lidar_ir.py`); schema pin ScopeX-ASU/LiDAR `@4e7004d3…` |
| `lidar/picset_task06_stub.yaml` | PIC-Set Task-6 topology stub; SPA goldens plant `RouteMetrics` in tests (`SYNTHETIC_NOT_LAYOUT`) |

## Formal / Place coordination (append-only)

- **Owner:** Lane SPA/IR for YAML contents; Lane Formal does **not** rewrite
  `mzi.yaml` / `mzm.yaml` / `ring_bus.yaml` / `linear.yaml`.
- New Formal or Place needs (e.g. asymmetric arm seeds) → **append** a new
  file (e.g. `mzi_asymmetric.yaml`) and note it here; do not edit goldens
  in place unless FoM gate breakage forces a coordinated fix.
