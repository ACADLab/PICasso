"""Optimizers Module."""

from .device_optimizer import DeviceOptimizer

try:
    from .netlist_optimize import Tunable, optimize_netlist, svd_bound
except ImportError:  # optional SciPy / SAX surface
    Tunable = None  # type: ignore[misc, assignment]
    optimize_netlist = None  # type: ignore[misc, assignment]
    svd_bound = None  # type: ignore[misc, assignment]

__all__ = ["DeviceOptimizer", "Tunable", "optimize_netlist", "svd_bound"]


