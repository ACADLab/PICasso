"""
LiDAR PIC IR identity + projection tests.

Schema pin: ScopeX-ASU/LiDAR @ 4e7004d32b0b80d959553797fb30f0737513de0c

Run:  pytest gd_picasso/pcg/test_lidar_ir.py -q
"""

from __future__ import annotations

from pathlib import Path

import yaml

from gd_picasso.pcg.lidar_ir import (
    LIDAR_SCHEMA_COMMIT,
    from_lidar_yaml,
    lidar_docs_equal,
    to_lidar_yaml,
)
from gd_picasso.pcg.store import PCGStore
from gd_picasso.pcg.types import (
    AttachmentKind,
    EdgeLayer,
    PCGNode,
    PCGPort,
    PortKind,
    RefLevel,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "lidar"
LIDAR_MZI = FIXTURES / "lidar_mzi_stub.yaml"


def test_lidar_schema_commit_pinned() -> None:
    assert LIDAR_SCHEMA_COMMIT == "4e7004d32b0b80d959553797fb30f0737513de0c"
    assert len(LIDAR_SCHEMA_COMMIT) == 40


def test_lidar_pcg_lidar_identity() -> None:
    """LiDAR → PCG → LiDAR is identity on the supported IR."""
    src = LIDAR_MZI.read_text()
    store = from_lidar_yaml(src)
    result = to_lidar_yaml(store)
    assert result.dropped == [], result.dropped
    assert result.is_identity_capable
    assert lidar_docs_equal(src, result.yaml_text)
    # Second hop stays stable.
    store2 = from_lidar_yaml(result.yaml_text)
    result2 = to_lidar_yaml(store2)
    assert lidar_docs_equal(src, result2.yaml_text)


def test_pcg_to_lidar_projection_reports_drops() -> None:
    """PCG → LiDAR projection drops ELECTRICAL / THERMAL / MULTI_PORT."""
    store = PCGStore(default_agent="proj")
    for nid, comp in [("a", "mmi1x2"), ("b", "straight"), ("c", "straight")]:
        store.add_node(
            PCGNode(id=nid, component=comp, level=RefLevel.L1_CIRCUIT),
            skip_component_check=True,
        )
    store.connect("a", "o2", "b", "o1", layer=EdgeLayer.OPTICAL)

    # Electrical + thermal ports/edges (PCG-only relative to LiDAR PIC IR).
    store._nodes["b"].ports["e1"] = PCGPort(name="e1", kind=PortKind.ELECTRICAL)
    store._nodes["c"].ports["e1"] = PCGPort(name="e1", kind=PortKind.ELECTRICAL)
    store._nodes["b"].ports["t1"] = PCGPort(name="t1", kind=PortKind.THERMAL)
    store._nodes["c"].ports["t1"] = PCGPort(name="t1", kind=PortKind.THERMAL)
    store.connect(
        "b", "e1", "c", "e1",
        layer=EdgeLayer.ELECTRICAL,
        attachment=AttachmentKind.ROUTED,
    )
    store.connect(
        "b", "t1", "c", "t1",
        layer=EdgeLayer.THERMAL,
        attachment=AttachmentKind.ROUTED,
    )

    result = to_lidar_yaml(store, design="proj_test")
    cats = {d.category for d in result.dropped}
    assert "ELECTRICAL" in cats, result.dropped
    assert "THERMAL" in cats, result.dropped
    doc = yaml.safe_load(result.yaml_text)
    # Only the optical net is emitted.
    assert len(doc["nets"]) == 1
    assert not result.is_identity_capable


def test_multiport_net_reported_on_projection() -> None:
    """Nets with >2 endpoints are not identity-capable; projection reports MULTI_PORT."""
    yaml_in = """\
schema: null
instances:
  s:
    component: mmi1x2
    settings:
      macro_type: m_mmi1x2_0
      placement: [UNPLACED, [0, 0], N, [0, 0, 0, 0]]
  u:
    component: straight
    settings:
      macro_type: m_straight_0
      placement: [UNPLACED, [10, 0], N, [0, 0, 0, 0]]
  l:
    component: straight
    settings:
      macro_type: m_straight_1
      placement: [UNPLACED, [10, 10], N, [0, 0, 0, 0]]
schematic_placements: {}
nets:
  star: ['s,o1', 'u,o1', 'l,o1']
ports: {}
schema_version: 1
settings:
  version: '1.0'
  design: multiport_probe
  units_distance_microns: 1
  die_area: [[0, 0], [50, 50]]
  num_instances: 3
  num_nets: 1
  num_ports: 0
  wg_radius: 5
library: {}
"""
    store = from_lidar_yaml(yaml_in)
    result = to_lidar_yaml(store)
    assert any(d.category == "MULTI_PORT" for d in result.dropped), result.dropped
    assert not lidar_docs_equal(yaml_in, result.yaml_text)


def test_fixture_loads() -> None:
    assert LIDAR_MZI.is_file()
    store = from_lidar_yaml(LIDAR_MZI.read_text())
    assert len(store.nodes) == 4
    assert len(store.edges) == 4
