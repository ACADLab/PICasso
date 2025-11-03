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

from s_optimize import DeviceOptimizer, ScatteringNetwork
from netlist_optimize import optimize_netlist, Tunable

logger = logging.getLogger(__name__)


class OptimizationStage:
    """
    Optimization stage for validated photonic circuit designs.

    This class wraps the optimization framework to work with validated GDSFactory components.
    """

    def __init__(self, enable_optimization: bool = True, max_iter: int = 400, n_restarts: int = 8):
        """
        Initialize optimization stage.

        Args:
            enable_optimization: Whether to run optimization
            max_iter: Maximum iterations for optimizer
            n_restarts: Number of random restarts
        """
        self.enable_optimization = enable_optimization
        self.max_iter = max_iter
        self.n_restarts = n_restarts

    def optimize_design(
        self,
        component: gf.Component,
        circuit_type: Optional[str] = None
    ) -> Dict:
        """
        Optimize phase shifters in the validated design.

        Args:
            component: Validated GDSFactory component
            circuit_type: Type of circuit (e.g., 'mzm', 'ring_filter') for context

        Returns:
            Dictionary with optimization results:
                - success: bool
                - il_before_db: float (insertion loss before optimization)
                - il_after_db: float (insertion loss after optimization)
                - improvement_db: float (reduction in insertion loss)
                - optimized_params: dict (optimized parameter values)
                - error: str (if failed)
        """
        result = {
            "success": False,
            "il_before_db": None,
            "il_after_db": None,
            "improvement_db": 0.0,
            "optimized_params": {},
            "error": None
        }

        if not self.enable_optimization:
            result["error"] = "Optimization disabled"
            logger.info("Optimization disabled - skipping")
            return result

        try:
            # Extract netlist from component
            netlist = component.get_netlist()

            if not netlist or 'instances' not in netlist:
                result["error"] = "Failed to extract netlist"
                logger.warning("Cannot optimize: netlist extraction failed")
                return result

            # Find tunable parameters (phase shifters, heaters, etc.)
            tunables = self._extract_tunables(netlist, circuit_type)

            if not tunables:
                result["error"] = "No tunable parameters found"
                logger.info("No tunable parameters found in design - skipping optimization")
                return result

            # Run SAX-based optimization
            logger.info(f"Optimizing {len(tunables)} parameters...")
            opt_result = self._run_sax_optimization(component, netlist, tunables)

            if opt_result["success"]:
                result["success"] = True
                result["il_before_db"] = opt_result.get("il_before_db", None)
                result["il_after_db"] = opt_result.get("il_after_db", None)
                result["improvement_db"] = result["il_before_db"] - result["il_after_db"] if result["il_before_db"] and result["il_after_db"] else 0.0
                result["optimized_params"] = opt_result.get("params", {})

                logger.info(
                    f"Optimization successful: IL improved from {result['il_before_db']:.2f} dB "
                    f"to {result['il_after_db']:.2f} dB ({result['improvement_db']:+.2f} dB)"
                )
            else:
                result["error"] = opt_result.get("error", "Optimization failed")
                logger.warning(f"Optimization failed: {result['error']}")

        except Exception as e:
            result["error"] = f"Optimization exception: {str(e)}"
            logger.error(f"Optimization error: {e}", exc_info=True)

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
            port_list = list(component.ports.keys())
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
        feedback_parts.append("OPTIMIZATION COMPLETED")

        if result["il_before_db"] and result["il_after_db"]:
            feedback_parts.append(
                f"Insertion Loss: {result['il_before_db']:.2f} dB → {result['il_after_db']:.2f} dB "
                f"(improvement: {result['improvement_db']:+.2f} dB)"
            )
        elif result["il_after_db"]:
            feedback_parts.append(f"Final Insertion Loss: {result['il_after_db']:.2f} dB")

        if result["optimized_params"]:
            feedback_parts.append(f"Optimized {len(result['optimized_params'])} parameters")

        return "\n".join(feedback_parts)
