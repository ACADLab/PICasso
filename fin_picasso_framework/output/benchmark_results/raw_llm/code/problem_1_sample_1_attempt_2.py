# Problem 1, Sample 1, Attempt 2
# Generated: 2025-11-12T14:49:32.744236

<think>
Alright, I need to address the user's request to create a Mach-Zehnder interferometer (MZI) using GDSFactory components. The user provided detailed instructions and an example, so I'll follow that structure closely.

First, I'll start by understanding the components required. The MZI typically consists of a splitter, two phase shifters, and a combiner. From the available components, I can use mmi1x2 for both the splitter and the combiner (with mirroring to make it function as a 2x1). The phase shifters can be implemented using straight_heater_metal components.

Next, I'll outline the steps. I'll instantiate the splitter, phase shifters, and combiner. I'll position the splitter at the origin, the combiner after some horizontal distance, and the phase shifters vertically offset to avoid collision.

I'll then connect the splitter's output ports to the phase shifters' input ports using route_single for each connection. After the phase shifters, I'll route their outputs to the combiner's input ports. Finally, I'll expose the input and output ports of the MZI.

I need to ensure that all components are correctly placed and that the routing follows the guidelines, using the correct functions and parameters. I'll also verify that all numeric values are valid Python floats and that the code adheres to ASCII characters.

In the previous attempt, there was a syntax error due to unterminated strings. I'll make sure all strings are properly closed and that there are no Unicode characters. I'll also check that all function calls are complete with proper parentheses.

By following these steps, I can create a correct and functional MZI design in GDSFactory.</think>

<analysis>
We need to create a Mach-Zehnder Interferometer (MZI) with:
  1. One splitter (MMI 1x2)
  2. One phase shifter (straight_heater_metal)
  3. One combiner (MMI 1x2 mirrored to function as 2x1)

Component arrangement:
  - Splitter at (0, 0)
  - Phase shifter at (100, 0)
  - Combiner at (200, 0) - horizontal separation 200um for DRC safety

Port connections:
  - Splitter o2 -> Phase shifter input
  - Phase shifter output -> Combiner o2

Parameters:
  - DeltaL = 10.0um (vertical length difference)
  - L = 10.0um (horizontal length)

Routing strategy:
  - Use route_single() for all optical connections
  - Maintain bend radius >= 15um
  - Ensure proper waveguide width continuity
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# 1. Instantiate components with settings
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((200, 0))

phase_shifter = r.add_ref(gf.components.straight_heater_metal(length=10.0))
phase_shifter.move((100, 0))

# 2. Route connections
gf.routing.route_single(
    component=r,
    port1=splitter.ports['o2'],
    port2=phase_shifter.ports['o1'],
    cross_section='strip',
    radius=15
)

gf.routing.route_single(
    component=r,
    port1=phase_shifter.ports['o2'],
    port2=combiner.ports['o2'],
    cross_section='strip',
    radius=15
)

# 3. Expose external ports
r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

# 4. Finalize
r.draw_ports()
r.plot()
</result>