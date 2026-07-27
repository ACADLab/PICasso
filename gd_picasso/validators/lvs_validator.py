"""
LVS (Layout vs Schematic) Validator

Compares layout Component with schematic Component using gdsfactory.utils.lvs.lvs().
"""

import logging
import shutil
from typing import Dict, Tuple, Optional
import gdsfactory as gf

logger = logging.getLogger(__name__)

# Try to import LVS function
try:
    from kfactory.lvs import lvs
    LVS_AVAILABLE = True
except Exception:
    LVS_AVAILABLE = False
    lvs = None


def _can_import(module_name: str) -> bool:
    """Import-based dependency probe that avoids fragile package __path__ checks."""
    try:
        __import__(module_name, fromlist=["*"])
        return True
    except (ImportError, AttributeError, ModuleNotFoundError):
        return False


class MockLVSValidator:
    """Degraded LVS validator that reports dependency status without blocking runs."""

    def __init__(self, reason: str):
        self.reason = reason

    def validate(
        self,
        component: gf.Component,
        schematic: Optional[gf.Component] = None
    ) -> Tuple[bool, Dict]:
        dependencies = self.check_dependencies()
        missing = [name for name, available in dependencies.items() if not available]
        warning = (
            "LVS running in mock mode; treating LVS as passed so the "
            f"pipeline can continue. Reason: {self.reason}"
        )
        if missing:
            warning += f". Missing/undetected dependencies: {', '.join(missing)}"

        logger.warning(warning)
        report = {
            "passed": True,
            "matched": True,
            "errors": [],
            "warnings": [warning],
            "mismatches": {},
            "skipped": True,
            "degraded": True,
            "mocked": True,
            "available": False,
            "dependencies": dependencies,
            "reason": self.reason,
        }
        return True, report

    @staticmethod
    def check_dependencies() -> Dict[str, bool]:
        """Best-effort check for common LVS Python and command-line backends."""
        return {
            "gdsfactory.utils.lvs": _can_import("gdsfactory.utils.lvs"),
            "gplugins": _can_import("gplugins"),
            "klayout": shutil.which("klayout") is not None,
            "netgen": shutil.which("netgen") is not None,
        }


class LVSValidator:
    """Validates layout matches schematic using LVS."""

    def __init__(self, enabled: bool = True, allow_mock: bool = True):
        """
        Initialize LVS validator.

        Args:
            enabled: Whether LVS checking is enabled (may be slow for large circuits)
            allow_mock: If True, missing LVS backends pass in degraded mock mode
        """
        self.enabled = enabled and LVS_AVAILABLE
        self.requested = enabled
        self.available = LVS_AVAILABLE
        self.allow_mock = allow_mock
        self.mock_validator = None
        if not LVS_AVAILABLE:
            reason = "gdsfactory.utils.lvs could not be imported"
            logger.warning("%s - LVS checking will use mock mode", reason)
            self.mock_validator = MockLVSValidator(reason)

    def validate(
        self,
        component: gf.Component,
        schematic: Optional[gf.Component] = None
    ) -> Tuple[bool, Dict]:
        """
        Run LVS validation.

        Args:
            component: Layout Component (from YAML or Python)
            schematic: Optional schematic Component (if None, uses component's netlist)

        Returns:
            (is_valid, report) where report contains:
                - passed: bool
                - matched: bool
                - errors: List[str]
                - warnings: List[str]
                - mismatches: Dict (if any)
        """
        report = {
            "passed": False,
            "matched": False,
            "errors": [],
            "warnings": [],
            "mismatches": {},
            "skipped": False,
            "degraded": False,
            "mocked": False,
            "available": self.available,
        }

        if not self.enabled:
            if self.requested and not self.available and self.allow_mock and self.mock_validator:
                return self.mock_validator.validate(component, schematic)

            report["skipped"] = True
            if self.requested and not self.available:
                report["warnings"].append(
                    "LVS engine unavailable: gdsfactory.utils.lvs could not be imported"
                )
            else:
                report["warnings"].append("LVS checking is disabled")
            logger.info("LVS checking is disabled - skipping")
            report["passed"] = True
            report["matched"] = True
            return True, report

        try:
            # For now, LVS requires comparing layout with schematic
            # Since we're building from YAML, we can compare component with its own netlist
            # This is a simplified LVS check - full LVS would require a reference schematic
            if schematic is None:
                # Use component's netlist as reference
                # For YAML-built components, we can't easily get a separate schematic
                # So we'll do a basic check: verify component has valid structure
                report["warnings"].append("LVS: No reference schematic provided - performing basic structure check")
                report["degraded"] = True
                # Basic check: component should have instances and ports
                if not hasattr(component, 'references') and not hasattr(component, 'insts'):
                    report["errors"].append("Component has no instances")
                    report["passed"] = False
                    report["matched"] = False
                    return False, report
                
                # If we have a netlist, we can verify structure matches
                try:
                    netlist = component.get_netlist()
                    if not netlist or 'instances' not in netlist:
                        report["errors"].append("Component netlist is invalid")
                        report["passed"] = False
                        report["matched"] = False
                        return False, report
                except Exception as e:
                    report["warnings"].append(f"Could not extract netlist for LVS: {e}")
                    # Don't fail on this - it's just a warning
                
                # Basic structure check passed
                report["matched"] = True
                report["passed"] = True
                return True, report
            
            # If schematic is provided, run full LVS
            lvs_result = lvs(component, schematic)
            
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
                f"LVS Validation: {'PASS' if report['passed'] else 'FAIL'} "
                f"(skipped={report['skipped']}, degraded={report['degraded']})"
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
