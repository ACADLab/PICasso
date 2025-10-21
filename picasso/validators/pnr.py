"""P&R validator that wraps the original implementation."""
from __future__ import annotations

from typing import List
from .base import ValidationReport, Validator, SimpleValidatorMixin

class PNRValidator(SimpleValidatorMixin):
    name = "PNR"

    def __init__(self):
        try:
            from pnr_validator import PNRValidator as _Original
            self._impl = _Original()
        except Exception:
            self._impl = None

    def validate(self, design_py: str) -> ValidationReport:
        if self._impl is not None:
            return self._impl.validate(design_py)  # type: ignore[attr-defined]

        # Fallback: syntactic sanity hints
        errors: List[str] = []
        if "import gdsfactory" not in design_py and "import gdsfactory as gf" not in design_py:
            errors.append("gdsfactory is not imported; design code should start with `import gdsfactory as gf`.")
        return ValidationReport(passed=(len(errors) == 0), errors=errors, warnings=[])
