"""Custom exceptions used across PICasso."""
from typing import Optional


class PICassoError(Exception):
    """Base class for all custom PICasso errors."""


class ConfigError(PICassoError):
    """Configuration or environment variable is missing or invalid."""


class ClientError(PICassoError):
    """Downstream model API failed or returned an invalid response."""


class ValidationError(PICassoError):
    """Raised when a validator fails critically (not just a soft failure)."""


class GenerationFailed(PICassoError):
    """Raised when generation exhausts all retries without passing validation."""


class NotInstalledError(PICassoError):
    """Raised when an optional dependency is required but not installed."""
    def __init__(self, package: str, extra: Optional[str] = None):
        msg = f"Optional dependency '{package}' is required but not installed."
        if extra:
            msg += f" {extra}"
        super().__init__(msg)
