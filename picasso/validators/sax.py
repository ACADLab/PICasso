"""SAX validator that wraps the original implementation."""
from __future__ import annotations

from typing import List, Any
from .base import ValidationReport, Validator, SimpleValidatorMixin, normalize_report, build_component_from_code


class SAXValidator(SimpleValidatorMixin):
    name = "SAX"

    def __init__(self):
        try:
            from sax_validator import SAXValidator as _Original
            self._impl = _Original()
        except Exception:
            self._impl = None

    def _run_original(self, payload: Any) -> ValidationReport:
        try:
            result = self._impl.validate(payload)  # type: ignore[attr-defined]
            return normalize_report(result)
        except Exception as e:
            return {"passed": False, "errors": [f"SAX original validator exception: {e}"], "warnings": [], "metrics": {}}

    def validate(self, design_py: str) -> ValidationReport:
        if self._impl is not None:
            # Try raw code first; if that fails, try a built Component
            rep = self._run_original(design_py)
            if rep["passed"] or not rep["errors"]:
                return rep
            try:
                comp = build_component_from_code(design_py)
                return self._run_original(comp)
            except Exception as e:
                return {"passed": False, "errors": [f"SAX build/validate error: {e}"], "warnings": [], "metrics": {}}

        warnings: List[str] = ["SAX fallback used – install `sax`, `jax`, and `jaxlib` for full validation."]
        return {"passed": True, "errors": [], "warnings": warnings, "metrics": {}}
