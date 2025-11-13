# Problem 2, Sample 0, Attempt 2
# Generated: 2025-11-12T17:03:06.022659

<think>
Okay, I need to help the user fix their GDSFactory code for creating a Mach-Zehnder Modulator (MZM). The user provided their original code and an error message indicating a problem during execution. Let me go through this step by step.

First, the error message says: "EXECUTION_ERROR: All ports at the target (end) must have the same angle. r.start.t=r0 210000,-100000/r.end.t=r0 410000,0". This suggests there's an issue with the routing, specifically that the angles at the target ports don't match, which is causing the route to fail.

Looking at the user's original code, I see they used route_bundle() for connecting the splitter to the phase shifters and then the phase shifters to the combiner. However, the error might be due to the way the ports are connected or the routing parameters.

I remember from the guidelines that route_bundle() is for multiple parallel connections, and each connection should have the same angle. Maybe the issue is that the phase shifters are not aligned correctly, causing different angles at the target ports.

In the original code, the phase shifters were placed at (100, 50) and (100, -50). The splitter was at (0,0) and the combiner at (250,0). The route_bundle() might be trying to connect ports that are not aligned, leading to different angles.

I think the solution is to ensure that the phase shifters are placed in a way that their output ports align properly with the combiner's ports. Maybe placing them horizontally after the splitter would help. Also, using route_single() for each connection might prevent angle mismatches.

So, I'll adjust the component placement. The splitter stays at (0,0). The phase shifters should be placed after the splitter, say at (200, 0) and (200, 0), but mirrored vertically. Wait, no, that might not work. Alternatively, place them side by side horizontally, ensuring their outputs are aligned for the combiner.

I'll move the phase shifters to (200, 0) and (200, 0) but mirrored vertically. Then, use route_single() for each connection from the splitter to the phase shifters and from the phase shifters to the combiner.

Also, the combiner needs to be mirrored correctly. In the original code, the combiner was moved to (250,0), but maybe it should be further away to avoid routing issues. Let's place it at (400,0).

I'll structure the code to add the splitter, then the phase shifters, then the combiner. Then, route each connection individually using route_single() to ensure proper alignment and angles.

Testing this approach should fix the routing error by ensuring all target ports have the same angle and proper connections.</think>

<analysis>
The error occurs because the routing angles between components are mismatched. To fix this:
1. Properly align components vertically for consistent routing angles
2. Use route_single() for individual connections instead of route_bundle()
3. Ensure proper spacing between components (200um minimum)
4. Verify all ports have matching angles at connections

Component arrangement:
  - Splitter at (0, 0)
  - Phase shifters at (200, 0) - placed horizontally for better alignment
  - Combiner at (400, 0) - increased spacing for safety

Port connections:
  - Splitter o2 -> Phase shifter1 o1
  - Splitter o3 -> Phase shifter2 o1
  - Phase shifter1 o2 -> Combiner o2
  - Phase shifter2 o2 -> Combiner o1

Routing strategy:
  - Use route_single() for all connections
  - Ensure consistent routing angles by aligning components properly
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# 1. Instantiate components with settings
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

phase_shifter1 = r.add_ref(gf.components.straight_heater_metal(length=10))
phase_shifter1.move((200, 0))

phase_shifter2 = r.add_ref(gf.components.straight_heater_metal(length=10))
phase_shifter2.mirror()
phase_shifter2.move((200, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((400, 0))

# 2. Route connections
gf.routing.route_single(r, splitter.ports['o2'], phase_shifter1.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(r, splitter.ports['o3'], phase_shifter2.ports['o1'], cross_section='strip', radius=20)

gf.routing.route_single(r, phase_shifter1.ports['o2'], combiner.ports['o2'], cross_section='strip', radius=20)
gf.routing.route_single(r, phase_shifter2.ports['o2'], combiner.ports['o1'], cross_section='strip', radius=20)

# 3. Expose external ports
r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

# 4. Finalize
r.draw_ports()
r.plot()
</result>