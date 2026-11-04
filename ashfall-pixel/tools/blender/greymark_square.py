"""Greymark square: the small hexagon diorama (Book 1 · Ch I, the well distribution).

    <bpy-venv>/bin/python tools/blender/greymark_square.py out.png [--size 1500] [--samples 40] [--night] [--toon]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import *  # noqa: F401,F403

# ---------------------------------------------------------------- build ---
R = 7.5  # slab radius
# hexagonal floating slab with soil strata
cyl(R, 1.6, (0, 0, -0.8), M['soil'], 6, rot=(0, 0, math.radians(30)), name='slab')
cyl(R - 0.02, 0.12, (0, 0, -0.04), M['grass'], 6, rot=(0, 0, math.radians(30)), name='turf')
# soil slab only (like the reference diorama); a mossy lip hangs over the rim
for i in range(10):  # moss/grass lip hanging over the edge
    a = i / 10 * math.tau + 0.3
    blob(0.4, (math.cos(a) * (R - 0.2), math.sin(a) * (R - 0.2), -0.15), M['moss'], seed=300 + i, rough=0.5, subdiv=1, squash=0.5)

# cobbled square + roads
cyl(2.6, 0.06, (0.3, 0.2, 0.03), M['cobble'], 10, name='square')
box(1.3, 7.0, 0.04, (0.3, -4.2, 0.02), M['dirt'], name='road_s')
box(5.5, 1.1, 0.04, (3.6, 0.2, 0.02), M['dirt'], name='road_e')

# the town well: stone ring, red water, timber frame, little roof, bucket
cyl(0.62, 0.55, (0.3, 0.2, 0.3), M['stone'], 14, name='well')
cyl(0.5, 0.05, (0.3, 0.2, 0.52), M['redwater'], 14, name='water')
POINTS['water'] += [(0.3 + 0.3 * math.cos(a), 0.2 + 0.3 * math.sin(a), 0.56) for a in (0, 1.6, 3.2, 4.7)]
for dx in (-0.55, 0.55): box(0.08, 0.08, 1.3, (0.3 + dx, 0.2, 0.9), M['timber'])
box(1.3, 0.08, 0.08, (0.3, 0.2, 1.5), M['timber'])
gable_roof(1.3, 0.8, 0.35, 0.1, (0.3, 0.2, 1.55), M['thatch_dark'], name='well_roof')
cyl(0.1, 0.16, (0.3, 0.2, 1.1), M['wood'], 8)
# Aldren's ledger table, ledger, chalice; Aldren in charcoal; the queue
box(0.9, 0.45, 0.06, (1.35, -0.6, 0.5), M['wood']); box(0.06, 0.4, 0.47, (1.0, -0.6, 0.24), M['wood']); box(0.06, 0.4, 0.47, (1.7, -0.6, 0.24), M['wood'])
box(0.3, 0.22, 0.04, (1.25, -0.6, 0.55), M['paper'])
cyl(0.05, 0.14, (1.55, -0.55, 0.6), M['gold'], 8, r2=0.08)
figure(1.4, -1.05, M['robe'], hood=True, s=1.1)                     # Aldren
figure(1.0, 0.05, M['robe'], hood=True)                              # his man with the cup
for i, c in enumerate(['cloth_b', 'cloth_w', 'cloth_r', 'cloth_b', 'cloth_w']):
    figure(1.9 + i * 0.45, -0.1 - i * 0.2, M[c], s=0.95)             # the line of the faithful
figure(-1.5, 1.6, M['cloak'], s=1.05, hood=True)                     # Kethric, watching, not drinking
box(0.05, 0.05, 0.5, (-1.32, 1.6, 0.45), M['iron'], rot=(0, math.radians(20), 0))  # his sword

# buildings around the square
timber_house(-3.0, -1.4, 2.6, 1.9, 2.4, rot=math.radians(90), roof='thatch', seed=1, name='broken_compass', lit=0.9)
box(0.05, 0.05, 0.8, (-1.85, -2.6, 1.7), M['iron'])                              # sign bracket
box(0.5, 0.05, 0.35, (-1.85, -2.6, 1.25), M['wood'])                             # the Broken Compass sign
timber_house(-2.2, 2.6, 2.2, 1.7, 2.2, rot=math.radians(0), roof='thatch_dark', seed=2, name='harren', plaster='plaster2')
timber_house(1.6, 3.6, 2.0, 1.6, 2.3, rot=math.radians(0), roof='thatch', seed=3, name='house_n')
timber_house(4.2, 3.6, 1.8, 1.6, 1.6, rot=math.radians(0), roof='thatch_dark', storeys=1, seed=4, name='house_ne')
timber_house(-1.2, 5.0, 2.2, 1.7, 2.6, rot=math.radians(0), roof='slate', seed=5, name='house_back', plaster='plaster2')
timber_house(-4.6, 2.0, 1.6, 1.4, 1.5, rot=math.radians(0), roof='thatch', storeys=1, seed=6, name='cottage')

# old ancient stones: carved doorstep and a mossy ruin fragment by Harren's
box(0.9, 0.5, 0.12, (-2.2, 1.6, 0.06), M['bone'])
for i, (dx, dy, hh) in enumerate([(-4.2, -0.2, 1.4), (-4.3, 0.7, 0.9)]):
    box(0.45, 0.45, hh, (dx, dy, hh / 2), M['bone']); box(0.47, 0.47, 0.12, (dx, dy, hh), M['moss'])

# Vex's mill (south-east): long stone-and-timber shed + treadwheel, linen drying
timber_house(4.4, 0.9, 2.6, 1.8, 1.8, rot=math.radians(90), roof='thatch_dark', storeys=1, seed=7, name='vex_mill', plaster='plaster2', chimney=False)
cyl(0.85, 0.22, (3.3, 0.2, 0.95), M['wood'], 16, rot=(math.radians(90), 0, 0), name='treadwheel')
cyl(0.7, 0.24, (3.3, 0.2, 0.95), M['timber'], 16, rot=(math.radians(90), 0, 0))
for i in range(3):
    box(0.04, 0.04, 0.9, (3.4 + i * 0.5, -2.2, 0.45), M['timber'])
box(1.1, 0.02, 0.02, (3.9, -2.2, 0.88), M['iron'])
for i in range(4):
    box(0.2, 0.02, 0.32, (3.5 + i * 0.27, -2.2, 0.7), M['linen'])
# flax field
for i in range(90):
    fx, fy = 3.0 + rnd.random() * 2.6, -3.0 - rnd.random() * 1.8
    if math.hypot(fx, fy) < R - 0.8:
        cyl(0.05, 0.35 + rnd.random() * 0.15, (fx, fy, 0.2), M['flax'], 5, r2=0.0)

# palisade: dark stakes on the back (north-west) arc + bone-white stone gate south
for i in range(70):
    a = math.radians(95 + i * 2.6)
    px, py = math.cos(a) * (R - 0.45), math.sin(a) * (R - 0.45)
    if abs(math.degrees(a) - 270) < 6: continue  # gap for the gate
    hh = 1.3 + rnd.random() * 0.25
    cyl(0.1, hh, (px, py, hh / 2), M['timber'], 6)
    cyl(0.1, 0.25, (px, py, hh + 0.12), M['timber'], 6, r2=0.0)
for gx in (-0.45, 1.05):
    box(0.6, 0.6, 2.0, (gx, -R + 0.5, 1.0), M['bone'])
    for cx in (-0.2, 0.2):
        for cy in (-0.2, 0.2): box(0.14, 0.14, 0.18, (gx + cx, -R + 0.5 + cy, 2.09), M['bone'])
box(1.0, 0.4, 0.3, (0.3, -R + 0.5, 1.75), M['bone'])

# trees: autumn around the edge, a couple of dark pines
for i, (tx, ty, k, s) in enumerate([(-5.2, -2.6, 'o', 1.1), (-5.6, 3.6, 'r', 1.0), (-1.0, 5.6, 'o', 1.2), (2.8, 5.3, 'r', 0.9),
                                    (6.0, 1.8, 'o', 0.9), (-3.4, -4.8, 'r', 1.0), (2.6, -5.2, 'o', 1.0), (5.4, -4.6, 'g', 0.8)]):
    tree(tx, ty, s, k, seed=i + 3)
for (px, py) in [(-6.0, 0.9), (-4.6, 5.0), (0.8, 6.2)]:
    pine(px, py, 1.2)

# props: barrels, crates, cart, lanterns, campfire by the gate
for (bx, by) in [(-1.75, -0.7), (-1.75, -0.3), (-1.4, -0.5), (3.5, -1.0)]: barrel(bx, by)
for i, (cx_, cy_) in enumerate([(-1.6, -1.2), (2.4, 1.6), (2.7, 1.8), (2.6, -0.9)]): crate(cx_, cy_, rz=i * 0.4)
lantern_post(-1.2, 0.9); lantern_post(2.2, -1.5); lantern_post(1.4, 2.0)
POINTS['fires'].append((-0.9, -4.2, 0.2)); cyl(0.25, 0.08, (-0.9, -4.2, 0.05), M['stone'], 8); cyl(0.12, 0.3, (-0.9, -4.2, 0.2), M['fire'], 6, r2=0.0)
Lf = bpy.data.lights.new('fire', 'POINT'); Lf.energy = 40; Lf.color = (1, 0.55, 0.25)
of = bpy.data.objects.new('fire', Lf); bpy.context.collection.objects.link(of); of.location = (-0.9, -4.2, 0.6)
# rocks + grass tufts
for i in range(28):
    a = rnd.random() * math.tau; d = 2.8 + rnd.random() * (R - 3.6)
    blob(0.1 + rnd.random() * 0.15, (math.cos(a) * d, math.sin(a) * d, 0.05), M['stone'] if i % 3 else M['moss'], seed=100 + i, rough=0.6, subdiv=1)

# story labels (world positions) -> ids match data/story.json where they exist
POINTS['labels'] = {
    'town_well': (0.3, 0.2, 2.0), 'broken_compass': (-3.0, -1.4, 4.2), 'harrens_place': (-2.2, 2.6, 4.0),
    'vex_mill': (4.4, 0.9, 3.3), 'aldren': (1.4, -1.05, 1.1), 'kethric': (-1.5, 1.6, 1.2),
    'greymark_walls': (0.3, -R + 0.5, 2.4), 'flax_farms': (4.2, -3.8, 0.8),
}

finish(21.0, shift_y=-0.05)
