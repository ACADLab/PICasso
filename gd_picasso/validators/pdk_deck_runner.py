"""PDK deck probes for the PIC gate — four-state reporting only.

SiEPIC: **SKIP(no emitter)** — Salt deck exists but PIC-Set does not emit
SiEPIC GDS; do not report FAIL (that would look like a regression).

sky130: **dropped** from the PIC gate (CMOS; can never apply to photonic PIC-Set).

Actual foundry DRC for emitted layouts belongs on ``PDKBackend.drc_runner``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class DeckResult:
    pdk: str
    available: bool
    ran: bool
    passed: Optional[bool]
    markers: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    vacuous: bool = False
    report_path: Optional[str] = None
    error: Optional[str] = None
    note: str = ""
    lvs: str = "n/a_no_schematic"
    status: str = "n/a"  # PASS|FAIL|SKIP|N/A

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def siepic_gate_status() -> DeckResult:
    """PIC-gate status for SiEPIC: SKIP until a SiEPIC emitter exists."""
    return DeckResult(
        pdk="siepic_ebeam",
        available=True,
        ran=False,
        passed=None,
        status="SKIP",
        note="SKIP(no emitter): Salt SiEPIC DRC is installed but PIC-Set "
        "emits generic_tech GDS only — not a regression",
        lvs="n/a_no_schematic",
    )


def pic_gate_pdk_probes() -> Dict[str, DeckResult]:
    """Report-only statuses for the PIC-Set e2e table (no foreign-deck runs)."""
    return {
        "siepic_ebeam": siepic_gate_status(),
        # sky130 intentionally omitted — never applies to PIC-Set
    }


def format_pdk_summary(results: Dict[str, DeckResult]) -> str:
    lines = ["PDK probe (PIC gate; four-state):"]
    for key, r in results.items():
        lines.append(f"  {key}: {r.status} — {r.note}")
    if "sky130" not in results:
        lines.append("  sky130: dropped from PIC gate (CMOS deck)")
    return "\n".join(lines)
