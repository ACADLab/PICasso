"""
gd_picasso.pcg — Photonic Circuit Graph intermediate representation.

Public API re-exports for convenience.
"""

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
from .legalize import detect_dangling_ports

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
    # store
    "PCGMutationError",
    "PCGStore",
    # bridge
    "from_gf_yaml",
    "to_gf_yaml",
    "to_sax_netlist",
    # legalize
    "detect_dangling_ports",
]
