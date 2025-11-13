# Problem 4, Sample 1, Attempt 0
# Error: Syntax error: unterminated string literal (detected at line 4) (<unknown>, line 4)
# Raw code:
<think>
Okay, I need to create a Python script using GDSFactory to design an optical QPSK transmitter. The components required are two Mach-Zehnder Modulators (mzm_i and mzm_q), one MMI1x2 Splitter, one MMI2x1 Combiner, and two phase biasers (pb_i and pb_q). 

First, I'll start by importing the necessary GDSFactory modules. I remember that I need to import components and maybe some for routing.

Next, I'll create a new component, let's call it 'r', which will be the main component containing all the parts.

Now, I need to instantiate each of the required components. The splitter is an MMI1x2, so I'll add it using splitter = r.add_ref(gf.components.mmi1x2()). Similarly, the combiner is an MMI2x1, but I think I can create that by taking another mmi1x2 component and mirroring it. So I'll add it as combiner = r.add_ref(gf.components.mmi1x2()) and then call combiner.mirror().

For the Mach-Zehnder Modulators, I'll use the mzi component. So mzm_i = r.add_ref(gf.components.mzi()) and mzm_q = r.add_ref(gf.components.mzi()). 

The phase biasers are simple straight waveguides, so I'll add them as pb_i = r.add_ref(gf.components.straight(length=10)) and pb_q = r.add_ref(gf.components.straight(length=10)).

Next, I need to position these components to avoid overlapping. The splitter and combiner should be placed on either side. Maybe place the splitter at (0,0) and the combiner at (200,0). The modulators can be positioned near the splitter and combiner. For example, mzm_i can be moved to (-50, -50) and mzm_q to (-50, 50). The phase biasers can be placed near the modulators, like pb_i at (-100, -50) and pb_q at (-100, 50).

Now, I need to connect the ports using route_bundle to ensure clean routing. The splitter has output ports o2 and o3, which should connect to the input ports of the mzm_i and mzm_q. So I'll use route_bundle with the splitter's o2 and o3 ports connected to mzm_i's o1 and mzm_q's o1. The cross_section is 'strip', radius 20, and separation 20 for DRC safety.

After the modulators, their output ports o2 and o3 need to connect to the combiner's input ports o1 and o2. Again, using route_bundle with the same parameters.

Then, the phase biasers are connected to the modulators. The pb_i's o1 connects to mzm_i's o3, and pb_q's o1 connects to mzm_q's o3. Another route_bundle call with the same settings.

I also need to expose the external ports. The input to the splitter is o1, and the output from the combiner is o3. So I'll add these ports to the main component 'r' using r.add_port('o1', port=splitter.ports['o1']) and r.add_port('o2', port=combiner.ports['o3']).

Finally, I'll draw all the ports and plot the component. I'll make sure to call r.draw_ports() and r.plot().

I think that covers all the steps. Now, I'll put it all together into a Python script, making sure to follow the syntax and avoid any mistakes.</think>

import gdsfactory as gf

r = gf.Component()

splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((200, 0))

mzm_i = r.add_ref(gf.components.mzi())
mzm_i.move((-50, -50))

mzm_q = r.add_ref(gf.components.mzi())
mzm_q.move((-50, 50))

pb_i = r.add_ref(gf.components.straight(length=10))
pb_i.move((-100, -50))

pb_q = r.add_ref(gf.components.straight(length=10))
pb_q.move((-100, 50))

gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [mzm_i.ports['o1'], mzm_q.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [mzm_i.ports['o2'], mzm_q.ports['o2']],
    [combiner.ports['o1'], combiner.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [mzm_i.ports['o3'], mzm_q.ports['o3']],
    [pb_i.ports['o1'], pb_q.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

r.draw_ports()
r.plot()

# Cleaned code:
<think>
Okay, I need to create a Python script using GDSFactory to design an optical QPSK transmitter. The components required are two Mach-Zehnder Modulators (mzm_i and mzm_q), one MMI1x2 Splitter, one MMI2x1 Combiner, and two phase biasers (pb_i and pb_q). 

First, I'll start by importing the necessary GDSFactory modules. I remember that I need to import components and maybe some for routing.

Next, I'll create a new component, let's call it 'r', which will be the main component containing all the parts.

Now, I need to instantiate each of the required components. The splitter is an MMI1x2, so I'll add it using splitter = r.add_ref(gf.components.mmi1x2()). Similarly, the combiner is an MMI2x1, but I think I can create that by taking another mmi1x2 component and mirroring it. So I'll add it as combiner = r.add_ref(gf.components.mmi1x2()) and then call combiner.mirror().

For the Mach-Zehnder Modulators, I'll use the mzi component. So mzm_i = r.add_ref(gf.components.mzi()) and mzm_q = r.add_ref(gf.components.mzi()). 

The phase biasers are simple straight waveguides, so I'll add them as pb_i = r.add_ref(gf.components.straight(length=10)) and pb_q = r.add_ref(gf.components.straight(length=10)).

Next, I need to position these components to avoid overlapping. The splitter and combiner should be placed on either side. Maybe place the splitter at (0,0) and the combiner at (200,0). The modulators can be positioned near the splitter and combiner. For example, mzm_i can be moved to (-50, -50) and mzm_q to (-50, 50). The phase biasers can be placed near the modulators, like pb_i at (-100, -50) and pb_q at (-100, 50).

Now, I need to connect the ports using route_bundle to ensure clean routing. The splitter has output ports o2 and o3, which should connect to the input ports of the mzm_i and mzm_q. So I'll use route_bundle with the splitter's o2 and o3 ports connected to mzm_i's o1 and mzm_q's o1. The cross_section is 'strip', radius 20, and separation 20 for DRC safety.

After the modulators, their output ports o2 and o3 need to connect to the combiner's input ports o1 and o2. Again, using route_bundle with the same parameters.

Then, the phase biasers are connected to the modulators. The pb_i's o1 connects to mzm_i's o3, and pb_q's o1 connects to mzm_q's o3. Another route_bundle call with the same settings.

I also need to expose the external ports. The input to the splitter is o1, and the output from the combiner is o3. So I'll add these ports to the main component 'r' using r.add_port('o1', port=splitter.ports['o1']) and r.add_port('o2', port=combiner.ports['o3']).

Finally, I'll draw all the ports and plot the component. I'll make sure to call r.draw_ports() and r.plot().

I think that covers all the steps. Now, I'll put it all together into a Python script, making sure to follow the syntax and avoid any mistakes.</think>

import gdsfactory as gf

r = gf.Component()

splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((200, 0))

mzm_i = r.add_ref(gf.components.mzi())
mzm_i.move((-50, -50))

mzm_q = r.add_ref(gf.components.mzi())
mzm_q.move((-50, 50))

pb_i = r.add_ref(gf.components.straight(length=10))
pb_i.move((-100, -50))

pb_q = r.add_ref(gf.components.straight(length=10))
pb_q.move((-100, 50))

gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [mzm_i.ports['o1'], mzm_q.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [mzm_i.ports['o2'], mzm_q.ports['o2']],
    [combiner.ports['o1'], combiner.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    r,
    [mzm_i.ports['o3'], mzm_q.ports['o3']],
    [pb_i.ports['o1'], pb_q.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

r.add_port('o1', port=splitter.ports['o1'])
r.add_port('o2', port=combiner.ports['o3'])

r.draw_ports()
r.plot()
