"""PDK backend registry — PCG → foundry-specific emit + SAX + DRC.

N6 note: until ≥2 *different foundries* emit, portability is NO EVIDENCE.
``generic_tech`` is a teaching stack, not a foundry PDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple


class LossProvenance(str, Enum):
    """Provenance for SAX / waveguide loss entries (ESTIMATOR_ONLY discipline)."""

    MEASURED_CS = "MEASURED_CS"  # foundry measurement or published PDK loss only
    CS_MODEL_SAX = "CS_MODEL_SAX"  # SAX over cspdk models (may inject Table II loss)
    TARGET_TABLE_II = "TARGET_TABLE_II"
    ESTIMATED = "ESTIMATED"


@dataclass(frozen=True)
class LossEntry:
    value_dB_cm: float
    provenance: LossProvenance
    note: str = ""


@dataclass
class DrcOutcome:
    """Four-state DRC result for a backend."""

    status: str  # PASS | FAIL | SKIP | N/A
    reason: str = ""
    markers: int = 0


ParamAdapter = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass
class PDKBackend:
    """One pinned PDK emit/verify surface."""

    id: str
    pinned_versions: Dict[str, str]
    # role (or GF default encoding) → cell name in this PDK
    component_map: Dict[str, str]
    param_adapters: Dict[str, ParamAdapter] = field(default_factory=dict)
    xs_map: Dict[str, str] = field(default_factory=dict)
    # (role, logical_port) → physical port; empty = identity
    port_map: Dict[Tuple[str, str], str] = field(default_factory=dict)
    strip_loss: Optional[LossEntry] = None
    # optional: reference IL for smoke (e.g. CS MZI 0.622 dB)
    reference_il_dB: Optional[float] = None
    reference_il_note: str = ""
    drc_fn: Optional[Callable[[str], DrcOutcome]] = None

    def map_component(self, role_or_component: str) -> str:
        return self.component_map.get(role_or_component, role_or_component)

    def adapt_params(self, role_or_component: str, params: Dict[str, Any]) -> Dict[str, Any]:
        fn = self.param_adapters.get(role_or_component)
        if fn is None:
            cell = self.map_component(role_or_component)
            fn = self.param_adapters.get(cell)
        if fn is None:
            return dict(params)
        return fn(dict(params))

    def map_port(self, role_or_component: str, port: str) -> str:
        return self.port_map.get((role_or_component, port), port)

    def run_drc(self, gds_path: str) -> DrcOutcome:
        if self.drc_fn is None:
            return DrcOutcome(status="N/A", reason="no drc_runner")
        return self.drc_fn(gds_path)
