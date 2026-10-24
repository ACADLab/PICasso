"""
I/O pad legalization for physical tapeout / lab measurement.

After the photonic core is placed (and optionally routed), attach a 1D fiber
array of grating couplers at the far west (inputs) and far east (outputs) of
the layout bounding box, pitched at the standard 127 µm fiber-array spacing,
and connect each coupler to the corresponding ``store.exported_ports`` pin.

The new optical edges are ``AttachmentKind.ROUTED`` so LiDAR / gdsfactory
``route_bundle`` materializes the fan-in / fan-out waveguides on the next
route pass. Exported port names are rewritten to the GC instances so the
tapeout I/O surface is the coupler array.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .store import PCGStore
from .types import (
    AttachmentKind,
    EdgeLayer,
    PCGNode,
    PCGPort,
    PortKind,
    RefLevel,
)

# Standard SMF fiber-array pitch (µm).
FIBER_ARRAY_PITCH_UM: float = 127.0
# Horizontal clearance from core bbox to the GC column (µm).
IO_MARGIN_UM: float = 150.0

# Preferred GC cells per PDK family.
_GC_BY_PDK: Dict[str, str] = {
    "siepic": "ebeam_gc_te895",
    "ubcpdk": "ebeam_gc_te895",
    "cornerstone": "grating_coupler_elliptical",
    "generic": "grating_coupler_elliptical",
    "generic_tech": "grating_coupler_elliptical",
}

_IN_NAME_RE = re.compile(r"^(in|input|west|o_in|din)", re.I)
_OUT_NAME_RE = re.compile(r"^(out|output|east|o_out|dout)", re.I)


@dataclass
class IOLegalizeResult:
    """Summary of a ``legalize_io_pads`` pass."""

    gc_ids: List[str] = field(default_factory=list)
    n_inputs: int = 0
    n_outputs: int = 0
    pitch_um: float = FIBER_ARRAY_PITCH_UM
    gc_component: str = "grating_coupler_elliptical"
    new_exported_ports: Dict[str, str] = field(default_factory=dict)
    skipped: bool = False
    detail: str = ""


def resolve_gc_component(
    pdk: str = "cornerstone",
    *,
    override: Optional[str] = None,
) -> str:
    """Pick a grating-coupler cell for ``pdk`` (or an explicit override)."""
    if override:
        return override
    key = (pdk or "cornerstone").strip().lower()
    return _GC_BY_PDK.get(key, "grating_coupler_elliptical")


def _layout_bbox(store: PCGStore) -> Tuple[float, float, float, float]:
    """Axis-aligned bbox of placed instances (xmin, ymin, xmax, ymax)."""
    xs: List[float] = []
    ys: List[float] = []
    for node in store.nodes.values():
        if node.x is None or node.y is None:
            continue
        xs.append(float(node.x))
        ys.append(float(node.y))
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _parse_export_ref(ref: str) -> Optional[Tuple[str, str]]:
    if not isinstance(ref, str) or "," not in ref:
        return None
    inst, port = ref.split(",", 1)
    inst, port = inst.strip(), port.strip()
    if not inst or not port:
        return None
    return inst, port


def _classify_io(
    store: PCGStore,
    exported: Dict[str, str],
) -> Tuple[List[Tuple[str, str, str]], List[Tuple[str, str, str]]]:
    """Split exports into (inputs, outputs) as ``(name, inst, port)`` lists.

    Prefer name prefixes (``in*`` / ``out*``); fall back to host ``x`` so the
    western half becomes inputs and the eastern half outputs.
    """
    named_in: List[Tuple[str, str, str]] = []
    named_out: List[Tuple[str, str, str]] = []
    unlabeled: List[Tuple[str, str, str, float]] = []

    for name, ref in exported.items():
        parsed = _parse_export_ref(ref)
        if parsed is None:
            continue
        inst, port = parsed
        if inst not in store.nodes:
            continue
        if _IN_NAME_RE.match(name):
            named_in.append((name, inst, port))
        elif _OUT_NAME_RE.match(name):
            named_out.append((name, inst, port))
        else:
            node = store.nodes[inst]
            x = float(node.x) if node.x is not None else 0.0
            unlabeled.append((name, inst, port, x))

    if unlabeled:
        xs = [u[3] for u in unlabeled]
        mid = 0.5 * (min(xs) + max(xs)) if xs else 0.0
        for name, inst, port, x in unlabeled:
            if x <= mid:
                named_in.append((name, inst, port))
            else:
                named_out.append((name, inst, port))

    def _sort_key(item: Tuple[str, str, str]) -> Tuple[float, str]:
        node = store.nodes[item[1]]
        y = float(node.y) if node.y is not None else 0.0
        return (y, item[0])

    named_in.sort(key=_sort_key)
    named_out.sort(key=_sort_key)
    return named_in, named_out


def _gc_port_name(component: str) -> str:
    """Waveguide-side port on the coupler (always ``o1`` in our PDK map)."""
    return "o1"


def _y_array(n: int, y_center: float, pitch: float) -> List[float]:
    """Centered 1D array of ``n`` pitches around ``y_center``."""
    if n <= 0:
        return []
    if n == 1:
        return [y_center]
    span = (n - 1) * pitch
    y0 = y_center - 0.5 * span
    return [y0 + i * pitch for i in range(n)]


def legalize_io_pads(
    store: PCGStore,
    *,
    pitch_um: float = FIBER_ARRAY_PITCH_UM,
    margin_um: float = IO_MARGIN_UM,
    pdk: str = "cornerstone",
    gc_component: Optional[str] = None,
    agent: str = "io_legalize",
    skip_if_present: bool = True,
) -> IOLegalizeResult:
    """Attach fiber-array grating couplers to ``store.exported_ports``.

    Places input GCs at ``xmin − margin`` (waveguide facing east, rot=180)
    and output GCs at ``xmax + margin`` (waveguide facing west, rot=0),
    spaced at ``pitch_um``. Connects each GC to its core export with a
    routed optical edge (materialized later by ``route_bundle``).
    """
    exported = dict(store.exported_ports)
    if not exported:
        return IOLegalizeResult(skipped=True, detail="no_exported_ports")

    if skip_if_present:
        for node in store.nodes.values():
            c = (node.component or "").lower()
            if "grating_coupler" in c or c.startswith("ebeam_gc") or c.startswith("gc_"):
                return IOLegalizeResult(
                    skipped=True,
                    detail=f"gc_already_present:{node.id}",
                    gc_component=node.component,
                )

    gc_comp = resolve_gc_component(pdk, override=gc_component)
    gc_port = _gc_port_name(gc_comp)
    inputs, outputs = _classify_io(store, exported)
    if not inputs and not outputs:
        return IOLegalizeResult(skipped=True, detail="no_classifiable_exports")

    xmin, ymin, xmax, ymax = _layout_bbox(store)
    y_center = 0.5 * (ymin + ymax)
    x_in = xmin - float(margin_um)
    x_out = xmax + float(margin_um)

    # SiEPIC cells are not always in gf.components — skip strict check.
    skip_check = gc_comp.startswith("ebeam_") or pdk.lower() in {
        "siepic",
        "ubcpdk",
    }

    new_exports: Dict[str, str] = {}
    gc_ids: List[str] = []
    ys_in = _y_array(len(inputs), y_center, float(pitch_um))
    ys_out = _y_array(len(outputs), y_center, float(pitch_um))

    for i, ((name, inst, port), y) in enumerate(zip(inputs, ys_in)):
        gid = f"gc_in_{i}"
        if gid in store.nodes:
            gid = f"gc_in_{i}_{name}"
        node = PCGNode(
            id=gid,
            component=gc_comp,
            level=RefLevel.L2_PLACED,
            ports={
                gc_port: PCGPort(
                    name=gc_port, kind=PortKind.OPTICAL, polarization="TE"
                )
            },
            x=x_in,
            y=y,
            rotation=180,  # waveguide toward +x (core)
            mirror=False,
        )
        node._placement_dirty = True
        store.add_node(node, skip_component_check=skip_check, agent=agent)
        store.set_placement(
            gid, x=x_in, y=y, rotation=180, mirror=False, agent=agent
        )
        # Fiber → GC → core
        store.connect(
            gid,
            gc_port,
            inst,
            port,
            layer=EdgeLayer.OPTICAL,
            attachment=AttachmentKind.ROUTED,
            bundle="io_west",
            agent=agent,
        )
        new_exports[name] = f"{gid},{gc_port}"
        gc_ids.append(gid)

    for i, ((name, inst, port), y) in enumerate(zip(outputs, ys_out)):
        gid = f"gc_out_{i}"
        if gid in store.nodes:
            gid = f"gc_out_{i}_{name}"
        node = PCGNode(
            id=gid,
            component=gc_comp,
            level=RefLevel.L2_PLACED,
            ports={
                gc_port: PCGPort(
                    name=gc_port, kind=PortKind.OPTICAL, polarization="TE"
                )
            },
            x=x_out,
            y=y,
            rotation=0,  # waveguide toward −x (core)
            mirror=False,
        )
        node._placement_dirty = True
        store.add_node(node, skip_component_check=skip_check, agent=agent)
        store.set_placement(
            gid, x=x_out, y=y, rotation=0, mirror=False, agent=agent
        )
        # Core → GC → fiber
        store.connect(
            inst,
            port,
            gid,
            gc_port,
            layer=EdgeLayer.OPTICAL,
            attachment=AttachmentKind.ROUTED,
            bundle="io_east",
            agent=agent,
        )
        new_exports[name] = f"{gid},{gc_port}"
        gc_ids.append(gid)

    store.set_exported_ports(new_exports, agent=agent)
    store.journal.append(
        "legalize_io_pads",
        {
            "n_inputs": len(inputs),
            "n_outputs": len(outputs),
            "pitch_um": float(pitch_um),
            "margin_um": float(margin_um),
            "gc_component": gc_comp,
            "gc_ids": list(gc_ids),
        },
        agent=agent,
    )
    return IOLegalizeResult(
        gc_ids=gc_ids,
        n_inputs=len(inputs),
        n_outputs=len(outputs),
        pitch_um=float(pitch_um),
        gc_component=gc_comp,
        new_exported_ports=new_exports,
        detail=f"placed {len(gc_ids)} GCs @ {pitch_um} µm pitch",
    )


def route_io_bundles_gf(
    component: "object",
    *,
    west_pairs: Sequence[Tuple[object, object]] = (),
    east_pairs: Sequence[Tuple[object, object]] = (),
    separation_um: float = 4.0,
) -> List[object]:
    """Optional live ``gdsfactory.routing.route_bundle`` for I/O fan-out.

    ``west_pairs`` / ``east_pairs`` are sequences of ``(port_a, port_b)``
    already resolved on a built Component. Returns the route objects.
    Intended for post-build tapeout polish; the PCG path relies on LiDAR
    ``route_bundle`` after ``legalize_io_pads``.
    """
    import gdsfactory as gf

    routes: List[object] = []
    for pairs, label in ((west_pairs, "io_west"), (east_pairs, "io_east")):
        if not pairs:
            continue
        ports1 = [p[0] for p in pairs]
        ports2 = [p[1] for p in pairs]
        try:
            batch = gf.routing.route_bundle(
                component,
                ports1,
                ports2,
                separation=separation_um,
                start_straight_length=separation_um,
                end_straight_length=separation_um,
            )
            routes.extend(list(batch or []))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"route_bundle[{label}] failed: {exc}") from exc
    return routes
