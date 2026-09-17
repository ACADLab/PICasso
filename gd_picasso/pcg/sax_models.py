"""
SAX model surface — silent-default audit and lossy model factory.

``loss_dB_cm=0.0`` on gplugins ``straight`` is the class of bug this module
guards against: physically-null defaults that silently pass gate checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Dict, List, Optional


# Waveguide target from PIC-Set / Table II
DEFAULT_LOSS_DB_CM = 0.7


@dataclass(frozen=True)
class SaxParamAuditRow:
    component: str
    param: str
    library_default: str
    what_we_set: str
    source: str
    risk: str  # "silent_null" | "ok" | "stub" | "unknown"


# One-pass audit table — extend when new models enter the gate.
SAX_PARAM_AUDIT: List[SaxParamAuditRow] = [
    SaxParamAuditRow(
        "straight", "loss_dB_cm", "0.0", str(DEFAULT_LOSS_DB_CM),
        "Table II / PIC-Set waveguide target", "silent_null",
    ),
    SaxParamAuditRow(
        "bend_euler / bend_circular", "loss", "model-dependent / often 0",
        "use gs.models.bend (no override yet)",
        "gplugins sax; needs PDK-calibrated bend loss", "unknown",
    ),
    SaxParamAuditRow(
        "mmi1x2 / mmi2x2", "excess_loss", "often ideal / 0",
        "library default (no override)",
        "gplugins; excess loss not forced", "silent_null",
    ),
    SaxParamAuditRow(
        "coupler", "loss / coupling", "ideal splitter common",
        "library default",
        "gplugins", "unknown",
    ),
    SaxParamAuditRow(
        "straight_heater_metal", "length / loss",
        "generic_tech length often 10 µm; loss via straight stub",
        f"mapped to lossy straight (loss_dB_cm={DEFAULT_LOSS_DB_CM})",
        "gate harness; Cornerstone default heater L≈320 µm — re-baseline open",
        "silent_null",
    ),
    SaxParamAuditRow(
        "ring_single", "S-model", "compound / may fall back to bend",
        "gs.models.ring_single if present else bend",
        "gplugins hasattr fallback", "stub",
    ),
    SaxParamAuditRow(
        "via_stack_heater_mtop", "S-model", "missing",
        "lossy straight stub",
        "electrical cell appearing in get_netlist()", "stub",
    ),
]


def audit_table_markdown() -> str:
    """Render the audit as a markdown table for docs / PR bodies."""
    lines = [
        "| component | param | library default | what we set | source | risk |",
        "|---|---|---|---|---|---|",
    ]
    for r in SAX_PARAM_AUDIT:
        lines.append(
            f"| {r.component} | {r.param} | {r.library_default} | "
            f"{r.what_we_set} | {r.source} | {r.risk} |"
        )
    return "\n".join(lines)


def build_lossy_models(
    loss_dB_cm: float = DEFAULT_LOSS_DB_CM,
) -> Dict[str, Callable[..., Any]]:
    """Return SAX model map with waveguide loss forced non-zero.

    Raises ImportError if gplugins/sax models are unavailable.
    """
    from gplugins import sax as gs

    straight = partial(gs.models.straight, loss_dB_cm=loss_dB_cm)
    models: Dict[str, Callable[..., Any]] = {
        "straight": straight,
        "bend_euler": gs.models.bend,
        "bend_circular": gs.models.bend,
        "mmi1x2": gs.models.mmi1x2,
        "mmi2x2": gs.models.mmi2x2 if hasattr(gs.models, "mmi2x2") else gs.models.mmi1x2,
        "coupler": gs.models.coupler if hasattr(gs.models, "coupler") else gs.models.mmi1x2,
        "ring_single": (
            gs.models.ring_single if hasattr(gs.models, "ring_single") else gs.models.bend
        ),
        "straight_heater_metal": straight,
        "straight_heater_metal_undercut": straight,
        "via_stack_heater_mtop": straight,
        "taper": straight,
        "terminator": straight,
    }
    return models


def ensure_jax_x64() -> None:
    """Enable JAX x64; safe to call multiple times."""
    try:
        import jax

        jax.config.update("jax_enable_x64", True)
    except Exception:
        pass
