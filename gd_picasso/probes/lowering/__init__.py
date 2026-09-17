"""Spec → unitary → Clements → Cornerstone probe scripts.

These are standalone scripts that import each other by flat module name
(``from mzi_extract import wrap``). That resolves automatically when a script
is run by path (``python gd_picasso/probes/lowering/lower.py``) because Python
puts the script's directory on ``sys.path``; it does not resolve under
``python -m``. Appending this directory here makes both invocations work.

Appended, not inserted: nothing in this directory shadows a stdlib or
site-packages module, and appending keeps it that way if one is ever added.
"""

import os as _os
import sys as _sys

_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.append(_HERE)
