"""Held-out functional oracle (n1-confirm-v2). Not used in any repair loop.

Thresholds and the applicable task list are frozen here. Do not retune after
looking at campaign outputs. Validate on golden fixtures before grading models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

# Equal-split trees: each output within SPLIT_TOL_DB of ideal 1/N.
EQUAL_SPLIT_TASK_IDS: Tuple[int, ...] = (26, 30, 34)
SPLIT_TOL_DB: float = 0.5
# Ideal power fraction per output is 1/N. Compare in dB: 10*log10(P / (1/N)).

# Switch / mesh fabrics. Pass = permutation at reference phases (all heater
# phases left at the store's stored params; missing phase = 0), NOT all-to-all.
# All-to-all would fail a correct single-state crossbar.
MESH_PERMUTATION_TASK_IDS: Tuple[int, ...] = (11, 13, 15, 17, 20, 21, 37, 38)
PERM_ON_MIN: float = 0.5  # |S|^2 on the claimed input→output entry
PERM_OFF_MAX: float = 0.1  # |S|^2 on every other entry of that row
PASSIVE_ROW_SUM_MAX: float = 1.0 + 1e-3

APPLICABLE_TASK_IDS: Tuple[int, ...] = EQUAL_SPLIT_TASK_IDS + MESH_PERMUTATION_TASK_IDS

# Ideal crossing: bar through-paths (o1↔o3, o2↔o4), zero cross state.
# Ideal MZI: two 50/50 couplers with a differential phase on the upper arm.
# Models are registered in sax_models.build_lossy_models.


def functional_check(task_id: int, store: Any) -> Dict[str, Any]:
    """Grade ``store`` with the frozen oracle. Never called from the repair loop.

    Returns ``applicable=False`` for tasks outside ``APPLICABLE_TASK_IDS``.
    SAX execution is deferred until golden validation (post-R1); this function
    records the frozen decision rule and refuses to invent a pass.
    """
    if task_id not in APPLICABLE_TASK_IDS:
        return {
            "task_id": task_id,
            "applicable": False,
            "functional_pass": None,
            "kind": None,
            "detail": "not in frozen applicable set",
        }
    kind = "equal_split" if task_id in EQUAL_SPLIT_TASK_IDS else "mesh_permutation"
    return {
        "task_id": task_id,
        "applicable": True,
        "functional_pass": None,
        "kind": kind,
        "detail": (
            "UNVERIFIED: SAX execution not run in the freeze commit. "
            f"kind={kind}; split_tol_dB={SPLIT_TOL_DB}; "
            f"perm_on>={PERM_ON_MIN}; perm_off<={PERM_OFF_MAX}; "
            f"row_sum<={PASSIVE_ROW_SUM_MAX}."
        ),
        "n_nodes": len(getattr(store, "nodes", {}) or {}),
    }


def oracle_spec() -> Dict[str, Any]:
    return {
        "equal_split_tasks": list(EQUAL_SPLIT_TASK_IDS),
        "split_tol_db": SPLIT_TOL_DB,
        "mesh_permutation_tasks": list(MESH_PERMUTATION_TASK_IDS),
        "perm_on_min": PERM_ON_MIN,
        "perm_off_max": PERM_OFF_MAX,
        "passive_row_sum_max": PASSIVE_ROW_SUM_MAX,
        "mzi_model": "two 50/50 couplers + differential phase (ideal)",
        "crossing_model": "bar through o1-o3 and o2-o4, zero crosstalk (ideal)",
        "not_in_repair_loop": True,
    }
