"""Adaptive retry policy with structured results.

If the repository also contains the original `retry_handler.AdaptiveRetryHandler`,
this module will adapt and delegate to it automatically.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Callable

from .validators.base import ValidationReport, Validator
from .clients.base import Conversation

import os

class ValidationStage(Enum):
    PNR = "PNR"
    DRC = "DRC"
    SAX = "SAX"


@dataclass
class RetryAttempt:
    attempt: int
    prompt_used: str
    generation: str
    reports: Dict[str, ValidationReport]


@dataclass
class RetryResult:
    success: bool
    attempts: List[RetryAttempt]
    best_code: Optional[str] = None


class _NativeRetryPolicy:
    """Reference retry policy used if the user's original handler isn't available."""

    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts

    def gen_params_for_attempt(self, attempt: int) -> Dict:
        return {"temperature": min(0.2 + 0.3 * (attempt - 1), 0.9)}

    def run(
        self,
        convo: Conversation,
        base_prompt: str,
        validators: List[Validator],
    ) -> RetryResult:
        attempts: List[RetryAttempt] = []
        best_code: Optional[str] = None

        for i in range(1, self.max_attempts + 1):
            params = self.gen_params_for_attempt(i)
            code = convo.ask(base_prompt, **params)

            reports: Dict[str, ValidationReport] = {}
            passed_all = True
            for v in validators:
                report = v.validate(code)
                reports[v.name] = report
                if not report.get("passed", False):
                    passed_all = False

            attempts.append(
                RetryAttempt(
                    attempt=i,
                    prompt_used=base_prompt,
                    generation=code,
                    reports=reports,
                )
            )

            if passed_all:
                return RetryResult(success=True, attempts=attempts, best_code=code)

            feedback = "\n\n".join(v.format_feedback(reports[v.name]) for v in validators)
            convo.append_feedback(feedback)

        return RetryResult(success=False, attempts=attempts, best_code=best_code)


class RetryPolicy:
    """Adapter that uses the user's AdaptiveRetryHandler if present; otherwise uses `_NativeRetryPolicy`."""

    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts
        self._delegate = None
        try:
            from retry_handler import AdaptiveRetryHandler  # type: ignore
            # Wrap to look like our interface
            self._delegate = AdaptiveRetryHandler(max_attempts=max_attempts)
        except Exception:
            self._delegate = _NativeRetryPolicy(max_attempts=max_attempts)

    def run(
        self,
        convo: Conversation,
        base_prompt: str,
        validators: List[Validator],
    ) -> RetryResult:
        # Delegate supports a similar interface? If not, emulate via our native policy.
        if hasattr(self._delegate, "run"):
            try:
                return self._delegate.run(convo, base_prompt, validators)  # type: ignore[attr-defined]
            except TypeError:
                # Fallback if signature differs
                pass
        # Fallback
        native = _NativeRetryPolicy(max_attempts=self.max_attempts)
        return native.run(convo, base_prompt, validators)
