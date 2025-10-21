"""Validator interface and common utilities."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, TypedDict, List, Optional, Dict


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
                lines.append(f"  • {k}: {v:.3f}" if isinstance(v, float) else f"  • {k}: {v}")
        return "\n".join(lines)
