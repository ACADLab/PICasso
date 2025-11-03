# custom_models.py
import gdsfactory as gf
import sax
import gplugins.sax as gs

@gf.cell
def mzm_layout(
    splitter=gf.components.mmi(inputs=1, outputs=2),
    combiner=gf.components.mmi(inputs=2, outputs=1),
    heater_length: float = 10.0,
):
    c = gf.Component()

    split = c << gf.get_component(splitter)
    comb = c << gf.get_component(combiner)
    split.move((0, 0))
    comb.move((200, 0))

    ps_top = c << gf.components.straight_heater_metal(length=heater_length)
    ps_bot = c << gf.components.straight_heater_metal(length=heater_length)
    ps_top.move((100, 20))
    ps_bot.move((100, -20))

    for p1, p2 in [
        (split.ports["o2"], ps_top.ports["o1"]),
        (split.ports["o3"], ps_bot.ports["o1"]),
        (comb.ports["o2"], ps_top.ports["o2"]),
        (comb.ports["o1"], ps_bot.ports["o2"]),
    ]:
        gf.routing.route_single(
            component=c,
            port1=p1,
            port2=p2,
            cross_section="strip",
            radius=5,
        )

    c.add_port("o1", port=split.ports["o1"])
    c.add_port("o2", port=comb.ports["o3"])
    return c


# build once
_mzm_cell = mzm_layout()
_raw = _mzm_cell.get_netlist(exclude_port_types=("electrical",))
_mzm_net = sax.netlist(_raw)

_base_models = {
    "straight": gs.models.straight,
    "bend_euler": gs.models.bend,
    "mmi": gs.models.mmi1x2,
    "straight_heater_metal": sax.models.phase_shifter,
    "straight_heater_metal_undercut": sax.models.phase_shifter,
}

mzm_model, _ = sax.circuit(
    netlist=_mzm_net,
    models=_base_models,
    backend="forward",
    ignore_impossible_connections=True,
)

__all__ = ["mzm_model"]