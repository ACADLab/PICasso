# Problem 2, Sample 0, Attempt 3
# Generated: 2025-11-12T14:52:32.376218

<think>
Okay, I need to create a single-input, single-output Mach-Zehnder Modulator (MZM) using GDSFactory. The user provided specific components and parameters, so I'll start by understanding the requirements.

First, the MZM consists of a splitter, two phase shifters, and a combiner. The splitter is an MMI1x2, and the combiner is an MMI2x1, which I can create by mirroring an MMI1x2 component. The phase shifters are straight_heater_metal components.

I'll begin by instantiating the splitter, phase shifters, and combiner. The splitter will be placed at the origin (0,0). The combiner needs to be mirrored after adding it to the component, so I'll add it first, then mirror it, and move it to the right side, ensuring enough spacing for routing.

Next, I'll position the phase shifters. To avoid routing collisions, I'll place them vertically offset from the splitter. A vertical spacing of 100µm should suffice, so I'll move one up by (100, 50) and the other down by (100, -50).

Now, I need to connect the ports. The splitter has output ports o2 and o3, which will connect to the inputs of the two phase shifters. Each phase shifter's output will then connect to the combiner's inputs. Since there are two connections, I'll use route_bundle() for both the splitter to phase shifters and the phase shifters to combiner.

I'll set the cross_section to 'strip' and ensure a radius of 15µm for the bends. The separation parameter in route_bundle() will be 15µm to maintain proper spacing between the routes.

Finally, I'll expose the external ports of the MZM by adding the splitter's input (o1) and the combiner's output (o3) as the device's ports.

I should double-check all component references, port connections, and ensure that all method calls are correctly formatted. Also, I'll verify that all numeric values are valid floats without any attached units and that all strings use ASCII characters.</think>

<analysis>
We need to create a Mach-Zehnder Modulator (MZM) with:
  1. One splitter (MMI 1x2)
  2. Two phase shifters (straight_heater_metal)
  3. One combiner (MMI 2x1, created by mirroring an MMI1x2)

Component arrangement:
  - Splitter at (0, 0)
  - Phase shifters at (100, 50) and (100, -50) - vertical separation prevents collision
  - Combiner at (250, 0) - horizontal separation provides safe routing space

Port connections:
  - Splitter o2, o3 -> Phase shifter inputs
  - Phase shifter outputs -> Combiner o2, o1 (note reversed order after mirroring)

Parameters:
  - All components use default parameters except position
  - Routing uses cross_section='strip' and radius=15
  - Separation=15 for route_bundle()

Special considerations:
  - Combiner needs mirror() called AFTER add_ref() to match port orientation
  - Proper vertical spacing between phase shifters to avoid routing collisions
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# 1. Instantiate components with settings
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

# Create combiner by mirroring splitter
combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((250, 0))

# Add phase shifters with vertical separation
ps1 = r.add_ref(gf.components.straight_heater_metal())
ps1.move((100, 50))

ps2 = r.add_ref(gf.components.straight_heater_metal())
ps2.move((100, -50))

# 2. Route connections
gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [ps1.ports['o1'], ps2.ports['o1']],
    cross_section='strip',
    radius=15,
    separation=15
)

gf.routing.route_bundle(
    r,
    [ps1.ports['o2'], ps2.ports['o2']],
    [combiner.ports['o2'], combiner.ports['o1']],
    cross_section='strip',
    radius=15,
    separation=15
)

# 3. Expose external ports
r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

# 4. Finalize
r.draw_ports()
r.plot()
</result>