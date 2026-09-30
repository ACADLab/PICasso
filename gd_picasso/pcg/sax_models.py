"""
SAX model surface — silent-default audit and lossy model factory.

``loss_dB_cm=0.0`` on gplugins ``straight`` is the class of bug this module
guards against: physically-null defaults that silently pass gate checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Dict, List, Optional


# Waveguide target from PIC-Set / Table II (provenance: TARGET_TABLE_II — not fab CS)
DEFAULT_LOSS_DB_CM = 0.7
DEFAULT_LOSS_PROVENANCE = "TARGET_TABLE_II"

# Cornerstone FINDINGS promoted under cspdk==1.3.2 + gf 9.23.0 (2026-09-29).
CS_ARM_L_UM = 320.0
CS_MMI2X2_EXCESS_LOSS_DB = 0.3
CS_MZI_IL_DB = 0.622
# Model-derived (cspdk SAX + Table II 0.7 dB/cm) — not a foundry measurement
CS_MZI_IL_PROVENANCE = "CS_MODEL_SAX"


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
        f"CS grade sidecar {CS_MMI2X2_EXCESS_LOSS_DB} dB (mmi2x2); "
        "gplugins model still ideal — FoM quotes FINDINGS IL",
        "FINDINGS cspdk==1.3.2 + gf 9.23.0 (promoted)", "ok",
    ),
    SaxParamAuditRow(
        "coupler", "loss / coupling", "ideal splitter common",
        "library default",
        "gplugins", "unknown",
    ),
    SaxParamAuditRow(
        "straight_heater_metal", "length / loss",
        "generic_tech length often 10 µm; loss via straight stub",
        f"CS ARM_L={CS_ARM_L_UM} µm; lossy straight "
        f"(loss_dB_cm={DEFAULT_LOSS_DB_CM}); MZI IL grade={CS_MZI_IL_DB} dB",
        "FINDINGS cspdk==1.3.2 + gf 9.23.0 (promoted)", "ok",
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
