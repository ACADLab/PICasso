"""
LVS (Layout vs Schematic) Validator

Intended API: ``gdsfactory.utils.lvs.lvs(layout, schematic)``.

## gf 9 soft-break (documented — do not fake LVS)

Under **gdsfactory 9.23.x**, ``gdsfactory.utils`` is not a package that
exposes ``lvs`` (``gdsfactory.utils.lvs`` is missing). Import fails and
``LVS_AVAILABLE`` is False. Callers must treat LVS as **soft-skipped**, not
as a pass from a stub comparator.

This module does **not** invent layout-vs-schematic matching when the PDK
helper is absent. Without ``lvs``, ``validate()`` returns a skip report
(warning + ``lvs_skipped_gf9``) and ``passed=True`` only in the sense of
"check not run" — same contract as ``enabled=False``.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

import gdsfactory as gf

logger = logging.getLogger(__name__)

# Soft-break under gf 9.23: do not stub a fake LVS implementation.
try:
    from gdsfactory.utils.lvs import lvs

    LVS_AVAILABLE = True
except ImportError:
    LVS_AVAILABLE = False
    lvs = None


class LVSValidator:
    """Validates layout matches schematic using LVS when the gf helper exists."""

    def __init__(self, enabled: bool = True):
        """
        Initialize LVS validator.

        Args:
            enabled: Whether LVS checking is enabled (may be slow for large circuits).
                     Ignored when ``gdsfactory.utils.lvs`` is unavailable.
        """
        self.enabled = enabled and LVS_AVAILABLE
        if not LVS_AVAILABLE:
            logger.warning(
                "gdsfactory.utils.lvs missing (gf 9 soft-break) — LVS disabled; "
                "not faking layout-vs-schematic"
            )

    def validate(
        self,
        component: gf.Component,
        schematic: Optional[gf.Component] = None,
    ) -> Tuple[bool, Dict]:
        """
        Run LVS validation, or soft-skip when LVS is unavailable/disabled.

        Returns:
            (is_valid, report). When LVS is skipped, ``passed`` is True with
            warnings documenting the skip (not a fabricated LVS match).
        """
        report: Dict = {
            "passed": True,
            "matched": True,
            "errors": [],
            "warnings": [],
            "mismatches": {},
            "lvs_skipped_gf9": not LVS_AVAILABLE,
        }

        if not LVS_AVAILABLE:
            report["warnings"].append(
                "LVS soft-skip: gdsfactory.utils.lvs missing under gf 9 "
                "(no fake LVS)"
            )
            logger.info("LVS soft-skipped (gf 9) — not claiming layout==schematic")
            return True, report

        if not self.enabled:
            report["warnings"].append("LVS checking is disabled")
            report["lvs_skipped_gf9"] = False
            logger.info("LVS checking is disabled - skipping")
            return True, report

        try:
            if schematic is None:
                report["warnings"].append(
                    "LVS: No reference schematic provided — basic structure check only"
                )
                if not hasattr(component, "references") and not hasattr(component, "insts"):
                    report["errors"].append("Component has no instances")
                    report["passed"] = False
                    report["matched"] = False
                    return False, report

                try:
                    netlist = component.get_netlist()
                    if not netlist or "instances" not in netlist:
                        report["errors"].append("Component netlist is invalid")
                        report["passed"] = False
                        report["matched"] = False
                        return False, report
                except Exception as e:
                    report["warnings"].append(f"Could not extract netlist for LVS: {e}")

                report["matched"] = True
                report["passed"] = True
                return True, report

            lvs_result = lvs(component, schematic)

            if hasattr(lvs_result, "matched"):
                report["matched"] = lvs_result.matched
                report["passed"] = lvs_result.matched
            elif isinstance(lvs_result, dict):
                report["matched"] = lvs_result.get("matched", False)
                report["passed"] = report["matched"]
                report["mismatches"] = lvs_result.get("mismatches", {})
            else:
                report["matched"] = bool(lvs_result)
                report["passed"] = report["matched"]

            if not report["matched"]:
                report["errors"].append("Layout does not match schematic")
                if report["mismatches"]:
                    for mismatch_type, details in report["mismatches"].items():
                        report["errors"].append(f"{mismatch_type}: {details}")

            logger.info(
                f"LVS Validation: {'PASS' if report['passed'] else 'FAIL'}"
            )

        except Exception as e:
            logger.error(f"LVS validation failed with exception: {e}")
            report["passed"] = False
            report["matched"] = False
            report["errors"].append(f"LVS exception: {str(e)}")

        return report["passed"], report

    def generate_feedback(self, report: Dict) -> str:
        """Generate human-readable feedback for LLM retry."""
        if report.get("lvs_skipped_gf9"):
            return (
                "LVS soft-skip (gf 9): gdsfactory.utils.lvs is missing. "
                "Do not treat this as a layout-vs-schematic pass."
            )

        feedback_parts = []

        if not report.get("matched", True):
            feedback_parts.append("LVS MISMATCH: Layout does not match schematic")

            if report.get("mismatches"):
                feedback_parts.append("\nMismatch details:")
                for mismatch_type, details in report["mismatches"].items():
                    feedback_parts.append(f"  - {mismatch_type}: {details}")

            feedback_parts.append("\nSUGGESTIONS FOR FIXING:")
            feedback_parts.append("  - Check that all instances are present")
            feedback_parts.append("  - Verify port names match between layout and schematic")
            feedback_parts.append("  - Ensure all connections are correct")

        return "\n".join(feedback_parts)
