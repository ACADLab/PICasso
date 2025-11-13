# Problem 4, Sample 2, Attempt 0
# Error: Syntax error: unterminated string literal (detected at line 6) (<unknown>, line 6)
# Raw code:
<think>
Okay, I need to create a Python script using GDSFactory to design an optical QPSK transmitter. The components required are two Mach-Zehnder Modulators (mzm_i and mzm_q), one MMI1x2 Splitter, one MMI2x1 Combiner, and two phase biasers (pb_i and pb_q). 

First, I'll start by importing the necessary GDSFactory components. I'll create a new component 'r' which will hold all the parts.

Next, I'll instantiate each component. The splitter is an MMI1x2, so I'll use mmi1x2(). Similarly, the combiner is an MMI2x1, which I can create by mirroring an mmi1x2 component. I'll add these using add_ref and then move them to position them correctly.

For the Mach-Zehnder Modulators, I'll use the mzm component with appropriate settings. Each mzm will have a length of 500 microns and a width of 2.5 microns. I'll add these and move them into place, probably positioning them below the splitter and combiner to avoid overlap.

The phase biasers are needed to control the phase of the modulators. I'll use the phase_bezier component with a length of 50 microns for each. I'll add these and position them near the modulators.

Now, I need to connect the splitter to the modulators and then combine them using the combiner. I'll use route_bundle for clean routing. The splitter's output ports (o2 and o3) will connect to the input ports of the two mzm components. Then, the output ports of the mzm components will connect to the combiner's input ports.

I'll make sure to set the cross_section to 'strip' and use a radius of 20 for the bends to prevent DRC issues. The separation parameter in route_bundle will be set to 20 to ensure the routes don't overlap.

Finally, I'll expose the external ports o1 and o2 from the splitter and combiner respectively, add all the ports to the component, and draw them for visualization.

I need to ensure all connections are correctly made and that the layout is DRC-safe with at least 20um spacing between parts. I'll double-check the positions and connections to make sure everything is properly aligned and routed.
</think>



import gdsfactory as gf

r = gf.Component()

splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((250, 0))

mzm_i = r.add_ref(gf.components.mach_zehnder_modulator(length=500.0, width=2.5))
mzm_i.move((100, -100))

mzm_q = r.add_ref(gf.components.mach_zehnder_modulator(length=500.0, width=2.5))
mzm_q.move((100, 100))

pb_i = r.add_ref(gf.components.phase_bezier(length=50.0))
pb_i.move((150, -150))

pb_q = r.add_ref(gf.components.phase_bezier(length=50.0))
pb_q.move((150, 150))

gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [mzm_i.ports['i'], mzm_q.ports['i']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [mzm_i.ports['o'], mzm_q.ports['o']],
    [combiner.ports['o1'], combiner.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

r.draw_ports()
r.plot()

# Cleaned code:
<think>
Okay, I need to create a Python script using GDSFactory to design an optical QPSK transmitter. The components required are two Mach-Zehnder Modulators (mzm_i and mzm_q), one MMI1x2 Splitter, one MMI2x1 Combiner, and two phase biasers (pb_i and pb_q). 

First, I'll start by importing the necessary GDSFactory components. I'll create a new component 'r' which will hold all the parts.

Next, I'll instantiate each component. The splitter is an MMI1x2, so I'll use mmi1x2(). Similarly, the combiner is an MMI2x1, which I can create by mirroring an mmi1x2 component. I'll add these using add_ref and then move them to position them correctly.

For the Mach-Zehnder Modulators, I'll use the mzm component with appropriate settings. Each mzm will have a length of 500 microns and a width of 2.5 microns. I'll add these and move them into place, probably positioning them below the splitter and combiner to avoid overlap.

The phase biasers are needed to control the phase of the modulators. I'll use the phase_bezier component with a length of 50 microns for each. I'll add these and position them near the modulators.

Now, I need to connect the splitter to the modulators and then combine them using the combiner. I'll use route_bundle for clean routing. The splitter's output ports (o2 and o3) will connect to the input ports of the two mzm components. Then, the output ports of the mzm components will connect to the combiner's input ports.

I'll make sure to set the cross_section to 'strip' and use a radius of 20 for the bends to prevent DRC issues. The separation parameter in route_bundle will be set to 20 to ensure the routes don't overlap.

Finally, I'll expose the external ports o1 and o2 from the splitter and combiner respectively, add all the ports to the component, and draw them for visualization.

I need to ensure all connections are correctly made and that the layout is DRC-safe with at least 20.0 spacing between parts. I'll double-check the positions and connections to make sure everything is properly aligned and routed.
</think>



import gdsfactory as gf

r = gf.Component()

splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((250, 0))

mzm_i = r.add_ref(gf.components.mach_zehnder_modulator(length=500.0, width=2.5))
mzm_i.move((100, -100))

mzm_q = r.add_ref(gf.components.mach_zehnder_modulator(length=500.0, width=2.5))
mzm_q.move((100, 100))

pb_i = r.add_ref(gf.components.phase_bezier(length=50.0))
pb_i.move((150, -150))

pb_q = r.add_ref(gf.components.phase_bezier(length=50.0))
pb_q.move((150, 150))

gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [mzm_i.ports['i'], mzm_q.ports['i']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [mzm_i.ports['o'], mzm_q.ports['o']],
    [combiner.ports['o1'], combiner.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

r.draw_ports()
r.plot()
