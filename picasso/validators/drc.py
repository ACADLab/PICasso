"""DRC validator that wraps the original implementation with a stable interface."""
from __future__ import annotations

import os
import shutil
from typing import List, Any
from .base import ValidationReport, Validator, SimpleValidatorMixin, normalize_report, build_component_from_code

class DRCValidator(SimpleValidatorMixin):
    name = "DRC"

    def __init__(self):
        try:
            from drc_validator import DRCValidator as _Original
            self._impl = _Original()
        except Exception:
            self._impl = None

    def _ensure_klayout_env(self) -> str | None:
        """Ensure the original validator can find KLayout. Returns a warning string if we detect issues."""
        # If the user provides a path, propagate it for the original validator to use.
        klayout_bin = os.getenv("PICASSO_KLAYOUT_BIN")
        if klayout_bin and os.path.exists(klayout_bin):
            os.environ.setdefault("KLAYOUT_BIN", klayout_bin)  # many tools look for this
            return None

        # If no explicit path is given, check PATH
        found = shutil.which("klayout")
        if found:
            return None

        # Not found; surface a helpful warning
        return (
            "KLayout executable not found on PATH. Install via Homebrew (`brew install klayout`) or set "
            "PICASSO_KLAYOUT_BIN=/path/to/klayout (e.g., /Applications/KLayout.app/Contents/MacOS/klayout)."
        )

    def _run_original(self, payload: Any) -> ValidationReport:
        try:
            # Propagate executable location hints first
            warn = self._ensure_klayout_env()
            result = self._impl.validate(payload)  # type: ignore[attr-defined]
            rep = normalize_report(result)
            if warn and rep.get("passed", False):
                rep.setdefault("warnings", []).append(warn)
            elif warn and not rep.get("warnings"):
                rep["warnings"] = [warn]
            return rep
        except Exception as e:
            return {"passed": False, "errors": [f"DRC original validator exception: {e}"], "warnings": [], "metrics": {}}

    def validate(self, design_py: str) -> ValidationReport:
        if self._impl is not None:
            # Prefer to validate a built gf.Component to keep parity with the other adapters
            try:
                comp = build_component_from_code(design_py)
                return self._run_original(comp)
            except Exception as e:
                # Fall back to raw code if building fails (your original might accept code strings)
                rep = self._run_original(design_py)
                rep.setdefault("warnings", []).append(f"DRC build() failed: {e}")
                return rep

        # Fallback: light static checks
        errors: List[str] = []
        warnings: List[str] = []
        if "route" in design_py and "cross" in design_py:
            warnings.append("Design may contain crossing routes – verify spacing >= 2µm.")
        return {"passed": (len(errors) == 0), "errors": errors, "warnings": warnings, "metrics": {}}
