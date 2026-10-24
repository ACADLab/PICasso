"""PIC-Bench-48 fixture builder.

Tasks 11–18 and 20–22 use topology-authentic builders in ``mesh_builders``
(Crossbar / Spanke / Benes / Spanke-Benes / Clements / Reck). Tasks 5–8,
23–25, 28, 31 are real GF PCGStore fixtures (former LiDAR stubs). Tasks
37–46 are formal stress circuits. Tasks 47–48 are gain specs rejected by
``psd_gate`` and are not written as YAML.

Run: ``python -m gd_picasso.pcg.build_formal_benchmarks``
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

from gd_picasso.pcg.bridge import from_gf_yaml, to_gf_yaml
from gd_picasso.pcg.store import PCGStore
from gd_picasso.pcg.types import EdgeLayer, PCGNode, RefLevel

PICSET = Path(__file__).resolve().parent / "fixtures" / "picset"

# Former LiDAR stubs — now real GF fixtures via stub_builders.
UPGRADED_STUB_TASKS = frozenset({5, 6, 7, 8, 23, 24, 25, 28, 31})
# Backward-compatible alias (empty: no LiDAR-only GF gaps remain).
LIDAR_ONLY_TASKS: frozenset = frozenset()
# Gain > 1. Encoded as specs only; psd_gate rejects them.
UNREALIZABLE_TASKS = frozenset({47, 48})

MESH_TASKS: Dict[int, Tuple[int, str]] = {
    11: (4, "Crossbar 4x4"),
    12: (8, "Crossbar 8x8"),
    13: (4, "Spanke 4x4"),
    14: (8, "Spanke 8x8"),
    15: (4, "Benes 4x4"),
    16: (8, "Benes 8x8"),
    17: (4, "Spanke-Benes 4x4"),
    18: (8, "Spanke-Benes 8x8"),
    20: (4, "Clements 4x4"),
    21: (4, "Reck 4x4 Mesh"),
    22: (8, "Reck 8x8 Mesh"),
}

MESH_TOPOLOGY_KIND = {
    11: "crossbar_grid",
    12: "crossbar_grid",
    13: "spanke_split_gate_combine",
    14: "spanke_split_gate_combine",
    15: "benes_odd_even",
    16: "benes_odd_even",
    17: "spanke_benes_hybrid",
    18: "spanke_benes_hybrid",
    20: "clements_decomposition",
    21: "reck_decomposition_numpy",
    22: "reck_decomposition_numpy",
}

# λλ specs copied from probes/lowering/lower.py CASES (not re-derived).
HADAMARD_4 = [
    "output(1) = (input(1)+input(2)+input(3)+input(4))/2",
    "output(2) = (input(1)-input(2)+input(3)-input(4))/2",
    "output(3) = (input(1)+input(2)-input(3)-input(4))/2",
    "output(4) = (input(1)-input(2)-input(3)+input(4))/2",
]
DFT_4 = [
    "output(1) = (input(1)+input(2)+input(3)+input(4))/2",
    "output(2) = (input(1)+I*input(2)-input(3)-I*input(4))/2",
    "output(3) = (input(1)-input(2)+input(3)-input(4))/2",
    "output(4) = (input(1)-I*input(2)-input(3)+I*input(4))/2",
]
# picset_specs.py infeasible probe, plus a second gain>1 line.
UNREALIZABLE_SPECS: Dict[int, Tuple[int, List[str]]] = {
    47: (1, ["output(1) = 2*input(1)"]),
    48: (1, ["output(1) = 1.5*input(1)"]),
}


@dataclass(frozen=True)
class BenchTask:
    task_id: int
    name: str
    kind: str  # gf | unrealizable
    n_modes: Optional[int] = None
    n_nodes: Optional[int] = None


def picbench_catalog() -> List[BenchTask]:
    """48 slots: PIC-Set 1–36 plus formal stress 37–48."""
    names = {
        1: "MZI",
        2: "MZM",
        3: "Direct Modulator",
        4: "QPSK Modulator",
        5: "8-QAM Modulator",
        6: "64-QAM Modulator",
        7: "WDM Multiplexer",
        8: "WDM Demultiplexer",
        9: "90deg Hybrid",
        10: "2x2 Optical Switch",
        19: "U-matrix Block 2x2",
        23: "Ring Add-Drop",
        24: "Dual-Ring Tunable Filter",
        25: "4-Channel WDM Cascaded MZI",
        26: "Tunable 1x4 Optical Switch",
        27: "Balanced Coherent RX FE",
        28: "16-Channel AWG Demux",
        29: "2x2 Thermo-Optic Switch",
        30: "Y-Branch Power Splitter",
        31: "WSS 1x8",
        32: "2x2 PCM Switch",
        33: "Optical Delay Line",
        34: "Simple MMI 1x2",
        35: "Simple MMI 2x1",
        36: "Straight + Phase Shifter",
        37: "4x4 Hadamard",
        38: "4x4 DFT",
        39: "Multi-PDK straight to ebeam_y_adiabatic",
        40: "Multi-PDK mmi1x2 to ebeam_YBranch_895",
        41: "Multi-PDK straights to ebeam_DC_te895",
        42: "Multi-PDK straights to crossing_horizontal",
        43: "Multi-PDK straights to ANT_MMI_1x2",
        44: "Multi-PDK straight to ebeam_gc_te895",
        45: "Multi-PDK straights to ebeam_Polarizer_TM_1550",
        46: "Multi-PDK Clements 2x2 plus ebeam_y_adiabatic",
        47: "Unrealizable gain 2x",
        48: "Unrealizable gain 1.5x",
    }
    out: List[BenchTask] = []
    for task_id in range(1, 49):
        if task_id in UNREALIZABLE_TASKS:
            out.append(BenchTask(task_id, names[task_id], "unrealizable"))
        elif task_id in MESH_TASKS:
            n, name = MESH_TASKS[task_id]
            out.append(BenchTask(task_id, name, "gf", n_modes=n))
        else:
            out.append(BenchTask(task_id, names.get(task_id, f"task {task_id}"), "gf"))
    return out


def gf_fixture_path(task_id: int) -> Path:
    return PICSET / f"task_{task_id:02d}.yaml"


def saved_gf_tasks() -> List[BenchTask]:
    """Realizable tasks that have a GF ``task_XX.yaml`` (excludes unrealizable)."""
    return [t for t in picbench_catalog() if t.kind == "gf"]


def _save_store(store: PCGStore, task: BenchTask, *, note: str) -> Path:
    data = yaml.safe_load(to_gf_yaml(store))
    if not isinstance(data, dict):
        raise RuntimeError(f"task {task.task_id} serializer returned non-mapping")
    info = dict(data.get("info") or {})
    info.update(
        {
            "picset_task_id": task.task_id,
            "picset_name": task.name,
            "picbench": "PIC-Bench-48",
            "topology_kind": note,
        }
    )
    data["info"] = info
    path = gf_fixture_path(task.task_id)
    header = (
        f"# PIC-Bench-48 Task-{task.task_id:02d}: {task.name}\n"
        f"# {note}. Serialized by build_formal_benchmarks via to_gf_yaml.\n"
    )
    path.write_text(header + yaml.dump(data, default_flow_style=False, sort_keys=False))
    reloaded = from_gf_yaml(path.read_text())
    from gd_picasso.agents.exact_critic import ExactCritic
    from gd_picasso.bench.contracts import (
        contract_failures,
        evaluate_task_contract,
        get_task_contract,
    )

    critique = ExactCritic().review(reloaded)
    if not critique.ok:
        raise RuntimeError(
            f"task {task.task_id} failed ExactCritic after save: {critique.problems[:8]}"
        )
    contract = get_task_contract(task.task_id)
    if contract is not None and not evaluate_task_contract(reloaded, contract):
        raise RuntimeError(
            f"task {task.task_id} failed TaskContract after save: "
            f"{contract_failures(reloaded, contract)}"
        )
    return path


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
    store.set_exported_ports(exported, agent="picbench")


def _add(store: PCGStore, nid: str, component: str, params: Optional[dict] = None) -> None:
    store.add_node(
        PCGNode(
            id=nid,
            component=component,
            params=dict(params or {}),
            level=RefLevel.L1_CIRCUIT,
        ),
        skip_component_check=True,
        agent="picbench",
    )


def _stamp_siepic(store: PCGStore, nid: str, component: str) -> None:
    from gd_picasso.backends.siepic import PORT_WIDTH_UM

    widths = PORT_WIDTH_UM[component]
    node = store.nodes[nid]
    for pname, width in widths.items():
        port = node.ports.get(pname)
        if port is not None:
            port.width_um = float(width)


def build_store_from_spec(spec_lines: Sequence[str], n_inputs: int) -> PCGStore:
    """λλ spec → PSD-guarded unitary → Clements cells → direct-wired PCG."""
    import numpy as np
    import sympy as sp

    from gd_picasso.agents.schematic_agent import SchematicAgent
    from gd_picasso.pcg.clements_scale import direct_mode_rail_mutations
    from gd_picasso.probes.lowering._path_bootstrap import ensure_ll_on_path
    from gd_picasso.probes.lowering.to_a1 import (
        annotations_from_mzicells,
        cells_to_a1_mutations,
    )

    ensure_ll_on_path()
    from lower import lower
    from psd_gate import infer_guarded

    result = infer_guarded(list(spec_lines), n_inputs)
    unitary = np.array(sp.Matrix(result["U"]).evalf().tolist(), dtype=complex)
    cells, _d, n_modes = lower(unitary)
    annotations = annotations_from_mzicells(cells, prefix="mzi")
    mutations, annotations = cells_to_a1_mutations(annotations, expand_instances=True)
    rail_muts, exported = direct_mode_rail_mutations(annotations, int(n_modes))
    store = PCGStore(default_agent="picbench")
    SchematicAgent().commit_mutations(store, list(mutations) + rail_muts)
    store.set_exported_ports(exported, agent="picbench")
    return store


def reject_unrealizable(task_id: int) -> str:
    """Run psd_gate on a gain>1 spec. Returns the rejection message."""
    from gd_picasso.probes.lowering._path_bootstrap import ensure_ll_on_path

    ensure_ll_on_path()
    from psd_gate import infer_guarded

    n_inputs, spec = UNREALIZABLE_SPECS[task_id]
    try:
        infer_guarded(spec, n_inputs)
    except ValueError as exc:
        message = str(exc)
        if "unrealizable" not in message.lower() and "gain" not in message.lower():
            raise RuntimeError(f"task {task_id} rejected without a gain reason: {message}") from exc
        return message
    raise RuntimeError(f"task {task_id} spec was accepted; expected psd_gate rejection")


def _cs_straight(store: PCGStore, nid: str) -> None:
    _add(store, nid, "straight", {"length": 10.0})


def _link(store: PCGStore, src: str, src_port: str, dst: str, dst_port: str) -> None:
    store.connect(src, src_port, dst, dst_port, bundle="optical", agent="picbench")


def build_multipdk_store(task_id: int) -> PCGStore:
    """Cornerstone 500 nm ports tied to a SiEPIC cell whose ports are not 500 nm.

    ``add_tapers`` inserts the linear taper before the store is saved.
    """
    from gd_picasso.pcg.legalize import add_tapers

    store = PCGStore(default_agent="picbench")
    if task_id == 39:
        _cs_straight(store, "cs0")
        _add(store, "sie", "ebeam_y_adiabatic")
        _stamp_siepic(store, "sie", "ebeam_y_adiabatic")
        _link(store, "cs0", "o2", "sie", "o1")
    elif task_id == 40:
        _add(store, "cs_mmi", "mmi1x2")
        _add(store, "sie_a", "ebeam_YBranch_895")
        _add(store, "sie_b", "ebeam_YBranch_895")
        _stamp_siepic(store, "sie_a", "ebeam_YBranch_895")
        _stamp_siepic(store, "sie_b", "ebeam_YBranch_895")
        _link(store, "cs_mmi", "o2", "sie_a", "o1")
        _link(store, "cs_mmi", "o3", "sie_b", "o1")
    elif task_id == 41:
        _add(store, "sie", "ebeam_DC_te895")
        _stamp_siepic(store, "sie", "ebeam_DC_te895")
        for idx, port in enumerate(("o1", "o2", "o3", "o4")):
            nid = f"cs{idx}"
            _cs_straight(store, nid)
            _link(store, nid, "o2", "sie", port)
    elif task_id == 42:
        _add(store, "sie", "crossing_horizontal")
        _stamp_siepic(store, "sie", "crossing_horizontal")
        for idx, port in enumerate(("o1", "o2", "o3", "o4")):
            nid = f"cs{idx}"
            _cs_straight(store, nid)
            _link(store, nid, "o2", "sie", port)
    elif task_id == 43:
        _add(store, "sie", "ANT_MMI_1x2_te1550_3dB_BB")
        _stamp_siepic(store, "sie", "ANT_MMI_1x2_te1550_3dB_BB")
        _cs_straight(store, "cs_in")
        _cs_straight(store, "cs_a")
        _cs_straight(store, "cs_b")
        _link(store, "cs_in", "o2", "sie", "o1")
        _link(store, "sie", "o2", "cs_a", "o1")
        _link(store, "sie", "o3", "cs_b", "o1")
    elif task_id == 44:
        _cs_straight(store, "cs0")
        _add(store, "sie", "ebeam_gc_te895")
        _stamp_siepic(store, "sie", "ebeam_gc_te895")
        _link(store, "cs0", "o2", "sie", "o1")
    elif task_id == 45:
        _add(store, "sie", "ebeam_Polarizer_TM_1550_UQAM")
        _stamp_siepic(store, "sie", "ebeam_Polarizer_TM_1550_UQAM")
        _cs_straight(store, "cs0")
        _cs_straight(store, "cs1")
        _link(store, "cs0", "o2", "sie", "o1")
        _link(store, "sie", "o2", "cs1", "o1")
    elif task_id == 46:
        store = build_store_from_spec(
            ["output(1) = input(2)", "output(2) = input(1)"],
            2,
        )
        _add(store, "sie", "ebeam_y_adiabatic")
        _stamp_siepic(store, "sie", "ebeam_y_adiabatic")
        # Boundary combiner port from the 2×2 Clements cell.
        _link(store, "mzi0_comb", "o3", "sie", "o1")
    else:
        raise KeyError(task_id)

    inserted = add_tapers(store, agent="picbench")
    if not inserted:
        raise RuntimeError(f"task {task_id} did not insert a taper")
    _export_dangling(store)
    return store


def write_mesh_fixtures() -> List[Path]:
    from gd_picasso.pcg.mesh_builders import build_mesh_for_task

    paths = []
    for task_id, (n_modes, name) in MESH_TASKS.items():
        store = build_mesh_for_task(task_id, n_modes)
        task = BenchTask(
            task_id,
            name,
            "gf",
            n_modes=n_modes,
            n_nodes=len(store.nodes),
        )
        kind = MESH_TOPOLOGY_KIND[task_id]
        note = (
            f"authentic {kind} builder (N={n_modes}, nodes={len(store.nodes)}, "
            f"io={len(store.exported_ports)}); de-aliased from Clements proxies"
        )
        paths.append(_save_store(store, task, note=note))
    return paths


def write_upgraded_stub_fixtures() -> List[Path]:
    from gd_picasso.pcg.stub_builders import build_stub_task

    catalog = {t.task_id: t for t in picbench_catalog()}
    paths = []
    for task_id in sorted(UPGRADED_STUB_TASKS):
        store = build_stub_task(task_id)
        paths.append(
            _save_store(
                store,
                catalog[task_id],
                note="upgraded LiDAR stub → deterministic GF PCGStore topology proxy",
            )
        )
    return paths


def write_formal_stress_fixtures() -> List[Path]:
    paths = []
    hadamard = build_store_from_spec(HADAMARD_4, 4)
    paths.append(
        _save_store(
            hadamard,
            BenchTask(37, "4x4 Hadamard", "gf", n_modes=4, n_nodes=len(hadamard.nodes)),
            note="lambda_lambda Hadamard-4 spec -> clements -> cells_to_a1",
        )
    )
    dft = build_store_from_spec(DFT_4, 4)
    paths.append(
        _save_store(
            dft,
            BenchTask(38, "4x4 DFT", "gf", n_modes=4, n_nodes=len(dft.nodes)),
            note="lambda_lambda 4-point DFT spec -> clements -> cells_to_a1",
        )
    )
    catalog = {t.task_id: t for t in picbench_catalog()}
    for task_id in range(39, 47):
        store = build_multipdk_store(task_id)
        paths.append(
            _save_store(
                store,
                catalog[task_id],
                note="Cornerstone 500nm mixed with SiEPIC non-500nm ports; add_tapers",
            )
        )
    return paths


def write_picbench_fixtures() -> List[Path]:
    """Overwrite meshes, upgraded stubs, and tasks 37–46. Does not write 47–48."""
    for task_id in UNREALIZABLE_TASKS:
        stale = gf_fixture_path(task_id)
        if stale.is_file():
            stale.unlink()
    return (
        write_mesh_fixtures()
        + write_upgraded_stub_fixtures()
        + write_formal_stress_fixtures()
    )


if __name__ == "__main__":
    written = write_picbench_fixtures()
    for task_id in sorted(UNREALIZABLE_TASKS):
        message = reject_unrealizable(task_id)
        print(f"task {task_id} rejected: {message}")
    print(f"wrote {len(written)} fixtures")
