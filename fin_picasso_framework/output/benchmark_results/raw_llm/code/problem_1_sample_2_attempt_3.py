# Problem 1, Sample 2, Attempt 3
# Generated: 2025-11-12T14:51:01.110927

<think>
Okay, I need to create a Mach-Zehnder interferometer using GDSFactory components. The user has specified that I should use two MMI1x2 components and one phase shifter. Let me think through how to approach this.

First, I'll start by understanding the components I need. The MMI1x2 is a 1x2 splitter, and I'll need two of them. The first will act as the splitter, and the second will function as the combiner after mirroring it. The phase shifter will be placed between them.

I remember that in GDSFactory, the mmi1x2 component has one input port (o1) and two output ports (o2 and o3). So, for the splitter (mmi1), I'll connect o1 as the input, and o2 and o3 will go to the phase shifter inputs.

Next, the phase shifter. I'll use the straight_heater_metal component, which has o1 as the input and o2 as the output. I'll need two of these, phase_shifter1 and phase_shifter2, placed side by side but vertically spaced to avoid collisions. Maybe placing them at (100, 50) and (100, -50) would give enough vertical separation.

Then, the combiner (mmi2) is another mmi1x2 that I'll mirror to function as a 2x1 combiner. I'll place it at (200, 0) to keep things aligned horizontally.

Now, connecting the ports. From the splitter's o2 and o3, I'll route to the phase shifters' o1 ports. Then, from the phase shifters' o2 ports, I'll connect to the combiner's o2 and o1 ports, respectively, after mirroring.

For routing, I'll use route_bundle because I'm connecting two ports in parallel. This ensures that the routes are properly separated and avoids any routing collisions. I'll set the separation parameter to 15um to maintain the required spacing.

I also need to make sure that all components are properly moved and that the ports are correctly connected. I'll add the ports o1 and o2 to the main component, referencing the splitter's o1 and the combiner's o3.

Wait, I should check the error message from the previous attempt. It said that ports1=2 and ports2=1 must be equal. That means I tried to connect two ports to one port, which isn't possible. I need to ensure that the number of source and destination ports match. In this case, I'm connecting two phase shifters to two combiner ports, so the counts should be equal.

I'll structure the code by first adding all components, then routing them using route_bundle for both connections. I'll make sure to call mirror() on the combiner after adding it as a reference.

Finally, I'll expose the external ports and draw them. This should fix the error and create a proper MZI.</think>

<analysis>
We need to create a Mach-Zehnder Interferometer with:
  1. One splitter (MMI 1x2)
  2. One phase shifter (straight_heater_metal)
  3. One combiner (MMI 1x2 mirrored to function as 2x1)

Component arrangement:
  - Splitter at (0, 0)
  - Phase shifter at (100, 0)
  - Combiner at (200, 0)

Port connections:
  - Splitter o2 -> Phase shifter o1
  - Splitter o3 -> Phase shifter o1 (mirrored for proper routing)
  - Phase shifter o2 -> Combiner o2
  - Phase shifter o2 -> Combiner o1 (mirrored)

Critical: Must maintain proper port count balance in route_bundle()
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Add components
mmi_splitter = r.add_ref(gf.components.mmi1x2())
mmi_splitter.move((0, 0))

phase_shifter = r.add_ref(gf.components.straight_heater_metal())
phase_shifter.move((100, 0))

mmi_combiner = r.add_ref(gf.components.mmi1x2())
mmi_combiner.mirror()
mmi_combiner.move((200, 0))

# Route connections using route_bundle
gf.routing.route_bundle(
    r,
    [mmi_splitter.ports['o2'], mmi_splitter.ports['o3']],  # 2 input ports
    [phase_shifter.ports['o1'], phase_shifter.ports['o1']],  # 2 output ports
    cross_section='strip',
    radius=15,
    separation=15
)

gf.routing.route_bundle(
    r,
    [phase_shifter.ports['o2']],  # 1 input port
    [mmi_combiner.ports['o2'], mmi_combiner.ports['o1']],  # 2 output ports
    cross_section='strip',
    radius=15,
    separation=15
)

# Add external ports
r.add_port('o1', port=mmi_splitter.ports['o1'])
r.add_port('o2', port=mmi_combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>