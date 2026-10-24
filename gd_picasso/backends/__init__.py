"""Foundry backends that sit beside the PCG (SiEPIC EBeam via ubcpdk)."""

from gd_picasso.backends.siepic import (
    COMPONENT_PORT_MAP,
    EULER_BEND_RMIN_UM,
    PORT_WIDTH_UM,
    STRIP_WIDTH_UM,
    WIDTHS_NOT_500NM,
)

__all__ = [
    "COMPONENT_PORT_MAP",
    "EULER_BEND_RMIN_UM",
    "PORT_WIDTH_UM",
    "STRIP_WIDTH_UM",
    "WIDTHS_NOT_500NM",
]
