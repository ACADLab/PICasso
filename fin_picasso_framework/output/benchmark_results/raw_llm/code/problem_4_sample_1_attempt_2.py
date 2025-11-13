# Problem 4, Sample 1, Attempt 2
# Generated: 2025-11-12T17:10:46.011096

<think>
Okay, so I need to create an optical QPSK transmitter using the specified components. Let me break down the problem and figure out how to approach it.

First, the components I have are two Mach-Zehnder Modulators (mzm_i and mzm_q), an MMI1x2 Splitter, an MMI2x1 Combiner, and two phase biasers (pb_i and pb_q). 

I remember from the reference that the MMI2x1 doesn't exist, so I'll need to use the mmi1x2 component and mirror it to create the combiner. That's a crucial point because using the wrong component would cause errors.

The QPSK transmitter typically has a structure where the input is split into two paths, each modulated by a Mach-Zehnder Modulator, and then combined again. So, the splitter will take the input and divide it into two equal parts, each going to a different modulator. Then, the combiner will merge the two modulated signals.

I need to think about the arrangement of these components. The splitter should be at the beginning, followed by the phase biasers and modulators. After that, the combiner will bring them together. 

Spacing is important to prevent routing collisions. The minimum spacing should be 200um, but for complex designs, it's better to have more. I'll place each component at least 200um apart. For example, the splitter at (0,0), then the phase biasers at (200, 0), the modulators at (400, 0) and (400, 100), and the combiner at (600, 0).

Ports need to be connected correctly. The splitter's output ports (o2 and o3) will connect to the phase biasers' input ports. Each phase biaser will then connect to the corresponding modulator. The modulators' outputs will connect to the combiner's input ports.

I should use the route_bundle function for connecting multiple ports at once, especially between the splitter and the two phase biasers. Similarly, route_bundle will be used to connect the two modulators to the combiner.

I need to make sure that all the port names are correct. The splitter's ports are o1, o2, o3. The phase biasers have input ports like o1 and output ports o2. The modulators have o1 and o2 as well. The combiner, after mirroring, will have o1 and o2 as inputs and o3 as the output.

I also need to mirror the combiner correctly. After adding the mmi1x2 component, I'll call mirror() on the reference to flip it, making it function as a 2x1 combiner.

I should avoid connecting more than two ports at a time to prevent netlist errors. So, each connection will be a one-to-one or one-to-two using route_bundle.

Finally, I'll add the external ports for the input and output of the transmitter. The input will be the splitter's o1, and the output will be the combiner's o3.

Putting it all together, I'll write the code step by step, making sure each component is added, moved, and connected correctly with proper routing and mirroring where needed.</think>

<analysis>
To create an optical QPSK transmitter, we need:
1. A splitter to divide the input signal
2. Two Mach-Zehnder Modulators (MZMs) for modulation
3. Two phase biasers to control the MZMs
4. A combiner to recombine the modulated signals

Component arrangement:
- Splitter at (0, 0)
- Phase biaser I at (200, 0)
- Phase biaser Q at (200, -100) - vertical separation for routing
- MZM I at (400, 0)
- MZM Q at (400, 100) - vertical separation for routing
- Combiner at (600, 0) - mirrored for correct orientation

Port connections:
- Splitter o2 -> Phase biaser I o1
- Splitter o3 -> Phase biaser Q o1
- Phase biaser I o2 -> MZM I o1
- Phase biaser Q o2 -> MZM Q o1
- MZM I o2 -> Combiner o1
- MZM Q o2 -> Combiner o2

Critical considerations:
- Use route_bundle() for parallel connections
- Mirror combiner after add_ref() for correct 2x1 orientation
- Maintain minimum 200um spacing between components
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Add splitter
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

# Add phase biasers
pb_i = r.add_ref(gf.components.coupler())
pb_i.move((200, 0))

pb_q = r.add_ref(gf.components.coupler())
pb_q.move((200, -100))

# Add Mach-Zehnder Modulators
mzm_i = r.add_ref(gf.components.mzm())
mzm_i.move((400, 0))

mzm_q = r.add_ref(gf.components.mzm())
mzm_q.move((400, 100))

# Add combiner (mirrored mmi1x2)
combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((600, 0))

# Route connections
gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [pb_i.ports['o1'], pb_q.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_single(
    r,
    pb_i.ports['o2'],
    mzm_i.ports['o1'],
    cross_section='strip',
    radius=20
)

gf.routing.route_single(
    r,
    pb_q.ports['o2'],
    mzm_q.ports['o1'],
    cross_section='strip',
    radius=20
)

gf.routing.route_bundle(
    r,
    [mzm_i.ports['o2'], mzm_q.ports['o2']],
    [combiner.ports['o1'], combiner.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

# Add external ports
r.add_port('o1', splitter.ports['o1'])
r.add_port('o2', combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>