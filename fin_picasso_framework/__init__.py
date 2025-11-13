"""PICasso Framework - Enhanced photonic integrated circuit generation framework."""

# Lazy imports to avoid requiring gdsfactory at import time
__all__ = ['PICassoFramework']

def __getattr__(name):
    """Lazy import for main framework class."""
    if name == "PICassoFramework":
        from .core.framework import PICassoFramework
        return PICassoFramework
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

