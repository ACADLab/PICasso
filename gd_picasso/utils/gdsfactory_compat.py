"""Compatibility patches for gdsfactory version-specific component issues."""

from __future__ import annotations

import logging

import gdsfactory as gf
from gdsfactory.component import Component
from gdsfactory.port import get_ports_list
from gdsfactory.snap import snap_to_grid
from gdsfactory.typings import CrossSectionSpec

logger = logging.getLogger(__name__)


def ensure_generic_pdk_active() -> bool:
    """Activate the generic PDK when no PDK is active."""
    try:
        gf.get_active_pdk()
        return False
    except Exception:
        try:
            gf.gpdk.PDK.activate()
            logger.info("Activated generic GDSFactory PDK")
            return True
        except Exception as exc:
            logger.debug("Could not activate generic GDSFactory PDK: %s", exc)
            return False


def patch_dbr_ports() -> bool:
    """Ensure ``gf.components.dbr`` exposes both optical ports.

    gdsfactory 9.44.0 builds the right-side DBR straight but only exports
    ``o1`` from the top-level ``dbr`` component. YAML netlists that connect
    to the physical through port ``o2`` then fail pilot validation and
    ``gf.read.from_yaml``. This patch replaces the registry entry with an
    equivalent implementation that also exports ``o2``.
    """
    ensure_generic_pdk_active()

    try:
        existing = gf.components.dbr()
        existing_ports = {port.name for port in get_ports_list(existing.ports)}
    except Exception as exc:
        logger.debug("Skipping DBR port patch; could not instantiate dbr: %s", exc)
        return False

    if {"o1", "o2"}.issubset(existing_ports):
        return False

    @gf.cell_with_module_name(tags=["filters"])
    def dbr(
        w1: float = 0.45,
        w2: float = 0.55,
        l1: float = 0.159,
        l2: float = 0.159,
        n: int = 10,
        cross_section: CrossSectionSpec = "strip",
        straight_length: float = 10e-3,
    ) -> Component:
        c = Component()
        xs = gf.get_cross_section(cross_section)
        s1 = c << gf.c.straight(cross_section=xs, length=straight_length)
        s2 = c << gf.c.straight(cross_section=xs, length=straight_length)

        l1_grid = snap_to_grid(l1)
        l2_grid = snap_to_grid(l2)
        cell = gf.components.dbr_cell(
            w1=w1,
            w2=w2,
            l1=l1_grid,
            l2=l2_grid,
            cross_section=cross_section,
        )
        ref = c.add_ref(cell, columns=n, rows=1, column_pitch=l1_grid + l2_grid)

        s1.connect(port="o1", other=cell.ports["o1"], allow_width_mismatch=True)
        s2.connect(port="o1", other=cell.ports["o2"], allow_width_mismatch=True)
        s2.xmin = ref.xmax

        c.add_port("o1", port=s1.ports["o2"])
        c.add_port("o2", port=s2.ports["o2"])
        return c

    import gdsfactory.components.filters.dbr as dbr_module

    dbr_module.dbr = dbr
    gf.components.dbr = dbr
    gf.c.dbr = dbr
    try:
        gf.get_active_pdk().cells["dbr"] = dbr
    except Exception as exc:
        logger.debug("Could not patch active PDK DBR cell registry: %s", exc)
    logger.info("Patched gf.components.dbr to expose ports o1 and o2")
    return True
