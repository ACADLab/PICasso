# Problem 1, Sample 0, Attempt 0
# Generated: 2025-11-12T16:59:41.408748

<think>
Okay, I need to create a Mach-Zehnder interferometer using GDSFactory. The user specified using two MMI1x2 components and a phase shifter. Let me break down the steps.

First, I'll start by importing GDSFactory as gf. Then, I'll create a new component called mzi.

Next, I'll add the first MMI1x2 component, mmi1, and position it at (0,0). This will be the input splitter.

Then, I'll add the second MMI1x2, mmi2, but I need to mirror it to act as a 2x1 combiner. I'll call the mirror method on mmi2 and move it to (200, 0) to ensure there's enough space between the splitters for the phase shifter.

Now, I need to add the phase shifter. I'll use the straight_heater_metal component with a length of 10.0 microns. I'll place it at (100, 0) so it's between the two MMI components.

After placing all components, I need to connect them. I'll use route_bundle for clean routing. First, I'll connect the output ports of mmi1 to the input of the phase shifter. Then, I'll connect the output of the phase shifter to the inputs of mmi2. I'll set the cross_section to 'strip', radius to 20, and separation to 20 to ensure DRC compliance.

Finally, I'll expose the external ports. The input will be from mmi1's 'o1' port, and the output will be from mmi2's 'o3' port after mirroring. I'll add these ports to the main component and draw them for clarity.

I should make sure all connections are correctly labeled and that the routing doesn't cause any overlaps. Also, I'll check that all parameters are correctly converted to floats and that I'm using the right methods without any typos.
</think>



import gdsfactory as gf

mzi = gf.Component()

mmi1 = mzi.add_ref(gf.components.mmi1x2())
mmi1.move((0, 0))

mmi2 = mzi.add_ref(gf.components.mmi1x2())
mmi2.mirror()
mmi2.move((200, 0))

phase_shifter = mzi.add_ref(gf.components.straight_heater_metal(length=10.0))
phase_shifter.move((100, 0))

gf.routing.route_bundle(
    mzi,
    [mmi1.ports['o2'], mmi1.ports['o3']],
    [phase_shifter.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    mzi,
    [phase_shifter.ports['o2']],
    [mmi2.ports['o1'], mmi2.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

mzi.add_port('o1', port=mmi1.ports['o1'])
mzi.add_port('o2', port=mmi2.ports['o3'])

mzi.draw_ports()
mzi.plot()