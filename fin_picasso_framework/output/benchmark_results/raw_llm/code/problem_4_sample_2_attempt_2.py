# Problem 4, Sample 2, Attempt 2
# Generated: 2025-11-12T17:13:09.980137

<think>
Okay, I need to create a Python code for an optical QPSK transmitter using the specified components. Let me break down the problem and figure out how to approach this.

First, the components I need are two Mach-Zehnder Modulators (mzm_i and mzm_q), one MMI1x2 Splitter, one MMI2x1 Combiner, and two phase biasers (pb_i and pb_q). 

I remember from the reference that mmi2x1 doesn't exist, so I should use mmi1x2 and mirror it to create the 2x1 combiner. Also, all components must be from GDSFactory, so I'll check each one exists.

Looking at the error from the previous attempt, it mentioned a port named 'bias' which isn't valid. So, I need to ensure all ports I'm connecting are correct. The phase biasers probably have different ports, maybe 'o1' and 'o2' or something else. I'll have to verify their port names from the reference.

The layout should have proper spacing. The Splitter and Combiner should be spaced at least 200um apart, and the Modulators should be placed after that with enough space to prevent routing collisions.

For routing, I'll need to connect the splitter to both mzm_i and mzm_q. Then, route their outputs to the combiner. The phase biasers should be connected to the inputs of the mzm's.

I should use route_bundle for multiple connections to avoid fan-out issues. Also, ensure that all ports are properly connected without any dangling ports.

Let me outline the steps:

1. Instantiate the Splitter, two Modulators, Combiner, and two Phase Biasers.
2. Position each component with sufficient spacing.
3. Connect the Splitter's output to both Modulators using route_bundle.
4. Connect each Modulator's output to the Combiner using route_bundle.
5. Connect the Phase Biasers to the Modulators' inputs.
6. Ensure all external ports are added correctly.

I need to make sure all port names match exactly what's in the component references. For example, the Splitter's output ports are 'o2' and 'o3', which will connect to the Modulators' inputs.

Also, the Combiner needs to be mirrored to function as a 2x1, so I'll call mirror() on its reference after adding it.

I'll structure the code by adding each component, moving them to the right positions, routing the connections, and then adding the external ports.

Now, putting it all together in code, making sure to follow the syntax rules and avoid any errors from the previous attempt.</think>

<analysis>
Optical QPSK Transmitter Design:

Components Needed:
1. MMI1x2 Splitter (splitter)
2. Two Mach-Zehnder Modulators (mzm_i, mzm_q)
3. MMI2x1 Combiner (combiner) - created by mirroring mmi1x2
4. Two Phase Biasers (pb_i, pb_q)

Component Arrangement:
- Splitter at (0, 0)
- mzm_i at (200, 0)
- mzm_q at (200, 0) - horizontally offset for routing
- Combiner at (400, 0)
- Phase biasers at (100, 50) and (100, -50)

Port Connections:
- Splitter o2 -> mzm_i o1
- Splitter o3 -> mzm_q o1
- mzm_i o2 -> combiner o2
- mzm_q o2 -> combiner o1
- pb_i -> mzm_i input
- pb_q -> mzm_q input

Critical Considerations:
- Use route_bundle() for multiple connections
- Maintain 200um spacing between components
- Properly mirror combiner from mmi1x2
- Ensure all ports are correctly named and connected
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Instantiate components
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

mzm_i = r.add_ref(gf.components.mzm())
mzm_i.move((200, 0))

mzm_q = r.add_ref(gf.components.mzm())
mzm_q.move((200, 0))  # Adjust x-coordinate as needed

# Create 2x1 combiner by mirroring mmi1x2
combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((400, 0))

# Add phase biasers
pb_i = r.add_ref(gf.components.straight())
pb_i.move((100, 50))

pb_q = r.add_ref(gf.components.straight())
pb_q.move((100, -50))

# Route connections
gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [mzm_i.ports['o1'], mzm_q.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [mzm_i.ports['o2'], mzm_q.ports['o2']],
    [combiner.ports['o2'], combiner.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

# Connect phase biasers to mzm inputs
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

# Add external ports
r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>