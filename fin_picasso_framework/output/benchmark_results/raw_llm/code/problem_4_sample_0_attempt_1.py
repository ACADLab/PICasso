# Problem 4, Sample 0, Attempt 1
# Generated: 2025-11-12T17:09:32.265593

<think>
Alright, I need to create an optical QPSK transmitter using the specified components. Let me break down the problem and figure out how to approach it step by step.

First, I remember that a QPSK transmitter typically uses two Mach-Zehnder Modulators (MZMs) for the I and Q channels. These modulators are driven by electrical signals to phase-shift the light. Then, the signals from both MZMs need to be combined, which is where the MMI components come in.

The problem specifies using an MMI1x2 splitter and an MMI2x1 combiner. Wait, but I think in GDSFactory, the MMI2x1 might not exist, so I should use the MMI1x2 and mirror it to create the 2x1 combiner. That makes sense because mirroring the splitter would reverse its function to combine two inputs into one output.

So, the structure should be: the input optical signal comes in, splits into two paths using the splitter. Each path goes through an MZM (mzm_i and mzm_q), then the phase biasers (pb_i and pb_q) to set the bias, and then both outputs are combined back using the combiner.

Now, considering the components and their ports:

- The splitter (MMI1x2) has an input port o1 and two output ports o2 and o3.
- Each MZM has an input and output port. Let's say mzm_i has o1 as input and o2 as output, and similarly for mzm_q.
- The phase biasers each have an input and output. So pb_i would take the output of mzm_i and pass it through, same for pb_q.
- The combiner, which is the mirrored MMI1x2, will have two input ports (from the two MZMs) and one output port.

Next, I need to arrange these components spatially. The splitter should be at the origin (0,0). The MZMs should be placed after the splitter, each in a different location to avoid routing collisions. I'll place mzm_i at (200, 0) and mzm_q at (200, 100). The phase biasers will follow each MZM, so pb_i at (300, 0) and pb_q at (300, 100). The combiner will be at (400, 50) to combine the two outputs.

For routing, I'll need to connect the splitter's o2 to mzm_i's o1, and o3 to mzm_q's o1. Then, route the outputs of mzm_i and mzm_q through the phase biasers to their respective inputs. Finally, connect the outputs of pb_i and pb_q to the combiner's input ports.

I should use route_single() for each individual connection to ensure proper routing without any fan-out issues. Each route will have a radius of 20um to prevent routing collisions and ensure a safe bend radius.

I also need to make sure that all components are properly spaced. The minimum spacing between components should be at least 200um. I'll arrange them in a way that each component is 100um apart vertically where necessary, and 200um apart horizontally.

Finally, I'll add the external ports to the main component, o1 from the splitter's input and o2 from the combiner's output.

Now, I'll structure the code accordingly, making sure to use the correct component references, mirror where necessary, and route each connection properly.</think>

<analysis>
The optical QPSK transmitter requires:
1. An MMI1x2 splitter to divide the input signal
2. Two Mach-Zehnder Modulators (mzm_i, mzm_q) for phase modulation
3. Two phase biasers (pb_i, pb_q) to set modulator biases
4. An MMI2x1 combiner to recombine the signals

Component arrangement:
- Splitter at (0, 0)
- mzm_i at (200, 0)
- mzm_q at (200, 100)
- pb_i at (300, 0)
- pb_q at (300, 100)
- Combiner at (400, 50)

Port connections:
- Splitter o2 -> mzm_i o1
- Splitter o3 -> mzm_q o1
- mzm_i o2 -> pb_i o1
- mzm_q o2 -> pb_q o1
- pb_i o2 -> combiner o2
- pb_q o2 -> combiner o1

Routing strategy:
- Use route_single() for individual connections
- Maintain 200um spacing between components
- Use 20um bend radius for safety
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
mzm_q.move((200, 100))

pb_i = r.add_ref(gf.components.coupler())
pb_i.move((300, 0))

pb_q = r.add_ref(gf.components.coupler())
pb_q.move((300, 100))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((400, 50))

# Route connections
gf.routing.route_single(r, splitter.ports['o2'], mzm_i.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(r, splitter.ports['o3'], mzm_q.ports['o1'], cross_section='strip', radius=20)

gf.routing.route_single(r, mzm_i.ports['o2'], pb_i.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(r, mzm_q.ports['o2'], pb_q.ports['o1'], cross_section='strip', radius=20)

gf.routing.route_single(r, pb_i.ports['o2'], combiner.ports['o2'], cross_section='strip', radius=20)
gf.routing.route_single(r, pb_q.ports['o2'], combiner.ports['o1'], cross_section='strip', radius=20)

# Add external ports
r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>