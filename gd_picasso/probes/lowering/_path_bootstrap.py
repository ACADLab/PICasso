"""Ensure λλ vendor + probe flat-imports resolve.

Call ``ensure_ll_on_path()`` before ``import unitary_inference`` / ``psd_gate``.
Also used by pytest via ``conftest.py`` and ``[tool.pytest.ini_options] pythonpath``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_VENDOR_SRC = (
    Path(__file__).resolve().parents[2] / "vendor" / "lambda_lambda" / "src"
)
_LOWERING_DIR = Path(__file__).resolve().parent


def ensure_ll_on_path() -> Path:
    """Prepend vendor ``src/`` and this lowering dir to ``sys.path`` once."""
    for p in (_VENDOR_SRC, _LOWERING_DIR):
        s = str(p)
        if p.is_dir() and s not in sys.path:
            sys.path.insert(0, s)
    return _VENDOR_SRC


# Auto-wire on import so ``from gd_picasso.probes.lowering…`` unlocks λλ.
ensure_ll_on_path()
