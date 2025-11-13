# Problem 10, Sample 2, Attempt 1
# Generated: 2025-11-12T17:06:55.927103

<think>
Okay, I need to create a 2x2 optical switch using an MZI-based switch cell and a phase control. Let me think through the steps.

First, I'll identify the components needed. The MZI cell is 'sw1' and the phase control is 'ctrl1'. I also need to include splitters, phase shifters, and combiners.

I'll start by importing GDSFactory as 'gf'. Then, I'll create a new component 'r'.

Next, I'll instantiate the MZI cell and add it to 'r'. I'll move it to the origin (0,0).

I need two phase controllers for the MZI's top and bottom arms. I'll create two references to 'straight_heater_metal' and move them appropriately, one above and one below the MZI.

Then, I'll add the phase control components. I'll create two more references to 'straight_heater_metal' and position them near the MZI's output ports.

Now, I'll route the connections. The MZI's input port 'o1' connects to the first splitter's input. The splitter's outputs connect to the phase controllers. The phase controllers' outputs connect to the MZI's output ports. Finally, the MZI's output connects to the combiner.

I'll use 'route_single()' for each connection to ensure proper routing without any fan-out, as per the restrictions.

Finally, I'll expose the external ports and draw them.

I need to ensure all components are properly spaced, at least 200um apart, to avoid routing collisions. I'll also make sure all method calls are complete and use valid Python literals without any Unicode characters.

Let me put it all together in the code.</think>

<analysis>
To create a 2x2 optical switch using an MZI-based switch cell:
  1. Use MZI cell (sw1) as the core switching component
  2. Use phase control (ctrl1) for optical path manipulation
  3. Connect components with proper routing
  4. Ensure all ports are properly connected
  5. Maintain minimum spacing requirements (200um between components)
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# Add MZI cell
mzi_cell = r.add_ref(gf.components.mzi())
mzi_cell.move((0, 0))

# Add phase controllers
ctrl1 = r.add_ref(gf.components.straight_heater_metal())
ctrl1.move((200, 50))

ctrl2 = r.add_ref(gf.components.straight_heater_metal())
ctrl2.move((200, -50))

# Add phase control components
ctrl3 = r.add_ref(gf.components.straight_heater_metal())
ctrl3.move((400, 50))

ctrl4 = r.add_ref(gf.components.straight_heater_metal())
ctrl4.move((400, -50))

# Route connections
gf.routing.route_single(r, mzi_cell.ports['o1'], ctrl1.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(r, mzi_cell.ports['o2'], ctrl2.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(r, ctrl1.ports['o2'], mzi_cell.ports['o3'], cross_section='strip', radius=20)
gf.routing.route_single(r, ctrl2.ports['o2'], mzi_cell.ports['o4'], cross_section='strip', radius=20)
gf.routing.route_single(r, mzi_cell.ports['o5'], ctrl3.ports['o1'], cross_section='strip', radius=20)
gf.routing.route_single(r, mzi_cell.ports['o6'], ctrl4.ports['o1'], cross_section='strip', radius=20)

# Expose external ports
r.add_port('o1', port=mzi_cell.ports['o1'])
r.add_port('o2', port=mzi_cell.ports['o2'])
r.add_port('o3', port=mzi_cell.ports['o3'])
r.add_port('o4', port=mzi_cell.ports['o4'])

r.draw_ports()
r.plot()
</result>