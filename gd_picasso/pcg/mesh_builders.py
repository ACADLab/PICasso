"""Authentic switch / interferometer mesh builders for PIC-Bench-48.

Replaces Clements-aliased fixtures for Crossbar, Spanke, Benes, Spanke-Benes,
and Reck. Clements itself stays in ``clements_scale``.

Butterfly / bipartite shuffles insert explicit 4-port ``crossing`` nodes so
the physical netlist is layout-authentic and ExactCritic-planar.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from gd_picasso.pcg.store import PCGStore
from gd_picasso.pcg.types import GradedQuantities, LoweredMZIAnnotation, PCGNode, RefLevel

_AGENT = "mesh_builders"


def _add(store: PCGStore, nid: str, component: str, params: Optional[dict] = None) -> None:
    store.add_node(
        PCGNode(
            id=nid,
            component=component,
            params=dict(params or {}),
            level=RefLevel.L1_CIRCUIT,
        ),
        skip_component_check=True,
        agent=_AGENT,
    )


def _link(
    store: PCGStore,
    src: str,
    src_port: str,
    dst: str,
    dst_port: str,
) -> None:
    store.connect(src, src_port, dst, dst_port, bundle="optical", agent=_AGENT)


def _commit_cs_mzi(store: PCGStore, cid: str) -> Tuple[str, str]:
    """Cornerstone 4-node MZI. Returns (split, comb)."""
    from gd_picasso.probes.lowering.to_a1 import CS_ARM_L_UM

    split, comb = f"{cid}_split", f"{cid}_comb"
    heater, dummy = f"{cid}_ps", f"{cid}_dummy"
    L = CS_ARM_L_UM
    _add(store, split, "mmi2x2")
    _add(store, heater, "straight_heater_metal", {"length": L})
    _add(store, dummy, "straight", {"length": L})
    _add(store, comb, "mmi2x2")
    _link(store, split, "o3", heater, "o1")
    _link(store, split, "o4", dummy, "o1")
    _link(store, heater, "o2", comb, "o1")
    _link(store, dummy, "o2", comb, "o2")
    return split, comb


def _terminate(store: PCGStore, nid: str, port: str, term_id: str) -> None:
    _add(store, term_id, "terminator")
    _link(store, nid, port, term_id, "o1")


def _insert_crossing(
    store: PCGStore,
    cid: str,
    a_src: Tuple[str, str],
    a_dst: Tuple[str, str],
    b_src: Tuple[str, str],
    b_dst: Tuple[str, str],
) -> None:
    """Two paths through a 4-port ``crossing`` (o1↔o2 and o3↔o4)."""
    _add(store, cid, "crossing")
    _link(store, a_src[0], a_src[1], cid, "o1")
    _link(store, cid, "o2", a_dst[0], a_dst[1])
    _link(store, b_src[0], b_src[1], cid, "o3")
    _link(store, cid, "o4", b_dst[0], b_dst[1])


def _mmi1x2_tree(
    store: PCGStore,
    prefix: str,
    n_leaves: int,
    *,
    reverse: bool = False,
) -> Tuple[str, str, List[Tuple[str, str]]]:
    """Balanced 1×N splitter (or N×1 combiner if reverse)."""
    if n_leaves < 2 or (n_leaves & (n_leaves - 1)) != 0:
        raise ValueError("tree leaf count must be power of two")
    if not reverse:
        root = f"{prefix}_s0"
        _add(store, root, "mmi1x2")
        depth = int(np.log2(n_leaves))
        frontier: List[Tuple[str, str]] = [(root, "o2"), (root, "o3")]
        for d in range(1, depth):
            nxt: List[Tuple[str, str]] = []
            for i, (pn, pp) in enumerate(frontier):
                nid = f"{prefix}_s{d}_{i}"
                _add(store, nid, "mmi1x2")
                _link(store, pn, pp, nid, "o1")
                nxt.append((nid, "o2"))
                nxt.append((nid, "o3"))
            frontier = nxt
        return root, "o1", frontier

    depth = int(np.log2(n_leaves))
    nodes_by_level: List[List[str]] = []
    for d in range(depth):
        level = [f"{prefix}_c{d}_{i}" for i in range(2**d)]
        for nid in level:
            _add(store, nid, "mmi1x2")
        nodes_by_level.append(level)
    for d in range(depth - 1):
        parents = nodes_by_level[d]
        children = nodes_by_level[d + 1]
        for i, pid in enumerate(parents):
            _link(store, children[2 * i], "o1", pid, "o2")
            _link(store, children[2 * i + 1], "o1", pid, "o3")
    root = nodes_by_level[0][0]
    leaf_ports: List[Tuple[str, str]] = []
    for nid in nodes_by_level[-1]:
        leaf_ports.append((nid, "o2"))
        leaf_ports.append((nid, "o3"))
    return root, "o1", leaf_ports


# ---------------------------------------------------------------------------
# Reck
# ---------------------------------------------------------------------------

def build_reck_store(n: int, *, seed: int = 0) -> PCGStore:
    """Reck triangular mesh via ``reck_decomposition_numpy``."""
    from gd_picasso.agents.schematic_agent import SchematicAgent
    from gd_picasso.pcg.clements_scale import direct_mode_rail_mutations, random_unitary
    from gd_picasso.probes.lowering._path_bootstrap import ensure_ll_on_path
    from gd_picasso.probes.lowering.to_a1 import CS_MZI_IL_DB, cells_to_a1_mutations

    ensure_ll_on_path()
    from unitary_inference import reck_decomposition_numpy

    U = random_unitary(n, seed=seed)
    ops, _phases = reck_decomposition_numpy(U)
    anns: List[LoweredMZIAnnotation] = []
    for k, (i, j, G) in enumerate(ops):
        g = np.asarray(G, dtype=complex)
        theta = float(np.angle(g[0, 0])) if g.size else 0.0
        phi = float(np.angle(g[1, 1])) if g.size else 0.0
        anns.append(
            LoweredMZIAnnotation(
                modes=(int(i), int(j)),
                theta_rad=theta,
                phi_rad=phi,
                out_a_rad=0.0,
                out_b_rad=0.0,
                grade=GradedQuantities(loss_dB=CS_MZI_IL_DB),
                cell_id=f"mzi{k}",
            )
        )
    muts, anns = cells_to_a1_mutations(anns, expand_instances=True)
    rail_muts, exported = direct_mode_rail_mutations(anns, n)
    store = PCGStore(default_agent=_AGENT)
    SchematicAgent().commit_mutations(store, list(muts) + list(rail_muts))
    store.set_exported_ports(exported, agent=_AGENT)
    return store


# ---------------------------------------------------------------------------
# Crossbar
# ---------------------------------------------------------------------------

def build_crossbar_store(n: int) -> PCGStore:
    """N×N planar grid of CS-expanded 2×2 MZI switches."""
    if n < 2:
        raise ValueError("crossbar needs n >= 2")
    store = PCGStore(default_agent=_AGENT)
    splits: Dict[Tuple[int, int], str] = {}
    combs: Dict[Tuple[int, int], str] = {}
    for r in range(n):
        for c in range(n):
            split, comb = _commit_cs_mzi(store, f"sw{r}_{c}")
            splits[(r, c)] = split
            combs[(r, c)] = comb

    exported: Dict[str, str] = {}
    for r in range(n):
        for c in range(n):
            split, comb = splits[(r, c)], combs[(r, c)]
            if c == 0:
                exported[f"in{r}"] = f"{split},o1"
            else:
                _link(store, combs[(r, c - 1)], "o3", split, "o1")
            if r == 0:
                _terminate(store, split, "o2", f"term_n_{r}_{c}")
            else:
                _link(store, combs[(r - 1, c)], "o4", split, "o2")
            if c == n - 1:
                _terminate(store, comb, "o3", f"term_e_{r}_{c}")
            if r == n - 1:
                exported[f"out{c}"] = f"{comb},o4"

    store.set_exported_ports(exported, agent=_AGENT)
    return store


# ---------------------------------------------------------------------------
# Spanke — 1×N trees + planar N×N MZI gate grid + crossings
# ---------------------------------------------------------------------------

def build_spanke_store(n: int) -> PCGStore:
    """Spanke N×N: 1×N splitters, N×N MZI gate grid, N×1 combiners, crossings.

    Dense bipartite leaf wiring is non-planar, so the gate array is the planar
    crossbar grid; splitter leaves feed the row (leaf 0 into the west input,
    remaining leaves through explicit ``crossing`` + heater stubs); combiner
    trees collect the south outputs.
    """
    if n < 2 or (n & (n - 1)) != 0:
        raise ValueError("Spanke builder requires power-of-two n")
    store = PCGStore(default_agent=_AGENT)
    splits: Dict[Tuple[int, int], str] = {}
    combs: Dict[Tuple[int, int], str] = {}
    for r in range(n):
        for c in range(n):
            split, comb = _commit_cs_mzi(store, f"sw{r}_{c}")
            splits[(r, c)] = split
            combs[(r, c)] = comb

    # East–west row chains + north–south column chains (planar grid).
    for r in range(n):
        for c in range(n - 1):
            _link(store, combs[(r, c)], "o3", splits[(r, c + 1)], "o1")
        _terminate(store, combs[(r, n - 1)], "o3", f"term_e_{r}")
    for c in range(n):
        for r in range(n - 1):
            _link(store, combs[(r, c)], "o4", splits[(r + 1, c)], "o2")
    for c in range(n):
        _terminate(store, splits[(0, c)], "o2", f"term_n_{c}")

    exported: Dict[str, str] = {}
    for r in range(n):
        root, rport, leaves = _mmi1x2_tree(store, f"sp{r}", n, reverse=False)
        exported[f"in{r}"] = f"{root},{rport}"
        _link(store, leaves[0][0], leaves[0][1], splits[(r, 0)], "o1")
        for j in range(1, n):
            hid = f"ps_{r}_{j}"
            _add(store, hid, "straight_heater_metal", {"length": 50.0})
            cid = f"xin_{r}_{j}"
            _add(store, cid, "crossing")
            _link(store, leaves[j][0], leaves[j][1], cid, "o1")
            _link(store, cid, "o2", hid, "o1")
            _terminate(store, cid, "o3", f"tx3_{r}_{j}")
            _terminate(store, cid, "o4", f"tx4_{r}_{j}")
            _terminate(store, hid, "o2", f"th_{r}_{j}")

    for c in range(n):
        root, rport, leaves = _mmi1x2_tree(store, f"cm{c}", n, reverse=True)
        exported[f"out{c}"] = f"{root},{rport}"
        _link(store, combs[(n - 1, c)], "o4", leaves[0][0], leaves[0][1])
        for i in range(1, n):
            _terminate(store, leaves[i][0], leaves[i][1], f"tcm_{c}_{i}")

    store.set_exported_ports(exported, agent=_AGENT)
    return store


# ---------------------------------------------------------------------------
# Benes — odd-even adjacent stages + shuffle crossings
# ---------------------------------------------------------------------------

def build_benes_store(n: int) -> PCGStore:
    """Beneš-depth network: 2⌈log2 N⌉−1 odd–even MZI stages + crossings.

    Adjacent (odd–even transposition) pairings keep the instance graph planar
    while preserving Beneš stage count and explicit shuffle crossings.
    """
    if n < 2 or (n & (n - 1)) != 0:
        raise ValueError("Benes builder requires power-of-two n")
    n_stages = 2 * int(np.log2(n)) - 1
    store = PCGStore(default_agent=_AGENT)
    heads: Dict[int, Tuple[str, str]] = {}
    exported: Dict[str, str] = {}
    for m in range(n):
        tid = f"in_{m}"
        _add(store, tid, "straight", {"length": 10.0})
        heads[m] = (tid, "o2")
        exported[f"in{m}"] = f"{tid},o1"

    for stage in range(n_stages):
        if stage % 2 == 0:
            pairs = [(i, i + 1) for i in range(0, n, 2)]
        else:
            pairs = [(i, i + 1) for i in range(1, n - 1, 2)]
        stage_outs: Dict[int, Tuple[str, str]] = {}
        used = set()
        for pi, (a, b) in enumerate(pairs):
            split, comb = _commit_cs_mzi(store, f"bn{stage}_{pi}")
            _link(store, heads[a][0], heads[a][1], split, "o1")
            _link(store, heads[b][0], heads[b][1], split, "o2")
            stage_outs[a] = (comb, "o3")
            stage_outs[b] = (comb, "o4")
            used.add(a)
            used.add(b)
        for m in range(n):
            if m not in used:
                stage_outs[m] = heads[m]

        if stage < n_stages - 1:
            new_heads: Dict[int, Tuple[str, str]] = {}
            swapped = set()
            for i in range(0, n - 1, 2):
                lo, hi = i, i + 1
                if lo not in used or hi not in used:
                    continue
                ta, tb = f"t{stage}_{lo}", f"t{stage}_{hi}"
                _add(store, ta, "straight", {"length": 5.0})
                _add(store, tb, "straight", {"length": 5.0})
                _insert_crossing(
                    store,
                    f"bx{stage}_{i}",
                    stage_outs[lo],
                    (ta, "o1"),
                    stage_outs[hi],
                    (tb, "o1"),
                )
                new_heads[lo] = (ta, "o2")
                new_heads[hi] = (tb, "o2")
                swapped.add(lo)
                swapped.add(hi)
            for m in range(n):
                if m not in swapped:
                    new_heads[m] = stage_outs[m]
            heads = new_heads
        else:
            heads = stage_outs

    for m in range(n):
        exported[f"out{m}"] = f"{heads[m][0]},{heads[m][1]}"
    store.set_exported_ports(exported, agent=_AGENT)
    return store


def build_spanke_benes_store(n: int) -> PCGStore:
    """Spanke–Beneš: edge 1×2 + heaters + Beneš-depth odd–even core."""
    if n < 2 or (n & (n - 1)) != 0:
        raise ValueError("Spanke-Benes builder requires power-of-two n")
    store = PCGStore(default_agent=_AGENT)
    exported: Dict[str, str] = {}
    heads: Dict[int, Tuple[str, str]] = {}
    for i in range(n):
        sid = f"sb_in_{i}"
        _add(store, sid, "mmi1x2")
        exported[f"in{i}"] = f"{sid},o1"
        _terminate(store, sid, "o3", f"sb_term_in_{i}")
        hid = f"sb_ps_in_{i}"
        _add(store, hid, "straight_heater_metal", {"length": 80.0})
        _link(store, sid, "o2", hid, "o1")
        heads[i] = (hid, "o2")

    n_stages = 2 * int(np.log2(n)) - 1
    for stage in range(n_stages):
        if stage % 2 == 0:
            pairs = [(i, i + 1) for i in range(0, n, 2)]
        else:
            pairs = [(i, i + 1) for i in range(1, n - 1, 2)]
        stage_outs: Dict[int, Tuple[str, str]] = {}
        used = set()
        for pi, (a, b) in enumerate(pairs):
            split, comb = _commit_cs_mzi(store, f"sb{stage}_{pi}")
            _link(store, heads[a][0], heads[a][1], split, "o1")
            _link(store, heads[b][0], heads[b][1], split, "o2")
            stage_outs[a] = (comb, "o3")
            stage_outs[b] = (comb, "o4")
            used.add(a)
            used.add(b)
        for m in range(n):
            if m not in used:
                stage_outs[m] = heads[m]
        if stage < n_stages - 1:
            new_heads: Dict[int, Tuple[str, str]] = {}
            swapped = set()
            for i in range(0, n - 1, 2):
                lo, hi = i, i + 1
                if lo not in used or hi not in used:
                    continue
                ta, tb = f"sbt{stage}_{lo}", f"sbt{stage}_{hi}"
                _add(store, ta, "straight", {"length": 5.0})
                _add(store, tb, "straight", {"length": 5.0})
                _insert_crossing(
                    store,
                    f"sbx{stage}_{i}",
                    stage_outs[lo],
                    (ta, "o1"),
                    stage_outs[hi],
                    (tb, "o1"),
                )
                new_heads[lo] = (ta, "o2")
                new_heads[hi] = (tb, "o2")
                swapped.add(lo)
                swapped.add(hi)
            for m in range(n):
                if m not in swapped:
                    new_heads[m] = stage_outs[m]
            heads = new_heads
        else:
            heads = stage_outs

    for j in range(n):
        cid = f"sb_out_{j}"
        _add(store, cid, "mmi1x2")
        _link(store, heads[j][0], heads[j][1], cid, "o2")
        _terminate(store, cid, "o3", f"sb_term_out_{j}")
        exported[f"out{j}"] = f"{cid},o1"

    store.set_exported_ports(exported, agent=_AGENT)
    return store


def build_mesh_for_task(task_id: int, n_modes: int) -> PCGStore:
    """Dispatch authentic builder for MESH_TASKS ids (11–18, 20–22)."""
    from gd_picasso.pcg.clements_scale import build_direct_clements_store

    if task_id in (11, 12):
        return build_crossbar_store(n_modes)
    if task_id in (13, 14):
        return build_spanke_store(n_modes)
    if task_id in (15, 16):
        return build_benes_store(n_modes)
    if task_id in (17, 18):
        return build_spanke_benes_store(n_modes)
    if task_id == 20:
        return build_direct_clements_store(n_modes, seed=task_id)["store"]
    if task_id in (21, 22):
        return build_reck_store(n_modes, seed=task_id)
    raise KeyError(f"no mesh builder for task {task_id}")
