# PIC-Bench-48 / PIC-Set fixtures

GF `task_XX.yaml` goldens for realizable tasks 1–46 (meshes are topology-
authentic; former LiDAR stubs 5–8/23–25/28/31 are real PCGStores). Tasks
47–48 are PSD rejects with no YAML. Optional `task_XX_lidar.yaml` IR files
remain for SPA experiments.

Structural scoring: `gd_picasso.bench.evaluate_submission` (ExactCritic ∧
TaskContract). Regenerate via `python -m gd_picasso.pcg.build_formal_benchmarks`.
