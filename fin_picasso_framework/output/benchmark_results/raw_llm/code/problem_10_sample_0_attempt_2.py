# Problem 10, Sample 0, Attempt 2
# Generated: 2025-11-12T17:05:51.265945

<think>
Okay, I need to create a fundamental 2x2 optical switch using an MZI-based switch cell. The user provided specific components to use: one MZI cell (id: sw1) and one phase control (id: ctrl1). 

First, I'll check the available components in GDSFactory. From the reference, I see that 'mzi' and 'straight_heater_metal' are available. So, I'll use gf.components.mzi() for the MZI and gf.components.straight_heater_metal() for the phase control.

Next, I need to figure out the ports. The MZI has 'o1' and 'o2' as input and output. The phase control (straight_heater_metal) has 'o1' and 'o2' as well. 

I'll start by adding the MZI component to the circuit and moving it to the origin. Then, I'll add the phase control component and move it somewhere else, ensuring there's enough spacing between them to avoid routing issues.

Now, I need to connect the ports. The MZI's 'o1' should connect to the phase control's 'o1', and the MZI's 'o2' should connect to the phase control's 'o2'. Since these are single connections, I'll use route_single() for each.

I should also expose the external ports of the MZI and phase control. The MZI's 'o1' and 'o2' will be the input and output of the switch, and the phase control's 'o1' and 'o2' will be connected internally.

I need to make sure all the parameters are set correctly. The MZI and phase control components have default parameters, so I don't need to adjust them unless specified.

Finally, I'll draw the ports and plot the component to visualize the connections.</think>

<analysis>
To create a 2x2 optical switch using MZI-based technology:
  1. Use MZI as the switching element (sw1)
  2. Use a phase control component (ctrl1) to control the MZI
  3. Connect the MZI and phase control with proper routing

Component arrangement:
  - MZI at (0, 0)
  - Phase control at (200, 0) - horizontal separation for routing

Port connections:
  - MZI o1 -> Phase control o1
  - MZI o2 -> Phase control o2

Parameters:
  - Use default MZI and straight_heater_metal parameters
  - Routing with default strip cross_section
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Add MZI component
mzi_switch = r.add_ref(gf.components.mzi())
mzi_switch.move((0, 0))

# Add phase control component
phase_control = r.add_ref(gf.components.straight_heater_metal())
phase_control.move((200, 0))

# Route connections
gf.routing.route_single(
    r,
    mzi_switch.ports['o1'],
    phase_control.ports['o1'],
    cross_section='strip',
    radius=20
)

gf.routing.route_single(
    r,
    mzi_switch.ports['o2'],
    phase_control.ports['o2'],
    cross_section='strip',
    radius=20
)

# Expose external ports
r.add_port('o1', port=mzi_switch.ports['o1'])
r.add_port('o2', port=mzi_switch.ports['o2'])
r.add_port('ctrl1', port=phase_control.ports['o1'])
r.add_port('ctrl2', port=phase_control.ports['o2'])

r.draw_ports()
r.plot()
</result>