# Problem 1, Sample 0, Attempt 3
# Generated: 2025-11-12T14:48:40.648607

<think>
Okay, so I need to create a Mach-Zehnder interferometer (MZI) using GDSFactory. The user has specified that I should use two MMI1x2 components and a phase shifter. Let me break down the problem and figure out how to approach this.

First, I remember that an MZI typically consists of a splitter, two phase shifters, and a combiner. Since the user mentioned using MMI1x2 components, I'll need to use one as the splitter and another as the combiner, but I have to mirror the combiner to make it function as a 2x1 instead of 1x2.

I'll start by instantiating the components. I'll add the first MMI1x2 as the splitter and place it at the origin. Then, I'll add the phase shifter component. For the combiner, I'll add another MMI1x2 and mirror it so it can combine the two outputs from the phase shifters.

Next, I need to position these components properly. The splitter should be at (0,0). The phase shifter needs to be placed after the splitter. Since the phase shifter is longer, I'll position it at (100, 0). The combiner should be placed after the phase shifter, so I'll put it at (200, 0). I'll also mirror the combiner to ensure the correct port orientation.

Now, I'll connect the ports. The splitter has an input port 'o1' and two output ports 'o2' and 'o3'. The phase shifter has input and output ports 'o1' and 'o2'. I'll route from the splitter's 'o2' to the phase shifter's 'o1' and from the splitter's 'o3' to the phase shifter's 'o2'. 

For the phase shifter's outputs, I'll route them to the combiner's 'o1' and 'o2'. But since the combiner is mirrored, I'll need to make sure the connections are correct. The top output of the phase shifter will connect to the combiner's 'o2', and the bottom output will connect to the combiner's 'o1'.

I'll use the route_single function for each connection because they are single connections. I'll set the cross_section to 'strip' and ensure the radius is at least 15um to prevent routing collisions. I'll also make sure the separation parameter isn't used here since it's only for multiple routes.

Finally, I'll add the external ports for the entire component. The input will be the splitter's 'o1', and the output will be the combiner's 'o3' after mirroring.

I think that covers all the necessary steps. Now, I'll structure the code accordingly, making sure to follow the GDSFactory syntax and avoid any common mistakes like incorrect mirroring or unmatched parentheses.</think>

<analysis>
The Mach-Zehnder interferometer (MZI) will be created using:
1. One splitter (MMI1x2) at position (0,0)
2. One phase shifter at position (100,0)
3. One mirrored combiner (MMI1x2) at position (200,0)

Component connections:
- Splitter o1 -> input
- Splitter o2 -> phase shifter input
- Splitter o3 -> phase shifter input (mirrored)
- Phase shifter outputs -> mirrored combiner inputs
- Mirrored combiner o3 -> output

Routing strategy:
- Use route_single() for all connections with radius=15um
- Ensure proper alignment of ports for clean routing
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# 1. Instantiate components with settings
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

phase_shifter = r.add_ref(gf.components.straight_heater_metal(length=10))
phase_shifter.move((100, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((200, 0))

# 2. Route connections
gf.routing.route_single(
    splitter,
    splitter.ports['o2'],
    phase_shifter.ports['o1'],
    cross_section='strip',
    radius=15
)

gf.routing.route_single(
    splitter,
    splitter.ports['o3'],
    phase_shifter.ports['o2'],
    cross_section='strip',
    radius=15
)

gf.routing.route_single(
    phase_shifter,
    phase_shifter.ports['o2'],
    combiner.ports['o2'],
    cross_section='strip',
    radius=15
)

gf.routing.route_single(
    phase_shifter,
    phase_shifter.ports['o1'],
    combiner.ports['o1'],
    cross_section='strip',
    radius=15
)

# 3. Expose external ports
r.add_port('o1', splitter.ports['o1'])
r.add_port('o2', combiner.ports['o3'])

# 4. Finalize
r.draw_ports()
r.plot()
</result>