# Phase 3 — GNN / RL status

| Item | Result |
|---|---|
| Topology generator + labels | `generate_sax_topology_labels` — real SAX IL (structural + clipped interference excess) on **MZI sweeps** (not full PIC-Set topology diversity) |
| GNN surrogate held-out MAE | **~0.12 dB** under a **random instance split** (`heldout_frac`), **not** a topology-level holdout — treat as smoke, not Paper B evidence; ExactCritic stays authoritative |
| Reward scalarization | Fixed a priori: `r = −(IL̂ + 0.5|Δφ̂| + 0.1·density)` in `REWARD_WEIGHTS` — uses `|Δφ̂|`, **not** `−|WNS|` |
| Discrete actions | `{net_group_order, hierarchy_cut, inflate_vs_replace, weight_band}` |
| Env | **`SYNTHETIC_ENV`** — delayed terminal reward (myopic greedy weakened); not layout/SPA |
| PPO-lite vs baselines | **PPO wins** on `SYNTHETIC_ENV` smoke → **RL kept as candidate** for Paper B discrete-controller work; do not cite as layout evidence |

Re-run: `python -c "from gd_picasso.pcg.gnn_rl import run_rl_bakeoff; print(run_rl_bakeoff())"`
