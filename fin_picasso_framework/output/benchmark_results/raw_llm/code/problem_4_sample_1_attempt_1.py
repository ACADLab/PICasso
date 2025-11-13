# Problem 4, Sample 1, Attempt 1
# Generated: 2025-11-12T17:10:15.198570

<think>
Alright, I need to create a Python script using GDSFactory to design an optical QPSK transmitter. The components required are two Mach-Zehnder Modulators (mzm_i and mzm_q), one MMI1x2 Splitter, one MMI2x1 Combiner, and two phase biasers (pb_i and pb_q). 

First, I'll start by importing the necessary GDSFactory modules. I remember that I need to import components and maybe some for routing.

I'll create a new component called 'r' which will be the main component containing all the parts. Then, I'll instantiate each required component and add them to 'r'. 

For the splitter, I'll use mmi1x2 and place it at the origin. The combiner also uses mmi1x2, but I need to mirror it after adding it to 'r' to get the correct orientation. I'll position the combiner to the right of the splitter, ensuring there's enough spacing for routing.

Next, I'll add the two Mach-Zehnder Modulators (mzm_i and mzm_q) below the splitter and combiner. I'll position them with some vertical offset to prevent routing collisions. Similarly, I'll add the phase biasers (pb_i and pb_q) below the MZMs, again with vertical spacing.

Now, I need to connect all these components using the routing functions. I'll use route_single for each connection since they are one-to-one. For example, connect the splitter's o2 to mzm_i's o1, and o3 to mzm_q's o1. Then, connect the MZMs' output ports to the combiner's ports. Finally, connect the phase biasers to the MZMs' other ports.

I'll make sure to set the cross_section to 'strip' and adjust the radius and any other parameters as needed. After routing, I'll add the external ports for the entire component, such as 'o1' and 'o2', and then draw and plot the final layout.

I need to ensure that all components are properly spaced to meet the minimum 200um requirement. I'll check each component's position and adjust if necessary to prevent any routing issues. Also, I'll verify that all method calls are complete and that there are no syntax errors, especially avoiding Unicode characters and ensuring all numbers are valid floats.

Finally, I'll review the code structure to make sure it follows the example provided, with clear comments and proper organization.</think>

<analysis>
The optical QPSK transmitter requires:
  1. Two Mach-Zehnder Modulators (mzm_i, mzm_q)
  2. One MMI1x2 Splitter
  3. One MMI2x1 Combiner (created by mirroring mmi1x2)
  4. Two phase biasers (pb_i, pb_q)

Component arrangement:
  - Splitter at (0, 0)
  - Combiner at (250, 0)
  - MZMs at (100, 100) and (100, -100) with vertical separation
  - Phase biasers at (200, 100) and (200, -100)

Port connections:
  - Splitter o2 -> mzm_i o1
  - Splitter o3 -> mzm_q o1
  - mzm_i o2 -> combiner o2
  - mzm_q o2 -> combiner o1
  - mzm_i o3 -> pb_i
  - mzm_q o3 -> pb_q

Special considerations:
  - Use route_single() for all connections
  - Proper spacing between components (200um minimum)
  - Mirror combiner after add_ref()
  - Use 'strip' cross_section for routing
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Instantiate components
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((250, 0))

mzm_i = r.add_ref(gf.components.mzm())
mzm_i.move((100, 100))

mzm_q = r.add_ref(gf.components.mzm())
mzm_q.move((100, -100))

pb_i = r.add_ref(gf.components.coupler())
pb_i.move((200, 100))

pb_q = r.add_ref(gf.components.coupler())
pb_q.move((200, -100))

# Route connections
gf.routing.route_single(r, splitter.ports['o2'], mzm_i.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(r, splitter.ports['o3'], mzm_q.ports['o1'], cross_section='strip', radius=20)

gf.routing.route_single(r, mzm_i.ports['o2'], combiner.ports['o2'], cross_section='strip', radius=20)
gf.routing.route_single(r, mzm_q.ports['o2'], combiner.ports['o1'], cross_section='strip', radius=20)

gf.routing.route_single(r, mzm_i.ports['o3'], pb_i.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(r, mzm_q.ports['o3'], pb_q.ports['o1'], cross_section='strip', radius=20)

# Add external ports
r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>