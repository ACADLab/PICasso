# Committed gate fixtures

YAML topologies checked into the repo so `python -m gd_picasso.pcg.pcg_roundtrip_test`
does not shrink to built-ins-only on a clean clone.

| file | intent |
|---|---|
| `linear.yaml` | guaranteed-routeable waveguide pair; ΔIL thesis |
| `mzi.yaml` | dual-arm MZI, single `optical` bundle, combiner rotated 180° |
| `mzm.yaml` | dual-drive MZM, single bundle, facing fixed |
| `ring_bus.yaml` | coupler + bus with same-instance feedback edge (IR probe) |

PIC-Set 36 freeze: add `task_XX.yaml` here as they are curated; `discover_corpus()`
loads every `*.yaml` in this directory automatically.
