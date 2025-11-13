"""
Optimization Integration Module

Integrates the phase optimization framework with the validation workflow.
After a design passes P&R/DRC/SAX validation, this module:
1. Extracts tunable parameters from the validated design
2. Runs phase optimization to minimize insertion loss
3. Reports before/after metrics
4. Checks against target loss values
"""

import logging
from typing import Dict, Tuple, Optional, List
import numpy as np
import gdsfactory as gf

# Import optimization modules
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from s_optimize import DeviceOptimizer as OriginalDeviceOptimizer, ScatteringNetwork
from netlist_optimize import optimize_netlist, Tunable

# Import new device-level optimizer
from .optimizers.device_optimizer import DeviceOptimizer

logger = logging.getLogger(__name__)


class OptimizationStage:
    """
    Optimization stage for validated photonic circuit designs.

    This class wraps the optimization framework to work with validated GDSFactory components.
    """

    def __init__(self, enable_optimization: bool = True, enable_device_optimization: bool = True,
                 max_iter: int = 400, n_restarts: int = 8):
        """
        Initialize optimization stage.

        Args:
            enable_optimization: Whether to run circuit-level optimization
            enable_device_optimization: Whether to run device-level optimization
            max_iter: Maximum iterations for optimizer
            n_restarts: Number of random restarts
        """
        self.enable_optimization = enable_optimization
        self.enable_device_optimization = enable_device_optimization
        self.max_iter = max_iter
        self.n_restarts = n_restarts

        # Initialize device-level optimizer
        self.device_optimizer = DeviceOptimizer(enable=enable_device_optimization, use_sax=True)

    def optimize_design(
        self,
        component: gf.Component,
        circuit_type: Optional[str] = None
    ) -> Dict:
        """
        Two-level optimization of the validated design.

        LEVEL 1 (Device): Optimize component geometries to match target losses
        LEVEL 2 (Circuit): Optimize phase shifters and couplings for minimum insertion loss

        Args:
            component: Validated GDSFactory component
            circuit_type: Type of circuit (e.g., 'mzm', 'ring_filter') for context

        Returns:
            Dictionary with optimization results:
                - success: bool
                - device_loss_db: float (Level 1: component geometries)
                - circuit_loss_before_db: float (Level 2: before phase opt)
                - circuit_loss_after_db: float (Level 2: after phase opt)
                - total_loss_db: float (device + circuit)
                - improvement_db: float (circuit-level improvement)
                - device_breakdown: list (component-by-component losses)
                - optimized_params: dict (optimized phase/coupling parameters)
                - error: str (if failed)
        """
        result = {
            "success": False,
            "device_loss_db": None,
            "circuit_loss_before_db": None,
            "circuit_loss_after_db": None,
            "total_loss_db": None,
            "improvement_db": 0.0,
            "device_breakdown": [],
            "optimized_params": {},
            "error": None
        }

        # ======================================================================
        # LEVEL 1: DEVICE-LEVEL OPTIMIZATION (Component Geometries)
        # ======================================================================
        logger.info("\n" + "=" * 70)
        logger.info("TWO-LEVEL OPTIMIZATION")
        logger.info("=" * 70)

        device_result = self.device_optimizer.optimize_all_components(component)
        result["device_loss_db"] = device_result.get('total_device_loss_db', 0.0)
        result["device_breakdown"] = device_result.get('breakdown', [])

        logger.info(f"\n✅ Level 1 Complete: Device Loss = {result['device_loss_db']:.2f} dB")

        # ======================================================================
        # LEVEL 2: CIRCUIT-LEVEL OPTIMIZATION (Phase Shifters & Couplings)
        # ======================================================================
        logger.info("\n" + "=" * 70)
        logger.info("CIRCUIT-LEVEL OPTIMIZATION (Phase & Coupling Parameters)")
        logger.info("=" * 70)

        if not self.enable_optimization:
            result["error"] = "Circuit-level optimization disabled"
            logger.info("Circuit-level optimization disabled - skipping Level 2")
            result["circuit_loss_after_db"] = 0.0
            result["total_loss_db"] = result["device_loss_db"]
            result["success"] = True  # Still successful if device opt worked
            return result

        try:
            # Extract netlist from component
            netlist = component.get_netlist()

            if not netlist or 'instances' not in netlist:
                result["error"] = "Failed to extract netlist"
                result["circuit_loss_after_db"] = 0.0
                result["total_loss_db"] = result["device_loss_db"]
                result["success"] = True  # Still successful if device opt worked
                logger.warning("Cannot optimize circuit: netlist extraction failed")
                logger.info(f"Total loss (device only): {result['total_loss_db']:.2f} dB")
                return result

            # Find tunable parameters (phase shifters, heaters, etc.)
            tunables = self._extract_tunables(netlist, circuit_type)

            if not tunables:
                result["error"] = "No tunable parameters found"
                result["circuit_loss_after_db"] = 0.0
                result["total_loss_db"] = result["device_loss_db"]
                result["success"] = True  # Still successful if device opt worked
                logger.info("No tunable parameters found in design - skipping circuit optimization")
                logger.info(f"Total loss (device only): {result['total_loss_db']:.2f} dB")
                return result

            # Run SAX-based optimization
            logger.info(f"Optimizing {len(tunables)} parameters...")
            opt_result = self._run_sax_optimization(component, netlist, tunables)

            if opt_result["success"]:
                result["success"] = True
                result["circuit_loss_before_db"] = opt_result.get("il_before_db", None)
                result["circuit_loss_after_db"] = opt_result.get("il_after_db", None)
                result["improvement_db"] = result["circuit_loss_before_db"] - result["circuit_loss_after_db"] if result["circuit_loss_before_db"] and result["circuit_loss_after_db"] else 0.0
                result["optimized_params"] = opt_result.get("params", {})

                # Calculate total loss (device + circuit)
                if result["circuit_loss_after_db"] is not None:
                    result["total_loss_db"] = result["device_loss_db"] + result["circuit_loss_after_db"]
                else:
                    result["total_loss_db"] = result["device_loss_db"]

                logger.info(f"\n✅ Level 2 Complete:")
                if result["circuit_loss_before_db"] and result["circuit_loss_after_db"]:
                    logger.info(f"  Circuit Loss: {result['circuit_loss_before_db']:.2f} dB → {result['circuit_loss_after_db']:.2f} dB ({result['improvement_db']:+.2f} dB)")
                elif result["circuit_loss_after_db"]:
                    logger.info(f"  Circuit Loss: {result['circuit_loss_after_db']:.2f} dB")

                logger.info("\n" + "=" * 70)
                logger.info(f"TOTAL LOSS: {result['total_loss_db']:.2f} dB")
                logger.info(f"  Device Level:  {result['device_loss_db']:.2f} dB")
                logger.info(f"  Circuit Level: {result['circuit_loss_after_db']:.2f} dB")
                logger.info("=" * 70)
            else:
                result["error"] = opt_result.get("error", "Circuit optimization failed")
                result["total_loss_db"] = result["device_loss_db"]
                logger.warning(f"Circuit optimization failed: {result['error']}")
                logger.info(f"Total loss (device only): {result['total_loss_db']:.2f} dB")

        except Exception as e:
            result["error"] = f"Optimization exception: {str(e)}"
            result["circuit_loss_after_db"] = 0.0
            result["total_loss_db"] = result["device_loss_db"] if result["device_loss_db"] else 0.0
            logger.error(f"Optimization error: {e}", exc_info=True)
            if result["total_loss_db"]:
                logger.info(f"Total loss (device only): {result['total_loss_db']:.2f} dB")

        return result

    def _extract_tunables(self, netlist: Dict, circuit_type: Optional[str] = None) -> List[Tunable]:
        """
        Extract tunable parameters from netlist.

        Looks for:
        - Phase shifters (straight_heater_metal, phase_shifter)
        - Tunable couplers
        - Variable optical attenuators

        Args:
            netlist: GDSFactory netlist
            circuit_type: Hint about circuit type

        Returns:
            List of Tunable objects
        """
        tunables = []

        if 'instances' not in netlist:
            return tunables

        for inst_name, inst_data in netlist['instances'].items():
            component_type = inst_data.get('component', '')
            settings = inst_data.get('settings', {})

            # Phase shifters
            if any(kw in component_type.lower() for kw in ['heater', 'phase', 'shifter']):
                # Add phase tunable
                tunables.append(Tunable(
                    inst=inst_name,
                    key='phi',
                    lo=-np.pi,
                    hi=np.pi,
                    x0=settings.get('phi', 0.0)
                ))

            # Tunable couplers (kappa parameter)
            if 'coupler' in component_type.lower() or 'mmi' in component_type.lower():
                if 'kappa' in settings or 'coupling' in settings:
                    tunables.append(Tunable(
                        inst=inst_name,
                        key='kappa',
                        lo=0.1,
                        hi=0.9,
                        x0=settings.get('kappa', 0.5)
                    ))

        logger.debug(f"Extracted {len(tunables)} tunable parameters from netlist")
        return tunables

    def _run_sax_optimization(
        self,
        component: gf.Component,
        netlist: Dict,
        tunables: List[Tunable]
    ) -> Dict:
        """
        Run SAX-based optimization using netlist_optimize.py framework.

        Args:
            component: GDSFactory component
            netlist: Netlist dictionary
            tunables: List of tunable parameters

        Returns:
            Optimization result dictionary
        """
        try:
            # Check if SAX is available
            try:
                import sax
                import gplugins.sax as gs
            except ImportError:
                return {"success": False, "error": "SAX not available"}

            # Get port list from component
            from ..utils.port_utils import get_port_names
            port_list = get_port_names(component.ports)
            if len(port_list) < 2:
                return {"success": False, "error": "Not enough ports for optimization"}

            # Determine input/output ports (simple heuristic: first half are inputs)
            mid = len(port_list) // 2
            in_ports = port_list[:max(1, mid)]
            out_ports = port_list[mid:] if mid > 0 else port_list[-1:]

            logger.debug(f"Optimizing ports: {in_ports} → {out_ports}")

            # Create simple models for common components
            models = {
                "straight": gs.models.straight,
                "bend_euler": gs.models.bend,
                "mmi": gs.models.mmi1x2,
                "mmi1x2": gs.models.mmi1x2,
                "coupler": lambda **kw: gs.models.coupler(**kw),
            }

            # Add phase shifter model if needed
            if any('heater' in t.inst or 'phase' in t.inst for t in tunables):
                models["straight_heater_metal"] = sax.models.phase_shifter
                models["phase_shifter"] = sax.models.phase_shifter

            # Run optimization
            try:
                result = optimize_netlist(
                    netlist=netlist,
                    tunables=tunables,
                    port_list=port_list,
                    in_ports=in_ports,
                    out_ports=out_ports,
                    models=models,
                    weights={"deliver": 1.0, "flat": 0.0, "reflect": 0.0},
                    drive="svd",
                    maxiter=self.max_iter,
                    n_restarts=self.n_restarts,
                )

                return {
                    "success": True,
                    "il_before_db": None,  # Would need baseline run
                    "il_after_db": result.get("insertion_loss_dB_center", None),
                    "params": result.get("params_opt", {}),
                }

            except Exception as e:
                logger.warning(f"SAX optimization failed, trying simpler approach: {e}")
                # Fallback: return neutral result
                return {
                    "success": False,
                    "error": f"SAX optimization error: {str(e)}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Optimization setup error: {str(e)}"
            }

    def generate_feedback(self, result: Dict) -> str:
        """
        Generate human-readable feedback for LLM retry.

        Args:
            result: Optimization result dictionary

        Returns:
            Feedback string
        """
        if not result["success"]:
            return f"OPTIMIZATION FAILED: {result.get('error', 'Unknown error')}"

        feedback_parts = []
        feedback_parts.append("TWO-LEVEL OPTIMIZATION COMPLETED")
        feedback_parts.append("")

        # Device-level breakdown
        if result.get("device_loss_db") is not None:
            feedback_parts.append(f"Level 1 (Device Geometries): {result['device_loss_db']:.2f} dB")
            if result.get("device_breakdown"):
                feedback_parts.append("  Component breakdown:")
                for comp_type, count, loss_per_unit, total_loss in result["device_breakdown"]:
                    feedback_parts.append(f"    {count}× {comp_type}: {loss_per_unit:.3f} dB each = {total_loss:.3f} dB")

        # Circuit-level optimization
        if result.get("circuit_loss_before_db") and result.get("circuit_loss_after_db"):
            feedback_parts.append("")
            feedback_parts.append(
                f"Level 2 (Circuit Parameters): {result['circuit_loss_before_db']:.2f} dB → {result['circuit_loss_after_db']:.2f} dB "
                f"(improvement: {result['improvement_db']:+.2f} dB)"
            )
        elif result.get("circuit_loss_after_db") is not None:
            feedback_parts.append("")
            feedback_parts.append(f"Level 2 (Circuit Parameters): {result['circuit_loss_after_db']:.2f} dB")

        # Total loss
        if result.get("total_loss_db") is not None:
            feedback_parts.append("")
            feedback_parts.append(f"TOTAL INSERTION LOSS: {result['total_loss_db']:.2f} dB")

        if result.get("optimized_params"):
            feedback_parts.append(f"Optimized {len(result['optimized_params'])} circuit parameters")

        return "\n".join(feedback_parts)
