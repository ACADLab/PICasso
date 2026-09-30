"""
Layout-vs-schematic **connectivity** check (PCG ↔ GF netlist).

This is **not** device-level foundry LVS (no parameter extract, no electrical/
thermal nets, no geometry beyond instance/port adjacency against the netlist).

gdsfactory 9.x has no ``gdsfactory.utils.lvs`` module (``gdsfactory.utils`` is
a single file). This validator does **not** probe for that API — connectivity
comparison is the only designed path under the gf 9.23 gate pin.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Optional, Tuple

import gdsfactory as gf

if TYPE_CHECKING:
    from gd_picasso.pcg.store import PCGStore

logger = logging.getLogger(__name__)


class LVSValidator:
    """PCG/YAML-to-layout connectivity check (named LVS only for report columns)."""

    def __init__(self, enabled: bool = True):
        """
        Args:
            enabled: When False, ``validate`` / ``validate_connectivity`` soft-skip.
        """
        self.enabled = enabled

    def validate(
        self,
        component: gf.Component,
        schematic: Optional[gf.Component] = None,
    ) -> Tuple[bool, Dict]:
        """Legacy entry without a PCG store — structure/netlist smoke only.

        Prefer ``validate_connectivity(store, component)`` for the e2e gate.
        ``schematic`` is ignored (no device-level LVS backend under gf 9).
        """
        del schematic  # no gf utils.lvs comparator
        report: Dict = {
            "passed": True,
            "matched": True,
            "errors": [],
            "warnings": [],
            "mismatches": {},
            "lvs_mode": "structure",
            "check": "structure",
        }

        if not self.enabled:
            report["warnings"].append("connectivity check disabled")
            report["lvs_mode"] = "disabled"
            return True, report

        try:
            netlist = component.get_netlist()
            if not netlist or "instances" not in netlist:
                report["errors"].append("Component netlist is invalid")
                report["passed"] = False
                report["matched"] = False
                return False, report
        except Exception as e:
            report["errors"].append(f"Could not extract netlist: {e}")
            report["passed"] = False
            report["matched"] = False
            return False, report

        report["warnings"].append(
            "structure check only — use validate_connectivity for PCG↔layout"
        )
        return True, report

    def validate_connectivity(
        self,
        store: "PCGStore",
        component: Optional[gf.Component] = None,
    ) -> Tuple[bool, Dict]:
        """Compare PCG optical graph instances/edges to the GF layout netlist.

        Verifies: named PCG nodes appear as GF instances; optical edge endpoints
        exist in the layout netlist.

        Does **not** verify: device parameters, electrical/thermal nets, or
        geometry beyond port/instance adjacency.
        """
        from gd_picasso.pcg.types import EdgeLayer

        report: Dict = {
            "passed": True,
            "matched": True,
            "errors": [],
            "warnings": [],
            "mismatches": {},
            "lvs_mode": "connectivity",
            "check": "connectivity",
        }

        if not self.enabled:
            report["warnings"].append("connectivity check disabled")
            report["lvs_mode"] = "disabled"
            return True, report

        optical = [e for e in store.edges if e.layer == EdgeLayer.OPTICAL]
        store_nodes = set(store.nodes.keys())
        if component is None:
            for e in optical:
                if e.src_node not in store_nodes or e.dst_node not in store_nodes:
                    report["errors"].append(
                        f"edge {e.src_node}->{e.dst_node} references missing node"
                    )
            report["passed"] = not report["errors"]
            report["matched"] = report["passed"]
            return report["passed"], report

        try:
            nl = component.get_netlist() or {}
        except Exception as e:
            report["errors"].append(f"netlist extract failed: {e}")
            report["passed"] = False
            report["matched"] = False
            return False, report

        insts = set((nl.get("instances") or {}).keys())
        missing = sorted(store_nodes - insts)
        if missing:
            report["mismatches"]["missing_in_layout"] = missing
            report["errors"].append(
                f"PCG nodes missing from GF netlist: {missing}"
            )
        for e in optical:
            if e.src_node not in insts or e.dst_node not in insts:
                report["errors"].append(
                    f"routed edge {e.src_node},{e.src_port}→"
                    f"{e.dst_node},{e.dst_port} not in layout instances"
                )
        report["passed"] = not report["errors"]
        report["matched"] = report["passed"]
        return report["passed"], report

    def generate_feedback(self, report: Dict) -> str:
        """Human-readable feedback for LLM retry."""
        if report.get("lvs_mode") == "disabled":
            return "Connectivity check disabled."

        feedback_parts = []
        if not report.get("matched", True):
            feedback_parts.append(
                "CONNECTIVITY MISMATCH: PCG/YAML does not match layout netlist"
            )
            if report.get("mismatches"):
                feedback_parts.append("\nMismatch details:")
                for mismatch_type, details in report["mismatches"].items():
                    feedback_parts.append(f"  - {mismatch_type}: {details}")
            feedback_parts.append("\nSUGGESTIONS:")
            feedback_parts.append("  - Check that all instances are present")
            feedback_parts.append(
                "  - Verify port names match between layout and schematic"
            )
            feedback_parts.append("  - Ensure optical connections are correct")
        return "\n".join(feedback_parts)
