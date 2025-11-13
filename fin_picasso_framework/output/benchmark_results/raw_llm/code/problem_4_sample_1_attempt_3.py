# Problem 4, Sample 1, Attempt 3
# Generated: 2025-11-12T15:00:40.289775

<think>
Alright, I need to address the problem of creating an optical QPSK transmitter using the specified components. Let me start by understanding the requirements and the error I encountered.

First, the components needed are two Mach-Zehnder Modulators (mzm_i and mzm_q), one MMI1x2 Splitter, one MMI2x1 Combiner, and two phase biasers (pb_i and pb_q). 

In my previous attempt, I received an error where a port 'o3' was not recognized. Looking back, I realize that I might have incorrectly connected ports or used the wrong port names. I need to ensure that I'm using the exact port names provided in the component references.

The error message indicated that 'o3' isn't a valid port. Checking the component references, the MMI1x2 has ports o1, o2, and o3. However, the phase biasers (straight_heater_metal) only have o1 and o2. So, I must have mistakenly connected a port that doesn't exist on the phase biaser.

To fix this, I'll re-examine the connections. The splitter (MMI1x2) should connect to the inputs of the two MZMs. Each MZM will have its own phase biaser on one arm. The outputs of the MZMs will then connect to the combiner (MMI2x1), which is a mirrored MMI1x2.

I'll start by instantiating the splitter, the two MZMs, the two phase biasers, and the combiner. I'll position each component with appropriate spacing to avoid routing collisions. 

Next, I'll route the connections using route_single() for each connection since they are 1-to-1. I'll make sure to use the correct port names: splitter's o2 and o3 connect to the first and second MZMs' o1 ports. The MZMs' o2 ports will connect to the phase biasers' o1. The phase biasers' o2 will then connect to the combiner's o1 and o2 ports.

I'll ensure that all components are properly moved and that the ports are correctly referenced. I'll avoid using any invalid port names and double-check each connection.

Finally, I'll add the external ports for the splitter's o1 and the combiner's o3 to complete the design.</think>

<analysis>
The optical QPSK transmitter requires:
1. 1x2 MMI Splitter to divide input into I and Q paths
2. Two MZMs (mzm_i and mzm_q) for modulation
3. Two phase biasers (pb_i, pb_q) for phase control
4. 2x1 MMI Combiner to recombine I and Q outputs

Component arrangement:
- Splitter at (0,0)
- MZMs at (100,0) and (100, 50) with vertical separation for routing
- Phase biasers at (200,0) and (200,50)
- Combiner at (300,0)

Port connections:
- Splitter o2 -> mzm_i o1
- Splitter o3 -> mzm_q o1
- mzm_i o2 -> pb_i o1
- mzm_q o2 -> pb_q o1
- pb_i o2 -> combiner o1
- pb_q o2 -> combiner o2

All components use default settings unless specified
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Instantiate components
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0,0))

mzm_i = r.add_ref(gf.components.mzm())
mzm_i.move((100,0))

mzm_q = r.add_ref(gf.components.mzm())
mzm_q.move((100,50))

pb_i = r.add_ref(gf.components.straight_heater_metal())
pb_i.move((200,0))

pb_q = r.add_ref(gf.components.straight_heater_metal())
pb_q.move((200,50))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((300,0))

# Route connections
gf.routing.route_single(r, splitter.ports['o2'], mzm_i.ports['o1'], cross_section='strip', radius=15)
gf.routing.route_single(r, splitter.ports['o3'], mzm_q.ports['o1'], cross_section='strip', radius=15)

gf.routing.route_single(r, mzm_i.ports['o2'], pb_i.ports['o1'], cross_section='strip', radius=15)
gf.routing.route_single(r, mzm_q.ports['o2'], pb_q.ports['o1'], cross_section='strip', radius=15)

gf.routing.route_single(r, pb_i.ports['o2'], combiner.ports['o1'], cross_section='strip', radius=15)
gf.routing.route_single(r, pb_q.ports['o2'], combiner.ports['o2'], cross_section='strip', radius=15)

# Add external ports
r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>