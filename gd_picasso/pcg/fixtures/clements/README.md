# Clements expanded PCG fixtures (Paper B)

Generated via `cells_to_a1_mutations(..., expand_instances=True)` from a
Clements decomposition of a random unitary (`gd_picasso/pcg/clements_scale.py`).

| Fixture | Modes | MZIs | Core component nodes | Notes |
|---|---|---|---|---|
| `clements_4x4_core.yaml` | 4 | 6 | **24** | CS MZI expand only |
| `clements_8x8_core.yaml` | 8 | 28 | **112** | CS MZI expand only |
| `clements_4x4_expanded.yaml` | 4 | 6 | 24 (+ rails/I-O) | Mode-rail mesh |
| `clements_8x8_expanded.yaml` | 8 | 28 | 112 (+ rails/I-O) | Mode-rail mesh |

Each MZI expands to `mmi2x2` + `straight_heater_metal` + loss-balancing
`straight` + `mmi2x2` (Cornerstone FINDINGS). These replace the 4-node
"mesh proxy" PIC-Set stubs (e.g. Task-20) in Paper B scaling experiments.

Regenerate:

```bash
PYTHONPATH=. python gd_picasso/pcg/clements_scale.py
```
