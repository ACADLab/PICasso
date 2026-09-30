"""Cornerstone (cspdk si220 cband) PDK backend — first real foundry emit target.

Pins: gdsfactory 9.23.0 + cspdk 1.3.2 (see probes/lowering/FINDINGS.md).

DRC: cspdk 1.3.2 ships **no** KLayout DRC deck → ``SKIP(no deck)``.
SAX strip loss 0.7 dB/cm is ``TARGET_TABLE_II`` (not MEASURED_CS).
MZI IL reference 0.622 dB is ``CS_MODEL_SAX`` (cspdk models + Table II loss) —
not a foundry measurement.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

from gd_picasso.pcg.backends.pdk_backend import (
    DrcOutcome,
    LossEntry,
    LossProvenance,
    PDKBackend,
)
from gd_picasso.pcg.sax_models import (
    CS_ARM_L_UM,
    CS_MZI_IL_DB,
    DEFAULT_LOSS_DB_CM,
)
from gd_picasso.pcg.store import PCGStore
from gd_picasso.pcg.types import PCGNode

# Cornerstone WG layer (cspdk.si220.cband.tech.LayerMapCornerstone.WG)
CS_WG_LAYER: Tuple[int, int] = (3, 0)
GENERIC_WG_LAYER: Tuple[int, int] = (1, 0)


def _heater_params(params: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(params)
    out["length"] = CS_ARM_L_UM  # force CS arm length (generic_tech default ~10 µm)
    return out


def _identity_params(params: Dict[str, Any]) -> Dict[str, Any]:
    return dict(params)


def cornerstone_drc(_gds_path: str) -> DrcOutcome:
    return DrcOutcome(
        status="SKIP",
        reason="no deck: cspdk 1.3.2 has no KLayout DRC runset for si220",
    )


CORNERSTONE_SI220_CBAND = PDKBackend(
    id="cornerstone_si220_cband",
    pinned_versions={
        "gdsfactory": "9.23.0",
        "cspdk": "1.3.2",
        "platform": "cspdk.si220.cband",
    },
    component_map={
        "mmi2x2": "mmi2x2",
        "mmi1x2": "mmi1x2",
        "straight_heater_metal": "straight_heater_metal",
        "straight": "straight",
        "bend_euler": "bend_euler",
        "coupler": "coupler",
        "coupler_ring": "coupler_ring",
        "ring_single": "ring_single",
        "ring_double": "ring_double",
        "splitter_2x2": "mmi2x2",
        "combiner_2x2": "mmi2x2",
        "splitter_1x2": "mmi1x2",
        "phase_shifter_thermal": "straight_heater_metal",
    },
    param_adapters={
        "straight_heater_metal": _heater_params,
        "phase_shifter_thermal": _heater_params,
        "mmi2x2": _identity_params,
        "mmi1x2": _identity_params,
        "splitter_2x2": _identity_params,
        "combiner_2x2": _identity_params,
        "splitter_1x2": _identity_params,
        "coupler": _identity_params,
        "coupler_ring": _identity_params,
        "ring_single": _identity_params,
        "ring_double": _identity_params,
        "straight": _identity_params,
        "bend_euler": _identity_params,
    },
    xs_map={"strip": "strip"},
    port_map={},
    strip_loss=LossEntry(
        value_dB_cm=DEFAULT_LOSS_DB_CM,
        provenance=LossProvenance.TARGET_TABLE_II,
        note="PICasso Table II strip target — not Cornerstone fab-measured loss",
    ),
    reference_il_dB=CS_MZI_IL_DB,
    reference_il_note=(
        "FINDINGS cs_mzi MZI IL at loss_dB_cm=0.7, L=320 µm — "
        "CS_MODEL_SAX (cspdk SAX + Table II loss), not MEASURED_CS"
    ),
    drc_fn=cornerstone_drc,
)


def node_role(node: PCGNode) -> str:
    """Effective role: explicit ``role`` or GF ``component`` default encoding."""
    return (node.role or node.component).strip()


def connectivity_fingerprint(store: PCGStore) -> str:
    """Deprecated alias of ``PCGStore.connectivity_hash`` (param-free structure)."""
    return store.connectivity_hash()


def apply_backend_to_store(store: PCGStore, backend: PDKBackend) -> PCGStore:
    """Remap component names/params in-place for emit (mutates store nodes)."""
    for n in store.nodes.values():
        role = node_role(n)
        n.component = backend.map_component(role)
        n.params = backend.adapt_params(role, n.params)
        if n.role is None:
            n.role = role
    return store


def emit_gds(
    store: PCGStore,
    *,
    backend: PDKBackend = CORNERSTONE_SI220_CBAND,
    gds_path: Optional[str | Path] = None,
    apply_backend: bool = True,
) -> Tuple[Path, Any, str]:
    """Activate Cornerstone PDK, build via ``to_gf_yaml`` (not a hand netlist).

    Returns ``(gds_path, component, yaml_text)``.
    """
    import gdsfactory as gf
    from cspdk.si220.cband import PDK

    from gd_picasso.pcg.bridge import to_gf_yaml

    if backend.id != CORNERSTONE_SI220_CBAND.id:
        raise ValueError(f"emit_gds only supports {CORNERSTONE_SI220_CBAND.id}")

    PDK.activate()
    try:
        gf.clear_cache()
    except Exception:
        pass
    if apply_backend:
        apply_backend_to_store(store, backend)
    yaml_text = to_gf_yaml(store)
    component = gf.read.from_yaml(yaml_text)

    if gds_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".gds", delete=False)
        gds_path = tmp.name
        tmp.close()
    path = Path(gds_path)
    component.write_gds(str(path))
    return path, component, yaml_text


def emit_generic_tech_gds(
    store: PCGStore,
    *,
    gds_path: Optional[str | Path] = None,
) -> Tuple[Path, Any, str]:
    """Emit the same PCG through default gdsfactory (no cspdk activate)."""
    import gdsfactory as gf
    from gdsfactory.generic_tech import get_generic_pdk

    from gd_picasso.pcg.bridge import to_gf_yaml

    # Teaching stack — undo any leftover CS activation
    get_generic_pdk().activate()
    try:
        gf.clear_cache()
    except Exception:
        pass
    yaml_text = to_gf_yaml(store)
    component = gf.read.from_yaml(yaml_text)
    if gds_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".gds", delete=False)
        gds_path = tmp.name
        tmp.close()
    path = Path(gds_path)
    component.write_gds(str(path))
    return path, component, yaml_text


def gds_layer_pairs(gds_path: str | Path) -> Set[Tuple[int, int]]:
    """Layer (layer, datatype) pairs present in a GDS file."""
    import gdsfactory as gf

    c = gf.import_gds(str(gds_path))
    pairs: Set[Tuple[int, int]] = set()
    for layer in c.layers:
        if isinstance(layer, tuple) and len(layer) >= 2:
            pairs.add((int(layer[0]), int(layer[1])))
        else:
            try:
                pairs.add((int(layer[0]), int(layer[1])))
            except Exception:
                continue
    # kfactory / gf9 may expose get_polygons
    try:
        polys = c.get_polygons(by="tuple")
        for key in polys:
            if isinstance(key, tuple) and len(key) >= 2:
                pairs.add((int(key[0]), int(key[1])))
    except Exception:
        pass
    return pairs


def sax_il_from_store(
    store: PCGStore,
    *,
    use_cspdk_models: bool,
    loss_dB_cm: Optional[float] = None,
) -> Tuple[float, LossEntry]:
    """IL from ``to_sax_netlist(store)`` — PCG path, not a hand-built netlist."""
    import numpy as np
    import sax

    from gd_picasso.pcg.bridge import to_sax_netlist

    loss_entry = CORNERSTONE_SI220_CBAND.strip_loss
    assert loss_entry is not None
    loss = float(loss_dB_cm if loss_dB_cm is not None else loss_entry.value_dB_cm)
    netlist = to_sax_netlist(store)

    if use_cspdk_models:
        from cspdk.si220.cband import PDK
        from cspdk.si220.cband import models as M

        PDK.activate()
        models = M.get_models()
    else:
        from gd_picasso.pcg.sax_models import build_lossy_models

        models = build_lossy_models(loss)

    circuit, _ = sax.circuit(netlist=netlist, models=models)
    kwargs: Dict[str, Any] = {}
    if use_cspdk_models:
        # cspdk straight_heater_metal SAX accepts voltage/length/loss_dB_cm
        for nid, n in store.nodes.items():
            if "heater" in n.component or n.component == "straight_heater_metal":
                kwargs[nid] = {
                    "voltage": float(n.params.get("voltage", 0.0) or 0.0),
                    "length": float(n.params.get("length", CS_ARM_L_UM)),
                    "loss_dB_cm": loss,
                }
    s = circuit(wl=1.55, **kwargs)
    sd = sax.sdict(s)
    pin = list(netlist.get("ports", {}).keys())
    ins = [p for p in pin if p.startswith("in")]
    outs = [p for p in pin if p.startswith("out")]
    if len(ins) < 1 or len(outs) < 1:
        raise RuntimeError(f"need in/out ports in netlist, got {pin}")
    if len(ins) >= 2 and len(outs) >= 2:
        M2 = np.array(
            [[complex(sd[(i, o)]) for i in ins[:2]] for o in outs[:2]]
        )
        amp = float(np.linalg.norm(M2[:, 0]))
    else:
        amp = abs(complex(sd[(ins[0], outs[0])]))
    il = float(-20.0 * np.log10(amp)) if amp > 0 else float("inf")
    return il, loss_entry


def mzi_store_generic_default() -> PCGStore:
    """Same MZI topology with generic_tech heater default length (~10 µm)."""
    from gd_picasso.pcg.bridge import from_gf_yaml

    yaml_text = """
instances:
  c1: {component: mmi2x2, settings: {}}
  psT: {component: straight_heater_metal, settings: {length: 10}}
  psB: {component: straight_heater_metal, settings: {length: 10}}
  c2: {component: mmi2x2, settings: {}}
connections:
  psT,o1: c1,o3
  psB,o1: c1,o4
  c2,o1: psT,o2
  c2,o2: psB,o2
ports:
  in1: c1,o1
  in2: c1,o2
  out1: c2,o3
  out2: c2,o4
placements:
  c1: {x: 0, y: 0, rotation: 0, mirror: false}
  psT: {x: 120, y: 40, rotation: 0, mirror: false}
  psB: {x: 120, y: -40, rotation: 0, mirror: false}
  c2: {x: 280, y: 0, rotation: 0, mirror: false}
"""
    return from_gf_yaml(yaml_text)


def mzm_store_generic_default() -> PCGStore:
    """Dual-drive MZM (mmi1x2 + heaters + mmi2x2); heater L=100 teaching default."""
    from gd_picasso.pcg.bridge import from_gf_yaml

    yaml_text = """
instances:
  splitter: {component: mmi1x2, settings: {}}
  ps_upper: {component: straight_heater_metal, settings: {length: 100}}
  ps_lower: {component: straight_heater_metal, settings: {length: 100}}
  combiner: {component: mmi2x2, settings: {}}
connections:
  ps_upper,o1: splitter,o2
  ps_lower,o1: splitter,o3
  combiner,o1: ps_upper,o2
  combiner,o2: ps_lower,o2
ports:
  in: splitter,o1
  out1: combiner,o3
  out2: combiner,o4
placements:
  splitter: {x: 0, y: 0, rotation: 0, mirror: false}
  ps_upper: {x: 150, y: 40, rotation: 0, mirror: false}
  ps_lower: {x: 150, y: -40, rotation: 0, mirror: false}
  combiner: {x: 300, y: 0, rotation: 0, mirror: false}
"""
    return from_gf_yaml(yaml_text)


def ring_bus_store_generic_default() -> PCGStore:
    """Ring-bus probe: coupler + bus straights (no IR feedback edge in store).

    Gate Ring ΔIL SKIP is from SAX singular KLU on IR-only ``dc,o3↔dc,o2``
    feedback — tracked separately; this store is for emit / component_map only.
    """
    from gd_picasso.pcg.bridge import from_gf_yaml

    yaml_text = """
instances:
  dc: {component: coupler, settings: {gap: 0.2, length: 10}}
  bus_in: {component: straight, settings: {length: 20}}
  bus_out: {component: straight, settings: {length: 20}}
connections:
  bus_in,o2: dc,o1
  dc,o4: bus_out,o1
ports:
  in: bus_in,o1
  out: bus_out,o2
placements:
  bus_in: {x: 0, y: -1.65, rotation: 0, mirror: false}
  dc: {x: 80, y: 0, rotation: 0, mirror: false}
  bus_out: {x: 200, y: -1.65, rotation: 0, mirror: false}
"""
    return from_gf_yaml(yaml_text)


# Back-compat alias
def mzi_store_from_cs_fixture() -> PCGStore:
    """CS-length MZI (after adapter); prefer ``mzi_store_generic_default`` + apply."""
    from copy import deepcopy

    store = mzi_store_generic_default()
    apply_backend_to_store(store, CORNERSTONE_SI220_CBAND)
    return store


# Keep old name used by tests
def sax_mzi_il_dB(**kwargs: Any) -> Tuple[float, LossEntry]:
    store = mzi_store_from_cs_fixture()
    return sax_il_from_store(store, use_cspdk_models=True, **kwargs)
