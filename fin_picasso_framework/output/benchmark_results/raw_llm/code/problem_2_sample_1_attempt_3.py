# Problem 2, Sample 1, Attempt 3
# Generated: 2025-11-12T14:53:52.825780

<think>
Okay, I need to create a single-input, single-output Mach-Zehnder Modulator (MZM) using GDSFactory. The user provided specific components and parameters, so I should follow their guidelines closely.

First, I'll recall the components needed: an MMI1x2 splitter, two phase shifters (straight_heater_metal), and an MMI2x1 combiner. Wait, but I remember that the MZM typically uses a splitter and a combiner, and two phase shifters in between.

Looking at the components reference, I see that the combiner is actually an MMI1x2 that's mirrored to act as a 2x1. So I'll need to add the combiner, then call mirror() on it after adding it to the component.

Next, I'll think about the layout. The splitter should be at the origin, then the phase shifters placed after it. Since they need to be on opposite sides for the MZI, I'll place one above and one below the splitter. I'll use a horizontal spacing of 150um to avoid routing collisions and vertical offsets of 80um and -80um for the phase shifters.

For the parameters, the length of the phase shifters is given as L=10.0 microns. I'll set the length parameter in the straight_heater_metal component to 10.0.

Now, I'll plan the routing. The splitter's output ports (o2 and o3) need to connect to the inputs of the phase shifters. Then, the outputs of the phase shifters will connect to the combiner's input ports. Since there are two connections, I'll use route_bundle() for both sets of connections to ensure proper separation and avoid routing issues.

I should also make sure to call mirror() on the combiner after adding it, as per the correct pattern. The combiner will be placed after the phase shifters, with enough horizontal space to ensure no routing conflicts.

Finally, I'll add the external ports for the MZM: 'o1' from the splitter's input and 'o2' from the combiner's output.

I need to be careful with the port connections. The splitter's o2 connects to phase_shifter1's o1, and o3 to phase_shifter2's o1. Then, phase_shifter1's o2 connects to the combiner's o2, and phase_shifter2's o2 connects to the combiner's o1. This ensures the correct routing through the MZM.

I'll also verify that all components are properly moved and that the routing uses the correct parameters, like cross_section='strip' and radius=15 to maintain bend safety.

Now, putting it all together, I'll structure the code to instantiate each component, move them to their positions, route the connections, and expose the external ports.</think>

<analysis>
We need to create a single-input, single-output Mach-Zehnder Modulator (MZM) with:
  1. One MMI1x2 splitter
  2. Two straight_heater_metal phase shifters
  3. One mirrored MMI1x2 combiner (acting as 2x1)

Component arrangement:
  - Splitter at (0, 0)
  - Phase shifters at (150, 80) and (150, -80) - vertical separation ensures no routing collisions
  - Combiner at (300, 0) - placed after phase shifters with 150um horizontal spacing

Port connections:
  - Splitter o2 -> phase_shifter1 o1
  - Splitter o3 -> phase_shifter2 o1
  - phase_shifter1 o2 -> combiner o2
  - phase_shifter2 o2 -> combiner o1

Parameters:
  - phase_shifter length = 10.0um (L parameter)
  - All other parameters use defaults
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

# 1. Instantiate components with settings
splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

phase_shifter1 = r.add_ref(gf.components.straight_heater_metal(length=10.0))
phase_shifter2 = r.add_ref(gf.components.straight_heater_metal(length=10.0))

phase_shifter1.move((150, 80))
phase_shifter2.move((150, -80))

combiner = r.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((300, 0))

# 2. Route connections
gf.routing.route_single(
    splitter,
    splitter.ports['o2'],
    phase_shifter1.ports['o1'],
    cross_section='strip',
    radius=15
)

gf.routing.route_single(
    splitter,
    splitter.ports['o3'],
    phase_shifter2.ports['o1'],
    cross_section='strip',
    radius=15
)

gf.routing.route_single(
    phase_shifter1,
    phase_shifter1.ports['o2'],
    combiner.ports['o2'],
    cross_section='strip',
    radius=15
)

gf.routing.route_single(
    phase_shifter2,
    phase_shifter2.ports['o2'],
    combiner.ports['o1'],
    cross_section='strip',
    radius=15
)

# 3. Expose external ports
r.add_port('o1', splitter.ports['o1'])
r.add_port('o2', combiner.ports['o3'])

# 4. Finalize
r.draw_ports()
r.plot()
</result>