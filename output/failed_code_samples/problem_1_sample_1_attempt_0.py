# Problem 1, Sample 1, Attempt 0
# Error: Syntax error: unterminated string literal (detected at line 6) (<unknown>, line 6)
# Raw code:
<think>
Okay, I need to create a Mach-Zehnder interferometer using GDSFactory. The user specified using two MMI1x2 components (mmi1 and mmi2) and a phase shifter. The parameters are DeltaL = 10.0 microns and L = 10.0 microns.

First, I'll start by importing the necessary modules. I know I need 'gdsfactory' as 'gf' and the components from 'gf.components'. Also, for routing, I'll need 'gf.routing'.

Next, I'll create a new component 'c' using 'gf.Component()'.

Now, I'll instantiate the first MMI1x2 as 'mmi1' and add it to the component. Then, I'll move it to the origin (0,0).

The second MMI1x2, 'mmi2', needs to be added and then mirrored to function as a 2x1 combiner. I'll move it to a position that ensures DRC safety, probably (200, 0) to give enough space.

The phase shifter component 'ps' is added next. I'll place it at (100, 0) so it's between the two MMI components.

Now, I need to connect the ports using route_bundle to ensure clean routing. The first routing connects the output of mmi1 (o2 and o3) to the input of the phase shifter (o1). I'll use a cross-section of 'strip', radius 20, and separation 20 for safety.

The second routing connects the output of the phase shifter (o2) to the inputs of mmi2 (o1 and o2). Again, I'll use the same parameters for consistency and DRC compliance.

Finally, I'll add the external ports 'o1' and 'o2' from mmi1 and mmi2 respectively. Then, I'll draw the ports and plot the component to visualize the layout.

I need to make sure all connections are made with route_bundle and that the code follows the structure specified, avoiding any route_single calls since they don't accept separation. Also, I'll ensure all numbers are floats and strings are in single quotes as per the instructions.
</think>



import gdsfactory as gf
from gdsfactory.components import mmi1x2, straight_heater_metal

c = gf.Component()

mmi1 = c.add_ref(mmi1x2())
mmi1.move((0, 0))

mmi2 = c.add_ref(mmi1x2())
mmi2.mirror()
mmi2.move((200, 0))

ps = c.add_ref(straight_heater_metal(length=10))
ps.move((100, 0))

gf.routing.route_bundle(
    c,
    [mmi1.ports['o2'], mmi1.ports['o3']],
    [ps.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    c,
    [ps.ports['o2']],
    [mmi2.ports['o1'], mmi2.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

c.add_port('o1', port=mmi1.ports['o1'])
c.add_port('o2', port=mmi2.ports['o3'])

c.draw_ports()
c.plot()

# Cleaned code:
<think>
Okay, I need to create a Mach-Zehnder interferometer using GDSFactory. The user specified using two MMI1x2 components (mmi1 and mmi2) and a phase shifter. The parameters are DeltaL = 10.0 microns and L = 10.0 microns.

First, I'll start by importing the necessary modules. I know I need 'gdsfactory' as 'gf' and the components from 'gf.components'. Also, for routing, I'll need 'gf.routing'.

Next, I'll create a new component 'c' using 'gf.Component()'.

Now, I'll instantiate the first MMI1x2 as 'mmi1' and add it to the component. Then, I'll move it to the origin (0,0).

The second MMI1x2, 'mmi2', needs to be added and then mirrored to function as a 2x1 combiner. I'll move it to a position that ensures DRC safety, probably (200, 0) to give enough space.

The phase shifter component 'ps' is added next. I'll place it at (100, 0) so it's between the two MMI components.

Now, I need to connect the ports using route_bundle to ensure clean routing. The first routing connects the output of mmi1 (o2 and o3) to the input of the phase shifter (o1). I'll use a cross-section of 'strip', radius 20, and separation 20 for safety.

The second routing connects the output of the phase shifter (o2) to the inputs of mmi2 (o1 and o2). Again, I'll use the same parameters for consistency and DRC compliance.

Finally, I'll add the external ports 'o1' and 'o2' from mmi1 and mmi2 respectively. Then, I'll draw the ports and plot the component to visualize the layout.

I need to make sure all connections are made with route_bundle and that the code follows the structure specified, avoiding any route_single calls since they don't accept separation. Also, I'll ensure all numbers are floats and strings are in single quotes as per the instructions.
</think>



import gdsfactory as gf
from gdsfactory.components import mmi1x2, straight_heater_metal

c = gf.Component()

mmi1 = c.add_ref(mmi1x2())
mmi1.move((0, 0))

mmi2 = c.add_ref(mmi1x2())
mmi2.0)
mmi2.move((200, 0))

ps = c.add_ref(straight_heater_metal(length=10))
ps.move((100, 0))

gf.routing.route_bundle(
    c,
    [mmi1.ports['o2'], mmi1.ports['o3']],
    [ps.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    c,
    [ps.ports['o2']],
    [mmi2.ports['o1'], mmi2.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

c.add_port('o1', port=mmi1.ports['o1'])
c.add_port('o2', port=mmi2.ports['o3'])

c.draw_ports()
c.plot()
