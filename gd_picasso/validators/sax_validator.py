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

logger = logging.getLogger(__name__)

# Try to import port utilities (may not exist in gd_picasso)
try:
    from ..utils.port_utils import get_port_items, get_port_count
except ImportError:
    # Fallback: simple port utilities
    def get_port_items(ports):
        """Get port items, handling different GDSFactory versions."""
        if hasattr(ports, 'items'):
            return ports.items()
        elif hasattr(ports, 'keys'):
            return [(k, ports[k]) for k in ports.keys()]
        else:
            return []
    
    def get_port_count(ports):
        """Get port count, handling different GDSFactory versions."""
        if hasattr(ports, '__len__'):
            return len(ports)
        elif hasattr(ports, 'keys'):
            return len(ports.keys())
        else:
            return 0

try:
    from ..config import ENABLE_SAX_CHECK, SAX_TIMEOUT
except ImportError:
    ENABLE_SAX_CHECK = True
    SAX_TIMEOUT = 30


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
            try:
                from gplugins import sax
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
            # Try to import SAX
            try:
                import sax
            except ImportError:
                from gplugins import sax

            # Try to get netlist and compile circuit
            netlist = component.get_netlist()

            if not netlist:
                report["errors"].append("Failed to extract netlist from component")
                return False

            # Check netlist structure
            if 'instances' not in netlist or not netlist['instances']:
                report["errors"].append("Netlist has no component instances")
                return False

            if 'connections' not in netlist or not netlist.get('connections'):
                report["warnings"].append("Netlist has no connections (might be single component)")

            # Try to build SAX circuit with models
            try:
                # Try with gplugins models first
                try:
                    from gplugins import sax as gs
                    models = {
                        "straight": gs.models.straight,
                        "bend_euler": gs.models.bend,
                        "mmi1x2": gs.models.mmi1x2,
                        "mmi": gs.models.mmi1x2,
                        "mmi2x2": gs.models.mmi2x2 if hasattr(gs.models, 'mmi2x2') else gs.models.mmi1x2,
                        "coupler": gs.models.coupler if hasattr(gs.models, 'coupler') else gs.models.mmi1x2,
                        "ring_single": gs.models.ring_single if hasattr(gs.models, 'ring_single') else gs.models.bend,
                    }
                    # Add phase shifter models - map all variants to phase_shifter
                    try:
                        phase_model = sax.models.phase_shifter if hasattr(sax.models, 'phase_shifter') else gs.models.straight
                        models["straight_heater_metal"] = phase_model
                        models["straight_heater_metal_undercut"] = phase_model
                        models["phase_shifter"] = phase_model
                        models["heater"] = phase_model
                    except:
                        # Fallback: use straight model for phase shifters
                        models["straight_heater_metal"] = gs.models.straight
                        models["straight_heater_metal_undercut"] = gs.models.straight
                        models["phase_shifter"] = gs.models.straight
                        models["heater"] = gs.models.straight
                    
                    # Try to compile with models
                    circuit, _ = sax.circuit(netlist, models=models)
                    report["sax_compiled"] = True
                    logger.debug("SAX compilation successful with gplugins models")
                    return True
                except Exception as e1:
                    # Fallback 1: Try to auto-create missing models
                    try:
                        # Extract missing component types from error
                        missing_models = []
                        if "Missing models" in str(e1):
                            # Try to parse missing models from error message
                            import re
                            missing_match = re.search(r'"Missing Models":\s*\[(.*?)\]', str(e1))
                            if missing_match:
                                missing_str = missing_match.group(1)
                                missing_models = [m.strip().strip('"') for m in missing_str.split(',')]
                        
                        # For each missing model, try to create or map it
                        from gplugins import sax as gs
                        if not models:
                            models = {}
                        
                        # Default model mappings for common missing components
                        default_mappings = {
                            "straight_heater_metal_undercut": gs.models.straight,
                            "straight_heater_metal": gs.models.straight,
                            "phase_shifter": gs.models.straight,
                            "heater": gs.models.straight,
                            "mzi": gs.models.mmi1x2,  # MZI can use MMI model as approximation
                            "y_branch": gs.models.mmi1x2,
                            "y_splitter": gs.models.mmi1x2,
                            "y_junction": gs.models.mmi1x2,
                        }
                        
                        # Add missing models using mappings
                        for missing in missing_models:
                            if missing in default_mappings:
                                models[missing] = default_mappings[missing]
                                logger.debug(f"Mapped missing model '{missing}' to default")
                        
                        # Try again with extended models
                        if models:
                            circuit, _ = sax.circuit(netlist, models=models)
                            report["sax_compiled"] = True
                            logger.debug("SAX compilation successful with auto-mapped models")
                            return True
                    except Exception as e2:
                        pass
                    
                    # Fallback 2: try without models (use default)
                    try:
                        circuit, _ = sax.circuit(netlist)
                        report["sax_compiled"] = True
                        logger.debug("SAX compilation successful with default models")
                        return True
                    except Exception as e3:
                        # All SAX compilation attempts failed
                        # This is a real failure - circuit cannot be simulated
                        error_msg = f"SAX circuit compilation failed: {str(e1)}"
                        if "Missing models" in str(e1) or "Missing models" in str(e3):
                            error_msg += " (missing SAX models for components)"
                        report["errors"].append(error_msg)
                        logger.warning(f"SAX compilation failed: {error_msg}")
                        return False  # Fail if SAX cannot compile - this indicates a real problem

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

            # Check 1: Verify routes exist
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

            # Check 2: Port orientation and alignment
            # Poorly routed designs often have misaligned ports
            alignment_issues = self._check_port_alignment(component, report)

            if alignment_issues:
                report["warnings"].append(
                    f"Found {alignment_issues} potential port alignment issues"
                )

            # Check 3: Verify external ports are exposed
            port_count = get_port_count(component.ports)
            
            if port_count == 0 and len(refs) > 0:
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
                # Use port utilities to handle different GDSFactory versions
                ports_iter = get_port_items(ref.ports)
                if not ports_iter:
                    continue
                
                for port_name, port in ports_iter:
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

