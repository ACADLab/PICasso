# Router status — Phase 2 cut line

**Decision (Scope C):** **LiDAR wrap is the primary detailed router** for Paper B.

## Status (Sep 2026)

| Path | Status |
|---|---|
| LiDAR-IR Manhattan driver | **Green** — default `route_with_lidar` / `lidar_driver.py` |
| gf 8.26 curvy (`try_full_route=True`) | **Green** — `route_bundle` / `route_single` / `route_astar` extract `length_um`, `n_bends`, Euler `bend_radius_um`, `n_crossings` → `apply_route_metrics` (Tasks 1/2/9 clean) |
| Full PICRoute (`--route` fallback) | **Green** on LiDAR `toy_example` via `comp_LiDAR.yml` when gf curvy fails |
| Hard/soft GPU min-plus novelty | **Cut** — kernels kept as appendix; no LiDAR IL/WL match claim |
| ESTIMATOR_ONLY drop | **Wired** — `fidelity_vs_routed` + `ROUTED_FIDELITY_BANNER` when MAE ≤ threshold |

## Why the cut fired (novelty)

Hard GPU min-plus has a CPU smoke kernel (`gd_picasso/pcg/route/minplus.py`) and a
soft logsumexp twin, but **no LiDAR `IL_max` / wirelength match within margin**
is claimed as our novelty. Detailed routing cites ScopeX-ASU/LiDAR.

Per plan cut line:

1. Paper B ships **LiDAR wrap** as primary detailed router (cite ScopeX-ASU/LiDAR).
2. Hard/soft min-plus demoted to appendix / future work (kernels kept).
3. Soft twin and estimator-through-soft-router are **cut** with novelty claims.
4. L3 JAX GD + A2/A3 use LiDAR-routed (or IR Manhattan) back-annotation.

## Pins

| Stack | `gdsfactory` |
|---|---|
| PICasso gate | **9.23.0** |
| LiDAR isolated env | **8.26.1** |

Do not import LiDAR into the gate venv. Setup: [`LIDAR_ENV.md`](LIDAR_ENV.md) /
`setup_lidar_env.sh`. Source tree may live at repo `.lidar_env/LiDAR`.
