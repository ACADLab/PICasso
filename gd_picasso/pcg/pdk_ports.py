"""
PDK optical port map used by PCG ingest, legalize, and exact critic.

Mirrors the static map in agents/critic_agent.py so bridge/legalize do not
depend on the LLM critic package.
"""

from __future__ import annotations

from typing import Dict, List

# Optical ports only — electrical heater pads are intentionally omitted.
COMPONENT_PORT_MAP: Dict[str, List[str]] = {
    "straight": ["o1", "o2"],
    "bend_euler": ["o1", "o2"],
    "bend_circular": ["o1", "o2"],
    "bend_s": ["o1", "o2"],
    "mmi1x2": ["o1", "o2", "o3"],
    "mmi2x2": ["o1", "o2", "o3", "o4"],
    "coupler": ["o1", "o2", "o3", "o4"],
    "mzi": ["o1", "o2"],
    "ring_single": ["o1", "o2"],
    "straight_heater_metal": ["o1", "o2"],
    "straight_heater_metal_undercut": ["o1", "o2"],
    "taper": ["o1", "o2"],
    "spiral": ["o1", "o2"],
    "grating_coupler_elliptical": ["o1", "o2"],
    "crossing": ["o1", "o2", "o3", "o4"],
    "terminator": ["o1"],
}


def ports_for_component(component: str) -> Dict[str, str]:
    """Return {port_name: kind} for known components; empty if unknown."""
    from .types import PortKind

    names = COMPONENT_PORT_MAP.get(component, [])
    return {n: PortKind.OPTICAL.value for n in names}
