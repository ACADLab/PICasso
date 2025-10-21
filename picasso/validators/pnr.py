"""P&R validator that wraps the original implementation."""
from __future__ import annotations

from typing import List, Any
from .base import (
    ValidationReport,
    Validator,
    SimpleValidatorMixin,
    normalize_report,
    build_component_from_code,
)

class PNRValidator(SimpleValidatorMixin):
    name = "PNR"

    def __init__(self):
        try:
            from pnr_validator import PNRValidator as _Original
            self._impl = _Original()
        except Exception:
            self._impl = None

    def _run_original(self, comp: Any) -> ValidationReport:
        """Call the original validator on a gf.Component and normalize the result."""
        try:
            result = self._impl.validate(comp)  # type: ignore[attr-defined]
            return normalize_report(result)
        except Exception as e:
            return {
                "passed": False,
                "errors": [f"PNR original validator exception: {e}"],
                "warnings": [],
                "metrics": {},
            }

    def validate(self, design_py: str) -> ValidationReport:
        # If the original validator exists, we *require* a built gf.Component.
        if self._impl is not None:
            try:
                comp = build_component_from_code(design_py)
            except Exception as e:
                # Fail fast with a clear message instead of ever passing a string to the original
                return {
                    "passed": False,
                    "errors": [f"PNR build() error: {e}"],
                    "warnings": [],
                    "metrics": {},
                }
            return self._run_original(comp)

        # Fallback (no original): syntactic sanity hints
        errors: List[str] = []
        if "import gdsfactory" not in design_py and "import gdsfactory as gf" not in design_py:
            errors.append("gdsfactory is not imported; design code should start with `import gdsfactory as gf`.")
        return {"passed": (len(errors) == 0), "errors": errors, "warnings": [], "metrics": {}}
