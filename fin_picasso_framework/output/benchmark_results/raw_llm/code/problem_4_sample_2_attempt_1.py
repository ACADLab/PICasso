# Problem 4, Sample 2, Attempt 1
# Generated: 2025-11-12T17:12:41.297914

<think>
Alright, I'm trying to figure out how to create an optical QPSK transmitter using the specified components. Let me break down the problem step by step.

First, I need to understand the components involved. The transmitter requires two Mach-Zehnder Modulators (mzm_i and mzm_q), an MMI1x2 Splitter, an MMI2x1 Combiner, and two phase biasers (pb_i and pb_q). 

I remember that in GDSFactory, the MMI2x1 component doesn't exist, so I'll have to use the mmi1x2 component and mirror it to create the 2x1 combiner. That's a common workaround, so I'll make sure to do that correctly by adding the reference and then calling mirror() on it.

Next, I need to arrange these components spatially. The Splitter should be at the input, followed by the two Modulators, and then the Combiner at the output. The phase biasers will be placed after each modulator to apply the bias. 

I'll start by adding the Splitter at position (0,0). Then, I'll add the two Modulators side by side, ensuring they are spaced adequately to prevent routing collisions. The Combiner will be placed after the modulators, and the phase biasers will be positioned below each modulator.

For the ports, the Splitter's o1 will be the input, and the Combiner's o3 will be the output. Each modulator's output will connect to the Combiner's respective ports. The phase biasers will connect to the modulators' bias ports.

I need to make sure all connections are properly routed using either route_single() or route_bundle(). Since each connection is a single port-to-port connection, I'll use route_single() for each route. I'll also ensure that the cross_section is set appropriately, probably to 'strip' as default.

Spacing is crucial to avoid routing issues. I'll place each component with enough horizontal and vertical separation. For example, the Splitter will be at (0,0), the Modulators at (200, 0) and (200, 200), and the Combiner at (400, 0). The phase biasers will be positioned below each modulator with a vertical offset to prevent overlap.

I'll also need to mirror the Combiner after adding it to the circuit to ensure the correct port orientation. This is important because the default mmi1x2 has the outputs on the right side, and mirroring will flip it to function as a 2x1 combiner.

Finally, I'll add the external ports for the input and output, making sure all internal ports are connected without any dangling ports. I'll verify that each component's ports are correctly connected and that the layout is clean and organized.

I think that's the plan. Now, I'll translate this into the actual Python code, making sure to follow all the syntax rules and component references correctly.</think>

<analysis>
We need to create an optical QPSK transmitter with:
  1. MMI1x2 Splitter at input
  2. Two Mach-Zehnder Modulators (mzm_i, mzm_q)
  3. MMI2x1 Combiner at output
  4. Two phase biasers (pb_i, pb_q)

Component arrangement:
  - Splitter at (0, 0)
  - Modulators at (200, 0) and (200, 200) - vertical separation for routing
  - Combiner at (400, 0) - horizontal separation for safe routing
  - Phase biasers at (300, -50) and (300, 250) - below each modulator

Port connections:
  - Splitter o1 -> mzm_i o1
  - Splitter o2 -> mzm_q o1
  - mzm_i o2 -> combiner o1
  - mzm_q o2 -> combiner o2
  - pb_i -> mzm_i bias
  - pb_q -> mzm_q bias

Critical: Combiner needs mirror() called AFTER add_ref() for correct orientation
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# 1. Instantiate components with settings
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

mzm_i = r.add_ref(gf.components.mzm())
mzm_i.move((200, 0))

mzm_q = r.add_ref(gf.components.mzm())
mzm_q.move((200, 200))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((400, 0))

pb_i = r.add_ref(gf.components.straight())
pb_i.move((300, -50))

pb_q = r.add_ref(gf.components.straight())
pb_q.move((300, 250))

# 2. Route connections
gf.routing.route_single(r, splitter.ports['o1'], mzm_i.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(r, splitter.ports['o2'], mzm_q.ports['o1'], cross_section='strip', radius=20)

gf.routing.route_single(r, mzm_i.ports['o2'], combiner.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(r, mzm_q.ports['o2'], combiner.ports['o2'], cross_section='strip', radius=20)

gf.routing.route_single(r, pb_i.ports['o1'], mzm_i.ports['bias'], cross_section='strip', radius=20)
gf.routing.route_single(r, pb_q.ports['o1'], mzm_q.ports['bias'], cross_section='strip', radius=20)

# 3. Expose external ports
r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

r.add_port('bias_i', port=pb_i.ports['o2'])
r.add_port('bias_q', port=pb_q.ports['o2'])

r.draw_ports()
r.plot()
</result>