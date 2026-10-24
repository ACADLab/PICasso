"""Lowering → A1 mutation interface (A1_MUTATION_CONTRACT.md v1).

Emits batches matching ``gd_picasso/pcg/A1_MUTATION_CONTRACT.md``.
Cornerstone MZI expansion uses ``cspdk==1.3.2`` FINDINGS: ``mmi2x2`` 50:50,
heater ``L=320 µm``, loss-balancing dummy arm.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from gd_picasso.pcg.types import GradedQuantities, LoweredMZIAnnotation, SpecAnnotation

# Re-export contract version for Agents / Env join checks.
A1_CONTRACT_VERSION = 1

# Cornerstone FINDINGS under cspdk==1.3.2 + gf 9.23.0 (promoted FoM constants).
CS_ARM_L_UM = 320.0
CS_MMI2X2_EXCESS_LOSS_DB = 0.3
CS_MZI_IL_DB = 0.622


class LoweringA1NotReady(NotImplementedError):
    """Raised when expansion cannot proceed (bad partition / missing cells)."""


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
                grade=GradedQuantities(loss_dB=CS_MZI_IL_DB),
                cell_id=f"{prefix}{k}",
            )
        )
    return out


def _expand_cs_mzi_cell(ann: LoweredMZIAnnotation) -> List[Dict[str, Any]]:
    """One Clements MZI → CS ``mmi2x2`` + heater + dummy + ``mmi2x2``.

    Topology mirrors the Cornerstone probe (FINDINGS rows 5–7): active arm is
    ``straight_heater_metal`` at ``CS_ARM_L_UM``; parallel arm is a loss-
    balancing ``straight`` of the same length. Phases stay on the annotation
    sidecar (no ``set_edge_grade`` in A1 v1).
    """
    cid = ann.cell_id or f"mzi_{ann.modes[0]}_{ann.modes[1]}"
    split = f"{cid}_split"
    comb = f"{cid}_comb"
    heater = f"{cid}_ps"
    dummy = f"{cid}_dummy"
    L = CS_ARM_L_UM
    return [
        {"op": "add_node", "id": split, "component": "mmi2x2", "params": {}},
        {
            "op": "add_node",
            "id": heater,
            "component": "straight_heater_metal",
            "params": {"length": L},
        },
        {
            "op": "add_node",
            "id": dummy,
            "component": "straight",
            "params": {"length": L},
        },
        {"op": "add_node", "id": comb, "component": "mmi2x2", "params": {}},
        {
            "op": "connect",
            "src": split,
            "src_port": "o3",
            "dst": heater,
            "dst_port": "o1",
            "bundle": "west",
        },
        {
            "op": "connect",
            "src": split,
            "src_port": "o4",
            "dst": dummy,
            "dst_port": "o1",
            "bundle": "west",
        },
        {
            "op": "connect",
            "src": heater,
            "src_port": "o2",
            "dst": comb,
            "dst_port": "o1",
            "bundle": "east",
        },
        {
            "op": "connect",
            "src": dummy,
            "src_port": "o2",
            "dst": comb,
            "dst_port": "o2",
            "bundle": "east",
        },
        {"op": "set_param", "node": heater, "key": "length", "value": L},
        {"op": "set_param", "node": dummy, "key": "length", "value": L},
    ]


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
        unchanged (annotations-only sidecar path).
        If True, emit Cornerstone MZI instance expansion (A1 v1 ops only).

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
        return [], ann

    mutations: List[Dict[str, Any]] = []
    for a in ann:
        # Attach CS grade if caller left grade empty.
        if a.grade.loss_dB is None:
            a.grade = GradedQuantities(
                loss_dB=CS_MZI_IL_DB,
                phase_rad=a.grade.phase_rad,
            )
        mutations.extend(_expand_cs_mzi_cell(a))
    return mutations, ann


def heater_set_param_mutations(
    node_id: str,
    *,
    length_um: float = CS_ARM_L_UM,
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
