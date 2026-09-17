"""
SPA × Table V — **comparator / unit test of the metric**, not evidence.

What this establishes
---------------------
Given planted path lengths (hence planted Δφ), SPA's sign convention and
WNS arithmetic match the expected verdict. That is the last link only:

    (planted L) → φ → slack → pass/fail

What this does **not** establish
--------------------------------
The causal claim geometry → L → φ → predicted Spec failure. Lengths here
are hand-chosen to encode which tasks "should" fail. A reviewer who sees
Δφ = 0.2 and Δφ ≈ π/2 as planted values should discount this as evidence.

Task 9 uses a **four-path** reconvergent group with targets
(0, π/2, π, 3π/2) — not a dual-arm MZI proxy. Failure is planted by giving
all four paths equal length (geometry does not realize the offsets).

Run:  python -m gd_picasso.pcg.spa_table_v
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from gd_picasso.pcg.backannotate import RouteMetrics, apply_route_metrics
from gd_picasso.pcg.spa import HYBRID_90_TARGETS_RAD, spa_analyze
from gd_picasso.pcg.store import PCGStore
from gd_picasso.pcg.types import (
    AttachmentKind,
    EdgeLayer,
    PCGNode,
    RefLevel,
)

TOL_RAD = 0.01
NEFF = 2.34
WL_UM = 1.55


def _L_for_phase(delta_phi_rad: float) -> float:
    return delta_phi_rad * WL_UM / (2.0 * math.pi * NEFF)


@dataclass
class TableVCase:
    task_id: int
    name: str
    expect_negative: bool
    store: PCGStore
    groups: Dict[str, Sequence[Sequence[str]]]
    group_targets: Optional[Dict[str, Sequence[float]]] = None


def _mzi_pair(
    arm_len_um: Tuple[float, float],
    *,
    prefix: str = "",
) -> Tuple[PCGStore, Dict[str, Sequence[Sequence[str]]]]:
    store = PCGStore(default_agent="spa_table_v")
    s, u, l, c = f"{prefix}s", f"{prefix}u", f"{prefix}l", f"{prefix}c"
    for nid, comp in [(s, "mmi1x2"), (u, "straight"), (l, "straight"), (c, "mmi1x2")]:
        store.add_node(
            PCGNode(id=nid, component=comp, level=RefLevel.L1_CIRCUIT),
            skip_component_check=True,
        )
    for a, ap, b, bp in [
        (s, "o2", u, "o1"),
        (s, "o3", l, "o1"),
        (u, "o2", c, "o2"),
        (l, "o2", c, "o3"),
    ]:
        store.connect(
            a, ap, b, bp,
            layer=EdgeLayer.OPTICAL,
            attachment=AttachmentKind.ROUTED,
            bundle="optical",
        )
    Lu, Ll = arm_len_um
    apply_route_metrics(
        store,
        {
            (s, "o2", u, "o1"): RouteMetrics(length_um=Lu / 2),
            (u, "o2", c, "o2"): RouteMetrics(length_um=Lu / 2),
            (s, "o3", l, "o1"): RouteMetrics(length_um=Ll / 2),
            (l, "o2", c, "o3"): RouteMetrics(length_um=Ll / 2),
        },
    )
    return store, {"arms": [[s, u, c], [s, l, c]]}


def _merge_stores(subs: List[Tuple[PCGStore, Dict[str, Sequence[Sequence[str]]]]]) -> Tuple[PCGStore, Dict[str, Sequence[Sequence[str]]]]:
    store = PCGStore(default_agent="spa_table_v")
    groups: Dict[str, Sequence[Sequence[str]]] = {}
    for sub, gmap in subs:
        for n in sub.nodes.values():
            store.add_node(n.model_copy(deep=True), skip_component_check=True)
        for e in sub.edges:
            store.connect(
                e.src_node, e.src_port, e.dst_node, e.dst_port,
                layer=e.layer, bundle=e.bundle, attachment=e.attachment,
            )
            for ee in store.edges:
                if (
                    ee.src_node == e.src_node and ee.src_port == e.src_port
                    and ee.dst_node == e.dst_node and ee.dst_port == e.dst_port
                ):
                    ee.length_um = e.length_um
                    ee.phase_rad = e.phase_rad
        groups.update(gmap)
    return store, groups


def _hybrid_four_path(
    path_len_um: Sequence[float],
    *,
    prefix: str = "hyb_",
) -> Tuple[PCGStore, Dict[str, Sequence[Sequence[str]]]]:
    """Four reconvergent paths src → arm_k → sink (optical hybrid skeleton)."""
    if len(path_len_um) != 4:
        raise ValueError("need four path lengths")
    store = PCGStore(default_agent="spa_table_v")
    src, sink = f"{prefix}src", f"{prefix}sink"
    # Use coupler as 4-port fan-in/out stand-in; arms are straights.
    store.add_node(
        PCGNode(id=src, component="mmi1x2", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    # Extra splitter node to get four launches (two mmi1x2)
    src2 = f"{prefix}src2"
    store.add_node(
        PCGNode(id=src2, component="mmi1x2", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    store.add_node(
        PCGNode(id=sink, component="mmi2x2", level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    arms = []
    for k in range(4):
        aid = f"{prefix}a{k}"
        store.add_node(
            PCGNode(id=aid, component="straight", level=RefLevel.L1_CIRCUIT),
            skip_component_check=True,
        )
        arms.append(aid)

    # Topology: src fans to a0,a1; src2 fans to a2,a3; feed src2 from a dummy
    # For path enumeration we only need src→arm→sink connectivity that SPA walks.
    # Connect: treat paths as [src, a_k, sink] with butt links; use a star via
    # dedicated ports on sink (o1..o4) and launch from src/src2.
    store.connect(src, "o2", arms[0], "o1", attachment=AttachmentKind.ROUTED, bundle="optical")
    store.connect(src, "o3", arms[1], "o1", attachment=AttachmentKind.ROUTED, bundle="optical")
    store.connect(src2, "o2", arms[2], "o1", attachment=AttachmentKind.ROUTED, bundle="optical")
    store.connect(src2, "o3", arms[3], "o1", attachment=AttachmentKind.ROUTED, bundle="optical")
    # Tie src2 into the same optical domain (zero-length conceptual — use tiny L later)
    store.connect(src, "o1", src2, "o1", attachment=AttachmentKind.BUTT_JOINT)

    sink_ports = ["o1", "o2", "o3", "o4"]
    for k, aid in enumerate(arms):
        store.connect(
            aid, "o2", sink, sink_ports[k],
            attachment=AttachmentKind.ROUTED, bundle="optical",
        )

    metrics = {}
    for k, aid in enumerate(arms):
        L = path_len_um[k]
        # launch edge
        if k < 2:
            metrics[(src, "o2" if k == 0 else "o3", aid, "o1")] = RouteMetrics(
                length_um=L / 2
            )
        else:
            metrics[(src2, "o2" if k == 2 else "o3", aid, "o1")] = RouteMetrics(
                length_um=L / 2
            )
        metrics[(aid, "o2", sink, sink_ports[k])] = RouteMetrics(length_um=L / 2)
    # butt joint src—src2: zero contribution
    apply_route_metrics(store, metrics)

    # Paths for SPA: each arm as reconvergent route into sink.
    # Path 0,1 from src; 2,3 from src2 — include src2 hop for 2,3.
    groups = {
        "quadrature": [
            [src, arms[0], sink],
            [src, arms[1], sink],
            [src, src2, arms[2], sink],
            [src, src2, arms[3], sink],
        ]
    }
    return store, groups


def _build_cases() -> List[TableVCase]:
    cases: List[TableVCase] = []
    balanced = 200.0

    for tid, name, dl in [
        (1, "MZI", (balanced, balanced)),
        (2, "MZM", (balanced, balanced)),
        (3, "Direct Modulator", (balanced, balanced)),
        (10, "2x2 Optical Switch", (balanced, balanced)),
    ]:
        store, groups = _mzi_pair(dl, prefix=f"t{tid}_")
        cases.append(TableVCase(tid, name, False, store, groups))

    # QPSK / 8-QAM: merged balanced MZMs
    qpsk_subs = [
        _mzi_pair((balanced, balanced), prefix="qpsk_i_"),
        _mzi_pair((balanced, balanced), prefix="qpsk_q_"),
    ]
    # rename groups
    s0, g0 = qpsk_subs[0]
    s1, g1 = qpsk_subs[1]
    store, _ = _merge_stores([(s0, {"I_arms": g0["arms"]}), (s1, {"Q_arms": g1["arms"]})])
    cases.append(
        TableVCase(
            4, "QPSK Modulator", False, store,
            {"I_arms": g0["arms"], "Q_arms": g1["arms"]},
        )
    )

    qam8 = []
    g8: Dict[str, Sequence[Sequence[str]]] = {}
    for bit in range(1, 4):
        sub, g = _mzi_pair((balanced, balanced), prefix=f"qam8_b{bit}_")
        qam8.append((sub, {f"bit{bit}": g["arms"]}))
        g8[f"bit{bit}"] = g["arms"]
    store, _ = _merge_stores(qam8)
    cases.append(TableVCase(5, "8-QAM Modulator", False, store, g8))

    # 64-QAM: matched-length group with planted Δφ ≈ 0.2 rad on one arm
    bad = balanced + _L_for_phase(0.2)
    store, groups = _mzi_pair((balanced, bad), prefix="qam64_")
    cases.append(TableVCase(6, "64-QAM Modulator", True, store, groups))

    for tid, name in [(7, "WDM Multiplexer"), (8, "WDM Demultiplexer")]:
        store, groups = _mzi_pair((balanced, balanced), prefix=f"t{tid}_")
        cases.append(TableVCase(tid, name, False, store, groups))

    # 90° Hybrid: four-path group, quadrature targets; plant EQUAL lengths
    # so geometry does not realize (0, π/2, π, 3π/2) → WNS < 0.
    store, groups = _hybrid_four_path(
        [balanced, balanced, balanced, balanced], prefix="hyb90_"
    )
    cases.append(
        TableVCase(
            9,
            "90-degree Optical Hybrid",
            True,
            store,
            groups,
            group_targets={"quadrature": HYBRID_90_TARGETS_RAD},
        )
    )

    for tid, name in [(19, "U-Matrix 2x2"), (20, "Clements 4x4")]:
        store, groups = _mzi_pair((balanced, balanced), prefix=f"t{tid}_")
        cases.append(TableVCase(tid, name, False, store, groups))

    assert len(cases) == 12, len(cases)
    return cases


def run_experiment(tol_rad: float = TOL_RAD) -> int:
    cases = _build_cases()
    print("SPA × Table V — COMPARATOR TEST (planted L → φ → WNS), not layout evidence")
    print(f"tol={tol_rad} rad  |  headline = WNS (min pair slack)")
    print(
        f"{'task':<4} {'name':<28} {'WNS':>10} {'n_pairs':>8} "
        f"{'expect':>8} {'got':>8}"
    )
    print("-" * 78)

    ok_count = 0
    mismatches: List[str] = []
    for case in sorted(cases, key=lambda c: c.task_id):
        report = spa_analyze(
            case.store,
            case.groups,
            tolerance_rad=tol_rad,
            group_targets=case.group_targets,
        )
        wns = report.wns_rad
        n_pairs = sum(len(g.pair_slacks) for g in report.groups)
        negative = wns < 0
        expect = "NEG" if case.expect_negative else "non-NEG"
        got = "NEG" if negative else "non-NEG"
        match = negative == case.expect_negative
        if match:
            ok_count += 1
        else:
            mismatches.append(
                f"task {case.task_id} {case.name}: expected {expect}, got {got} "
                f"(WNS={wns:.4f})"
            )
        flag = "OK" if match else "MISS"
        print(
            f"{case.task_id:<4} {case.name:<28} {wns:10.4f} {n_pairs:8d} "
            f"{expect:>8} {got:>8}  {flag}"
        )

    print("-" * 78)
    print(f"Comparator match: {ok_count}/{len(cases)}")
    if mismatches:
        for m in mismatches:
            print(f"  - {m}")
        return 1
    print(
        "VERDICT: comparator GREEN — metric sign/WNS OK on planted φ; "
        "not evidence for N3 from layout"
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_experiment())
