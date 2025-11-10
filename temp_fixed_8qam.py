import gdsfactory as gf

r = gf.Component()

# Create MZMs vertically aligned
mzm_bit1 = r.add_ref(gf.components.mzm())
mzm_bit1.move((200, 0))

mzm_bit2 = r.add_ref(gf.components.mzm())
mzm_bit2.move((200, 100))

mzm_bit3 = r.add_ref(gf.components.mzm())
mzm_bit3.move((200, 200))

# Create splitters
splitter1 = r.add_ref(gf.components.mmi1x2())
splitter1.move((0, 50))

splitter2 = r.add_ref(gf.components.mmi1x2())
splitter2.move((0, 150))

# Create combiners (FIXED: mirror AFTER add_ref)
combiner1 = r.add_ref(gf.components.mmi1x2())
combiner1.mirror()  # ✓ CORRECT: Call mirror() on ComponentReference
combiner1.move((400, 50))

combiner2 = r.add_ref(gf.components.mmi1x2())
combiner2.mirror()  # ✓ CORRECT: Call mirror() on ComponentReference
combiner2.move((400, 150))

# Route splitter1 outputs to MZMs
gf.routing.route_bundle(
    r,
    [splitter1.ports['o2'], splitter1.ports['o3']],
    [mzm_bit1.ports['o1'], mzm_bit2.ports['o1']],
    cross_section='strip',
    radius=10,
    separation=10
)

# Route splitter2 outputs to MZMs
gf.routing.route_bundle(
    r,
    [splitter2.ports['o2'], splitter2.ports['o3']],
    [mzm_bit2.ports['o2'], mzm_bit3.ports['o1']],
    cross_section='strip',
    radius=10,
    separation=10
)

# Route MZM outputs to combiners
gf.routing.route_bundle(
    r,
    [mzm_bit1.ports['o2'], mzm_bit2.ports['o2']],
    [combiner1.ports['o2'], combiner1.ports['o3']],
    cross_section='strip',
    radius=10,
    separation=10
)

gf.routing.route_bundle(
    r,
    [mzm_bit3.ports['o2']],
    [combiner2.ports['o2']],
    cross_section='strip',
    radius=10,
    separation=10
)

# Add external ports
r.add_port('input1', port=splitter1.ports['o1'])
r.add_port('input2', port=splitter2.ports['o1'])
r.add_port('output1', port=combiner1.ports['o1'])
r.add_port('output2', port=combiner2.ports['o1'])

r.draw_ports()
