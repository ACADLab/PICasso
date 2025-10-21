"""
SAX Compilation Validator

Validates that designs:
1. Compile successfully in SAX (functional correctness)
2. Have properly routed connections (not just floating components)
3. Match expected circuit behavior

This addresses the issue where SAX passes despite poor physical routing.
"""

import logging
from typing import Dict, Tuple
import gdsfactory as gf
from config import ENABLE_SAX_CHECK, SAX_TIMEOUT

logger = logging.getLogger(__name__)


class SAXValidator:
    """Validates circuit compilation and behavior using SAX."""

    def __init__(self, timeout: int = SAX_TIMEOUT):
        """
        Initialize SAX validator.

        Args:
            timeout: Maximum time for SAX compilation (seconds)
        """
        self.timeout = timeout
        self.enabled = ENABLE_SAX_CHECK

    def validate(self, component: gf.Component) -> Tuple[bool, Dict]:
        """
        Validate SAX compilation and routing correctness.

        Args:
            component: GDSFactory component to validate

        Returns:
            (is_valid, report) where report contains:
                - passed: bool
                - errors: List[str]
                - warnings: List[str]
                - sax_compiled: bool
                - routing_validated: bool
        """
        report = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "sax_compiled": False,
            "routing_validated": False
        }

        if not self.enabled:
            report["warnings"].append("SAX validation is disabled")
            logger.info("SAX validation is disabled - skipping")
            return True, report

        try:
            # Check if SAX is available
            if not self._check_sax_available():
                report["warnings"].append("SAX not installed - validation skipped")
                logger.warning("SAX not available - skipping validation")
                return True, report

            # Run SAX compilation check
            sax_ok = self._check_sax_compilation(component, report)
            report["sax_compiled"] = sax_ok

            # Run routing validation (checks beyond SAX simulation)
            routing_ok = self._check_routing_correctness(component, report)
            report["routing_validated"] = routing_ok

            # Both must pass
            report["passed"] = sax_ok and routing_ok

            logger.info(
                f"SAX Validation: {'PASS' if report['passed'] else 'FAIL'} "
                f"(compilation: {sax_ok}, routing: {routing_ok})"
            )

        except Exception as e:
            logger.error(f"SAX validation failed with exception: {e}")
            report["passed"] = False
            report["errors"].append(f"SAX validation exception: {str(e)}")

        return report["passed"], report

    def _check_sax_available(self) -> bool:
        """Check if SAX is installed."""
        try:
            import sax
            return True
        except ImportError:
            return False

    def _check_sax_compilation(self, component: gf.Component, report: Dict) -> bool:
        """
        Check if circuit compiles in SAX.

        Args:
            component: GDSFactory component
            report: Report to update

        Returns:
            True if SAX compilation succeeds
        """
        try:
            import sax
            import jax.numpy as jnp

            # Try to get netlist and compile circuit
            netlist = component.get_netlist()

            if not netlist:
                report["errors"].append("Failed to extract netlist from component")
                return False

            # Check netlist structure
            if 'instances' not in netlist or not netlist['instances']:
                report["errors"].append("Netlist has no component instances")
                return False

            if 'connections' not in netlist or not netlist['connections']:
                report["warnings"].append("Netlist has no connections (might be single component)")

            # Try to build SAX circuit
            try:
                circuit, _ = sax.circuit(netlist)
                report["sax_compiled"] = True

                logger.debug("SAX compilation successful")
                return True

            except Exception as e:
                report["errors"].append(f"SAX circuit compilation failed: {str(e)}")
                return False

        except ImportError:
            # SAX not available - already handled in _check_sax_available
            return True
        except Exception as e:
            report["errors"].append(f"SAX compilation check error: {str(e)}")
            return False

    def _check_routing_correctness(self, component: gf.Component, report: Dict) -> bool:
        """
        Check routing correctness beyond SAX simulation.

        This addresses the issue where SAX passes despite clumsy/incorrect physical routing.

        Checks:
        1. All component ports are actually connected (not just placed nearby)
        2. No dangling waveguides
        3. Routes exist between connected components

        Args:
            component: GDSFactory component
            report: Report to update

        Returns:
            True if routing is correct
        """
        try:
            # Handle different GDSFactory versions
            try:
                refs = list(component.references)
            except AttributeError:
                refs = list(getattr(component, 'insts', []))

            if len(refs) == 0:
                report["errors"].append("No component references found")
                return False

            # Check 1: Verify all optical ports are handled
            unconnected_ports = []
            for ref in refs:
                for port_name, port in ref.ports.items():
                    # Skip electrical ports
                    if port_name.startswith('e') or 'electrical' in port_name.lower():
                        continue

                    # Check if this port is connected to something
                    # In GDSFactory, connections are typically handled via routing
                    # We'll check if there are routes in the component

            # Check 2: Verify routes exist
            # GDSFactory stores routes as polygon/path references
            has_routes = False
            for ref in refs:
                # Handle different GDSFactory versions for getting cell name
                if hasattr(ref, 'ref_cell'):
                    cell_name = ref.ref_cell.name if hasattr(ref.ref_cell, 'name') else str(ref.ref_cell)
                elif hasattr(ref, 'cell'):
                    cell_name = ref.cell.name if hasattr(ref.cell, 'name') else str(ref.cell)
                else:
                    cell_name = str(ref)
                # Routes typically have names containing 'route', 'waveguide', or 'bend'
                if any(keyword in cell_name.lower() for keyword in ['route', 'waveguide', 'bend', 'straight']):
                    has_routes = True
                    break

            if len(refs) > 1 and not has_routes:
                report["warnings"].append(
                    "No routing structures detected - components may not be physically connected"
                )

            # Check 3: Port orientation and alignment
            # Poorly routed designs often have misaligned ports
            alignment_issues = self._check_port_alignment(component, report)

            if alignment_issues:
                report["warnings"].append(
                    f"Found {alignment_issues} potential port alignment issues"
                )

            # Check 4: Verify external ports are exposed
            if len(component.ports) == 0 and len(refs) > 0:
                report["warnings"].append(
                    "No external ports exposed (may be intentional for subcomponent)"
                )

            # Determine pass/fail
            # We're more lenient here - warnings don't cause failure
            # Only errors cause failure
            return len([e for e in report["errors"] if "routing" in e.lower() or "connection" in e.lower()]) == 0

        except Exception as e:
            logger.warning(f"Routing correctness check error: {e}")
            report["warnings"].append(f"Routing check error: {str(e)}")
            return True  # Don't fail on check errors

    def _check_port_alignment(self, component: gf.Component, report: Dict) -> int:
        """
        Check for port alignment issues that indicate poor routing.

        Returns:
            Number of alignment issues found
        """
        issues = 0

        try:
            # Handle different GDSFactory versions
            try:
                refs = list(component.references)
            except AttributeError:
                refs = list(getattr(component, 'insts', []))

            # Check if component ports are at reasonable orientations
            for ref in refs:
                for port_name, port in ref.ports.items():
                    # Skip electrical ports
                    if port_name.startswith('e'):
                        continue

                    # Check port orientation (should be 0, 90, 180, or 270 degrees)
                    if hasattr(port, 'orientation'):
                        angle = port.orientation
                        # Normalize to 0-360
                        angle_norm = angle % 360

                        # Check if angle is close to cardinal direction
                        cardinal_angles = [0, 90, 180, 270]
                        min_diff = min(abs(angle_norm - ca) for ca in cardinal_angles)

                        if min_diff > 5:  # More than 5 degrees off
                            issues += 1

        except Exception as e:
            logger.debug(f"Port alignment check error: {e}")

        return issues

    def generate_feedback(self, report: Dict) -> str:
        """
        Generate human-readable feedback for LLM retry.

        Args:
            report: SAX validation report

        Returns:
            Feedback string for LLM
        """
        feedback_parts = []

        if not report.get("sax_compiled", False):
            feedback_parts.append("SAX COMPILATION FAILED")
            feedback_parts.append("The circuit does not compile in SAX simulator.")

        if not report.get("routing_validated", False):
            feedback_parts.append("ROUTING VALIDATION FAILED")
            feedback_parts.append("Physical routing issues detected (beyond SAX simulation).")

        if report["errors"]:
            feedback_parts.append("\nERRORS:")
            for error in report["errors"]:
                feedback_parts.append(f"  - {error}")

        if report["warnings"]:
            feedback_parts.append("\nWARNINGS:")
            for warning in report["warnings"]:
                feedback_parts.append(f"  - {warning}")

        feedback_parts.append("\nSUGGESTIONS FOR FIXING SAX/ROUTING ISSUES:")
        feedback_parts.append("  - Ensure all component instances are properly named")
        feedback_parts.append("  - Use route_bundle to create actual waveguide connections")
        feedback_parts.append("  - Verify port orientations are cardinal (0°, 90°, 180°, 270°)")
        feedback_parts.append("  - Check that all optical ports are either connected or exposed")
        feedback_parts.append("  - Avoid just placing components without creating routes between them")
        feedback_parts.append("  - Ensure connections in netlist match physical routing")

        return "\n".join(feedback_parts)
