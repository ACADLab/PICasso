"""Client interfaces for text-generation backends."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Protocol, Sequence


Messages = Sequence[Dict[str, str]]  # [{"role": "...", "content": "..."}]


class ChatClient(Protocol):
    """Minimal synchronous chat-completion interface."""

    model: str

    def complete(self, messages: Messages, **gen_params) -> str:
        """Return the assistant message content."""

    def test_connection(self) -> bool:
        """Return True if the remote service is reachable."""


@dataclass
class Conversation:
    """Lightweight conversation helper used by the generator + retry policy."""
    client: ChatClient
    history: List[Dict[str, str]]

    @classmethod
    def start(cls, client: ChatClient, system_prompt: Optional[str] = None) -> "Conversation":
        hist: List[Dict[str, str]] = []
        if system_prompt:
            hist.append({"role": "system", "content": system_prompt})
        return cls(client=client, history=hist)

    def ask(self, user_content: str, **gen_params) -> str:
        self.history.append({"role": "user", "content": user_content})
        reply = self.client.complete(self.history, **gen_params)
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def append_feedback(self, feedback: str) -> None:
        self.history.append({"role": "system", "content": f"Validation feedback:\n{feedback}"})

    # --- add at end of file ---

def normalize_report(result) -> ValidationReport:
    """Convert various return shapes to a ValidationReport dict."""
    # Already correct dict-like
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

    # Bare boolean: treat as pass/fail, no details
    if isinstance(result, bool):
        return {"passed": result, "errors": [] if result else ["Validation failed"], "warnings": [], "metrics": {}}

    # Fallback: unknown type
    return {"passed": False, "errors": [f"Validator returned unsupported type: {type(result).__name__}"], "warnings": [], "metrics": {}}


def build_component_from_code(design_py: str):
    """Exec the generated code and call build() -> gf.Component if present."""
    # Local, lazy import to avoid hard dependency during type checks
    import types
    glb = {}
    lcl = {}
    # Provide a gdsfactory alias commonly used by prompts
    try:
        import gdsfactory as gf  # type: ignore
        glb["gf"] = gf
        glb["gdsfactory"] = gf
    except Exception as e:
        raise RuntimeError(f"gdsfactory import failed: {e}")

    # Execute user code safely-ish within temp dicts (still trusted code!)
    exec(design_py, glb, lcl)  # noqa: S102 (we're intentionally executing generated code)
    ns = {**glb, **lcl}
    build = ns.get("build")
    if callable(build):
        comp = build()
        return comp
    # If the code defined a variable 'component' or similar
    for k in ("component", "c", "COMPONENT"):
        if k in ns:
            return ns[k]
    raise RuntimeError("No build() function or component object found in generated code.")

