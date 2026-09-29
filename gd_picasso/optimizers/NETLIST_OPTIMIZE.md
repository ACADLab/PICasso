# `netlist_optimize` status (ICLAD Table III/V)

## Status (Lane FoM)

**Recovered** into [`netlist_optimize.py`](netlist_optimize.py) from git history
(`0834331` / `ae2cc83`, identical blob). Root `netlist_optimize.py` was
untracked after `83c175d` added a bare `netlist_optimize.py` gitignore rule
(legacy root cleanup); that rule is now scoped to `/netlist_optimize.py` so
the package copy can be tracked.

## What it is

SAX netlist-level optimizer (`optimize_netlist`, `Tunable`, `svd_bound`) used
for circuit FoMs that drive σ₁²(T) / SVD bounds — the path needed to reproduce
ICLAD Table III/V optimization columns.

Import path:

```python
from gd_picasso.optimizers.netlist_optimize import optimize_netlist, Tunable, svd_bound
```

[`optimization_integration.py`](optimization_integration.py) uses the same
package import (no `sys.path` root hack).

## Reproduction gap (honest)

- Restored source matches the last committed root file; it was never rewritten
  for gf 9.23 / current gplugins SAX APIs.
- End-to-end Table III/V numbers are **not** re-validated in this FoM leftover
  pass — only source recovery + import wiring.
- If a local root copy still exists and differs, prefer the package module;
  reconcile against paper numbers before claiming table reproduction.
