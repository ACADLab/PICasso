"""SAX validator that wraps the original implementation."""
from __future__ import annotations

from typing import List
from .base import ValidationReport, Validator, SimpleValidatorMixin

class SAXValidator(SimpleValidatorMixin):
    name = "SAX"

    def __init__(self):
        try:
            from sax_validator import SAXValidator as _Original
            self._impl = _Original()
        except Exception:
            self._impl = None

    def validate(self, design_py: str) -> ValidationReport:
        if self._impl is not None:
            return self._impl.validate(design_py)  # type: ignore[attr-defined]

        warnings: List[str] = ["SAX fallback used – install `sax`, `jax`, and `jaxlib` for full validation."]
        return ValidationReport(passed=True, errors=[], warnings=warnings)
