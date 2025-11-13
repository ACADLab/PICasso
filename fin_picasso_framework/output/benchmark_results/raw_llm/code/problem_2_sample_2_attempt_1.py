# Problem 2, Sample 2, Attempt 1
# Generated: 2025-11-12T17:04:40.571435

<think>
Alright, I need to design a single-input, single-output Mach-Zehnder Modulator (MZM) using GDSFactory. Let me break down the steps I should take.

First, I'll start by importing the GDSFactory library. Then, I'll create a new component called 'c'. 

Next, I need to instantiate the components. The MZM requires a splitter, two phase shifters, and a combiner. I'll use the 'mzi' component for the splitter and another 'mzi' component for the combiner, which I'll mirror to get the 2x1 configuration.

I'll add the splitter, phase shifters, and combiner to the component 'c' and position them appropriately. The splitter will be at the origin, the phase shifters will be placed next, and the combiner will be at the end. I'll make sure to keep the spacing between components at least 200um to avoid routing issues.

After placing the components, I'll connect the ports. The splitter's output ports will connect to the phase shifters, and the phase shifters' output ports will connect to the combiner. I'll use the 'route_single' function for each connection to ensure proper routing.

Finally, I'll add the external ports to the main component and draw the ports for visualization.

I need to ensure that all method calls are complete, with proper parentheses and arguments. Also, I'll avoid any Unicode characters and use valid Python float literals throughout the code.</think>

<analysis>
We need to create a single-input, single-output Mach-Zehnder Modulator (MZM) with:
  1. One splitter (MMI 1x2)
  2. Two phase shifters (straight_heater_metal)
  3. One combiner (MMI 2x1, needs mirroring for correct orientation)

Component arrangement:
  - Splitter at (0, 0)
  - Phase shifters at (200, 0) - placed side by side
  - Combiner at (400, 0) - horizontal separation for safe routing

Port connections:
  - Splitter o2 -> Phase shifter 1 input
  - Splitter o3 -> Phase shifter 2 input
  - Phase shifter 1 output -> Combiner o1
  - Phase shifter 2 output -> Combiner o2

Parameters:
  - All components use default parameters unless specified
  - Use route_single() for all connections to ensure proper routing
</analysis>

<result>
import gdsfactory as gf

c = gf.Component()

# Instantiate components
splitter = c.add_ref(gf.components.mzi())
splitter.move((0, 0))

phase_shifter1 = c.add_ref(gf.components.straight_heater_metal())
phase_shifter1.move((200, 0))

phase_shifter2 = c.add_ref(gf.components.straight_heater_metal())
phase_shifter2.move((200, 0))

combiner = c.add_ref(gf.components.mzi())
combiner.mirror()
combiner.move((400, 0))

# Route connections
gf.routing.route_single(c, splitter.ports['o2'], phase_shifter1.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(c, splitter.ports['o3'], phase_shifter2.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(c, phase_shifter1.ports['o2'], combiner.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(c, phase_shifter2.ports['o2'], combiner.ports['o2'], cross_section='strip', radius=20)

# Add external ports
c.add_port('o1', splitter.ports['o1'])
c.add_port('o2', combiner.ports['o3'])

# Draw ports and plot
c.draw_ports()
c.plot()
</result>