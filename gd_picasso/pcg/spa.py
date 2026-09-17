"""
Static Phase-and-loss Analysis (SPA).

Photonic analogue of STA over reconvergent optical paths.

Headline metric
---------------
**WNS** (worst negative / least slack) over all path-*pairs* in a group —
same dual reporting as VLSI STA: per-pair slack is the diagnostic; WNS is
the circuit-level number.

Scope
-----
- v0 (``phase_slack`` / ``spa_v0``): two-arm matched-length difference.
  Kept as a thin wrapper. Adequate for MZI/MZM; **structurally wrong** for
  a 90° hybrid (needs four paths with fixed relative offsets).
- v1 (``phase_slack_group`` / ``spa_analyze``): N reconvergent paths with
  optional per-path target offsets relative to path 0. Expresses matched-
  length (all targets 0) and quadrature hybrids (0, π/2, π, 3π/2).

What the Table V synthetic probe establishes
--------------------------------------------
``spa_table_v`` plants Δφ and checks the comparator. That is a **unit test
of the metric**, not evidence that layout geometry predicts functional
failure. The causal claim (geometry → L → φ → slack → Spec fail) still
requires routed back-annotation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations
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
class PairSlack:
    """Diagnostic: slack between one path pair."""

    path_i: int
    path_j: int
    actual_delta_rad: float
    target_delta_rad: float
    error_rad: float
    tolerance_rad: float
    slack_rad: float  # tol - |error|; negative = violate

    @property
    def ok(self) -> bool:
        return self.slack_rad >= 0.0


@dataclass
class PhaseSlackResult:
    """One reconvergent path group.

    ``slack_rad`` / ``delta_phi_rad`` remain the v0 two-path fields
    (worst pair). Prefer ``wns_rad`` and ``pair_slacks`` for v1.
    """

    group_id: str
    paths: List[PathMetrics]
    delta_phi_rad: float
    tolerance_rad: float
    slack_rad: float
    pair_slacks: List[PairSlack] = field(default_factory=list)
    targets_rad: List[float] = field(default_factory=list)
    wns_rad: float = 0.0  # min pair slack — headline

    @property
    def ok(self) -> bool:
        return self.wns_rad >= 0.0


@dataclass
class SPAReport:
    groups: List[PhaseSlackResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return all(g.ok for g in self.groups)

    @property
    def wns_rad(self) -> float:
        """Circuit-level WNS across all groups."""
        if not self.groups:
            return 0.0
        return min(g.wns_rad for g in self.groups)


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
    used: set[int] = set()
    for a, b in zip(node_sequence, node_sequence[1:]):
        candidates = [
            e for e in edges
            if e.layer == EdgeLayer.OPTICAL
            and (
                (e.src_node == a and e.dst_node == b)
                or (e.src_node == b and e.dst_node == a)
            )
        ]
        unused = [e for e in candidates if id(e) not in used]
        pool = unused if unused else candidates
        if not pool:
            raise ValueError(
                f"No optical edge between '{a}' and '{b}' in path "
                f"{list(node_sequence)}; path is incomplete"
            )
        if len(pool) > 1:
            raise ValueError(
                f"Ambiguous optical edges between '{a}' and '{b}' "
                f"({len(pool)} candidates); qualify the path by port"
            )
        matched = pool[0]
        used.add(id(matched))
        L = matched.length_um or 0.0
        metrics.length_um += L
        metrics.n_crossings += matched.n_crossings or 0
        if matched.phase_rad is not None:
            metrics.phase_rad += matched.phase_rad
        elif L:
            metrics.phase_rad += 2.0 * math.pi * neff * L / wavelength_um
        metrics.loss_db += loss_dB_cm * (L / 1e4)  # µm → cm
    return metrics


def _wrap_pi(x: float) -> float:
    """Wrap to (−π, π] for phase-error magnitude."""
    return (x + math.pi) % (2.0 * math.pi) - math.pi


def phase_slack_group(
    store: PCGStore,
    group_id: str,
    paths: Sequence[Sequence[str]],
    *,
    tolerance_rad: float = 0.01,
    targets_rad: Optional[Sequence[float]] = None,
    **path_kwargs,
) -> PhaseSlackResult:
    """N-path reconvergent phase slack.

    ``targets_rad[i]`` is the required phase of path i *relative to path 0*
    (defaults to 0 for every path → matched-length / matched-phase group).

    For every pair (i, j):
        actual Δ = φ_j − φ_i
        target Δ = targets[j] − targets[i]
        error = wrap(actual − target)
        slack_ij = tolerance − |error|

    **WNS** = min_ij slack_ij  (headline). Per-pair entries are diagnostics.
    """
    path_metrics = [accumulate_path(store, p, **path_kwargs) for p in paths]
    n = len(path_metrics)
    if targets_rad is None:
        targets = [0.0] * n
    else:
        targets = list(targets_rad)
        if len(targets) != n:
            raise ValueError(
                f"targets_rad length {len(targets)} != number of paths {n}"
            )

    pair_slacks: List[PairSlack] = []
    if n < 2:
        wns = tolerance_rad
        dphi = 0.0
    else:
        for i, j in combinations(range(n), 2):
            actual = path_metrics[j].phase_rad - path_metrics[i].phase_rad
            target = targets[j] - targets[i]
            err = _wrap_pi(actual - target)
            slack = tolerance_rad - abs(err)
            pair_slacks.append(
                PairSlack(
                    path_i=i,
                    path_j=j,
                    actual_delta_rad=actual,
                    target_delta_rad=target,
                    error_rad=err,
                    tolerance_rad=tolerance_rad,
                    slack_rad=slack,
                )
            )
        wns = min(ps.slack_rad for ps in pair_slacks)
        # Legacy two-path field: max−min measured phase (ignores targets)
        phases = [p.phase_rad for p in path_metrics]
        dphi = max(phases) - min(phases)

    return PhaseSlackResult(
        group_id=group_id,
        paths=path_metrics,
        delta_phi_rad=dphi,
        tolerance_rad=tolerance_rad,
        slack_rad=wns,  # align legacy field with WNS
        pair_slacks=pair_slacks,
        targets_rad=targets,
        wns_rad=wns,
    )


def phase_slack(
    store: PCGStore,
    group_id: str,
    paths: Sequence[Sequence[str]],
    *,
    tolerance_rad: float = 0.01,
    **path_kwargs,
) -> PhaseSlackResult:
    """v0 wrapper: matched-length group (all targets 0)."""
    return phase_slack_group(
        store, group_id, paths, tolerance_rad=tolerance_rad, targets_rad=None,
        **path_kwargs,
    )


def spa_analyze(
    store: PCGStore,
    groups: Dict[str, Sequence[Sequence[str]]],
    *,
    tolerance_rad: float = 0.01,
    group_targets: Optional[Dict[str, Sequence[float]]] = None,
    **path_kwargs,
) -> SPAReport:
    """Run SPA v1 over named path groups.

    ``group_targets`` optionally maps group_id → per-path target offsets
    relative to path 0 (e.g. hybrid ``[0, π/2, π, 3π/2]``).
    """
    group_targets = group_targets or {}
    report = SPAReport()
    for gid, paths in groups.items():
        report.groups.append(
            phase_slack_group(
                store,
                gid,
                paths,
                tolerance_rad=tolerance_rad,
                targets_rad=group_targets.get(gid),
                **path_kwargs,
            )
        )
    return report


def spa_v0(
    store: PCGStore,
    groups: Dict[str, Sequence[Sequence[str]]],
    *,
    tolerance_rad: float = 0.01,
    **path_kwargs,
) -> SPAReport:
    """Backward-compatible matched-length SPA (all targets 0)."""
    return spa_analyze(
        store, groups, tolerance_rad=tolerance_rad, group_targets=None,
        **path_kwargs,
    )


# Canonical 90° hybrid target offsets relative to path 0.
HYBRID_90_TARGETS_RAD: Tuple[float, float, float, float] = (
    0.0,
    math.pi / 2,
    math.pi,
    3.0 * math.pi / 2,
)
