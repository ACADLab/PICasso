"""Unit tests for layout-vs-schematic connectivity check."""

from __future__ import annotations

import gdsfactory as gf

from gd_picasso.pcg.store import PCGStore
from gd_picasso.pcg.types import EdgeLayer, PCGEdge, PCGNode
from gd_picasso.validators.lvs_validator import LVSValidator


def test_validate_disabled_skips() -> None:
    validator = LVSValidator(enabled=False)
    passed, report = validator.validate(gf.components.mmi1x2())
    assert passed is True
    assert report["lvs_mode"] == "disabled"
    assert report["errors"] == []


def test_validate_structure_smoke() -> None:
    validator = LVSValidator(enabled=True)
    passed, report = validator.validate(gf.components.mmi1x2())
    assert passed is True
    assert report["lvs_mode"] == "structure"
    assert report.get("check") == "structure"
    assert "lvs_skipped_gf9" not in report


def test_validate_connectivity_store_only() -> None:
    store = PCGStore()
    store.add_node(PCGNode(id="a", component="mmi1x2"), skip_component_check=True)
    store.add_node(PCGNode(id="b", component="mmi1x2"), skip_component_check=True)
    store.connect("a", "o1", "b", "o1")
    validator = LVSValidator(enabled=True)
    passed, report = validator.validate_connectivity(store, component=None)
    assert passed is True
    assert report["lvs_mode"] == "connectivity"
    assert report["errors"] == []


def test_validate_connectivity_missing_node_fails() -> None:
    store = PCGStore()
    store.add_node(PCGNode(id="a", component="mmi1x2"), skip_component_check=True)
    # Bypass connect() so we can plant a dangling endpoint
    store._edges.append(
        PCGEdge(
            src_node="a",
            src_port="o1",
            dst_node="missing",
            dst_port="o1",
            layer=EdgeLayer.OPTICAL,
        )
    )
    validator = LVSValidator(enabled=True)
    passed, report = validator.validate_connectivity(store, component=None)
    assert passed is False
    assert report["errors"]
