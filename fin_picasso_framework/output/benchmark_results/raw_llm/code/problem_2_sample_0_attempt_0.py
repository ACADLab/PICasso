# Problem 2, Sample 0, Attempt 0
# Generated: 2025-11-12T17:02:14.368200

<think>
Okay, I need to create a Python script using GDSFactory 9.9.4 to design a single-input, single-output Mach-Zehnder Modulator (MZM). The user has specified the components to use: an MMI1x2 splitter, an MMI2x1 combiner, and two straight phase shifters. The length L is given as 10.0 microns.

First, I'll start by importing the GDSFactory library as gf. Then, I'll create a new component called mzm.

Next, I'll instantiate the splitter by adding a reference to the mmi1x2 component and move it to the origin. Similarly, I'll add the combiner, but since it's an MMI2x1, I think I need to mirror the splitter to make it work as a combiner. So I'll mirror the combiner component.

For the phase shifters, I'll add two references to the straight_heater_metal component, each with a length of 10.0 microns. I'll move them to positions (100, 50) and (100, -50) respectively to ensure they don't overlap and maintain DRC spacing.

Now, I need to connect the ports using route_bundle to ensure clean routing. I'll connect the splitter's output ports o2 and o3 to the phase shifters' o1 ports. Then, I'll connect the phase shifters' o2 ports to the combiner's o1 and o2 ports.

I'll make sure to use the correct parameters for route_bundle, including the cross_section, radius of 20um, and separation of 20um to maintain DRC safety.

Finally, I'll expose the external ports o1 and o2 from the splitter and combiner respectively, draw the ports, and plot the component.

I should double-check that all connections are correctly made and that the components are properly positioned without overlapping. Also, ensure that all required parameters are set as floats and that the correct methods are used without any typos.
</think>



```python
import gdsfactory as gf

mzm = gf.Component()

# Add components
splitter = mzm.add_ref(gf.components.mmi1x2())
splitter.move((0, 0))

combiner = mzm.add_ref(gf.components.mmi1x2())
combiner.mirror()
combiner.move((200, 0))

phase_shifter1 = mzm.add_ref(gf.components.straight_heater_metal(length=10.0))
phase_shifter1.move((100, 50))

phase_shifter2 = mzm.add_ref(gf.components.straight_heater_metal(length=10.0))
phase_shifter2.move((100, -50))

# Route splitter to phase shifters
gf.routing.route_bundle(
    mzm,
    [splitter.ports['o2'], splitter.ports['o3']],
    [phase_shifter1.ports['o1'], phase_shifter2.ports['o1']],
    cross_section='strip',
    radius=20,
    separation=20
)

# Route phase shifters to combiner
gf.routing.route_bundle(
    mzm,
    [phase_shifter1.ports['o2'], phase_shifter2.ports['o2']],
    [combiner.ports['o1'], combiner.ports['o2']],
    cross_section='strip',
    radius=20,
    separation=20
)

# Add external ports
mzm.add_port('o1', port=combiner.ports['o3'])
mzm.add_port('o2', port=combiner.ports['o1'])

mzm.draw_ports()
mzm.plot()
```