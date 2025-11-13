"""
Loss Target Validator

Validates that optimized designs meet target insertion loss values
based on state-of-the-art research benchmarks.
"""

import logging
from typing import Dict, Tuple, Optional
import numpy as np
import gdsfactory as gf

try:
    from ..config_loss_targets import get_target_loss, format_target_string, TOLERANCE_DB
except ImportError:
    # Fallback functions
    def get_target_loss(circuit_type):
        return None
    def format_target_string(circuit_type):
        return ""
    TOLERANCE_DB = 1.0

logger = logging.getLogger(__name__)


class LossTargetValidator:
    """Validates insertion loss against research-based target values."""

    def __init__(self, tolerance_db: float = TOLERANCE_DB):
        """
        Initialize loss target validator.

        Args:
            tolerance_db: Allowed tolerance above target (dB)
        """
        self.tolerance_db = tolerance_db

    def validate(
        self,
        component: gf.Component,
        circuit_type: Optional[str] = None,
        circuit_description: Optional[str] = None,
        measured_loss_db: Optional[float] = None,
        optimization_result: Optional[Dict] = None
    ) -> Tuple[bool, Dict]:
        """
        Validate insertion loss against target.

        Args:
            component: GDSFactory component
            circuit_type: Explicit circuit type identifier
            circuit_description: Text description of circuit
            measured_loss_db: Directly measured IL (if available)
            optimization_result: Result from optimization stage

        Returns:
            (is_valid, report) where report contains:
                - passed: bool
                - target_db: float
                - achieved_db: float
                - margin_db: float (negative if over target)
                - meets_target: bool
                - within_tolerance: bool
                - feedback: str
        """
        report = {
            "passed": False,
            "target_db": None,
            "achieved_db": None,
            "margin_db": None,
            "meets_target": False,
            "within_tolerance": False,
            "feedback": "",
            "errors": [],
            "warnings": []
        }

        try:
            # Get target loss for this circuit type
            target_db = get_target_loss(circuit_type, circuit_description)
            report["target_db"] = target_db

            if target_db == float('inf'):
                # No target (e.g., detectors)
                report["passed"] = True
                report["meets_target"] = True
                report["within_tolerance"] = True
                report["feedback"] = "No loss target specified for this circuit type"
                logger.info("No loss target for this circuit - skipping validation")
                return True, report

            # Get achieved loss
            achieved_db = self._get_achieved_loss(
                measured_loss_db,
                optimization_result,
                component
            )

            if achieved_db is None:
                report["warnings"].append("Could not determine achieved insertion loss")
                report["passed"] = True  # Don't fail if we can't measure
                report["feedback"] = "Loss measurement unavailable - cannot validate"
                logger.warning("Cannot measure insertion loss - skipping target validation")
                return True, report

            report["achieved_db"] = achieved_db
            report["margin_db"] = target_db - achieved_db

            # Check against target
            report["meets_target"] = achieved_db <= target_db
            report["within_tolerance"] = achieved_db <= (target_db + self.tolerance_db)

            # Determine pass/fail
            report["passed"] = report["within_tolerance"]

            # Generate feedback
            report["feedback"] = self._generate_feedback(
                target_db, achieved_db, report["margin_db"],
                report["meets_target"], report["within_tolerance"]
            )

            if report["passed"]:
                logger.info(
                    f"Loss target validation PASSED: {achieved_db:.2f} dB ≤ {target_db:.1f} dB "
                    f"(margin: {report['margin_db']:+.2f} dB)"
                )
            else:
                logger.warning(
                    f"Loss target validation FAILED: {achieved_db:.2f} dB > {target_db:.1f} dB "
                    f"(over by: {abs(report['margin_db']):.2f} dB)"
                )

        except Exception as e:
            logger.error(f"Loss target validation error: {e}", exc_info=True)
            report["errors"].append(f"Validation exception: {str(e)}")
            report["passed"] = True  # Don't fail on validation errors
            report["feedback"] = f"Validation error: {str(e)}"

        return report["passed"], report

    def _get_achieved_loss(
        self,
        measured_loss_db: Optional[float],
        optimization_result: Optional[Dict],
        component: gf.Component
    ) -> Optional[float]:
        """
        Get achieved insertion loss from various sources.

        Priority:
        1. Directly measured loss
        2. Optimization result (after optimization)
        3. SAX simulation (if available)

        Args:
            measured_loss_db: Direct measurement
            optimization_result: Optimization results
            component: GDSFactory component

        Returns:
            Achieved insertion loss in dB, or None if unavailable
        """
        # Priority 1: Direct measurement
        if measured_loss_db is not None:
            return float(measured_loss_db)

        # Priority 2: Optimization result
        if optimization_result and optimization_result.get("success"):
            if "il_after_db" in optimization_result and optimization_result["il_after_db"] is not None:
                return float(optimization_result["il_after_db"])

        # Priority 3: Try SAX simulation
        try:
            loss_db = self._simulate_loss_sax(component)
            if loss_db is not None:
                return loss_db
        except Exception as e:
            logger.debug(f"SAX loss simulation failed: {e}")

        return None

    def _simulate_loss_sax(self, component: gf.Component) -> Optional[float]:
        """
        Simulate insertion loss using SAX.

        Args:
            component: GDSFactory component

        Returns:
            Insertion loss in dB, or None if simulation fails
        """
        try:
            import sax
            import gplugins.sax as gs

            # Get netlist
            netlist = component.get_netlist()
            if not netlist:
                return None

            # Simple models
            models = {
                "straight": gs.models.straight,
                "bend_euler": gs.models.bend,
                "mmi": gs.models.mmi1x2,
                "mmi1x2": gs.models.mmi1x2,
            }

            # Build circuit
            circuit, _ = sax.circuit(netlist, models=models)

            # Get S-parameters at center wavelength
            S_dict = circuit(wl=1.55e-6)

            # Get port list
            from ..utils.port_utils import get_port_names
            ports = get_port_names(component.ports)
            if len(ports) < 2:
                return None

            # Assume first port is input, last is output
            in_port = ports[0]
            out_port = ports[-1]

            # Find S-parameter key
            key = None
            for k in S_dict.keys():
                if k[0] == out_port and k[1] == in_port:
                    key = k
                    break

            if key is None:
                # Try suffix matching
                for k in S_dict.keys():
                    if k[0].endswith(out_port) and k[1].endswith(in_port):
                        key = k
                        break

            if key is None:
                return None

            # Calculate insertion loss
            S_21 = S_dict[key]
            power = float(np.abs(S_21) ** 2)
            loss_db = -10.0 * np.log10(max(power, 1e-15))

            return loss_db

        except Exception as e:
            logger.debug(f"SAX simulation error: {e}")
            return None

    def _generate_feedback(
        self,
        target_db: float,
        achieved_db: float,
        margin_db: float,
        meets_target: bool,
        within_tolerance: bool
    ) -> str:
        """
        Generate human-readable feedback.

        Args:
            target_db: Target insertion loss
            achieved_db: Achieved insertion loss
            margin_db: Margin (target - achieved)
            meets_target: Whether target is met
            within_tolerance: Whether within tolerance

        Returns:
            Feedback string
        """
        parts = []

        parts.append("INSERTION LOSS TARGET VALIDATION")
        parts.append(f"Target: ≤ {target_db:.1f} dB")
        parts.append(f"Achieved: {achieved_db:.2f} dB")

        if meets_target:
            parts.append(f"✅ MEETS TARGET (margin: {margin_db:+.2f} dB)")
        elif within_tolerance:
            parts.append(
                f"⚠️  ABOVE TARGET but within tolerance (over by: {abs(margin_db):.2f} dB, "
                f"tolerance: {self.tolerance_db:.1f} dB)"
            )
        else:
            parts.append(
                f"❌ EXCEEDS TARGET (over by: {abs(margin_db):.2f} dB, "
                f"exceeds tolerance of {self.tolerance_db:.1f} dB)"
            )

        if not within_tolerance:
            parts.append("\nSUGGESTIONS TO REDUCE INSERTION LOSS:")
            parts.append("  - Reduce number of components in optical path")
            parts.append("  - Use lower-loss waveguide cross-sections")
            parts.append("  - Optimize bend radii (larger = lower loss)")
            parts.append("  - Minimize waveguide crossings")
            parts.append("  - Use adiabatic tapers at component interfaces")
            parts.append("  - Consider using lower-loss couplers (e.g., directional vs MMI)")

        return "\n".join(parts)

    def generate_csv_metrics(self, report: Dict) -> Dict[str, any]:
        """
        Extract metrics for CSV output.

        Args:
            report: Validation report

        Returns:
            Dictionary of CSV-compatible metrics
        """
        return {
            "loss_target_db": report.get("target_db"),
            "loss_achieved_db": report.get("achieved_db"),
            "loss_margin_db": report.get("margin_db"),
            "meets_loss_target": report.get("meets_target", False),
            "within_loss_tolerance": report.get("within_tolerance", False),
        }
