# Problem 10, Sample 0, Attempt 0
# Generated: 2025-11-12T17:05:16.036198

<think>
Okay, so I need to create a fundamental 2x2 optical switch using an MZI-based switch cell with the given components. Let me break this down step by step.

First, I know that an MZI (Mach-Zehnder Interferometer) based switch typically consists of two MZI arms that can be controlled to switch the input between two outputs. The components given are sw1 (the MZI cell) and ctrl1 (the phase control).

I'll start by instantiating these components. Using GDSFactory, I'll add the MZI component and the phase control. I'll reference them as sw1 and ctrl1 respectively.

Next, I need to position these components in the layout. The MZI will be placed at the origin. The phase control, which usually has two ports for the inputs and two for the outputs, needs to be placed such that it connects to the MZI. So I'll move ctrl1 to a position that's 200 micrometers to the right of sw1 to avoid overlapping and ensure DRC compliance.

Now, I need to connect the ports. The phase control has four ports: two inputs (o1, o2) and two outputs (o3, o4). The MZI has four ports: o1, o2, o3, o4. Typically, the inputs of the phase control connect to the top and bottom arms of the MZI, and the outputs of the phase control connect to the corresponding outputs of the MZI.

So, I'll route from ctrl1's o1 to sw1's o1, ctrl1's o2 to sw1's o2, ctrl1's o3 to sw1's o3, and ctrl1's o4 to sw1's o4. Using route_bundle for each connection ensures that the routing is clean and maintains the required separation for DRC.

After connecting all the ports, I need to expose the external ports. The external ports of the switch are the inputs and outputs of the MZI. So, I'll add ports o1, o2, o3, o4 from sw1 to the main component.

Finally, I'll draw the ports and plot the layout to visualize the connections.

Putting it all together, the code will instantiate the components, position them, connect the ports using route_bundle, and expose the necessary external ports.</think>

import gdsfactory as gf

r = gf.Component()

sw1 = r.add_ref(gf.components.mzi_cell())
ctrl1 = r.add_ref(gf.components.phase_control())
ctrl1.move((200, 0))

gf.routing.route_bundle(r, [ctrl1.ports['o1'], ctrl1.ports['o2']], [sw1.ports['o1'], sw1.ports['o2']], cross_section='strip', radius=20, separation=20)
gf.routing.route_bundle(r, [sw1.ports['o3'], sw1.ports['o4']], [ctrl1.ports['o3'], ctrl1.ports['o4']], cross_section='strip', radius=20, separation=20)

r.add_port('o1', port=sw1.ports['o1'])
r.add_port('o2', port=sw1.ports['o2'])
r.add_port('o3', port=sw1.ports['o3'])
r.add_port('o4', port=sw1.ports['o4'])

r.draw_ports()
r.plot()