# Problem 1, Sample 1, Attempt 3
# Generated: 2025-11-12T01:19:22.533989

<analysis>
We need to create a Mach-Zehnder interferometer with:
  1. Two splitters (MMI 1x2)
  2. One phase shifter (straight_heater_metal)
  
Component arrangement:
  - The first MMI (splitter) will be placed at (0, 0).
  - The second MMI (combiner) will be mirrored and placed at (250, 0) to ensure proper orientation.
  - The phase shifter will be placed at (100, 50) and (100, -50) for vertical separation of 100um to prevent collisions.

Port connections:
  - The output ports o2 and o3 of the first MMI will connect to the inputs of the phase shifter.
  - The outputs of the phase shifter will connect to the inputs of the second MMI, with the output ports o2 and o1 being used.

Critical: The second MMI needs mirror() called after add_ref() to match port orientation.
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

mmi_splitter = r.add_ref(gf.components.mmi1x2())
mmi_splitter.move((0, 0))

mmi_combiner = r.add_ref(gf.components.mmi1x2())
mmi_combiner.mirror()
mmi_combiner.move((250, 0))

ps1 = r.add_ref(gf.components.straight_heater_metal(length=10.0))
ps1.move((100, 50))

ps2 = r.add_ref(gf.components.straight_heater_metal(length=10.0))
ps2.move((100, -50))

gf.routing.route_bundle(
    r,
    [mmi_splitter.ports['o2'], mmi_splitter.ports['o3']],
    [ps1.ports['o1'], ps2.ports['o1']],
    cross_section='strip',
    radius=15,
    separation=15
)

gf.routing.route_bundle(
    r,
    [ps1.ports['o2'], ps2.ports['o2']],
    [mmi_combiner.ports['o2'], mmi_combiner.ports['o1']],
    cross_section='strip',
    radius=15,
    separation=15
)

r.add_port('o1', port=mmi_splitter.ports['o1'])
r.add_port('o2', port=mmi_combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>