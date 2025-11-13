# Problem 2, Sample 1, Attempt 2
# Generated: 2025-11-12T17:04:10.874821

<think>
Okay, I need to create a single-input, single-output Mach-Zehnder Modulator (MZM) using GDSFactory. The user has provided specific components and parameters, so I'll start by understanding the requirements.

First, the components needed are:
1. An MMI1x2 splitter.
2. Two straight heater metal components as phase shifters.
3. An MMI1x2 combiner, which will be mirrored to function as a 2x1.

I remember that in GDSFactory, the mmi2x1 component doesn't exist, so I'll use mmi1x2 and mirror it to create the combiner.

Next, I'll think about the layout. The splitter should be at the origin (0,0). The two phase shifters will be placed after the splitter, each moving in the x-direction. To avoid routing collisions, I'll place them vertically apart by at least 200um. So, phase_shifter1 will be at (200, 50) and phase_shifter2 at (200, -50). The combiner will be placed further along the x-axis, say at (400, 0), ensuring enough horizontal spacing.

Now, connecting the ports. The splitter has an input port o1 and two output ports o2 and o3. These outputs will connect to the inputs of the two phase shifters. Each phase shifter has o1 and o2 ports, so I'll connect splitter.o2 to ps1.o1 and splitter.o3 to ps2.o1. After the phase shifters, their outputs (ps1.o2 and ps2.o2) will connect to the combiner's inputs. Since the combiner is mirrored, its input ports will be o2 and o1, so I'll connect ps1.o2 to combiner.o2 and ps2.o2 to combiner.o1.

For routing, I'll use route_bundle because it's for multiple connections. I'll set the cross_section to 'strip', radius to 20um, and separation to 20um to ensure proper routing without collisions.

I also need to add the external ports. The main input will be from the splitter's o1, and the output will be from the combiner's o3.

I should make sure all components are properly moved and that the code structure follows the example provided, with comments for clarity. I'll avoid any Unicode characters and ensure all numeric values are valid Python floats.

Finally, I'll review the code to ensure all method calls are complete and that all parentheses and quotes are properly closed. This should fix any previous errors related to unmatched brackets or incorrect port connections.</think>

<analysis>
We need to create a single-input/single-output Mach-Zehnder Modulator (MZM) with:
  1. One MMI1x2 splitter
  2. Two straight heater metal phase shifters
  3. One mirrored MMI1x2 combiner (acting as 2x1)

Component arrangement:
  - Splitter at (0, 0)
  - Phase shifters at (200, 50) and (200, -50) - vertical separation ensures no routing collisions
  - Combiner at (400, 0) - sufficient horizontal spacing for safe routing

Port connections:
  - Splitter o2, o3 -> Phase shifter inputs
  - Phase shifter outputs -> Combiner o2, o1 (after mirroring)

Parameters:
  - Use default values for all components
  - Set minimum bend radius to 20um for safer routing
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# 1. Instantiate components with settings
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((400, 0))

ps1 = r.add_ref(gf.components.straight_heater_metal(length=10.0))
ps1.move((200, 50))

ps2 = r.add_ref(gf.components.straight_heater_metal(length=10.0))
ps2.move((200, -50))

# 2. Route connections
gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [ps1.ports['o1'], ps2.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [ps1.ports['o2'], ps2.ports['o2']],
    [combiner.ports['o2'], combiner.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

# 3. Add external ports
r.add_port('o1', splitter.ports['o1'])
r.add_port('o2', combiner.ports['o3'])

# 4. Finalize
r.draw_ports()
r.plot()
</result>