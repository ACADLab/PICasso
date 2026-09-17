"""
gd_picasso.pcg — Photonic Circuit Graph intermediate representation.

Public API re-exports for convenience.
"""

from .sax_models import ensure_jax_x64

ensure_jax_x64()

from .types import (
    AttachmentKind,
    BundleSettings,
    ConstraintEntry,
    ConstraintKind,
    ConstraintStatus,
    EdgeLayer,
    PCGEdge,
    PCGNode,
    PCGPort,
    PortKind,
    RefLevel,
)
from .store import PCGMutationError, PCGStore
from .bridge import from_gf_yaml, to_gf_yaml, to_sax_netlist
from .legalize import detect_dangling_ports, insert_terminators
from .journal import MutationJournal, MutationRecord
from .spa import (
    SPAReport,
    PhaseSlackResult,
    PairSlack,
    spa_v0,
    spa_analyze,
    phase_slack,
    phase_slack_group,
    HYBRID_90_TARGETS_RAD,
)
from .backannotate import RouteMetrics, apply_route_metrics
from .sax_models import SAX_PARAM_AUDIT, audit_table_markdown, build_lossy_models

__all__ = [
    # types / enums
    "AttachmentKind",
    "BundleSettings",
    "ConstraintEntry",
    "ConstraintKind",
    "ConstraintStatus",
    "EdgeLayer",
    "PCGEdge",
    "PCGNode",
    "PCGPort",
    "PortKind",
    "RefLevel",
    # store / journal
    "PCGMutationError",
    "PCGStore",
    "MutationJournal",
    "MutationRecord",
    # bridge
    "from_gf_yaml",
    "to_gf_yaml",
    "to_sax_netlist",
    # legalize
    "detect_dangling_ports",
    "insert_terminators",
    # spa / back-annot
    "SPAReport",
    "PhaseSlackResult",
    "PairSlack",
    "spa_v0",
    "spa_analyze",
    "phase_slack",
    "phase_slack_group",
    "HYBRID_90_TARGETS_RAD",
    "RouteMetrics",
    "apply_route_metrics",
    # sax
    "SAX_PARAM_AUDIT",
    "audit_table_markdown",
    "build_lossy_models",
    "ensure_jax_x64",
]
