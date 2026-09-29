"""
Deterministic A0 elaborator: topology_program → A1 mutation list.

Expands compact programs (``mzi(...)``, ``mzm(...)``) into typed store
mutations consumed by :class:`~gd_picasso.agents.schematic_agent.SchematicAgent`.
No LLM; enumeration lives here so A0 never emits free-form node lists.

Batch ops obey ``gd_picasso/pcg/A1_MUTATION_CONTRACT.md`` (v1): only
``add_node`` / ``connect`` / ``set_param``. Boundary ports are returned
separately for a direct ``PCGStore.set_exported_ports`` call (not a batch op).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from gd_picasso.agents.intent_agent import TypedIntent
from gd_picasso.pcg.pdk_ports import COMPONENT_PORT_MAP

# Default arm length (µm) matching pcg/fixtures/mzi.yaml / mzm.yaml.
_DEFAULT_ARM_LENGTH = 100.0

_PROG_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?:\((.*)\))?\s*$",
    re.DOTALL,
)

# Frozen A1 batch vocabulary (CONTRACT_VERSION = 1).
_A1_BATCH_OPS = frozenset({"add_node", "connect", "set_param"})


class ElaboratorError(ValueError):
    """Raised when a topology_program cannot be elaborated."""


@dataclass
class ElaborationResult:
    """A1 batch mutations plus boundary ports (store-direct, not batch op)."""

    mutations: List[Dict[str, Any]]
    exported_ports: Dict[str, str] = field(default_factory=dict)


def _parse_value(raw: str) -> Any:
    text = raw.strip()
    if not text:
        raise ElaboratorError("Empty keyword value in topology_program")
    lower = text.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        return ast.literal_eval(text)
    except (SyntaxError, ValueError):
        # Unquoted PDK / identifier tokens (e.g. straight_heater_metal).
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text):
            return text
        raise ElaboratorError(f"Cannot parse topology_program value {text!r}")


def parse_topology_program(program: str) -> Tuple[str, Dict[str, Any]]:
    """Parse ``name(k=v, ...)`` into ``(name, kwargs)``."""
    text = (program or "").strip()
    if not text:
        raise ElaboratorError("Empty topology_program")
    m = _PROG_RE.match(text)
    if not m:
        raise ElaboratorError(f"Malformed topology_program: {program!r}")
    name = m.group(1)
    body = (m.group(2) or "").strip()
    kwargs: Dict[str, Any] = {}
    if not body:
        return name, kwargs
    # Split on top-level commas (no nested calls required for MZI/MZM).
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    for ch in body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf))
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if "=" not in piece:
            raise ElaboratorError(
                f"Expected key=value in topology_program args, got {piece!r}"
            )
        key, _, val = piece.partition("=")
        key = key.strip()
        if not key:
            raise ElaboratorError(f"Missing key in topology_program arg {piece!r}")
        kwargs[key] = _parse_value(val)
    return name, kwargs


def _add_node(
    node_id: str, component: str, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    if component not in COMPONENT_PORT_MAP:
        raise ElaboratorError(f"Unknown component {component!r} for node {node_id!r}")
    return {
        "op": "add_node",
        "id": node_id,
        "component": component,
        "params": dict(params or {}),
    }


def _connect(
    src: str, src_port: str, dst: str, dst_port: str, *, bundle: str = "optical"
) -> Dict[str, Any]:
    return {
        "op": "connect",
        "src": src,
        "src_port": src_port,
        "dst": dst,
        "dst_port": dst_port,
        "bundle": bundle,
    }


def _validate_batch_ops(mutations: List[Dict[str, Any]]) -> None:
    for m in mutations:
        op = m.get("op")
        if op not in _A1_BATCH_OPS:
            raise ElaboratorError(
                f"Elaborator emitted non-contract op {op!r}; "
                f"v1 batch ops are {sorted(_A1_BATCH_OPS)}"
            )


def elaborate_mzi(kwargs: Dict[str, Any]) -> ElaborationResult:
    """Dual-arm MZI matching fixtures/mzi.yaml topology (heater + passive arm)."""
    arms = int(kwargs.get("arms", 2))
    if arms != 2:
        raise ElaboratorError(f"mzi template currently supports arms=2, got {arms}")
    ps = str(kwargs.get("ps", "straight_heater_metal"))
    length = float(kwargs.get("length", _DEFAULT_ARM_LENGTH))
    passive = str(kwargs.get("passive", "straight"))
    splitter = str(kwargs.get("splitter", "mmi1x2"))
    combiner = str(kwargs.get("combiner", "mmi1x2"))

    mutations: List[Dict[str, Any]] = [
        _add_node("splitter", splitter),
        _add_node("ps_upper", ps, {"length": length}),
        _add_node("ps_lower", passive, {"length": length}),
        _add_node("combiner", combiner),
        _connect("splitter", "o2", "ps_upper", "o1", bundle="west"),
        _connect("splitter", "o3", "ps_lower", "o1", bundle="west"),
        _connect("ps_upper", "o2", "combiner", "o2", bundle="east"),
        _connect("ps_lower", "o2", "combiner", "o3", bundle="east"),
    ]
    _validate_batch_ops(mutations)
    return ElaborationResult(
        mutations=mutations,
        exported_ports={"in": "splitter,o1", "out": "combiner,o1"},
    )


def elaborate_mzm(kwargs: Dict[str, Any]) -> ElaborationResult:
    """Dual-drive MZM matching fixtures/mzm.yaml (mmi2x2 combiner, both arms PS)."""
    dual_drive = bool(kwargs.get("dual_drive", True))
    if not dual_drive:
        raise ElaboratorError("mzm template currently requires dual_drive=true")
    ps = str(kwargs.get("ps", "straight_heater_metal"))
    length = float(kwargs.get("length", _DEFAULT_ARM_LENGTH))
    splitter = str(kwargs.get("splitter", "mmi1x2"))
    combiner = str(kwargs.get("combiner", "mmi2x2"))

    mutations: List[Dict[str, Any]] = [
        _add_node("splitter", splitter),
        _add_node("ps_upper", ps, {"length": length}),
        _add_node("ps_lower", ps, {"length": length}),
        _add_node("combiner", combiner),
        _connect("splitter", "o2", "ps_upper", "o1", bundle="west"),
        _connect("splitter", "o3", "ps_lower", "o1", bundle="west"),
        _connect("ps_upper", "o2", "combiner", "o1", bundle="east"),
        _connect("ps_lower", "o2", "combiner", "o2", bundle="east"),
    ]
    _validate_batch_ops(mutations)
    return ElaborationResult(
        mutations=mutations,
        exported_ports={
            "in": "splitter,o1",
            "out1": "combiner,o3",
            "out2": "combiner,o4",
        },
    )


class TopologyElaborator:
    """Map TypedIntent.topology_program → A1 mutations + boundary ports."""

    TEMPLATES = {
        "mzi": elaborate_mzi,
        "mzm": elaborate_mzm,
    }

    def elaborate(self, intent: TypedIntent) -> ElaborationResult:
        program = intent.topology_program
        if not program:
            raise ElaboratorError(
                "TypedIntent has no topology_program; free-form schematic required"
            )
        name, kwargs = parse_topology_program(program)
        key = name.lower()
        handler = self.TEMPLATES.get(key)
        if handler is None:
            raise ElaboratorError(
                f"Unsupported topology program {name!r}; "
                f"known: {sorted(self.TEMPLATES)}"
            )
        return handler(kwargs)

    def elaborate_program(self, program: str) -> ElaborationResult:
        return self.elaborate(TypedIntent(topology_program=program))
