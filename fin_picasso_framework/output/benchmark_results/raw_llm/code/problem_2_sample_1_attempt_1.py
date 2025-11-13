# Problem 2, Sample 1, Attempt 1
# Generated: 2025-11-12T17:03:47.540247

<think>
Okay, so I need to create a Mach-Zehnder Modulator (MZM) using GDSFactory components. Let me think about how to approach this step by step.

First, I remember that an MZM typically consists of a splitter, two phase shifters, and a combiner. The splitter and combiner are usually 1x2 and 2x1 MMI components, respectively. But wait, I recall that GDSFactory doesn't have a direct 2x1 MMI component. So, I'll need to use the 1x2 MMI and mirror it to create the combiner.

I'll start by importing the necessary components. I'll need mmi1x2 for both the splitter and the combiner. Also, I'll need straight_heater_metal for the phase shifters.

Next, I'll create the main component 'r' using gf.Component(). Then, I'll add the splitter and position it at (0,0). After that, I'll add two phase shifters. To avoid routing collisions, I'll place them slightly offset from each other, maybe at (200, 0) and (200, 0), but I need to ensure they have enough vertical spacing. Oh, right, the minimum spacing should be 200um, so I'll adjust their y positions accordingly, like (200, 50) and (200, -50).

Then, I'll add the combiner by mirroring the mmi1x2 component. I'll move it to (400, 0) to maintain sufficient horizontal spacing.

Now, I need to route the connections. The splitter has output ports o2 and o3, which will connect to the inputs of the phase shifters. Each phase shifter has o1 and o2 ports. After the phase shifters, their outputs will connect to the combiner's inputs, which are o2 and o1 after mirroring.

I'll use route_bundle() for the connections because there are multiple parallel routes. For the splitter to phase shifters, I'll route o2 and o3 to the phase shifters' o1 ports. Then, from the phase shifters' o2 ports to the combiner's o2 and o1 ports.

I should ensure that the cross_section is set to 'strip' for all routes. The radius should be at least 20um to prevent routing issues, and the separation should be 20um to keep the routes apart.

Finally, I'll expose the external ports of the splitter (o1) and the combiner (o3) as 'o1' and 'o2' for the MZM component.

I need to make sure that all method calls are complete and that I'm using valid Python float literals without any Unicode characters. Also, I'll check that all parentheses and quotes are properly closed to avoid syntax errors.

Putting it all together, I'll write the code step by step, making sure to follow the GDSFactory syntax and best practices for component placement and routing.</think>

<analysis>
The circuit requires a Mach-Zehnder Modulator (MZM) with:
1. One MMI1x2 splitter
2. Two straight_heater_metal phase shifters
3. One mirrored MMI1x2 combiner (used as 2x1)

Component arrangement:
- Splitter at (0, 0)
- Phase shifters at (200, 50) and (200, -50) - vertical offset ensures no collision
- Combiner at (400, 0) - maintains proper spacing

Port connections:
- Splitter o2, o3 -> Phase shifter inputs
- Phase shifter outputs -> Combiner o2, o1 (after mirroring)

Parameters:
- All parameters use defaults except specified lengths
- Proper mirroring ensures correct port orientation
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Instantiate components
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

phase_shifter1 = r.add_ref(gf.components.straight_heater_metal(length=10))
phase_shifter1.move((200, 50))

phase_shifter2 = r.add_ref(gf.components.straight_heater_metal(length=10))
phase_shifter2.move((200, -50))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((400, 0))

# Route connections
gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [phase_shifter1.ports['o1'], phase_shifter2.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [phase_shifter1.ports['o2'], phase_shifter2.ports['o2']],
    [combiner.ports['o2'], combiner.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

# Add external ports
r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>