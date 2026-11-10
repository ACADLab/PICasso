"""Held-out functional oracle (n1-confirm-v3). Not used in any repair loop.

Thresholds and the applicable task list are frozen here. Do not retune after
looking at campaign outputs. Validate on golden fixtures before grading models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# Equal-split trees: each output within SPLIT_TOL_DB of ideal 1/N.
EQUAL_SPLIT_TASK_IDS: Tuple[int, ...] = (26, 30, 34)
SPLIT_TOL_DB: float = 0.5
# Ideal power fraction per output is 1/N. Compare in dB: 10*log10(P / (1/N)).

# Switch / mesh fabrics. Pass = permutation at reference phases (all heater
# phases left at the store's stored params; missing phase = 0), NOT all-to-all.
# All-to-all would fail a correct single-state crossbar.
# Tasks 13 (Spanke) and 17 (Spanke–Beneš) dropped in n1-confirm-v3: goldens
# fail the frozen permutation rule at stored/zero phases.
MESH_PERMUTATION_TASK_IDS: Tuple[int, ...] = (11, 15, 20, 21, 37, 38)
PERM_ON_MIN: float = 0.5  # |S|^2 on the claimed input→output entry
PERM_OFF_MAX: float = 0.1  # |S|^2 on every other entry of that row
PASSIVE_ROW_SUM_MAX: float = 1.0 + 1e-3

APPLICABLE_TASK_IDS: Tuple[int, ...] = EQUAL_SPLIT_TASK_IDS + MESH_PERMUTATION_TASK_IDS

# Ideal crossing: straight-through o1↔o3 and o2↔o4 (gdsfactory + gplugins).
# Ideal MZI: two 50/50 couplers with a differential phase on the upper arm.
# The oracle uses these ideal models, not the 0.7 dB/cm lossy factory.


def _as_complex(value: Any) -> complex:
    if hasattr(value, "item"):
        value = value.item()
    return complex(value)


def _phase_rad(settings: Dict[str, Any]) -> float:
    """Stored heater phase. Missing key → 0, per the freeze. Length is not phase."""
    for key in ("delta_phase_rad", "phase", "phi", "phi_rad"):
        if key in settings and settings[key] is not None:
            try:
                return float(settings[key])
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _ideal_through(**settings: Any) -> Dict[Tuple[str, str], complex]:
    import math

    phi = _phase_rad(settings)
    t = complex(math.cos(phi), math.sin(phi))
    return {("o1", "o2"): t, ("o2", "o1"): t}


def _ideal_mmi1x2(**_settings: Any) -> Dict[Tuple[str, str], complex]:
    import math

    c = 1.0 / math.sqrt(2.0)
    return {
        ("o1", "o2"): c,
        ("o1", "o3"): c,
        ("o2", "o1"): c,
        ("o3", "o1"): c,
    }


def _ideal_mmi2x2(**_settings: Any) -> Dict[Tuple[str, str], complex]:
    """Lossless 50/50. o1→o4 and o2→o3 carry the j so a zero-phase MZI is a permutation."""
    import math

    s = 1.0 / math.sqrt(2.0)
    j = 1.0j
    return {
        ("o1", "o3"): s,
        ("o1", "o4"): j * s,
        ("o2", "o3"): j * s,
        ("o2", "o4"): s,
        ("o3", "o1"): s,
        ("o3", "o2"): j * s,
        ("o4", "o1"): j * s,
        ("o4", "o2"): s,
    }


def _ideal_terminator(**_settings: Any) -> Dict[Tuple[str, str], complex]:
    return {("o1", "o1"): 0.0 + 0.0j}


def oracle_models() -> Dict[str, Any]:
    """Ideal models for the held-out check. Not the lossy FoM factory."""
    from gd_picasso.pcg.sax_models import _ideal_crossing_model, _ideal_mzi_model

    through = _ideal_through
    return {
        "straight": through,
        "bend_euler": through,
        "bend_circular": through,
        "straight_heater_metal": through,
        "straight_heater_metal_undercut": through,
        "taper": through,
        "mmi1x2": _ideal_mmi1x2,
        "mmi2x2": _ideal_mmi2x2,
        "coupler": _ideal_mmi2x2,
        "mzi": _ideal_mzi_model,
        "crossing": _ideal_crossing_model,
        "terminator": _ideal_terminator,
    }


def _lookup_s(sdict: Mapping[Any, Any], src: str, dst: str) -> complex:
    if (dst, src) in sdict:
        return _as_complex(sdict[(dst, src)])
    if (src, dst) in sdict:
        return _as_complex(sdict[(src, dst)])
    return 0.0 + 0.0j


def _split_io(port_names: Sequence[str]) -> Tuple[List[str], List[str]]:
    inputs = [p for p in port_names if p.lower().startswith("in")]
    outputs = [p for p in port_names if p.lower().startswith("out")]
    return inputs, outputs


def evaluate_sdict(task_id: int, sdict: Mapping[Any, Any], port_names: Sequence[str]) -> Dict[str, Any]:
    """Apply frozen thresholds to an already-computed S dictionary."""
    kind = "equal_split" if task_id in EQUAL_SPLIT_TASK_IDS else "mesh_permutation"
    inputs, outputs = _split_io(port_names)
    if not inputs or not outputs:
        return {
            "functional_pass": False,
            "kind": kind,
            "detail": f"could not split in/out from {list(port_names)}",
            "inputs": inputs,
            "outputs": outputs,
        }
    power = {
        inn: {out: abs(_lookup_s(sdict, inn, out)) ** 2 for out in outputs}
        for inn in inputs
    }
    row_sums = {inn: sum(power[inn].values()) for inn in inputs}
    problems: List[str] = []
    for inn, total in row_sums.items():
        if total > PASSIVE_ROW_SUM_MAX:
            problems.append(f"row_sum {inn}={total:.4f} > {PASSIVE_ROW_SUM_MAX}")
    if kind == "equal_split":
        if len(inputs) != 1:
            problems.append(f"equal_split expected 1 input, got {inputs}")
        n_out = len(outputs)
        ideal = 1.0 / n_out
        import math

        for inn in inputs:
            for out, pwr in power[inn].items():
                if pwr <= 0.0:
                    problems.append(f"{inn}->{out} power 0")
                    continue
                db = 10.0 * math.log10(pwr / ideal)
                if abs(db) > SPLIT_TOL_DB:
                    problems.append(f"{inn}->{out} {db:+.3f} dB vs 1/{n_out}")
    else:
        claimed: Dict[str, str] = {}
        for inn in inputs:
            ons = [out for out, pwr in power[inn].items() if pwr >= PERM_ON_MIN]
            offs = [out for out, pwr in power[inn].items() if pwr > PERM_OFF_MAX and pwr < PERM_ON_MIN]
            strong = [out for out, pwr in power[inn].items() if pwr > PERM_OFF_MAX]
            if len(ons) != 1 or strong != ons:
                top = max(power[inn].items(), key=lambda kv: kv[1])
                problems.append(
                    f"{inn} not a permutation row; top {top[0]}={top[1]:.3f}; "
                    f"on={ons} mid={offs}"
                )
            else:
                claimed[inn] = ons[0]
        if len(set(claimed.values())) != len(claimed):
            problems.append(f"outputs collide: {claimed}")
    return {
        "functional_pass": len(problems) == 0,
        "kind": kind,
        "detail": "ok" if not problems else "; ".join(problems[:8]),
        "inputs": inputs,
        "outputs": outputs,
        "row_sums": {k: round(v, 6) for k, v in row_sums.items()},
        "n_problems": len(problems),
    }


def circuit_sdict(store: Any) -> Dict[Any, Any]:
    """SAX S-dict of ``store`` under ideal oracle models. Not used in repair."""
    import sax

    from gd_picasso.pcg.bridge import to_sax_netlist
    from gd_picasso.pcg.sax_models import ensure_jax_x64

    ensure_jax_x64()
    netlist = to_sax_netlist(store)
    present = {inst["component"] for inst in netlist["instances"].values()}
    models = oracle_models()
    missing = sorted(present - set(models))
    if missing:
        raise RuntimeError(f"oracle has no model for {missing}")
    built = sax.circuit(netlist, models=models)
    circuit = built[0] if isinstance(built, tuple) else built
    sdict = circuit()
    return dict(sdict)


def functional_check(task_id: int, store: Any) -> Dict[str, Any]:
    """Grade ``store`` with the frozen oracle. Never called from the repair loop.

    Returns ``applicable=False`` for tasks outside ``APPLICABLE_TASK_IDS``.
    """
    n_nodes = len(getattr(store, "nodes", {}) or {})
    if task_id not in APPLICABLE_TASK_IDS:
        return {
            "task_id": task_id,
            "applicable": False,
            "functional_pass": None,
            "kind": None,
            "detail": "not in frozen applicable set",
            "n_nodes": n_nodes,
        }
    kind = "equal_split" if task_id in EQUAL_SPLIT_TASK_IDS else "mesh_permutation"
    try:
        sdict = circuit_sdict(store)
    except Exception as exc:  # noqa: BLE001 — validation must record the failure
        return {
            "task_id": task_id,
            "applicable": True,
            "functional_pass": False,
            "kind": kind,
            "detail": f"SAX failed: {type(exc).__name__}: {exc}",
            "n_nodes": n_nodes,
        }
    ports = list(getattr(store, "exported_ports", {}) or {})
    graded = evaluate_sdict(task_id, sdict, ports)
    graded.update({"task_id": task_id, "applicable": True, "n_nodes": n_nodes})
    return graded


def oracle_spec() -> Dict[str, Any]:
    return {
        "equal_split_tasks": list(EQUAL_SPLIT_TASK_IDS),
        "split_tol_db": SPLIT_TOL_DB,
        "mesh_permutation_tasks": list(MESH_PERMUTATION_TASK_IDS),
        "perm_on_min": PERM_ON_MIN,
        "perm_off_max": PERM_OFF_MAX,
        "passive_row_sum_max": PASSIVE_ROW_SUM_MAX,
        "mzi_model": "two 50/50 couplers + differential phase (ideal)",
        "crossing_model": "straight-through o1-o3 and o2-o4 (gdsfactory + gplugins crossing_ideal)",
        "not_in_repair_loop": True,
    }
