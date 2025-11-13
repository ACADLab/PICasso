# Problem 10, Sample 1, Attempt 1
# Generated: 2025-11-12T17:06:19.546939

<think>
Okay, let's break down how to create a 2x2 optical switch using GDSFactory. 

First, I'll need to use an MZI cell and a phase control. The MZI (Mach-Zehnder Interferometer) is a common component in photonic integrated circuits, and it can be used as a switch when combined with a phase controller.

I'll start by creating a new Component called 'r'. Then, I'll add the MZI cell and the phase control components. The MZI cell, 'sw1', will be placed at the origin (0,0). The phase control, 'ctrl1', which I assume is a component that controls the phase of the light, will be placed at (200, 0) to ensure proper spacing.

Next, I need to connect the ports correctly. The MZI has an input port 'o1' and an output port 'o2'. The phase control will have its own input and output ports. I'll route the connections using GDSFactory's routing functions.

Since the MZI and phase control are two separate components, I'll use the `route_single()` function to connect their ports. This function is suitable for single connections between two ports. I'll set the cross-section to 'strip' and ensure the radius is sufficient to prevent routing issues.

Finally, I'll add the external ports for the entire component, 'o1' and 'o2', which will connect to the input and output of the MZI cell.

I need to make sure all the code follows the structure: instantiate components, move them to their positions, route the connections, and then add the external ports. I'll also ensure that all numbers are valid Python floats and that there are no syntax errors like unmatched parentheses or Unicode characters.

Putting it all together, I'll write the code step by step, making sure each part is correctly implemented and adheres to the guidelines provided.</think>

<analysis>
To create a 2x2 optical switch using an MZI-based switch cell with phase control:
1. Use MZI cell (sw1) as the core switching component
2. Add phase control (ctrl1) to enable optical switching
3. Place MZI at (0,0) and phase control at (200,0) with 200um spacing
4. Connect input/output ports using route_single() for proper optical routing
5. Ensure all ports are properly connected with valid cross_section and radius parameters
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Add MZI cell at origin
sw1 = r.add_ref(gf.components.mzi())
sw1.move((0, 0))

# Add phase control component with proper spacing
ctrl1 = r.add_ref(gf.components.mzi())
ctrl1.move((200, 0))

# Route connections using proper routing functions
gf.routing.route_single(
    r,
    sw1.ports['o1'],
    ctrl1.ports['o1'],
    cross_section='strip',
    radius=20
)

gf.routing.route_single(
    r,
    ctrl1.ports['o2'],
    sw1.ports['o2'],
    cross_section='strip',
    radius=20
)

# Expose external ports
r.add_port('o1', port=sw1.ports['o1'])
r.add_port('o2', port=sw1.ports['o2'])

r.draw_ports()
r.plot()
</result>