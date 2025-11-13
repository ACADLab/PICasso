"""Core Module."""

# Lazy imports - import only when needed
__all__ = ['FrameworkPipeline', 'PICassoFramework']

def __getattr__(name):
    """Lazy import for core classes."""
    if name == "FrameworkPipeline":
        from .pipeline import FrameworkPipeline
        return FrameworkPipeline
    elif name == "PICassoFramework":
        from .framework import PICassoFramework
        return PICassoFramework
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

