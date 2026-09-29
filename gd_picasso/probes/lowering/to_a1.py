"""Lowering → A1 mutation interface (stub until patched λλ lands).

Emits batches matching ``gd_picasso/pcg/A1_MUTATION_CONTRACT.md`` v1.
Lane λλ/Env fills real Cornerstone cell expansion; Agents consume the
frozen payload keys only.

Do not invent ``insert_module`` / ``group_constraint`` / ``set_edge_grade``
ops here until Formal re-freezes the contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from gd_picasso.pcg.types import GradedQuantities, LoweredMZIAnnotation, SpecAnnotation

# Re-export contract version for Agents / Env join checks.
A1_CONTRACT_VERSION = 1


class LoweringA1NotReady(NotImplementedError):
    """Raised when full cell→instance expansion needs patched λλ / CS cells."""


def annotations_from_mzicells(
    cells: Sequence[Any],
    *,
    prefix: str = "mzi",
) -> List[LoweredMZIAnnotation]:
    """Adapt ``lower.MZICell``-like objects into Formal annotations.

    Accepts duck-typed cells with ``.modes``, ``.theta``, ``.phi``,
    ``.out_a``, ``.out_b`` (as in ``lower.MZICell``).
    """
    out: List[LoweredMZIAnnotation] = []
    for k, c in enumerate(cells):
        modes = tuple(c.modes)
        if len(modes) != 2:
            raise ValueError(f"expected 2 modes, got {modes!r}")
        out.append(
            LoweredMZIAnnotation(
                modes=(int(modes[0]), int(modes[1])),
                theta_rad=float(c.theta),
                phi_rad=float(c.phi),
                out_a_rad=float(c.out_a),
                out_b_rad=float(c.out_b),
                grade=GradedQuantities(),
                cell_id=f"{prefix}{k}",
            )
        )
    return out


def cells_to_a1_mutations(
    annotations: Sequence[LoweredMZIAnnotation],
    *,
    spec: Optional[SpecAnnotation] = None,
    expand_instances: bool = False,
) -> Tuple[List[Dict[str, Any]], List[LoweredMZIAnnotation]]:
    """Translate lowered MZI annotations into an A1 mutation batch.

    Parameters
    ----------
    annotations:
        Output of Clements + extract (or ``annotations_from_mzicells``).
    spec:
        Optional PIC-Set / probe annotation (partition must be expressible*).
    expand_instances:
        If False (default), return an empty mutation list and the annotations
        unchanged — topology emission waits on λλ/Env cell templates.
        If True, raise ``LoweringA1NotReady`` until Env wires real expansion.

    Returns
    -------
    mutations, annotations
        ``mutations`` obey A1 contract v1 keys only.
    """
    if spec is not None and spec.partition not in (
        "expressible",
        "expressible_trivial",
    ):
        raise ValueError(
            f"refusing lowering→A1 for partition={spec.partition!r} "
            f"(task_id={spec.task_id}); see PICSET_PARTITION.md"
        )

    ann = list(annotations)
    if not expand_instances:
        # Stub path: Agents/λλ can fill; Formal freezes the return shape.
        return [], ann

    raise LoweringA1NotReady(
        "Cornerstone MZI instance expansion (mmi2x2 + heaters + dummy arm) "
        "requires patched λλ + cspdk==1.3.2 cell choices — Lane λλ/Env owns fill-in. "
        f"A1_CONTRACT_VERSION={A1_CONTRACT_VERSION}; "
        f"{len(ann)} annotation(s) ready as sidecar."
    )


def heater_set_param_mutations(
    node_id: str,
    *,
    length_um: float,
    phase_rad: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Helper: frozen ``set_param`` ops for a heater instance (no expand).

    ``phase_rad`` is recorded only in caller-side ``GradedQuantities`` until
    a future ``set_edge_grade`` op is frozen; length is a real PDK param.
    """
    _ = phase_rad  # sidecar sole; keep signature for Env fill-in
    return [
        {
            "op": "set_param",
            "node": node_id,
            "key": "length",
            "value": float(length_um),
        }
    ]
