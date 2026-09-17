"""
Back-annotation contract — write routed geometry onto PCG edges.

N2 claim: simulate the *routed* circuit. The router (or a harness that
reads ``component.get_netlist()``) calls ``apply_route_metrics`` so
``length_um`` / ``phase_rad`` / ``n_crossings`` land on edges before SPA
or SAX.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .store import PCGStore
from .types import EdgeLayer


@dataclass
class RouteMetrics:
    length_um: float = 0.0
    phase_rad: Optional[float] = None
    n_crossings: int = 0
    bend_angle_rad: float = 0.0


def apply_route_metrics(
    store: PCGStore,
    metrics: Dict[Tuple[str, str, str, str], RouteMetrics],
    *,
    agent: Optional[str] = "backannotate",
    neff: float = 2.34,
    wavelength_um: float = 1.55,
) -> int:
    """Write metrics onto matching optical edges.

    Keys are ``(src_node, src_port, dst_node, dst_port)``. Undirected match
    is accepted (src/dst may be swapped). Returns number of edges updated.
    """
    updated = 0
    for e in store.edges:
        if e.layer != EdgeLayer.OPTICAL:
            continue
        key = (e.src_node, e.src_port, e.dst_node, e.dst_port)
        rev = (e.dst_node, e.dst_port, e.src_node, e.src_port)
        m = metrics.get(key) or metrics.get(rev)
        if m is None:
            continue
        e.length_um = m.length_um
        e.n_crossings = m.n_crossings
        if m.phase_rad is not None:
            e.phase_rad = m.phase_rad
        elif m.length_um:
            e.phase_rad = 2.0 * math.pi * neff * m.length_um / wavelength_um
        updated += 1
        store.journal.append(
            "backannotate_edge",
            {
                "src": f"{e.src_node},{e.src_port}",
                "dst": f"{e.dst_node},{e.dst_port}",
                "length_um": e.length_um,
                "phase_rad": e.phase_rad,
                "n_crossings": e.n_crossings,
            },
            agent=agent,
        )
    return updated


def delta_il_from_netlists(
    ideal_il_db: float,
    routed_il_db: float,
) -> Dict[str, float]:
    """Tiny helper for the N2 harness — keeps sign convention in one place."""
    return {
        "il_ideal_db": ideal_il_db,
        "il_routed_db": routed_il_db,
        "dIL_db": routed_il_db - ideal_il_db,
    }
