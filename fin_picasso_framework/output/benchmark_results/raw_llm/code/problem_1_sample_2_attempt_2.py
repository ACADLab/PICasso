# Problem 1, Sample 2, Attempt 2
# Generated: 2025-11-12T14:50:37.969153

<think>
Alright, let's tackle this problem step by step. The goal is to create a Mach-Zehnder interferometer (MZI) using GDSFactory components. The user has specified using two MMI1x2 components and one phase shifter. 

First, I need to understand the components involved. The MMI1x2 is a 1x2 splitter, and to create a 2x1 combiner, I'll mirror one of them. The phase shifter will act as the phase difference element in the MZI.

I'll start by instantiating the components. The first MMI1x2 (mmi_splitter) will be placed at the origin. The second MMI1x2 (mmi_combiner) will be mirrored to function as a 2x1 combiner and placed some distance away. The phase shifter will be positioned between them.

Next, I need to connect these components. The splitter's outputs will connect to the phase shifter's inputs. The phase shifter's outputs will then connect to the combiner's inputs. Since there are two connections, I'll use route_bundle() for both the splitter to phase shifter and the phase shifter to combiner routes.

I must ensure proper spacing to avoid routing collisions. The phase shifter should be placed horizontally after the splitter, and the combiner should be spaced enough to the right for safe routing. I'll use a horizontal shift for the phase shifter and a larger horizontal shift for the combiner.

For the routing, I'll use the default cross_section and a bend radius of 15um. The separation parameter in route_bundle will ensure the routes don't overlap.

Finally, I'll expose the input and output ports of the MZI by adding the splitter's input and the combiner's output to the main component.

I need to make sure all method calls are complete and correct, avoiding any syntax errors. Also, I'll verify that all components are correctly referenced and mirrored where necessary.</think>

<analysis>
We need to create a Mach-Zehnder Interferometer (MZI) with:
  1. One splitter (MMI 1x2)
  2. One phase shifter (straight_heater_metal)
  3. One combiner (MMI 2x1, created by mirroring a MMI 1x2)

Component arrangement:
  - Splitter at (0, 0)
  - Phase shifter at (100, 0)
  - Combiner at (200, 0) - spaced 100um for safe routing

Port connections:
  - Splitter o2, o3 -> Phase shifter inputs
  - Phase shifter outputs -> Combiner o2, o1 (note reversed order after mirroring)

Parameters:
  - DeltaL = 10.0 (vertical length difference)
  - L = 10.0 (vertical length for both arms)
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# 1. Instantiate components with settings
mmi_splitter = r.add_ref(gf.components.mmi1x2())
mmi_splitter.move((0, 0))

phase_shifter = r.add_ref(gf.components.straight_heater_metal(length=10.0))
phase_shifter.move((100, 0))

mmi_combiner = r.add_ref(gf.components.mmi1x2())  # Use mmi1x2 and mirror for 2x1
mmi_combiner.mirror()
mmi_combiner.move((200, 0))

# 2. Route connections
gf.routing.route_bundle(
    r,
    [mmi_splitter.ports['o2'], mmi_splitter.ports['o3']],
    [phase_shifter.ports['o1']],
    cross_section='strip',
    radius=15,
)

gf.routing.route_bundle(
    r,
    [phase_shifter.ports['o2']],
    [mmi_combiner.ports['o2'], mmi_combiner.ports['o1']],
    cross_section='strip',
    radius=15,
)

# 3. Expose external ports
r.add_port('o1', port=mmi_splitter.ports['o1'])
r.add_port('o2', port=mmi_combiner.ports['o3'])

# 4. Finalize
r.draw_ports()
r.plot()
</result>