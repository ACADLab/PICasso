# Problem 2, Sample 1, Attempt 0
# Error: Syntax error: unterminated string literal (detected at line 6) (<unknown>, line 6)
# Raw code:
<think>
Alright, I need to create a Python script using GDSFactory to design a single-input, single-output Mach-Zehnder Modulator (MZM). The user provided specific components and parameters, so I should follow their instructions carefully.

First, I'll start by importing the necessary GDSFactory components. From the example, I see that the code uses 'import gdsfactory as gf', so I'll include that.

Next, I'll create a new component 'r' using gf.Component(). This will be the main layout where all other components are added.

The MZM consists of an MMI splitter, two phase shifters, and an MMI combiner. The splitter is an MMI1x2, and the combiner is an MMI2x1. However, I remember that GDSFactory doesn't have an MMI2x1 component directly, so I'll need to use the MMI1x2 and mirror it to create the combiner.

I'll add the splitter using splitter = r.add_ref(gf.components.mmi1x2()). Then, I'll position it at (0,0) using splitter.move((0,0)).

For the combiner, I'll add another mmi1x2 component and mirror it. So, combiner = r.add_ref(gf.components.mmi1x2()), then combiner.mirror(), and move it to a position that's DRC-safe, probably (250, 0), ensuring there's enough spacing between components.

Next, I need to add the two phase shifters. Each phase shifter is a straight heater metal with a length of 10.0 microns. I'll add them as phase_shifter1 and phase_shifter2, moving them to positions (100, 50) and (100, -50) respectively. This places them symmetrically above and below the splitter.

Now, I need to connect the ports using route_bundle. The splitter has two output ports, o2 and o3, which I'll connect to the input ports of the phase shifters. I'll use gf.routing.route_bundle(), specifying the ports, cross-section, radius, and separation. The radius is set to 20 for safety, and separation is 20 to prevent overlapping.

After that, I'll connect the output ports of the phase shifters to the combiner's input ports. Again, using route_bundle to ensure clean and coordinated routing.

Finally, I'll expose the external ports. The splitter's o1 port becomes the input, and the combiner's o3 port becomes the output. I'll add these to the main component 'r' using r.add_port() with the appropriate labels.

I'll make sure to draw all ports with r.draw_ports() and plot the layout with r.plot() for visualization.

Throughout the process, I'll ensure all parameters are correctly formatted as floats, use single quotes for strings, and follow the correct method calls to avoid any syntax errors. I'll also check that all components are moved to avoid overlap, maintaining a minimum spacing of 20um for DRC compliance.</think>

import gdsfactory as gf

r = gf.Component()

splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((250, 0))

phase_shifter1 = r.add_ref(gf.components.straight_heater_metal(length=10.0))
phase_shifter1.move((100, 50))

phase_shifter2 = r.add_ref(gf.components.straight_heater_metal(length=10.0))
phase_shifter2.move((100, -50))

gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [phase_shifter1.ports['o1'], phase_shifter2.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [phase_shifter1.ports['o2'], phase_shifter2.ports['o2']],
    [combiner.ports['o1'], combiner.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

r.add_port('o1', port=combiner.ports['o3'])
r.add_port('o2', port=combiner.ports['o3'])  # Corrected to add 'o3' as output

r.draw_ports()
r.plot()

# Cleaned code:
<think>
Alright, I need to create a Python script using GDSFactory to design a single-input, single-output Mach-Zehnder Modulator (MZM). The user provided specific components and parameters, so I should follow their instructions carefully.

First, I'll start by importing the necessary GDSFactory components. From the example, I see that the code uses 'import gdsfactory as gf', so I'll include that.

Next, I'll create a new component 'r' using gf.Component(). This will be the main layout where all other components are added.

The MZM consists of an MMI splitter, two phase shifters, and an MMI combiner. The splitter is an MMI1x2, and the combiner is an MMI2x1. However, I remember that GDSFactory doesn't have an MMI2x1 component directly, so I'll need to use the MMI1x2 and mirror it to create the combiner.

I'll add the splitter using splitter = r.add_ref(gf.components.mmi1x2()). Then, I'll position it at (0,0) using splitter.move((0,0)).

For the combiner, I'll add another mmi1x2 component and mirror it. So, combiner = r.add_ref(gf.components.mmi1x2()), then combiner.mirror(), and move it to a position that's DRC-safe, probably (250, 0), ensuring there's enough spacing between components.

Next, I need to add the two phase shifters. Each phase shifter is a straight heater metal with a length of 10.0 microns. I'll add them as phase_shifter1 and phase_shifter2, moving them to positions (100, 50) and (100, -50) respectively. This places them symmetrically above and below the splitter.

Now, I need to connect the ports using route_bundle. The splitter has two output ports, o2 and o3, which I'll connect to the input ports of the phase shifters. I'll use gf.routing.route_bundle(), specifying the ports, cross-section, radius, and separation. The radius is set to 20 for safety, and separation is 20 to prevent overlapping.

After that, I'll connect the output ports of the phase shifters to the combiner's input ports. Again, using route_bundle to ensure clean and coordinated routing.

Finally, I'll expose the external ports. The splitter's o1 port becomes the input, and the combiner's o3 port becomes the output. I'll add these to the main component 'r' using r.add_port() with the appropriate labels.

I'll make sure to draw all ports with r.draw_ports() and plot the layout with r.plot() for visualization.

Throughout the process, I'll ensure all parameters are correctly formatted as floats, use single quotes for strings, and follow the correct method calls to avoid any syntax errors. I'll also check that all components are moved to avoid overlap, maintaining a minimum spacing of 20.0 for DRC compliance.</think>

import gdsfactory as gf

r = gf.Component()

splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((250, 0))

phase_shifter1 = r.add_ref(gf.components.straight_heater_metal(length=10.0))
phase_shifter1.move((100, 50))

phase_shifter2 = r.add_ref(gf.components.straight_heater_metal(length=10.0))
phase_shifter2.move((100, -50))

gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [phase_shifter1.ports['o1'], phase_shifter2.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [phase_shifter1.ports['o2'], phase_shifter2.ports['o2']],
    [combiner.ports['o1'], combiner.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

r.add_port('o1', port=combiner.ports['o3'])
r.add_port('o2', port=combiner.ports['o3'])  # Corrected to add 'o3' as output

r.draw_ports()
r.plot()
