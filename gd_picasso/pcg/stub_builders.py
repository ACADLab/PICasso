"""Deterministic GF PCGStore builders for former PIC-Set LiDAR stubs.

Tasks 5–8, 23–25, 28, 31 become real ExactCritic-passing circuits (topology
proxies — not spectral/constellation oracles).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from gd_picasso.pcg.mesh_builders import _add, _commit_cs_mzi, _link, _terminate
from gd_picasso.pcg.store import PCGStore
from gd_picasso.pcg.types import EdgeLayer

_AGENT = "stub_builders"


def _export(store: PCGStore, ports: Dict[str, str]) -> None:
    store.set_exported_ports(ports, agent=_AGENT)


def _export_dangling(store: PCGStore) -> None:
    connected = set()
    for edge in store.edges:
        if edge.layer != EdgeLayer.OPTICAL:
            continue
        connected.add((edge.src_node, edge.src_port))
        connected.add((edge.dst_node, edge.dst_port))
    exported: Dict[str, str] = {}
    k = 0
    for nid, node in store.nodes.items():
        for pname, port in node.ports.items():
            if port.kind.value != "OPTICAL":
                continue
            if (nid, pname) in connected:
                continue
            exported[f"io{k}"] = f"{nid},{pname}"
            k += 1
    store.set_exported_ports(exported, agent=_AGENT)


def _add_mzm(store: PCGStore, prefix: str) -> Tuple[str, str, str]:
    """Dual-drive MZM: mmi1x2 → 2 heaters → mmi2x2. Returns (split, comb, unused)."""
    split, c_ps_a, c_ps_b, comb = (
        f"{prefix}_sp",
        f"{prefix}_psa",
        f"{prefix}_psb",
        f"{prefix}_cb",
    )
    _add(store, split, "mmi1x2")
    _add(store, c_ps_a, "straight_heater_metal", {"length": 320.0})
    _add(store, c_ps_b, "straight_heater_metal", {"length": 320.0})
    _add(store, comb, "mmi2x2")
    _link(store, split, "o2", c_ps_a, "o1")
    _link(store, split, "o3", c_ps_b, "o1")
    _link(store, c_ps_a, "o2", comb, "o1")
    _link(store, c_ps_b, "o2", comb, "o2")
    return split, comb, "o1"


def build_qam8_modulator() -> PCGStore:
    """Task 5: 8-QAM — three MZM leaves combined with MMI tree."""
    store = PCGStore(default_agent=_AGENT)
    exported: Dict[str, str] = {}
    leaves = []
    for i in range(3):
        split, comb, _ = _add_mzm(store, f"mzm{i}")
        exported[f"in{i}"] = f"{split},o1"
        leaves.append(comb)
        # Export one MZM output; terminate the other
        _terminate(store, comb, "o4", f"term_mzm{i}")
    # Combine three MZM o3 ports via two mmi1x2 used as 2→1 (o2/o3 in, o1 out)
    _add(store, "mix0", "mmi1x2")
    _add(store, "mix1", "mmi1x2")
    _link(store, leaves[0], "o3", "mix0", "o2")
    _link(store, leaves[1], "o3", "mix0", "o3")
    _link(store, "mix0", "o1", "mix1", "o2")
    _link(store, leaves[2], "o3", "mix1", "o3")
    exported["out"] = "mix1,o1"
    _export(store, exported)
    return store


def build_qam64_modulator() -> PCGStore:
    """Task 6: 64-QAM — seven MZMs in a binary combining tree."""
    store = PCGStore(default_agent=_AGENT)
    exported: Dict[str, str] = {}
    # frontier entries are (node_id, free_output_port)
    frontier: List[Tuple[str, str]] = []
    for i in range(7):
        split, comb, _ = _add_mzm(store, f"mzm{i}")
        exported[f"in{i}"] = f"{split},o1"
        _terminate(store, comb, "o4", f"term_mzm{i}")
        frontier.append((comb, "o3"))
    stage = 0
    while len(frontier) > 1:
        nxt: List[Tuple[str, str]] = []
        i = 0
        while i < len(frontier):
            if i + 1 < len(frontier):
                mid = f"mix{stage}_{i}"
                _add(store, mid, "mmi1x2")
                a_n, a_p = frontier[i]
                b_n, b_p = frontier[i + 1]
                _link(store, a_n, a_p, mid, "o2")
                _link(store, b_n, b_p, mid, "o3")
                nxt.append((mid, "o1"))
                i += 2
            else:
                nxt.append(frontier[i])
                i += 1
        frontier = nxt
        stage += 1
    last_n, last_p = frontier[0]
    exported["out"] = f"{last_n},{last_p}"
    _export(store, exported)
    return store


def build_cascaded_mzi_lattice(n_stages: int = 4, *, prefix: str = "lat") -> PCGStore:
    """Cascaded MZI lattice (Tasks 7/8/25 WDM topology proxies)."""
    store = PCGStore(default_agent=_AGENT)
    prev_split = None
    exported: Dict[str, str] = {}
    drop_ports: List[Tuple[str, str]] = []
    for s in range(n_stages):
        split, comb = _commit_cs_mzi(store, f"{prefix}{s}")
        if s == 0:
            exported["in0"] = f"{split},o1"
            _terminate(store, split, "o2", f"{prefix}_term_in")
        else:
            assert prev_split is not None
            # previous through → this stage
            _link(store, prev_split[0], prev_split[1], split, "o1")
            _terminate(store, split, "o2", f"{prefix}_term_{s}")
        # through continues on o3; drop on o4
        drop_ports.append((comb, "o4"))
        prev_split = (comb, "o3")
    exported["through"] = f"{prev_split[0]},{prev_split[1]}"
    for i, (nid, port) in enumerate(drop_ports):
        exported[f"drop{i}"] = f"{nid},{port}"
    _export(store, exported)
    return store


def build_ring_add_drop() -> PCGStore:
    """Task 23: ring add-drop — coupler + ring_single feedback + through/drop."""
    store = PCGStore(default_agent=_AGENT)
    _add(store, "c1", "coupler")
    _add(store, "ring", "ring_single", {"radius": 10.0, "gap": 0.2})
    _add(store, "c2", "coupler")
    _link(store, "c1", "o2", "c2", "o1")
    _link(store, "c1", "o3", "ring", "o1")
    _link(store, "ring", "o2", "c2", "o3")
    _terminate(store, "c1", "o4", "term_c1")
    _export(store, {"in": "c1,o1", "through": "c2,o2", "drop": "c2,o4"})
    return store


def build_dual_ring_filter() -> PCGStore:
    """Task 24: dual-ring tunable filter with heaters on coupling gaps."""
    store = PCGStore(default_agent=_AGENT)
    _add(store, "c1", "coupler")
    _add(store, "r1", "ring_single", {"radius": 10.0})
    _add(store, "ps1", "straight_heater_metal", {"length": 50.0})
    _add(store, "r2", "ring_single", {"radius": 12.0})
    _add(store, "ps2", "straight_heater_metal", {"length": 50.0})
    _add(store, "c2", "coupler")
    _link(store, "c1", "o2", "ps1", "o1")
    _link(store, "ps1", "o2", "c2", "o1")
    _link(store, "c1", "o3", "r1", "o1")
    _link(store, "r1", "o2", "ps2", "o1")
    _link(store, "ps2", "o2", "r2", "o1")
    _link(store, "r2", "o2", "c2", "o3")
    _terminate(store, "c1", "o4", "term_c1")
    _export(store, {"in": "c1,o1", "through": "c2,o2", "drop": "c2,o4"})
    return store


def build_awg_demux_16() -> PCGStore:
    """Task 28: 16-channel AWG proxy — input star + 16 array WGs + output star.

    Each array waveguide feeds both a channel export (via ``mmi1x2`` tap) and
    the output star-coupler leaf so the dual-slab AWG stays one connected
    component.
    """
    from gd_picasso.pcg.mesh_builders import _mmi1x2_tree

    store = PCGStore(default_agent=_AGENT)
    root, rport, leaves = _mmi1x2_tree(store, "awg_in", 16, reverse=False)
    exported: Dict[str, str] = {"in": f"{root},{rport}"}
    out_root, out_port, out_leaves = _mmi1x2_tree(store, "awg_out", 16, reverse=True)
    _terminate(store, out_root, out_port, "awg_out_term")
    for i, (ln, lp) in enumerate(leaves):
        wid = f"awg_wg_{i}"
        _add(store, wid, "straight", {"length": float(100 + 10 * i)})
        _link(store, ln, lp, wid, "o1")
        tap = f"awg_tap_{i}"
        _add(store, tap, "mmi1x2")
        _link(store, wid, "o2", tap, "o1")
        exported[f"out{i}"] = f"{tap},o2"
        _link(store, tap, "o3", out_leaves[i][0], out_leaves[i][1])
    _export(store, exported)
    return store


def build_wss_1x8() -> PCGStore:
    """Task 31: 1×8 thermo-optic WSS — binary MZI tree with heaters."""
    store = PCGStore(default_agent=_AGENT)
    # Depth-3 binary tree of CS MZIs: 7 MZIs for 8 outputs
    # Stage 0: 1 MZI, stage 1: 2, stage 2: 4
    exported: Dict[str, str] = {}
    # Root
    s0, c0 = _commit_cs_mzi(store, "wss0")
    exported["in"] = f"{s0},o1"
    _terminate(store, s0, "o2", "wss_term_root")

    def branch(parent_comb: str, parent_port: str, cid: str) -> Tuple[str, str]:
        sp, cb = _commit_cs_mzi(store, cid)
        _link(store, parent_comb, parent_port, sp, "o1")
        _terminate(store, sp, "o2", f"term_{cid}")
        return sp, cb

    _, c10 = branch(c0, "o3", "wss1_0")
    _, c11 = branch(c0, "o4", "wss1_1")
    leaves = []
    for idx, (pc, pp) in enumerate(
        ((c10, "o3"), (c10, "o4"), (c11, "o3"), (c11, "o4"))
    ):
        _, cb = branch(pc, pp, f"wss2_{idx}")
        leaves.append(cb)
    # Each leaf MZI has two outputs → 8 ports
    k = 0
    for cb in leaves:
        exported[f"out{k}"] = f"{cb},o3"
        k += 1
        exported[f"out{k}"] = f"{cb},o4"
        k += 1
    _export(store, exported)
    return store


def build_stub_task(task_id: int) -> PCGStore:
    """Dispatch builder for upgraded LiDAR-stub task ids."""
    if task_id == 5:
        return build_qam8_modulator()
    if task_id == 6:
        return build_qam64_modulator()
    if task_id == 7:
        return build_cascaded_mzi_lattice(4, prefix="wdm_mux")
    if task_id == 8:
        return build_cascaded_mzi_lattice(4, prefix="wdm_demux")
    if task_id == 23:
        return build_ring_add_drop()
    if task_id == 24:
        return build_dual_ring_filter()
    if task_id == 25:
        return build_cascaded_mzi_lattice(4, prefix="wdm_casc")
    if task_id == 28:
        return build_awg_demux_16()
    if task_id == 31:
        return build_wss_1x8()
    raise KeyError(task_id)
