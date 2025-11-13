# Problem 1, Sample 2, Attempt 0
# Error: Syntax error: unterminated string literal (detected at line 6) (<unknown>, line 6)
# Raw code:
<think>
Alright, I need to create a Mach-Zehnder interferometer using GDSFactory. The user specified using two MMI1x2 components and a phase shifter. Let me break down the steps.

First, I'll start by importing the necessary modules. I know I need 'gdsfactory' as 'gf' and 'numpy' for any calculations, but maybe I'll need 'cmath' for complex numbers if positioning is tricky.

Next, I'll create a new component 'c' using gf.Component(). This will hold all the subcomponents.

The first step is to instantiate the components. I'll add two MMI1x2 splitters, mmi1 and mmi2. Then, I'll add the phase shifter. I'll position mmi1 at the origin. For mmi2, I need to place it a certain distance away. The problem says DeltaL is 10.0 microns, so I'll move it (DeltaL, 0) which should be (10.0, 0).

Now, the phase shifter needs to be placed in between the two MMIs. Since the total length L is 10.0 microns, the phase shifter should be centered. So, I'll calculate its position as (DeltaL/2, 0) which is (5.0, 0).

Next, I need to connect these components without overlapping. I'll use route_bundle for clean routing. The first connection is from mmi1's o2 and o3 ports to the phase shifter's o1 and o2 ports. I'll set the cross-section to 'strip', radius 20 for safety, and separation 20 to prevent DRC issues.

Then, I'll connect the phase shifter's o2 and o3 ports to mmi2's o1 and o2 ports using the same route_bundle parameters.

After connecting, I need to expose the external ports. The input will be mmi1's o1, and the output will be mmi2's o3. I'll add these ports to the main component 'c'.

Finally, I'll draw the ports and plot the layout. I'll make sure all connections are clean and DRC-safe with at least 20um spacing.

I think that covers all the requirements. Let me put it all together in code.
</think>



import gdsfactory as gf
import numpy as np
import cmath

c = gf.Component()

# Add components
mmi1 = c.add_ref(gf.components.mmi1x2())
mmi2 = c.add_ref(gf.components.mmi1x2())
phase_shifter = c.add_ref(gf.components.straight_heater_metal(length=10.0))

# Position components
mmi1.move((0, 0))
mmi2.move((10.0, 0))
phase_shifter.move((5.0, 0))

# Route connections
gf.routing.route_bundle(
    c,
    [mmi1.ports['o2'], mmi1.ports['o3']],
    [phase_shifter.ports['o1'], phase_shifter.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    c,
    [phase_shifter.ports['o2'], phase_shifter.ports['o3']],
    [mmi2.ports['o1'], mmi2.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

# Add external ports
c.add_port('o1', port=mmi1.ports['o1'])
c.add_port('o2', port=mmi2.ports['o3'])

c.draw_ports()
c.plot()

# Cleaned code:
<think>
Alright, I need to create a Mach-Zehnder interferometer using GDSFactory. The user specified using two MMI1x2 components and a phase shifter. Let me break down the steps.

First, I'll start by importing the necessary modules. I know I need 'gdsfactory' as 'gf' and 'numpy' for any calculations, but maybe I'll need 'cmath' for complex numbers if positioning is tricky.

Next, I'll create a new component 'c' using gf.Component(). This will hold all the subcomponents.

The first step is to instantiate the components. I'll add two MMI1x2 splitters, mmi1 and mmi2. Then, I'll add the phase shifter. I'll position mmi1 at the origin. For mmi2, I need to place it a certain distance away. The problem says DeltaL is 10.0 microns, so I'll move it (DeltaL, 0) which should be (10.0, 0).

Now, the phase shifter needs to be placed in between the two MMIs. Since the total length L is 10.0 microns, the phase shifter should be centered. So, I'll calculate its position as (DeltaL/2, 0) which is (5.0, 0).

Next, I need to connect these components without overlapping. I'll use route_bundle for clean routing. The first connection is from mmi1's o2 and o3 ports to the phase shifter's o1 and o2 ports. I'll set the cross-section to 'strip', radius 20 for safety, and separation 20 to prevent DRC issues.

Then, I'll connect the phase shifter's o2 and o3 ports to mmi2's o1 and o2 ports using the same route_bundle parameters.

After connecting, I need to expose the external ports. The input will be mmi1's o1, and the output will be mmi2's o3. I'll add these ports to the main component 'c'.

Finally, I'll draw the ports and plot the layout. I'll make sure all connections are clean and DRC-safe with at least 20.0 spacing.

I think that covers all the requirements. Let me put it all together in code.
</think>



import gdsfactory as gf
import numpy as np
import cmath

c = gf.Component()

# Add components
mmi1 = c.add_ref(gf.components.mmi1x2())
mmi2 = c.add_ref(gf.components.mmi1x2())
phase_shifter = c.add_ref(gf.components.straight_heater_metal(length=10.0))

# Position components
mmi1.move((0, 0))
mmi2.move((10.0, 0))
phase_shifter.move((5.0, 0))

# Route connections
gf.routing.route_bundle(
    c,
    [mmi1.ports['o2'], mmi1.ports['o3']],
    [phase_shifter.ports['o1'], phase_shifter.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

gf.routing.route_bundle(
    c,
    [phase_shifter.ports['o2'], phase_shifter.ports['o3']],
    [mmi2.ports['o1'], mmi2.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

# Add external ports
c.add_port('o1', port=mmi1.ports['o1'])
c.add_port('o2', port=mmi2.ports['o3'])

c.draw_ports()
c.plot()
