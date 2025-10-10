
from typing import List, Tuple
import gdsfactory as gf

def _ref(comp_name: str, settings: dict | None = None):
    factory = getattr(gf.components, comp_name, None)
    if factory is None:
        # fallback: try namespaced access like "mmi2x2" or "bend_circular"
        factory = getattr(gf.components, comp_name.replace("-", "_"), None)
    if factory is None:
        raise ValueError(f"Unknown component '{comp_name}' in gdsfactory.components")
    return factory(**(settings or {}))

def build_component_from_netlist(nl, cross_section="strip") -> gf.Component:
    c = gf.Component()
    # create refs
    refs = {}
    for name, inst in nl.instances.items():
        cell = _ref(inst.component, inst.settings)
        ref = c.add_ref(cell)
        ref.move((inst.x, inst.y))
        if inst.rotation:
            ref.rotate(inst.rotation)
        refs[name] = ref

    # route optical connections as bundles when possible
    # group by endpoints to bundle later
    for a, pa, b, pb in nl.connections:
        ra, rb = refs[a], refs[b]
        p1 = ra.ports[pa]
        p2 = rb.ports[pb]
        # Use a simple single route for now; get_route handles bends and min radius
        r = gf.routing.get_route(p1, p2, cross_section=cross_section)
        c.add(r.references)

    # expose top ports
    for top_name, target in nl.ports.items():
        inst, port = target.split(",")
        c.add_port(top_name, port=refs[inst].ports[port])
    return c
