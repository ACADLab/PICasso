"""Validator interface and common utilities."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, TypedDict, List, Optional, Dict, Any


class ValidationReport(TypedDict, total=False):
    passed: bool
    errors: List[str]
    warnings: List[str]
    metrics: Dict[str, float]


class Validator(Protocol):
    name: str

    def validate(self, design_py: str) -> ValidationReport:
        """Return a structured ValidationReport for the generated design code."""

    def format_feedback(self, report: ValidationReport) -> str:
        """Return human-readable feedback for the LLM."""


@dataclass
class SimpleValidatorMixin:
    """Mixin providing a default `format_feedback` implementation."""
    name: str

    def format_feedback(self, report: ValidationReport) -> str:
        header = f"[{self.name}] {'PASSED' if report.get('passed') else 'FAILED'}"
        lines = [header]

        for key in ("errors", "warnings"):
            items = report.get(key) or []
            if items:
                lines.append(key.upper() + ":")
                lines.extend(f"  - {it}" for it in items)

        metrics = report.get("metrics")
        if metrics:
            lines.append("METRICS:")
            for k, v in metrics.items():
                if isinstance(v, float):
                    lines.append(f"  • {k}: {v:.3f}")
                else:
                    lines.append(f"  • {k}: {v}")
        return "\n".join(lines)


# ---------- Helpers added for adapters ----------

def normalize_report(result: Any) -> ValidationReport:
    """Convert various return shapes to a ValidationReport dict."""
    # Already dict-like
    if isinstance(result, dict):
        passed = bool(result.get("passed", False))
        errors = list(result.get("errors", []) or [])
        warnings = list(result.get("warnings", []) or [])
        metrics = dict(result.get("metrics", {}) or {})
        return {"passed": passed, "errors": errors, "warnings": warnings, "metrics": metrics}

    # Tuple/list formats: (passed, errors, warnings[, metrics])
    if isinstance(result, (tuple, list)) and result:
        passed = bool(result[0])
        errors = list(result[1] if len(result) > 1 else []) or []
        warnings = list(result[2] if len(result) > 2 else []) or []
        metrics = dict(result[3] if len(result) > 3 else {}) or {}
        return {"passed": passed, "errors": errors, "warnings": warnings, "metrics": metrics}

    # Bare boolean
    if isinstance(result, bool):
        return {"passed": result, "errors": [] if result else ["Validation failed"], "warnings": [], "metrics": {}}

    # Unknown type
    return {
        "passed": False,
        "errors": [f"Validator returned unsupported type: {type(result).__name__}"],
        "warnings": [],
        "metrics": {},
    }


def build_component_from_code(design_py: str):
    """Exec the generated code and call build() -> gf.Component if present.

    Returns:
        gf.Component

    Raises:
        RuntimeError: if gdsfactory is missing, code fails, or build() doesn't return a Component.
    """
    try:
        import gdsfactory as gf  # type: ignore
    except Exception as e:
        raise RuntimeError(f"gdsfactory import failed: {e}")

    glb: Dict[str, Any] = {"gf": gf, "gdsfactory": gf, "__name__": "__generated_design__"}
    lcl: Dict[str, Any] = {}

    # Execute the generated code
    exec(design_py, glb, lcl)  # noqa: S102

    ns = {**glb, **lcl}

    # Prefer an explicit build() function
    build = ns.get("build")
    if callable(build):
        obj = build()
    else:
        # Fallback: look for a common variable name
        for k in ("component", "c", "COMPONENT"):
            if k in ns:
                obj = ns[k]
                break
        else:
            raise RuntimeError("No build() function or component object found in generated code.")

    # Validate type strictly
    try:
        import gdsfactory as gf  # ensure we have the type
        if not isinstance(obj, gf.Component):  # type: ignore[attr-defined]
            raise RuntimeError(f"build() returned {type(obj).__name__}, expected gf.Component")
    except Exception as e:
        raise RuntimeError(f"Invalid build() result: {e}")

    return obj
