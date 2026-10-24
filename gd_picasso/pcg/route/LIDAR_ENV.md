# LiDAR isolated env

```bash
cd /Users/deepak/Desktop/work/PICasso
bash gd_picasso/pcg/route/setup_lidar_env.sh
# or manually:
python3 -m venv .lidar_env/venv
source .lidar_env/venv/bin/activate
pip install "gdsfactory==8.26.1" "numpy==1.26.4" pyyaml "pydantic==2.10.6" \
  "multimethod==1.12" "ryaml==0.4.0" "numba==0.60.0" loguru
pip install torch   # required for full PICRoute
export PICASSO_LIDAR_PYTHON="$PWD/.lidar_env/venv/bin/python"
export PYTHONPATH="$PWD/.lidar_env/LiDAR/src:${PYTHONPATH:-}"
```

Verify from the **gate** venv (`.venv`):

```bash
source .venv/bin/activate
export PICASSO_LIDAR_PYTHON="$PWD/.lidar_env/venv/bin/python"
export PYTHONPATH="$PWD/.lidar_env/LiDAR/src:$PYTHONPATH"
python -c "from gd_picasso.pcg.route import check_lidar_gf_pin; print(check_lidar_gf_pin())"
```

Expect: `lidar_gf='8.26.1'`, `mismatch=True`, `lidar_import_ok=True`.

Driver: `lidar_driver.py` → default **LiDAR-IR Manhattan** metrics from PIC YAML;
`--route` / `try_full_route=True` runs gdsfactory 8.26 curvy routing
(`route_bundle` / `route_single` / `route_astar`), extracts length / bend count /
Euler radius / crossings, then falls back to PICRoute / IR Manhattan on failure.
Cite LiDAR; do not claim curvy A* as ours.

Paper B smoke: `python gd_picasso/pcg/test_gf_curvy_tasks_129.py`
(Tasks 1, 2, 9 with `allow_stub=False`).

Integration: `pytest gd_picasso/pcg/test_scope_c_integration.py -q`
