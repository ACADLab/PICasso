# Problem 10, Sample 1, Attempt 2
# Generated: 2025-11-12T14:56:47.343008

<think>
Alright, I need to create a fundamental 2x2 optical switch using an MZI-based switch cell. The user has provided specific components and guidelines, so I should carefully follow them.

First, I'll identify the components needed. The problem mentions using one MZI cell (sw1) and one phase control (ctrl1). From the available components, I see that the mzi() function is suitable for the MZI cell. For the phase control, the straight_heater_metal() component is appropriate as it can act as a phase shifter.

Next, I need to understand the ports of these components. The mzi() component has input port 'o1' and output port 'o2'. The straight_heater_metal() has input 'o1' and output 'o2' as well. 

Now, I'll think about how to connect them. The MZI cell will split the input into two paths, and the phase control will adjust the phase difference between them. Then, the combiner part of the MZI will recombine the two paths to produce the output states.

I should arrange the components spatially. The MZI cell will be placed at (0,0). The phase control needs to be placed such that it's connected to the MZI's splitter and combiner. To avoid routing collisions, I'll position the phase control at (150, 0), ensuring enough horizontal space.

For the connections, I'll use the route_single() function because it's a single connection. The MZI's 'o1' will connect to the phase control's 'o1', and the phase control's 'o2' will connect back to the MZI's 'o2'. This forms the loop necessary for the phase shift.

I must ensure all ports are properly connected and no dangling ports exist. The MZI's input and output will be exposed as the switch's ports, while the phase control's ports are internal.

I'll also check the parameters. Since no specific parameters are given, I'll use the defaults for the components and routing. The cross_section will be 'strip', and the radius will be 15 um for safety.

Finally, I'll structure the code correctly, making sure to add components, route them, and expose the necessary ports. I'll avoid any syntax errors by using valid Python literals and ensuring all parentheses are closed.</think>

<analysis>
Create a fundamental 2x2 optical switch using:
  1. One MZI cell (sw1) as the switching element
  2. One phase control (ctrl1) for optical modulation

Component arrangement:
  - MZI cell at (0, 0)
  - Phase control at (150, 0) - spaced 150um for safe routing
  - Use MZI's internal splitter/combiner for 2x2 switching

Port connections:
  - MZI o1 -> Phase control o1
  - Phase control o2 -> MZI o2
  - MZI o1 and o2 will be external switch ports

Routing strategy:
  - Use route_single() for direct connections
  - Maintain minimum spacing of 15um between routes
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# 1. Instantiate components with settings
mzi_switch = r.add_ref(gf.components.mzi())
mzi_switch.move((0, 0))

phase_control = r.add_ref(gf.components.straight_heater_metal(length=10))
phase_control.move((150, 0))

# 2. Route connections
gf.routing.route_single(
    r,
    mzi_switch.ports['o1'],
    phase_control.ports['o1'],
    cross_section='strip',
    radius=15
)

gf.routing.route_single(
    r,
    phase_control.ports['o2'],
    mzi_switch.ports['o2'],
    cross_section='strip',
    radius=15
)

# 3. Expose external ports
r.add_port('o1', port=mzi_switch.ports['o1'])
r.add_port('o2', port=mzi_switch.ports['o2'])

# 4. Finalize
r.draw_ports()
r.plot()
</result>