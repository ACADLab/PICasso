# Problem 10, Sample 1, Attempt 0
# Generated: 2025-11-12T17:06:01.330780

<think>
Okay, so I need to write Python code to create a 2x2 optical switch using GDSFactory. The problem says to use an MZI cell and a phase control. Let me think about how to structure this.

First, I remember that in GDSFactory, components are added using the Component class. So I'll start by creating a new component called 'r'. Then, I need to add the MZI cell and the phase control to this component.

The MZI cell is typically an mzi component. I'll add it with an id of 'sw1' and move it to the origin. Next, the phase control is probably a straight waveguide, maybe 10 microns long, so I'll add that with an id of 'ctrl1' and move it somewhere else, like (200, 0) to avoid overlapping.

Now, I need to connect the ports. The MZI has four ports: o1, o2, o3, o4. The phase control has two ports, o1 and o2. I think the phase control connects to the MZI's top and bottom arms. So I'll use route_bundle to connect the MZI's o3 and o4 to the control's o1 and o2. I'll set the cross_section to 'strip', radius to 20, and separation to 20 for safety.

After connecting, I need to expose the external ports. The MZI's o1 and o2 should be the external ports. So I'll add 'o1' and 'o2' from the MZI's ports. Then, I'll draw all ports and plot the component.

I should make sure all connections are made with route_bundle, not route_single, and that all ports are correctly labeled. Also, I need to avoid any comments or extra text and stick strictly to the required structure.</think>

import gdsfactory as gf

r = gf.Component()

sw1 = r.add_ref(gf.components.mzi())
sw1.move((0, 0))

ctrl1 = r.add_ref(gf.components.straight_heater_metal(length=10))
ctrl1.move((200, 0))

gf.routing.route_bundle(
    r,
    [sw1.ports['o3'], sw1.ports['o4']],
    [ctrl1.ports['o1'], ctrl1.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

r.add_port('o1', port=sw1.ports['o1'])
r.add_port('o2', port=sw1.ports['o2'])

r.draw_ports()
r.plot()