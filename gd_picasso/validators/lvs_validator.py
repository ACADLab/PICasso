"""
LVS (Layout vs Schematic) Validator

Compares layout Component with schematic Component using gdsfactory.utils.lvs.lvs().
"""

import logging
from typing import Dict, Tuple, Optional
import gdsfactory as gf

logger = logging.getLogger(__name__)

# Try to import LVS function
try:
    from gdsfactory.utils.lvs import lvs
    LVS_AVAILABLE = True
except ImportError:
    LVS_AVAILABLE = False
    lvs = None


class LVSValidator:
    """Validates layout matches schematic using LVS."""

    def __init__(self, enabled: bool = True):
        """
        Initialize LVS validator.

        Args:
            enabled: Whether LVS checking is enabled (may be slow for large circuits)
        """
        self.enabled = enabled and LVS_AVAILABLE
        if not LVS_AVAILABLE:
            logger.warning("gdsfactory.utils.lvs not available - LVS checking disabled")

    def validate(
        self,
        layout: gf.Component,
        schematic: gf.Component
    ) -> Tuple[bool, Dict]:
        """
        Run LVS validation.

        Args:
            layout: Layout Component (from YAML or Python)
            schematic: Schematic Component (reference or from YAML)

        Returns:
            (is_valid, report) where report contains:
                - passed: bool
                - matched: bool
                - errors: List[str]
                - warnings: List[str]
                - mismatches: Dict (if any)
        """
        report = {
            "passed": True,
            "matched": True,
            "errors": [],
            "warnings": [],
            "mismatches": {}
        }

        if not self.enabled:
            report["warnings"].append("LVS checking is disabled")
            logger.info("LVS checking is disabled - skipping")
            return True, report

        try:
            # Run LVS
            lvs_result = lvs(layout, schematic)
            
            # Check result
            if hasattr(lvs_result, 'matched'):
                report["matched"] = lvs_result.matched
                report["passed"] = lvs_result.matched
            elif isinstance(lvs_result, dict):
                report["matched"] = lvs_result.get('matched', False)
                report["passed"] = report["matched"]
                report["mismatches"] = lvs_result.get('mismatches', {})
            else:
                # Assume boolean result
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
        feedback_parts = []

        if not report["matched"]:
            feedback_parts.append("LVS MISMATCH: Layout does not match schematic")
            
            if report["mismatches"]:
                feedback_parts.append("\nMismatch details:")
                for mismatch_type, details in report["mismatches"].items():
                    feedback_parts.append(f"  - {mismatch_type}: {details}")
            
            feedback_parts.append("\nSUGGESTIONS FOR FIXING:")
            feedback_parts.append("  - Check that all instances are present")
            feedback_parts.append("  - Verify port names match between layout and schematic")
            feedback_parts.append("  - Ensure all connections are correct")

        return "\n".join(feedback_parts)

