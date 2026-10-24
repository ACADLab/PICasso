"""TaskContract oracle — closes the trivial 1-node ExactCritic loophole.

A submission must satisfy both ``ExactCritic.review().ok`` and the per-task
structural contract (min nodes / I/O / component types / phase shifters).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, Mapping, Optional, Set, Union

from gd_picasso.pcg.store import PCGStore

PHASE_SHIFTER_COMPONENTS = frozenset(
    {"straight_heater_metal", "straight_heater_metal_undercut"}
)


@dataclass(frozen=True)
class TaskContract:
    """Structural constraints a task-faithful PCGStore must meet."""

    min_nodes: int
    min_io_ports: int
    required_component_types: FrozenSet[str]
    min_phase_shifters: int = 0

    def __post_init__(self) -> None:
        # Allow callers to pass a plain set.
        if not isinstance(self.required_component_types, frozenset):
            object.__setattr__(
                self,
                "required_component_types",
                frozenset(self.required_component_types),
            )


def _component_counts(store: PCGStore) -> Counter:
    return Counter(n.component for n in store.nodes.values())


def count_phase_shifters(store: PCGStore) -> int:
    counts = _component_counts(store)
    return sum(counts[c] for c in PHASE_SHIFTER_COMPONENTS)


def _has_required_type(counts: Mapping[str, int], type_name: str) -> bool:
    """Match literal PDK names plus a few abstract aliases used in contracts."""
    if counts.get(type_name, 0) > 0:
        return True
    name = type_name.lower()
    if name == "mzi":
        return (
            counts.get("mzi", 0) > 0
            or counts.get("mmi2x2", 0) >= 2
            or (
                counts.get("mmi1x2", 0) >= 1
                and sum(counts[c] for c in PHASE_SHIFTER_COMPONENTS) >= 1
            )
        )
    if name == "mzm":
        return counts.get("mmi1x2", 0) >= 1 and sum(
            counts[c] for c in PHASE_SHIFTER_COMPONENTS
        ) >= 1
    if name in {"crossing", "crossing_horizontal"}:
        return counts.get("crossing", 0) + counts.get("crossing_horizontal", 0) > 0
    if name in {"ring", "ring_single"}:
        return counts.get("ring_single", 0) > 0
    if name in {"phase_shifter", "heater"}:
        return sum(counts[c] for c in PHASE_SHIFTER_COMPONENTS) > 0
    if name == "taper":
        return counts.get("taper", 0) > 0
    if name in {"mmi", "splitter"}:
        return counts.get("mmi1x2", 0) + counts.get("mmi2x2", 0) > 0
    if name in {"star_coupler", "awg"}:
        return counts.get("mmi1x2", 0) + counts.get("coupler", 0) > 0
    return False


def evaluate_task_contract(
    store: PCGStore,
    contract: TaskContract,
) -> bool:
    """Return True iff ``store`` meets every field of ``contract``."""
    if len(store.nodes) < contract.min_nodes:
        return False
    if len(store.exported_ports) < contract.min_io_ports:
        return False
    if count_phase_shifters(store) < contract.min_phase_shifters:
        return False
    counts = _component_counts(store)
    for req in contract.required_component_types:
        if not _has_required_type(counts, req):
            return False
    return True


def contract_failures(
    store: PCGStore,
    contract: TaskContract,
) -> list[str]:
    """Human-readable reasons ``evaluate_task_contract`` would return False."""
    problems: list[str] = []
    n_nodes = len(store.nodes)
    n_io = len(store.exported_ports)
    n_ps = count_phase_shifters(store)
    if n_nodes < contract.min_nodes:
        problems.append(f"min_nodes: have {n_nodes}, need ≥ {contract.min_nodes}")
    if n_io < contract.min_io_ports:
        problems.append(f"min_io_ports: have {n_io}, need ≥ {contract.min_io_ports}")
    if n_ps < contract.min_phase_shifters:
        problems.append(
            f"min_phase_shifters: have {n_ps}, need ≥ {contract.min_phase_shifters}"
        )
    counts = _component_counts(store)
    for req in sorted(contract.required_component_types):
        if not _has_required_type(counts, req):
            problems.append(f"required_component_types: missing {req!r}")
    return problems


def _C(
    min_nodes: int,
    min_io_ports: int,
    required: Iterable[str],
    min_phase_shifters: int = 0,
) -> TaskContract:
    return TaskContract(
        min_nodes=min_nodes,
        min_io_ports=min_io_ports,
        required_component_types=frozenset(required),
        min_phase_shifters=min_phase_shifters,
    )


# Strict floors for all 46 realizable PIC-Bench-48 tasks.
# Mesh / upgraded stubs use authentic topology sizes; frozen PIC-Set rows use
# golden fixture floors so trivial waveguides cannot pass.
TASK_CONTRACTS: Dict[int, TaskContract] = {
    # --- frozen PIC-Set expressible rows ---
    1: _C(4, 2, {"mzi", "mmi1x2"}, 1),
    2: _C(4, 3, {"mzm", "mmi1x2"}, 2),
    3: _C(4, 2, {"mzi", "mmi1x2"}, 1),
    4: _C(4, 2, {"mzi", "mmi1x2"}, 2),
    # --- upgraded former LiDAR stubs ---
    5: _C(16, 4, {"mzm", "mmi1x2"}, 6),  # 8-QAM MZM tree
    6: _C(40, 8, {"mzm", "mmi1x2"}, 14),  # 64-QAM MZM tree
    7: _C(12, 5, {"mzi", "mmi2x2"}, 4),  # WDM mux cascaded MZI
    8: _C(12, 5, {"mzi", "mmi2x2"}, 4),  # WDM demux cascaded MZI
    9: _C(4, 2, {"mzi", "mmi1x2"}, 1),
    10: _C(4, 2, {"mzi", "mmi1x2"}, 1),
    # --- de-aliased switch / mesh fabrics ---
    11: _C(64, 8, {"mzi", "mmi2x2"}, 16),  # Crossbar 4x4: 16 MZIs × 4
    12: _C(256, 16, {"mzi", "mmi2x2"}, 64),  # Crossbar 8x8: 64 MZIs × 4
    13: _C(100, 8, {"mmi1x2", "crossing", "mzi"}, 16),  # Spanke 4x4
    14: _C(400, 16, {"mmi1x2", "crossing", "mzi"}, 64),  # Spanke 8x8
    15: _C(28, 8, {"mzi", "crossing"}, 5),  # Benes 4x4 odd-even
    16: _C(100, 16, {"mzi", "crossing"}, 18),  # Benes 8x8 odd-even
    17: _C(36, 8, {"mzi", "crossing", "mmi1x2"}, 6),  # Spanke-Benes 4x4
    18: _C(100, 16, {"mzi", "crossing", "mmi1x2"}, 20),  # Spanke-Benes 8x8
    19: _C(4, 2, {"mzi", "mmi1x2"}, 1),
    20: _C(24, 8, {"mzi"}, 6),  # Clements 4x4
    21: _C(24, 8, {"mzi"}, 6),  # Reck 4x4
    22: _C(112, 16, {"mzi"}, 28),  # Reck 8x8
    23: _C(4, 3, {"ring_single", "coupler"}, 0),  # Ring add-drop
    24: _C(6, 3, {"ring_single"}, 2),  # Dual-ring tunable
    25: _C(16, 5, {"mzi", "mmi2x2"}, 4),  # 4-ch cascaded MZI
    26: _C(7, 5, {"mmi1x2"}, 0),
    27: _C(4, 2, {"mzi", "mmi1x2"}, 1),
    28: _C(34, 17, {"star_coupler", "straight"}, 0),  # 16-ch AWG proxy
    29: _C(4, 2, {"mzi", "mmi1x2"}, 2),
    30: _C(3, 3, {"mmi1x2"}, 0),
    31: _C(22, 9, {"mzi", "mmi2x2"}, 7),  # WSS 1x8 thermo-optic MZI tree
    32: _C(4, 2, {"mzi", "mmi1x2"}, 2),
    33: _C(1, 2, {"straight"}, 0),
    34: _C(3, 3, {"mmi1x2"}, 0),
    35: _C(3, 3, {"mmi1x2"}, 0),
    36: _C(1, 2, {"phase_shifter"}, 1),
    # --- formal stress ---
    37: _C(24, 8, {"mzi"}, 6),
    38: _C(24, 8, {"mzi"}, 6),
    39: _C(3, 3, {"taper", "ebeam_y_adiabatic"}, 0),
    40: _C(5, 5, {"taper", "mmi1x2"}, 0),
    41: _C(9, 4, {"taper", "ebeam_DC_te895"}, 0),
    42: _C(9, 4, {"taper", "crossing"}, 0),
    43: _C(7, 3, {"taper"}, 0),
    44: _C(3, 1, {"taper", "ebeam_gc_te895"}, 0),
    45: _C(5, 2, {"taper"}, 0),
    46: _C(6, 5, {"mzi", "taper"}, 1),
}


def get_task_contract(task_id: int) -> Optional[TaskContract]:
    """Return the contract for a realizable task, or None for 47/48 rejects."""
    return TASK_CONTRACTS.get(task_id)
