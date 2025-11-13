# Problem 1, Sample 0, Attempt 1
# Generated: 2025-11-12T17:00:03.778786

<think>
Alright, I need to create a Mach-Zehnder interferometer using GDSFactory. The user provided specific components and parameters, so I'll start by understanding the requirements.

First, the components needed are two MMI1x2 splitters and one phase shifter. The phase shifter can be either a straight_heater_metal or straight_heater_metal_undercut. I'll choose straight_heater_metal for simplicity.

I remember that in GDSFactory, the mmi2x1 doesn't exist, so I'll use mmi1x2 and mirror it to create the combiner. I'll need to add the components to the circuit and position them correctly.

Spacing is crucial to avoid routing collisions. The minimum spacing should be at least 200um. I'll place the first splitter at (0,0), the phase shifter at (200,0), and the mirrored combiner at (400,0). This ensures enough space for routing.

Next, I'll connect the splitter's o2 and o3 ports to the phase shifter's o1 port using route_bundle. Then, connect the phase shifter's o2 port to the combiner's o2 and o1 ports using route_bundle as well. Using route_bundle allows me to handle multiple connections efficiently with the required separation.

I'll make sure all method calls are complete and correct, avoiding any syntax errors. I'll also verify that all numeric values are valid Python floats and use ASCII characters only.

Finally, I'll add the external ports and ensure all connections are properly exposed. I'll review the code structure to follow the example provided, ensuring that the code is clean and executable without any syntax issues.</think>

<analysis>
The circuit requires:
1. Two MMI1x2 components (splitter and mirrored combiner)
2. One phase shifter (straight_heater_metal)
3. Proper spatial arrangement with adequate spacing (200um minimum)
4. Connection strategy:
   - Splitter o2, o3 -> Phase shifter inputs
   - Phase shifter outputs -> Combiner ports

Component placement:
- Splitter at (0,0)
- Phase shifter at (200,0)
- Mirrored combiner at (400,0)

Routing:
- Use route_bundle() for multiple connections
- Maintain 20um bend radius and separation
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Add components
mmi_splitter = r.add_ref(gf.components.mmi1x2())
mmi_splitter.move((0, 0))

phase_shifter = r.add_ref(gf.components.straight_heater_metal())
phase_shifter.move((200, 0))

mmi_combiner = r.add_ref(gf.components.mmi1x2())
mmi_combiner.mirror()
mmi_combiner.move((400, 0))

# Route connections
gf.routing.route_bundle(
    r,
    [mmi_splitter.ports['o2'], mmi_splitter.ports['o3']],
    [phase_shifter.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [phase_shifter.ports['o2']],
    [mmi_combiner.ports['o2'], mmi_combiner.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

# Add external ports
r.add_port('o1', port=mmi_splitter.ports['o1'])
r.add_port('o2', port=mmi_combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>