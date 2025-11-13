# Problem 4, Sample 0, Attempt 2
# Generated: 2025-11-12T14:58:36.610174

<think>
Alright, I'm trying to create an optical QPSK transmitter using the specified components. Let me break down the problem and figure out how to approach it step by step.

First, I need to understand the components required:

1. Two Mach-Zehnder Modulators (mzm_i and mzm_q)
2. One MMI1x2 Splitter (splitter)
3. One MMI2x1 Combiner (combiner)
4. Two phase biasers (pb_i and pb_q)

From the reference, I know that the MMI2x1 component doesn't exist, so I'll have to mirror an MMI1x2 component to create the combiner. That's a common workaround.

Next, I need to figure out how these components connect. The splitter will take the input and split it into two paths. Each path will go through a Mach-Zehnder Modulator and a phase biaser before combining again with the combiner.

I should start by placing the splitter at the origin (0,0). Then, the two MZMs will be placed side by side, but to prevent routing collisions, I'll offset them vertically. Maybe place one at (100, 50) and the other at (100, -50). The combiner will be at (200, 0) to ensure enough horizontal spacing.

For the phase biasers, I'll place them after each MZM. So, after mzm_i at (100,50), pb_i will be at (150,50), and similarly for mzm_q and pb_q at (150,-50).

Now, connecting the ports:

- The splitter's o2 and o3 ports will connect to the inputs of mzm_i and mzm_q respectively.
- The outputs of mzm_i and mzm_q will go to the inputs of pb_i and pb_q.
- The outputs of pb_i and pb_q will then connect to the combiner's o2 and o1 ports.

I need to make sure all connections are properly routed using route_single() for each connection since they are 1-to-1. Also, I should verify that all ports are correctly named according to the component references.

I should also check for any syntax errors, like using only ASCII characters and ensuring all numbers are valid floats. For example, using 10.0 instead of 10 or 10.0.5.

Putting it all together, I'll instantiate each component, move them to their positions, route the connections, and expose the external ports. Finally, I'll draw the ports and plot the layout to visualize everything.</think>

<analysis>
We need to create an optical QPSK transmitter with:
  1. Two Mach-Zehnder Modulators (mzm_i, mzm_q)
  2. One MMI1x2 Splitter
  3. One mirrored MMI1x2 Combiner (used as MMI2x1)
  4. Two phase biasers (pb_i, pb_q)

Component arrangement:
  - Splitter at (0, 0)
  - MZMs at (100, 50) and (100, -50) - vertical separation for routing
  - Phase biasers at (150, 50) and (150, -50)
  - Combiner at (200, 0)

Port connections:
  - Splitter o2 -> mzm_i o1
  - Splitter o3 -> mzm_q o1
  - mzm_i o2 -> pb_i o1
  - mzm_q o2 -> pb_q o1
  - pb_i o2 -> combiner o2
  - pb_q o2 -> combiner o1

Routing strategy:
  - Use route_single() for all connections due to 1-to-1 routing
  - Ensure proper spacing between components (20um minimum)
  - Verify all ports have correct cardinal orientations
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Instantiate components
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

mzm_i = r.add_ref(gf.components.mzm())
mzm_i.move((100, 50))

mzm_q = r.add_ref(gf.components.mzm())
mzm_q.move((100, -50))

pb_i = r.add_ref(gf.components.coupler())
pb_i.move((150, 50))

pb_q = r.add_ref(gf.components.coupler())
pb_q.move((150, -50))

# Create mirrored combiner from mmi1x2
combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((200, 0))

# Route connections
gf.routing.route_single(r, splitter.ports['o2'], mzm_i.ports['o1'], cross_section='strip', radius=15)
gf.routing.route_single(r, splitter.ports['o3'], mzm_q.ports['o1'], cross_section='strip', radius=15)

gf.routing.route_single(r, mzm_i.ports['o2'], pb_i.ports['o1'], cross_section='strip', radius=15)
gf.routing.route_single(r, mzm_q.ports['o2'], pb_q.ports['o1'], cross_section='strip', radius=15)

gf.routing.route_single(r, pb_i.ports['o2'], combiner.ports['o2'], cross_section='strip', radius=15)
gf.routing.route_single(r, pb_q.ports['o2'], combiner.ports['o1'], cross_section='strip', radius=15)

# Expose external ports
r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>