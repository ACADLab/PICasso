# Problem 2, Sample 0, Attempt 1
# Generated: 2025-11-12T17:02:41.475818

<think>
Alright, I need to create a single-input, single-output Mach-Zehnder Modulator (MZM) using GDSFactory. Let me break down the problem and figure out the steps.

First, I know that an MZM typically consists of a splitter, two phase shifters, and a combiner. The splitter and combiner are usually MMI (Mach-Zehner Interferometer) components. Since the problem specifies using an MMI1x2 splitter and an MMI2x1 combiner, but I remember that GDSFactory doesn't have an MMI2x1 component. So, I'll use the MMI1x2 component and mirror it to create the combiner.

Next, I need to consider the components available. The splitter is the mmi1x2 component, and the combiner will be a mirrored version of the same. For the phase shifters, I'll use the straight_heater_metal component, which includes the heating mechanism.

Now, thinking about the layout. The splitter should be at the origin (0,0). The two phase shifters need to be placed symmetrically above and below the splitter to avoid routing collisions. I'll position them at (200, 100) and (200, -100), ensuring they are spaced adequately. The combiner will be placed further along the x-axis, say at (400, 0), to maintain proper spacing for routing.

For the connections, the splitter has an input port o1 and two output ports o2 and o3. These outputs need to connect to the input ports of the phase shifters. Each phase shifter has an input (o1) and an output (o2). The outputs of the phase shifters will then connect to the combiner's input ports, which, after mirroring, will be o2 and o1.

I'll use route_bundle for connecting the splitter to both phase shifters since it's a multiple connection scenario. Similarly, I'll route the outputs of the phase shifters to the combiner using route_bundle. This ensures that the routes are parallel and properly separated.

I also need to ensure that all components are correctly referenced and moved. The combiner must be mirrored after being added as a reference to the main component. The phase shifters are added and moved to their respective positions.

Finally, I'll expose the external ports of the MZM by adding the splitter's o1 as the input and the combiner's o3 (after mirroring) as the output.

I should double-check all port connections and ensure that the routing doesn't cause any overlaps. Also, I'll verify that all numeric values are valid Python floats and that there are no syntax errors, such as missing parentheses or quotes.</think>

<analysis>
To create a single-input, single-output Mach-Zehnder Modulator (MZM), we need:
1. An MMI1x2 splitter
2. Two straight_heater_metal phase shifters
3. A mirrored MMI1x2 combiner (acting as MMI2x1)

Component arrangement:
- Splitter at (0, 0)
- Phase shifters at (200, 100) and (200, -100) - vertical separation ensures no collision
- Combiner at (400, 0) - sufficient horizontal spacing for routing

Port connections:
- Splitter o2, o3 -> Phase shifter inputs
- Phase shifter outputs -> Combiner o2, o1 (after mirroring)

Parameters:
- All components use default parameters except position
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Instantiate components
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((400, 0))

phase_shifter1 = r.add_ref(gf.components.straight_heater_metal(length=10.0))
phase_shifter2 = r.add_ref(gf.components.straight_heater_metal(length=10.0))

phase_shifter1.move((200, 100))
phase_shifter2.move((200, -100))

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
r.add_port('o1', splitter.ports['o1'])
r.add_port('o2', combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>