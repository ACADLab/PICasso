# Problem 10, Sample 0, Attempt 1
# Generated: 2025-11-12T17:05:32.868459

<think>
Alright, I need to address the problem of creating a fundamental 2x2 optical switch using an MZI-based switch cell with the provided components. Let me go through the thought process step by step.

First, understanding the components available is crucial. The user provided two components: sw1 (an MZI cell) and ctrl1 (a phase control component). The goal is to connect these components correctly to form a 2x2 optical switch.

I recall that an MZI-based switch typically has two input ports and two output ports. The MZI cell (sw1) will act as the core of the switch, and the phase control (ctrl1) will be used to control the phase difference between the two arms of the MZI, thereby enabling the switching functionality.

Next, I need to consider the spatial arrangement of these components. According to the guidelines, components should be spaced at least 200um apart to prevent routing collisions. However, since this is a simple design with only two components, I can place them 200um apart.

I'll start by adding the MZI cell (sw1) to the component container. Then, I'll add the phase control component (ctrl1) and move it to the right of sw1, ensuring the spacing is at least 200um.

Now, I need to connect the ports correctly. The MZI cell has input and output ports, and the phase control has its own input and output ports. I'll connect the input of the MZI to the input of the phase control and the output of the MZI to the output of the phase control. Since each connection is a single port-to-port link, I'll use the route_single() function for each connection.

I must ensure that all ports are properly connected without any dangling ports. Also, I need to avoid connecting more than two ports together to prevent issues with GDSFactory's get_netlist() function.

Finally, I'll expose the external ports of the entire structure by adding the input and output ports of the MZI cell as the external ports of the final component.

Throughout this process, I need to ensure that I'm using valid Python syntax, avoiding Unicode characters, and using correct decimal literals. I'll also make sure all method calls are complete and properly formatted.</think>

<analysis>
To create a fundamental 2x2 optical switch using an MZI-based switch cell:
  1. Use the provided MZI cell (sw1) and phase control (ctrl1)
  2. Connect the MZI input to the phase control input
  3. Connect the MZI output to the phase control output
  4. Ensure proper spacing between components (minimum 200um)
  5. Use route_single() for all connections
  6. Expose the switch's external ports
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Add MZI cell and phase control
mzi_cell = r.add_ref(gf.components.mzi())
mzi_cell.move((0, 0))

phase_ctrl = r.add_ref(gf.components.ctrl1)
phase_ctrl.move((200, 0))

# Route connections
gf.routing.route_single(r, mzi_cell.ports['o1'], phase_ctrl.ports['o1'], cross_section='strip', radius=15)
gf.routing.route_single(r, phase_ctrl.ports['o2'], mzi_cell.ports['o2'], cross_section='strip', radius=15)

# Expose external ports
r.add_port('o1', port=mzi_cell.ports['o1'])
r.add_port('o2', port=mzi_cell.ports['o2'])

r.draw_ports()
r.plot()
</result>