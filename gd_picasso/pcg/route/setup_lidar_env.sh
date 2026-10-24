#!/usr/bin/env bash
# Create isolated LiDAR env (gf==8.26.1) — never install into PICasso gate venv.
set -euo pipefail
ROOT="${PICASSO_LIDAR_ROOT:-$(cd "$(dirname "$0")/../../.." && pwd)/.lidar_env/LiDAR}"
VENV="${PICASSO_LIDAR_VENV:-$(cd "$(dirname "$0")/../../.." && pwd)/.lidar_env/venv}"
SHA=4e7004d32b0b80d959553797fb30f0737513de0c

mkdir -p "$(dirname "$ROOT")" "$(dirname "$VENV")"
if [[ ! -d "$ROOT/.git" ]]; then
  git clone https://github.com/ScopeX-ASU/LiDAR.git "$ROOT"
fi
git -C "$ROOT" fetch --depth 1 origin "$SHA" || true
git -C "$ROOT" checkout "$SHA"

python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -U pip
pip install "gdsfactory==8.26.1" "numpy==1.26.4" "ryaml==0.4.0" "numba==0.60.0" \
  "multimethod==1.12" "pydantic==2.10.6" pyyaml loguru
# PICRoute needs torch (CPU wheel fine for smoke)
pip install torch || true
# Editable install if package layout allows
if [[ -f "$ROOT/pyproject.toml" || -f "$ROOT/setup.py" || -f "$ROOT/setup.cfg" ]]; then
  pip install -e "$ROOT" || pip install -e "$ROOT/src" || true
fi
# Ensure picroute import path
export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"
python -c "import importlib.metadata as m; print('lidar gf', m.version('gdsfactory'))"
python -c "from picroute.main.picroute import PICRoute; print('PICRoute ok', PICRoute)" || echo "PICRoute import soft-fail (check multimethod/torch)"
echo "export PICASSO_LIDAR_PYTHON=$VENV/bin/python"
echo "export PYTHONPATH=$ROOT/src:\$PYTHONPATH"
echo "Add the export lines above to your shell before routing."
