"""
Static Phase-and-loss Analysis (SPA) v0.

Photonic analogue of STA: accumulate optical phase and loss along paths;
phase slack = group tolerance − |Δφ|. Negative slack flags Table-V-style
failures (64-QAM, 90° Hybrid) once wired to published Spec@k tasks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .store import PCGStore
from .types import EdgeLayer


@dataclass
class PathMetrics:
    nodes: List[str]
    length_um: float = 0.0
    phase_rad: float = 0.0
    loss_db: float = 0.0
    n_crossings: int = 0


@dataclass
class PhaseSlackResult:
    group_id: str
    paths: List[PathMetrics]
    delta_phi_rad: float
    tolerance_rad: float
    slack_rad: float  # tolerance - |delta|; negative = fail

    @property
    def ok(self) -> bool:
        return self.slack_rad >= 0.0


@dataclass
class SPAReport:
    groups: List[PhaseSlackResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return all(g.ok for g in self.groups)


def _edge_key(e) -> Tuple[str, str, str, str]:
    return (e.src_node, e.src_port, e.dst_node, e.dst_port)


def accumulate_path(
    store: PCGStore,
    node_sequence: Sequence[str],
    *,
    loss_dB_cm: float = 0.7,
    neff: float = 2.34,
    wavelength_um: float = 1.55,
) -> PathMetrics:
    """Accumulate L / φ / IL along a node sequence using back-annot fields.

    Missing ``length_um`` / ``phase_rad`` contribute 0 (explicit; not silent
    library defaults). Phase from length uses Δφ = 2π·neff·L/λ when phase
    is unset but length is present.
    """
    metrics = PathMetrics(nodes=list(node_sequence))
    if len(node_sequence) < 2:
        return metrics

    edges = store.edges
    for a, b in zip(node_sequence, node_sequence[1:]):
        matched = None
        for e in edges:
            if e.layer != EdgeLayer.OPTICAL:
                continue
            if (e.src_node == a and e.dst_node == b) or (
                e.src_node == b and e.dst_node == a
            ):
                matched = e
                break
        if matched is None:
            continue
        L = matched.length_um or 0.0
        metrics.length_um += L
        metrics.n_crossings += matched.n_crossings or 0
        if matched.phase_rad is not None:
            metrics.phase_rad += matched.phase_rad
        elif L:
            metrics.phase_rad += 2.0 * math.pi * neff * L / wavelength_um
        metrics.loss_db += loss_dB_cm * (L / 1e4)  # µm → cm
    return metrics


def phase_slack(
    store: PCGStore,
    group_id: str,
    paths: Sequence[Sequence[str]],
    *,
    tolerance_rad: float = 0.01,
    **path_kwargs,
) -> PhaseSlackResult:
    """Compute phase slack for a matched-length / phase-critical group."""
    path_metrics = [accumulate_path(store, p, **path_kwargs) for p in paths]
    if len(path_metrics) < 2:
        dphi = 0.0
    else:
        phases = [p.phase_rad for p in path_metrics]
        dphi = max(phases) - min(phases)
    slack = tolerance_rad - abs(dphi)
    return PhaseSlackResult(
        group_id=group_id,
        paths=path_metrics,
        delta_phi_rad=dphi,
        tolerance_rad=tolerance_rad,
        slack_rad=slack,
    )


def spa_v0(
    store: PCGStore,
    groups: Dict[str, Sequence[Sequence[str]]],
    *,
    tolerance_rad: float = 0.01,
    **path_kwargs,
) -> SPAReport:
    """Run SPA over named path groups.

    ``groups`` maps group_id → list of node-id paths (e.g. MZI arms).
    """
    report = SPAReport()
    for gid, paths in groups.items():
        report.groups.append(
            phase_slack(
                store, gid, paths, tolerance_rad=tolerance_rad, **path_kwargs
            )
        )
    return report
