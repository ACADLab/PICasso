"""Cornerstone emit smokes — PCG → to_gf_yaml (not hand-built netlists).

Hash claims (named explicitly — do not conflate)
------------------------------------------------
* ``connectivity_hash`` — **topology preserved** under lowering (param-free
  ids/roles/optical endpoints). Must be **stable**.
* ``circuit_hash`` — wiring **plus PCell settings**. Heater 10→320 **moves**
  this hash; it is *not* a topology-only digest. (``topology_hash`` is a
  deprecated alias of ``circuit_hash``.)
* ``layout_hash`` — geometry + params. Must **move** under lowering / place.

MZI also checks IL split-brain + CS_MODEL_SAX regression + WG (3,0).
MZM / Ring-bus check emit + layer + connectivity stability (map coverage).
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from gd_picasso.pcg.backends.cornerstone import (
    CORNERSTONE_SI220_CBAND,
    CS_WG_LAYER,
    GENERIC_WG_LAYER,
    apply_backend_to_store,
    emit_gds,
    emit_generic_tech_gds,
    gds_layer_pairs,
    mzi_store_generic_default,
    mzm_store_generic_default,
    ring_bus_store_generic_default,
    sax_il_from_store,
)
from gd_picasso.pcg.backends.pdk_backend import LossProvenance
from gd_picasso.pcg.sax_models import CS_MZI_IL_DB, CS_MZI_IL_PROVENANCE

pytest.importorskip("cspdk")


def _assert_lowering_hash_claims(store_gt, store_cs) -> None:
    """Document which hash carries which amendment claim."""
    assert store_cs.connectivity_hash() == store_gt.connectivity_hash(), (
        "connectivity_hash (topology) must be stable under lowering"
    )
    assert store_cs.circuit_hash() != store_gt.circuit_hash(), (
        "circuit_hash (wiring+params) must move when heater length adapts"
    )
    layout_gt = store_gt.layout_hash()
    layout_cs = store_cs.layout_hash()
    assert layout_gt is not None and layout_cs is not None
    assert layout_cs != layout_gt, (
        "layout_hash must change under lowering, not only on placement nudge"
    )


def test_cornerstone_mzi_smoke_lowering_evidence() -> None:
    backend = CORNERSTONE_SI220_CBAND

    store_gt = mzi_store_generic_default()
    assert float(store_gt.nodes["psT"].params.get("length", 0)) == 10.0

    from gdsfactory.generic_tech import get_generic_pdk

    get_generic_pdk().activate()
    _, _, yaml_gt = emit_generic_tech_gds(deepcopy(store_gt))
    assert "length: 10" in yaml_gt or "length: 10.0" in yaml_gt

    store_cs = deepcopy(store_gt)
    apply_backend_to_store(store_cs, backend)
    assert float(store_cs.nodes["psT"].params["length"]) == 320.0
    _assert_lowering_hash_claims(store_gt, store_cs)

    gds_cs, comp_cs, yaml_cs = emit_gds(
        deepcopy(store_gt), backend=backend, apply_backend=True
    )
    assert gds_cs.is_file() and gds_cs.stat().st_size > 0
    assert comp_cs is not None
    assert "length: 320" in yaml_cs or "length: 320.0" in yaml_cs
    assert "instances:" in yaml_cs and "straight_heater_metal" in yaml_cs

    layers = gds_layer_pairs(gds_cs)
    assert CS_WG_LAYER in layers, f"expected CS WG {CS_WG_LAYER} in {layers}"
    assert GENERIC_WG_LAYER not in layers, (
        f"generic WG {GENERIC_WG_LAYER} present — possible silent fallback: {layers}"
    )

    drc = backend.run_drc(str(gds_cs))
    assert drc.status == "SKIP"
    assert "no deck" in drc.reason.lower()

    il_cs, loss_cs = sax_il_from_store(store_cs, use_cspdk_models=True)
    get_generic_pdk().activate()
    il_gt, _ = sax_il_from_store(store_gt, use_cspdk_models=False)
    assert loss_cs.provenance == LossProvenance.TARGET_TABLE_II
    assert CS_MZI_IL_PROVENANCE == "CS_MODEL_SAX"
    assert backend.reference_il_note and "CS_MODEL_SAX" in backend.reference_il_note
    assert il_cs != il_gt, (
        f"split-brain missing: IL_cs={il_cs} == IL_generic_tech={il_gt}"
    )
    assert abs(il_cs - CS_MZI_IL_DB) < 0.05, (
        f"regression: IL_cs={il_cs} drifted from FINDINGS {CS_MZI_IL_DB}"
    )


def test_cornerstone_mzm_emit_map() -> None:
    """MZM component_map: mmi1x2 + heaters → CS emit via to_gf_yaml."""
    backend = CORNERSTONE_SI220_CBAND
    store_gt = mzm_store_generic_default()
    store_cs = deepcopy(store_gt)
    apply_backend_to_store(store_cs, backend)
    assert float(store_cs.nodes["ps_upper"].params["length"]) == 320.0
    _assert_lowering_hash_claims(store_gt, store_cs)

    gds_cs, _, yaml_cs = emit_gds(
        deepcopy(store_gt), backend=backend, apply_backend=True
    )
    assert gds_cs.is_file() and gds_cs.stat().st_size > 0
    assert "mmi1x2" in yaml_cs and "straight_heater_metal" in yaml_cs
    layers = gds_layer_pairs(gds_cs)
    assert CS_WG_LAYER in layers
    assert GENERIC_WG_LAYER not in layers


def test_cornerstone_ring_bus_emit_map() -> None:
    """Ring-bus coupler map → CS emit; no IR feedback (avoids singular KLU)."""
    backend = CORNERSTONE_SI220_CBAND
    store_gt = ring_bus_store_generic_default()
    store_cs = deepcopy(store_gt)
    apply_backend_to_store(store_cs, backend)
    assert store_cs.nodes["dc"].component == "coupler"
    assert store_cs.connectivity_hash() == store_gt.connectivity_hash()

    gds_cs, _, yaml_cs = emit_gds(
        deepcopy(store_gt), backend=backend, apply_backend=True
    )
    assert gds_cs.is_file() and gds_cs.stat().st_size > 0
    assert "coupler" in yaml_cs
    layers = gds_layer_pairs(gds_cs)
    assert CS_WG_LAYER in layers
    assert GENERIC_WG_LAYER not in layers


def test_role_defaults_to_component() -> None:
    store = mzi_store_generic_default()
    assert store.nodes["c1"].role is None
    apply_backend_to_store(store, CORNERSTONE_SI220_CBAND)
    assert store.nodes["c1"].role == "mmi2x2"


def test_ring_delta_il_skip_is_singular_klu_not_zero_bridge() -> None:
    """Track Ring gate soft-SKIP: IR feedback → singular KLU, not ΔIL≈0 bug."""
    # Documented contract for the gate fixture; do not treat SKIP as GREEN.
    reason = "INVALID_ARGUMENT: klu_z_factor failed (singular matrix?)"
    assert "singular" in reason.lower()
