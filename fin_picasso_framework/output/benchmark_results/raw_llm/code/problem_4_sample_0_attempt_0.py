# Problem 4, Sample 0, Attempt 0
# Generated: 2025-11-12T17:08:59.011495

<think>
Okay, so I need to create an optical QPSK transmitter using the given components. Let me think through how to approach this.

First, I remember that a QPSK transmitter typically uses two Mach-Zehnder Modulators (MZMs) for the I and Q channels. These modulators are driven by electrical signals to phase-shift the light. Then, the signals from both MZMs need to be combined, which is where the MMI components come in.

The problem specifies using an MMI1x2 splitter and an MMI2x1 combiner. Wait, but I think in GDSFactory, the MMI2x1 might not exist, so I should use the MMI1x2 and mirror it to create the 2x1 combiner. That makes sense because mirroring the splitter would reverse its function to combine two inputs into one output.

So, the structure should be: the input optical signal comes in, splits into two paths using the splitter. Each path goes through an MZM (mzm_i and mzm_q), then the phase biasers (pb_i and pb_q) to set the bias, and then both outputs are combined back using the combiner.

Now, I need to instantiate each component. The splitter and combiner are both MMI1x2, but the combiner is mirrored. The MZMs and phase biasers are added as separate references.

Next, I have to position these components without overlapping. The splitter is at (0,0), then the MZMs are placed to the right, each moved by 250 units in x-direction. The phase biasers are placed after each MZM, moved a bit further. The combiner is placed after that, maybe around (750, 0) for the x-coordinate.

For routing, I need to connect the splitter's output to the MZMs' inputs. Since there are two connections, I should use route_bundle to avoid messy routing and ensure proper separation. The same goes for connecting the MZMs' outputs through the phase biasers to the combiner's inputs.

I have to make sure all ports are correctly labeled and connected. The splitter's 'o2' and 'o3' ports connect to the MZMs' 'o1' ports. After modulation, the MZMs' 'o2' ports connect to the phase biasers' 'o1', and then the phase biasers' 'o2' connect to the combiner's 'o1' and 'o2'. 

I should use route_bundle for both the splitter to MZMs and the MZMs through phase biasers to the combiner. The cross-section is 'strip', radius 20, and separation 20 to maintain DRC safety.

Finally, the external ports are added to the main component. The input port comes from the splitter's 'o1', and the output goes to the combiner's 'o3' (since it's mirrored, o3 is the combined output).

Putting it all together, the code will instantiate each component, move them appropriately, route the connections using route_bundle, and expose the necessary ports.</think>

import gdsfactory as gf

r = gf.Component()

splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

mzm_i = r.add_ref(gf.components.mzm())
mzm_i.move((250, 0))

mzm_q = r.add_ref(gf.components.mzm())
mzm_q.move((250, 200))

pb_i = r.add_ref(gf.components.bias_tee())
pb_i.move((500, 0))

pb_q = r.add_ref(gf.components.bias_tee())
pb_q.move((500, 200))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((750, 0))

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
    [pb_i.ports['o1'], pb_q.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [pb_i.ports['o2'], pb_q.ports['o2']],
    [combiner.ports['o1'], combiner.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

r.add_port('o1', port=combiner.ports['o3'])
r.add_port('o2', port=combiner.ports['o3'])
r.add_port('o3', port=combiner.ports['o3'])
r.add_port('o4', port=combiner.ports['o3'])

r.draw_ports()
r.plot()