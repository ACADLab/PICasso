"""
Photonic Circuit Graph — Type definitions.

Pydantic models for the PCG intermediate representation:
nodes (device instances), edges (nets), ports, constraints, bundles.

Lane Formal owns graded annotation extensions (``loss_dB`` / ``phase_rad``)
and the A1 mutation contract freeze — see ``A1_MUTATION_CONTRACT.md``.
Additive fields only; do not thrash signatures without a Formal re-freeze.
"""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RefLevel(str, enum.Enum):
    """Refinement level of a graph element."""
    L0_INTENT = "L0_INTENT"
    L1_CIRCUIT = "L1_CIRCUIT"
    L2_PLACED = "L2_PLACED"
    L3_ROUTED = "L3_ROUTED"


class PortKind(str, enum.Enum):
    OPTICAL = "OPTICAL"
    ELECTRICAL = "ELECTRICAL"
    THERMAL = "THERMAL"


class EdgeLayer(str, enum.Enum):
    OPTICAL = "OPTICAL"
    ELECTRICAL = "ELECTRICAL"
    THERMAL = "THERMAL"


class AttachmentKind(str, enum.Enum):
    """How two ports are physically joined."""
    ROUTED = "ROUTED"        # routes.<bundle>.links — materialises waveguides
    BUTT_JOINT = "BUTT_JOINT"  # connections dict — zero-length butt joint


class ConstraintKind(str, enum.Enum):
    SPACING = "SPACING"
    MATCHED_LENGTH = "MATCHED_LENGTH"
    THERMAL_KEEPAWAY = "THERMAL_KEEPAWAY"
    DANGLING_PORT = "DANGLING_PORT"
    PORT_DEGREE = "PORT_DEGREE"
    CUSTOM = "CUSTOM"


class ConstraintStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    WAIVED = "WAIVED"


# ---------------------------------------------------------------------------
# Port
# ---------------------------------------------------------------------------

class PCGPort(BaseModel):
    """A single port on a device instance."""
    name: str
    kind: PortKind = PortKind.OPTICAL
    width_um: float = 0.5
    layer: str = "strip"


# ---------------------------------------------------------------------------
# Node  (= device instance)
# ---------------------------------------------------------------------------

class PCGNode(BaseModel):
    """A device instance in the photonic circuit graph."""
    id: str
    component: str
    params: Dict[str, Any] = Field(default_factory=dict)
    level: RefLevel = RefLevel.L1_CIRCUIT
    ports: Dict[str, PCGPort] = Field(default_factory=dict)

    # Placement — populated at L2+
    x: Optional[float] = None
    y: Optional[float] = None
    rotation: Optional[int] = None
    mirror: bool = False

    # Verbatim stash of original placement dict from GDSFactory YAML.
    # Re-emitted unchanged by to_gf_yaml unless _placement_dirty is True.
    raw_placement: Optional[Dict[str, Any]] = None
    _placement_dirty: bool = False


# ---------------------------------------------------------------------------
# Edge  (= net / connection)
# ---------------------------------------------------------------------------

class PCGEdge(BaseModel):
    """A connection between two ports in the photonic circuit graph."""
    src_node: str
    src_port: str
    dst_node: str
    dst_port: str

    attachment: AttachmentKind = AttachmentKind.ROUTED
    bundle: Optional[str] = None
    layer: EdgeLayer = EdgeLayer.OPTICAL

    # Back-annotation / graded fields — populated at L3 (or intent pre-route)
    phase_rad: Optional[float] = None
    loss_dB: Optional[float] = None  # Formal graded pair with phase_rad
    length_um: Optional[float] = None
    n_crossings: int = 0

    # Phase-critical group membership
    constraint_group: Optional[str] = None


# ---------------------------------------------------------------------------
# Bundle settings  (per route bundle)
# ---------------------------------------------------------------------------

class BundleSettings(BaseModel):
    """Per-bundle routing settings from GDSFactory YAML."""
    routing_strategy: Optional[str] = None
    radius: Optional[float] = None
    separation: Optional[float] = None
    cross_section: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Constraint ledger entry
# ---------------------------------------------------------------------------

class ConstraintEntry(BaseModel):
    """A single entry in the constraint ledger."""
    id: str
    kind: ConstraintKind
    elements: List[str] = Field(default_factory=list)
    status: ConstraintStatus = ConstraintStatus.OPEN
    evidence: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Graded annotations (Lane Formal — Paper A)
# ---------------------------------------------------------------------------

class GradedQuantities(BaseModel):
    """First-class ``(loss_dB, phase_rad)`` pair for intent or measurement.

    Additive sidecar for Formal / SPA / FoM. Does not replace edge geometry
    fields; ``PCGEdge.loss_dB`` / ``PCGEdge.phase_rad`` mirror the measured
    half after back-annotation.
    """

    loss_dB: Optional[float] = None
    phase_rad: Optional[float] = None


class SpecAnnotation(BaseModel):
    """λλ linear-spec annotation for a PIC-Set task or ad-hoc probe.

    ``partition`` must match ``PICSET_PARTITION.md`` tags. Only
    ``expressible`` / ``expressible_trivial`` enter PSD→Clements this cycle.
    """

    task_id: Optional[int] = None
    n_inputs: int
    spec_lines: List[str] = Field(default_factory=list)
    partition: str = "expressible"
    ancillas: Optional[int] = None
    notes: str = ""
    grade: GradedQuantities = Field(default_factory=GradedQuantities)


class LoweredMZIAnnotation(BaseModel):
    """One Clements MZI cell ready for A1 emission (sidecar grades).

    Phases are radians, wrapped to a conventional principal range by the
    extractor. Topology expansion into ``add_node``/``connect``/``set_param``
    is ``probes.lowering.to_a1`` (stub until patched λλ lands).
    """

    modes: Tuple[int, int]
    theta_rad: float
    phi_rad: float
    out_a_rad: float
    out_b_rad: float
    grade: GradedQuantities = Field(default_factory=GradedQuantities)
    cell_id: Optional[str] = None
