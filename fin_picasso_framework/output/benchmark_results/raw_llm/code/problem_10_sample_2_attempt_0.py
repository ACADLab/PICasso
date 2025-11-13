# Problem 10, Sample 2, Attempt 0
# Generated: 2025-11-12T17:06:34.263821

<think>
Okay, I need to write Python code to create a 2x2 optical switch using GDSFactory. The problem says to use an MZI cell (id: sw1) and a phase control (id: ctrl1). 

First, I'll start by importing the necessary GDSFactory components. I remember from the example that I need to import 'gf' as the main library.

Next, I'll create a new component 'r' which will be the main circuit. Then, I'll add the MZI cell using r.add_ref(gf.components.mzi()) and move it to the origin (0,0).

Now, I need to add the phase control. I'll use r.add_ref(gf.components.phase_control()) and move it somewhere, maybe (200, 0) to avoid overlapping with the MZI.

The MZI has four ports: o1, o2, o3, o4. The phase control has two ports: o1 and o2. I need to connect the MZI's output ports to the phase control's input ports. 

I'll use route_bundle to connect o3 and o4 of the MZI to o1 and o2 of the phase control. I'll set the cross_section to 'strip', radius to 20, and separation to 20 for DRC safety.

After routing, I need to expose the external ports. The MZI's o1 and o2 will be the input ports, and the phase control's o3 and o4 will be the output ports. I'll add these to the main component 'r' using add_port with the correct labels.

Finally, I'll draw the ports and plot the component to visualize the layout.

I should make sure all the method calls are complete and use the correct parameters. Also, I'll avoid any comments or extra text as per the instructions.
</think>



```python
import gdsfactory as gf

r = gf.Component()

# Add MZI cell and phase control component
mzi = r.add_ref(gf.components.mzi())
mzi.move((0, 0))

ctrl = r.add_ref(gf.components.phase_control())
ctrl.move((200, 0))

# Route MZI output to phase control input
gf.routing.route_bundle(
    r,
    [mzi.ports['o3'], mzi.ports['o4']],
    [ctrl.ports['o1'], ctrl.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

# Add external ports
r.add_port('o1', port=mzi.ports['o1'])
r.add_port('o2', port=mzi.ports['o2'])
r.add_port('o3', port=ctrl.ports['o3'])
r.add_port('o4', port=ctrl.ports['o4'])

r.draw_ports()
r.plot()
```