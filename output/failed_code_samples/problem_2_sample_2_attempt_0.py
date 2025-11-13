# Problem 2, Sample 2, Attempt 0
# Error: Syntax error: unterminated string literal (detected at line 2) (<unknown>, line 2)
# Raw code:
<think>
Okay, I need to create a Python script using GDSFactory 9.9.4 to design a single-input, single-output Mach-Zehnder Modulator (MZM). The user provided specific components and parameters, so I'll follow those instructions carefully.

First, I'll start by importing the GDSFactory library as 'gf'. Then, I'll create a new component 'c' using 'gf.Component()'.

Next, I need to instantiate the components. The MZM requires a splitter, two phase shifters, and a combiner. I'll add the splitter using 'splitter = c.add_ref(gf.components.mmi1x2())'. Since the splitter has three ports labeled o1, o2, o3, I'll connect o1 as the input and o2 and o3 to the phase shifters.

For the phase shifters, I'll use 'straight_heater_metal' components. I'll add two instances, 'ps1' and 'ps2', each with a length of 10.0 microns. I'll position 'ps1' at (200, 50) and 'ps2' at (200, -50) to ensure they don't overlap and maintain a DRC-safe spacing of at least 20um.

Now, I need to connect the splitter to the phase shifters. Using 'route_bundle()' ensures clean routing and allows for separation. I'll connect the splitter's o2 and o3 ports to the phase shifters' o1 ports with a cross-section of 'strip', radius of 20um, and separation of 20um. Similarly, I'll connect the phase shifters' o2 ports to the combiner's o1 and o2 ports using the same parameters.

The combiner is created by mirroring the splitter, so I'll add it with 'combiner = c.add_ref(gf.components.mmi1x2())' and then call 'combiner.mirror()'. I'll position it at (400, 0) to avoid overlapping with other components.

Finally, I'll expose the external ports. The input port will be 'o1' from the splitter, and the output will be 'o3' from the combiner. I'll add these using 'c.add_port()' and then draw and plot the component to visualize the layout.

I made sure to follow all the user's instructions, such as using only the specified component IDs, ensuring DRC safety, and correctly applying the routing methods without any extraneous comments or text.</think>

import gdsfactory as gf

c = gf.Component()

splitter = c.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

ps1 = c.add_ref(gf.components.straight_heater_metal(length=10.0))
ps1.move((200, 50))

ps2 = c.add_ref(gf.components.straight_heater_metal(length=10.0))
ps2.move((200, -50))

gf.routing.route_bundle(
    c,
    [splitter.ports['o2'], splitter.ports['o3']],
    [ps1.ports['o1'], ps2.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

combiner = c.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((400, 0))

gf.routing.route_bundle(
    c,
    [ps1.ports['o2'], ps2.ports['o2']],
    [combiner.ports['o1'], combiner.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

c.add_port('o1', port=combiner.ports['o3'])
c.add_port('o2', port=combiner.ports['o3'])

c.draw_ports()
c.plot()

# Cleaned code:
<think>
Okay, I need to create a Python script using GDSFactory 9.9 to design a single-input, single-output Mach-Zehnder Modulator (MZM). The user provided specific components and parameters, so I'll follow those instructions carefully.

First, I'll start by importing the GDSFactory library as 'gf'. Then, I'll create a new component 'c' using 'gf.Component()'.

Next, I need to instantiate the components. The MZM requires a splitter, two phase shifters, and a combiner. I'll add the splitter using 'splitter = c.add_ref(gf.components.mmi1x2())'. Since the splitter has three ports labeled o1, o2, o3, I'll connect o1 as the input and o2 and o3 to the phase shifters.

For the phase shifters, I'll use 'straight_heater_metal' components. I'll add two instances, 'ps1' and 'ps2', each with a length of 10.0 microns. I'll position 'ps1' at (200, 50) and 'ps2' at (200, -50) to ensure they don't overlap and maintain a DRC-safe spacing of at least 20um.

Now, I need to connect the splitter to the phase shifters. Using 'route_bundle()' ensures clean routing and allows for separation. I'll connect the splitter's o2 and o3 ports to the phase shifters' o1 ports with a cross-section of 'strip', radius of 20.0, and separation of 20um. Similarly, I'll connect the phase shifters' o2 ports to the combiner's o1 and o2 ports using the same parameters.

The combiner is created by mirroring the splitter, so I'll add it with 'combiner = c.add_ref(gf.components.mmi1x2())' and then call 'combiner.mirror()'. I'll position it at (400, 0) to avoid overlapping with other components.

Finally, I'll expose the external ports. The input port will be 'o1' from the splitter, and the output will be 'o3' from the combiner. I'll add these using 'c.add_port()' and then draw and plot the component to visualize the layout.

I made sure to follow all the user's instructions, such as using only the specified component IDs, ensuring DRC safety, and correctly applying the routing methods without any extraneous comments or text.</think>

import gdsfactory as gf

c = gf.Component()

splitter = c.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

ps1 = c.add_ref(gf.components.straight_heater_metal(length=10.0))
ps1.move((200, 50))

ps2 = c.add_ref(gf.components.straight_heater_metal(length=10.0))
ps2.move((200, -50))

gf.routing.route_bundle(
    c,
    [splitter.ports['o2'], splitter.ports['o3']],
    [ps1.ports['o1'], ps2.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

combiner = c.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((400, 0))

gf.routing.route_bundle(
    c,
    [ps1.ports['o2'], ps2.ports['o2']],
    [combiner.ports['o1'], combiner.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

c.add_port('o1', port=combiner.ports['o3'])
c.add_port('o2', port=combiner.ports['o3'])

c.draw_ports()
c.plot()
