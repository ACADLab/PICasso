"""
Clements mesh scaling setup — ≥16×16 (compute wall-clock separate).

Builds parameter counts / MZI cell counts for N=4..32 and a smoke lower for
N=4; N≥16 is setup-only here (hours of compute on full FoM).

Also materializes real expanded PCG fixtures (4×4 / 8×8) via
``cells_to_a1_mutations(..., expand_instances=True)`` so Paper B can drop
4-node mesh proxies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class ClementsScaleRow:
    n: int
    n_mzi: int
    n_heaters_naive: int
    n_params_l3: int


def clements_mzi_count(n: int) -> int:
    """Number of 2×2 blocks in a Clements triangular mesh for N modes."""
    # Clements: N(N-1)/2 MZIs
    return n * (n - 1) // 2


def scale_table(ns: List[int] | None = None) -> List[ClementsScaleRow]:
    ns = ns or [4, 8, 16, 32]
    rows = []
    for n in ns:
        mzi = clements_mzi_count(n)
        heaters = 3 * mzi + n  # naive upper bound from FINDINGS
        # L3 params: theta, phi per MZI (+ optional out phases folded)
        params = 2 * mzi
        rows.append(
            ClementsScaleRow(
                n=n, n_mzi=mzi, n_heaters_naive=heaters, n_params_l3=params
            )
        )
    return rows


def random_unitary(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))
    q, r = np.linalg.qr(z)
    # Make Q uniquely unitary with positive diagonal of R
    d = np.sign(np.real(np.diag(r)))
    d = np.where(d == 0, 1.0, d)
    q = q * d
    return q


def setup_clements_16() -> Dict[str, object]:
    """Materialize N=16 unitary + mesh size metadata (no full FoM train)."""
    U = random_unitary(16, seed=16)
    row = scale_table([16])[0]
    return {
        "n": 16,
        "unitary_shape": U.shape,
        "unitary_err_eye": float(np.linalg.norm(U.conj().T @ U - np.eye(16))),
        "n_mzi": row.n_mzi,
        "n_params_l3": row.n_params_l3,
        "ready_for_compute": True,
        "note": "Full SAX/Clements FoM for 16×16 is hours of wall-clock; setup only.",
    }


def clements_lower_smoke(n: int = 8, *, seed: int = 0) -> Dict[str, float]:
    """Real Clements lower+rebuild for N modes (N=8 smoke; N=16 is slow).

    Uses vendored ``unitary_inference.clements_decomposition`` via ``lower``.
    """
    from gd_picasso.probes.lowering._path_bootstrap import ensure_ll_on_path

    ensure_ll_on_path()
    from lower import lower, rebuild  # flat import after bootstrap

    U = random_unitary(n, seed=seed)
    cells, D, N = lower(U)
    err = float(np.linalg.norm(rebuild(cells, D, N) - U))
    return {
        "n": float(n),
        "n_mzi": float(len(cells)),
        "rebuild_err": err,
    }


def _mode_rail_mutations(
    annotations: List[Any],
    n_modes: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Wire mode rails across expanded Clements MZIs + I/O terminals.

    Each expanded MZI ``{cid}_split`` / ``{cid}_comb`` uses mmi2x2 ports:
    inputs ``o1``/``o2`` (modes i/j), outputs ``o3``/``o4``.
    """
    muts: List[Dict[str, Any]] = []
    # Input terminals
    heads: Dict[int, Tuple[str, str]] = {}
    for m in range(n_modes):
        tid = f"in_{m}"
        muts.append(
            {
                "op": "add_node",
                "id": tid,
                "component": "straight",
                "params": {"length": 10.0},
            }
        )
        heads[m] = (tid, "o2")

    for ann in annotations:
        cid = ann.cell_id or f"mzi_{ann.modes[0]}_{ann.modes[1]}"
        i, j = int(ann.modes[0]), int(ann.modes[1])
        split, comb = f"{cid}_split", f"{cid}_comb"
        # Connect current rail heads into this MZI
        for mode, sport in ((i, "o1"), (j, "o2")):
            src_n, src_p = heads[mode]
            # Intermediate straight for explicit rail segment
            rail = f"rail_{cid}_m{mode}"
            muts.append(
                {
                    "op": "add_node",
                    "id": rail,
                    "component": "straight",
                    "params": {"length": 20.0},
                }
            )
            muts.append(
                {
                    "op": "connect",
                    "src": src_n,
                    "src_port": src_p,
                    "dst": rail,
                    "dst_port": "o1",
                    "bundle": "rail",
                }
            )
            muts.append(
                {
                    "op": "connect",
                    "src": rail,
                    "src_port": "o2",
                    "dst": split,
                    "dst_port": sport,
                    "bundle": "rail",
                }
            )
        # Update heads to combiner outputs
        heads[i] = (comb, "o3")
        heads[j] = (comb, "o4")

    exported: Dict[str, str] = {}
    for m in range(n_modes):
        tid = f"out_{m}"
        muts.append(
            {
                "op": "add_node",
                "id": tid,
                "component": "straight",
                "params": {"length": 10.0},
            }
        )
        src_n, src_p = heads[m]
        muts.append(
            {
                "op": "connect",
                "src": src_n,
                "src_port": src_p,
                "dst": tid,
                "dst_port": "o1",
                "bundle": "rail",
            }
        )
        exported[f"out{m}"] = f"{tid},o2"
        exported[f"in{m}"] = f"in_{m},o1"
    return muts, exported


def direct_mode_rail_mutations(
    annotations: List[Any],
    n_modes: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Connect Clements MZIs along mode rails without extra straight nodes.

    ``cells_to_a1`` expansion is 4 nodes per MZI (24 at N=4, 112 at N=8).
    Boundary splitter inputs and combiner outputs are exported instead of
    being tied to ``in_*`` / ``out_*`` terminals.
    """
    muts: List[Dict[str, Any]] = []
    exported: Dict[str, str] = {}
    heads: Dict[int, Optional[Tuple[str, str]]] = {m: None for m in range(n_modes)}
    for ann in annotations:
        cid = ann.cell_id or f"mzi_{ann.modes[0]}_{ann.modes[1]}"
        i, j = int(ann.modes[0]), int(ann.modes[1])
        split, comb = f"{cid}_split", f"{cid}_comb"
        for mode, sport in ((i, "o1"), (j, "o2")):
            head = heads[mode]
            if head is None:
                exported[f"in{mode}"] = f"{split},{sport}"
            else:
                src_n, src_p = head
                muts.append(
                    {
                        "op": "connect",
                        "src": src_n,
                        "src_port": src_p,
                        "dst": split,
                        "dst_port": sport,
                        "bundle": "rail",
                    }
                )
        heads[i] = (comb, "o3")
        heads[j] = (comb, "o4")
    for mode in range(n_modes):
        head = heads[mode]
        if head is None:
            raise RuntimeError(f"mode {mode} never entered the Clements mesh")
        src_n, src_p = head
        exported[f"out{mode}"] = f"{src_n},{src_p}"
    return muts, exported


def build_direct_clements_store(n: int, *, seed: int = 0) -> Dict[str, Any]:
    """Full-size Clements mesh: N(N-1)/2 MZIs, no proxy straights.

    N=4 → 24 nodes. N=8 → 112 nodes. Mode rails are direct port links.
    """
    from gd_picasso.agents.schematic_agent import SchematicAgent

    built = build_clements_pcg_store(n, seed=seed, wire_rails=False)
    expected = 4 * clements_mzi_count(n)
    if built["n_component_core"] != expected or built["n_mzi"] != clements_mzi_count(n):
        raise RuntimeError(
            f"Clements N={n} seed={seed} emitted {built['n_mzi']} MZIs, "
            f"expected {clements_mzi_count(n)}"
        )
    muts, exported = direct_mode_rail_mutations(built["annotations"], n)
    SchematicAgent().commit_mutations(built["store"], muts)
    built["store"].set_exported_ports(exported, agent="clements_scale")
    built["n_nodes"] = len(built["store"].nodes)
    built["n_edges"] = len(built["store"].edges)
    built["exported_ports"] = exported
    if built["n_nodes"] != expected:
        raise RuntimeError(
            f"direct Clements N={n} has {built['n_nodes']} nodes, expected {expected}"
        )
    return built


def build_clements_pcg_store(
    n: int,
    *,
    seed: int = 0,
    wire_rails: bool = True,
) -> Dict[str, Any]:
    """Lower a random NxN unitary → expanded CS-MZI PCGStore.

    Uses ``cells_to_a1_mutations(..., expand_instances=True)``. Each MZI
    expands to 4 component nodes (2×mmi2x2 + heater + dummy). For N=4 that
    is 6×4=24; for N=8 that is 28×4=112 (plus optional rail/I-O straights).
    """
    from gd_picasso.agents.schematic_agent import SchematicAgent
    from gd_picasso.pcg.store import PCGStore
    from gd_picasso.probes.lowering._path_bootstrap import ensure_ll_on_path
    from gd_picasso.probes.lowering.to_a1 import (
        annotations_from_mzicells,
        cells_to_a1_mutations,
    )

    ensure_ll_on_path()
    from lower import lower, rebuild

    U = random_unitary(n, seed=seed)
    cells, D, N = lower(U)
    assert int(N) == n
    rebuild_err = float(np.linalg.norm(rebuild(cells, D, N) - U))
    ann = annotations_from_mzicells(cells, prefix="mzi")
    muts, ann_out = cells_to_a1_mutations(ann, expand_instances=True)
    n_mzi = len(ann_out)
    n_component_core = 4 * n_mzi  # split, heater, dummy, comb per MZI

    exported: Dict[str, str] = {}
    if wire_rails:
        rail_muts, exported = _mode_rail_mutations(ann_out, n)
        muts = list(muts) + rail_muts

    store = PCGStore(default_agent="clements_scale")
    SchematicAgent().commit_mutations(store, muts)
    if exported:
        store.set_exported_ports(exported, agent="clements_scale")

    return {
        "store": store,
        "n": n,
        "n_mzi": n_mzi,
        "n_component_core": n_component_core,
        "n_nodes": len(store.nodes),
        "n_edges": len(store.edges),
        "rebuild_err": rebuild_err,
        "annotations": ann_out,
        "exported_ports": exported,
    }


def write_clements_fixture(
    n: int,
    out_path: Path,
    *,
    seed: int = 0,
    wire_rails: bool = True,
) -> Dict[str, Any]:
    """Build store and write GF-compatible YAML fixture."""
    from gd_picasso.pcg.bridge import to_gf_yaml

    built = build_clements_pcg_store(n, seed=seed, wire_rails=wire_rails)
    store = built["store"]
    yaml_text = to_gf_yaml(store)
    header = (
        f"# Clements {n}x{n} expanded CS-MZI mesh "
        f"(n_mzi={built['n_mzi']}, core_nodes={built['n_component_core']}).\n"
        f"# Generated via cells_to_a1_mutations(expand_instances=True); "
        f"seed={seed}.\n"
        f"# rebuild_err={built['rebuild_err']:.3e}. "
        f"Replaces 4-node mesh proxies for Paper B scaling.\n"
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + yaml_text)
    built["path"] = str(out_path)
    # Drop live store from serializable summary
    summary = {k: v for k, v in built.items() if k not in ("store", "annotations")}
    summary["path"] = str(out_path)
    summary["n_nodes"] = built["n_nodes"]
    summary["n_edges"] = built["n_edges"]
    return summary


def materialize_paper_b_clements_fixtures(
    fixtures_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Write 4×4 (24 core nodes) and 8×8 (112 core nodes) fixtures."""
    root = fixtures_dir or (
        Path(__file__).resolve().parent / "fixtures" / "clements"
    )
    out = {
        "4x4_core": write_clements_fixture(
            4, root / "clements_4x4_core.yaml", seed=4, wire_rails=False
        ),
        "8x8_core": write_clements_fixture(
            8, root / "clements_8x8_core.yaml", seed=8, wire_rails=False
        ),
        "4x4_mesh": write_clements_fixture(
            4, root / "clements_4x4_expanded.yaml", seed=4, wire_rails=True
        ),
        "8x8_mesh": write_clements_fixture(
            8, root / "clements_8x8_expanded.yaml", seed=8, wire_rails=True
        ),
    }
    return out


if __name__ == "__main__":
    import json

    report = materialize_paper_b_clements_fixtures()
    print(json.dumps(report, indent=2))
