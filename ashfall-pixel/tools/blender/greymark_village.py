"""Greymark, the whole town, laid out as one isometric diorama (single fixed camera from the south-east).

    <bpy-venv>/bin/python tools/blender/greymark_town.py out.png [--size 3000] [--samples 24] [--night] [--toon]

Layout rules for a one-sided view (camera looks north-west):
  * tall things at the BACK (north-west): forest edge, north gate, tallest houses
  * the square + story buildings in the MIDDLE, unobstructed
  * low things at the FRONT (south-east): fields, the south road running out toward the viewer
  * Vex's mill + flax outside the palisade to the EAST (screen right)
Story facts (book 3.0): dark-timber palisade with bone-white stone gates; the town well with
faintly red water; Aldren's ledger table; the Broken Compass; Harren's place over the old
foundations; the blacksmith; Vex's linen mill outside the walls with flax farms and dye that
won't set; ancient carved stones in the doorsteps; forest around the clearing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import *  # noqa: F401,F403

R = 29.0          # slab radius (hexagon)
PAL_R = 15.0      # palisade radius
SQ_R = 3.6        # square radius
M['dye'] = mat('dye', ['#1e2c5a', '#2a3f7a', '#3a56a0'], 'noise', 6, 0.05, 0.2)
M['field'] = mat('field', ['#2e2016', '#4a3424', '#3e5a30', '#4f7040'], 'wave', 3, 0.6)
M['fence'] = mat('fence', ['#3e2a1c', '#5a3e28'], 'wave', 12, 0.2)


def P(angle_deg, r):
    a = math.radians(angle_deg); return (math.cos(a) * r, math.sin(a) * r)


def in_hex(x, y, rad):
    # pointy-side hexagon matching the slab (rotated 30deg)
    for k in range(6):
        a = math.radians(60 * k)
        if x * math.cos(a) + y * math.sin(a) > rad * math.cos(math.radians(30)):
            return False
    return True


def seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


# ------------------------------------------------------------------ ground ---
cyl(R, 2.0, (0, 0, -1.0), M['soil'], 6, rot=(0, 0, math.radians(30)), name='slab')
cyl(R - 0.03, 0.12, (0, 0, -0.04), M['grass'], 6, rot=(0, 0, math.radians(30)), name='turf')
for i in range(26):  # mossy lip over the rim
    a = i / 26 * math.tau + 0.1
    blob(0.55, (math.cos(a) * (R - 0.5), math.sin(a) * (R - 0.5), -0.15), M['moss'], seed=500 + i, rough=0.5, subdiv=1, squash=0.45)

# gates (angles: south gate faces the viewer, north gate at the back, mill gate east)
G_SOUTH, G_NORTH, G_MILL = -45, 135, 10
gS, gN, gM = P(G_SOUTH, PAL_R), P(G_NORTH, PAL_R), P(G_MILL, PAL_R)

# streets inside (centre lines) and roads outside
streets = [((0, 0), gS), ((0, 0), gN), ((0, 0), gM), ((0, 0), P(215, PAL_R - 1.0)), ((0, 0), P(75, PAL_R - 1.0))]
roads_out = [(gS, P(G_SOUTH, R + 1)), (gN, P(G_NORTH, R + 1)), (gM, (20.5, 4.4))]
for a, b in streets + roads_out:
    L = math.hypot(b[0] - a[0], b[1] - a[1]); ang = math.atan2(b[1] - a[1], b[0] - a[0])
    box(L, 1.5, 0.06, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.03), M['cobble'] if (a, b) in streets else M['dirt'], rot=(0, 0, ang), name='street')
# packed earth inside the walls (towns were mud and cobbles, not lawn)
cyl(PAL_R - 0.2, 0.05, (0, 0, 0.02), M['dirt'], 48, name='town_ground')
cyl(SQ_R, 0.07, (0, 0, 0.035), M['cobble'], 16, name='square')

# ---------------------------------------------------------------- palisade ---
gate_ang = [G_SOUTH, G_NORTH, G_MILL]
n_st = 200
for i in range(n_st):
    a = i / n_st * 360
    if any(abs(((a - g + 180) % 360) - 180) < (5 if g != G_MILL else 3.5) for g in gate_ang):
        continue
    x, y = P(a, PAL_R)
    hh = 1.6 + rnd.random() * 0.35
    cyl(0.12, hh, (x, y, hh / 2), M['timber'], 6)
    cyl(0.12, 0.3, (x, y, hh + 0.15), M['timber'], 6, r2=0.0)
# bone-white stone gatehouses (south + north), a timber gate for the mill side
for g in (G_SOUTH, G_NORTH):
    for side in (-1, 1):
        x, y = P(g + side * 5.4, PAL_R)
        box(1.0, 1.0, 2.8, (x, y, 1.4), M['bone'])
        for cx in (-0.33, 0.33):
            for cy in (-0.33, 0.33): box(0.2, 0.2, 0.22, (x + cx, y + cy, 2.9), M['bone'])
    x, y = P(g, PAL_R)
    box(2.4, 0.8, 0.5, (x, y, 2.45), M['bone'], rot=(0, 0, math.radians(g + 90)))
x, y = P(G_MILL, PAL_R)
for side in (-1, 1):
    px, py = P(G_MILL + side * 3.6, PAL_R); box(0.3, 0.3, 2.2, (px, py, 1.1), M['timber'])
box(1.6, 0.25, 0.25, (x, y, 2.1), M['timber'], rot=(0, 0, math.radians(G_MILL + 90)))
POINTS['labels']['greymark_walls'] = (*P(G_SOUTH, PAL_R), 3.6)

# ------------------------------------------------------------- the square ---
cyl(0.62, 0.55, (0, 0, 0.3), M['stone'], 14, name='well')
cyl(0.5, 0.05, (0, 0, 0.52), M['redwater'], 14, name='water')
POINTS['water'] += [(0.3 * math.cos(a), 0.3 * math.sin(a), 0.56) for a in (0, 1.6, 3.2, 4.7)]
for dx in (-0.55, 0.55): box(0.08, 0.08, 1.3, (dx, 0, 0.9), M['timber'])
box(1.3, 0.08, 0.08, (0, 0, 1.5), M['timber'])
gable_roof(1.3, 0.8, 0.35, 0.1, (0, 0, 1.55), M['thatch_dark'], name='well_roof')
box(0.9, 0.45, 0.06, (1.1, -0.9, 0.5), M['wood']); box(0.06, 0.4, 0.47, (0.75, -0.9, 0.24), M['wood']); box(0.06, 0.4, 0.47, (1.45, -0.9, 0.24), M['wood'])
box(0.3, 0.22, 0.04, (1.0, -0.9, 0.55), M['paper']); cyl(0.05, 0.14, (1.3, -0.85, 0.6), M['gold'], 8, r2=0.08)
figure(1.15, -1.35, M['robe'], hood=True, s=1.1)                       # Aldren
figure(0.7, 0.4, M['robe'], hood=True)                                 # his man with the cup
for i, c in enumerate(['cloth_b', 'cloth_w', 'cloth_r', 'cloth_b', 'cloth_w', 'cloth_b', 'cloth_r']):
    figure(1.7 + i * 0.42, -0.6 - i * 0.28, M[c], s=0.95)               # the line of the faithful
POINTS['labels'].update({'town_well': (0, 0, 2.1), 'aldren': (1.15, -1.35, 1.2)})
for (lx, ly) in [(-2.6, 2.2), (2.8, -2.4), (2.6, 2.4), (-2.9, -2.0)]: lantern_post(lx, ly)
for (bx, by) in [(-2.2, -1.0), (-2.2, -0.6), (-1.9, -0.8)]: barrel(bx, by)
crate(2.9, 0.9); crate(3.1, 1.2, 0.5)

# -------------------------------------------------------- story buildings ---
placed = []  # (x, y, radius) footprints to keep plots apart


def house_at(x, y, face_to, w, d, h, storeys, roof, plaster='plaster', name='house', lit=0.5, seed=0, chimney=True):
    nx, ny = face_to[0] - x, face_to[1] - y
    rot = math.atan2(nx, -ny)  # local -y (door side) faces the street
    timber_house(x, y, w, d, h, rot=rot, roof=roof, storeys=storeys, plaster=plaster, chimney=chimney, lit=lit, seed=seed, name=name)
    placed.append((x, y, max(w, d) * 0.62))


# the Broken Compass: west side of the square, big two-storey, sign out front
bc = (-5.4, 0.6)
house_at(*bc, (0, 0), 3.2, 2.2, 2.8, 2, 'thatch', name='broken_compass', lit=0.95, seed=11)
box(0.06, 0.06, 0.9, (-3.9, -0.6, 1.9), M['iron']); box(0.6, 0.06, 0.4, (-3.9, -0.6, 1.4), M['wood'])
figure(-3.7, 0.3, M['cloak'], hood=True, s=1.05)                      # Kethric at the door
POINTS['labels'].update({'broken_compass': (*bc, 4.6), 'kethric': (-3.7, 0.3, 1.3)})

# Harren's place: back-left (north-west) of the square, on the old foundations
hp = (-3.4, 5.6)
house_at(*hp, (0, 0), 2.6, 2.0, 2.4, 2, 'thatch_dark', plaster='plaster2', name='harrens_place', seed=12)
box(0.7, 0.5, 0.06, (-2.6, 4.5, 0.06), M['wood'])                       # cellar hatch
POINTS['labels']['harrens_place'] = (*hp, 4.2)
# ancient ruin fragments: older than the walls, mossy, carved
for i, (rx, ry, hh) in enumerate([(-6.2, 6.4, 1.8), (-6.6, 5.2, 1.1), (-5.6, 7.6, 2.4), (-4.4, 8.0, 0.8)]):
    box(0.6, 0.6, hh, (rx, ry, hh / 2), M['bone']); box(0.62, 0.62, 0.14, (rx, ry, hh), M['moss'])
box(2.0, 0.6, 0.5, (-5.9, 7.0, 2.45), M['bone'], rot=(0, 0, math.radians(70)))  # broken lintel of the old arch
POINTS['labels']['ancient_ruin'] = (-6.0, 6.6, 3.2)

# the blacksmith by the south gate: open forge with fire
bs = (3.6, -6.2)
house_at(*bs, (0, 0), 2.2, 1.8, 1.7, 1, 'slate', name='greymark_blacksmith', seed=13, chimney=True)
box(0.4, 0.25, 0.35, (2.4, -5.0, 0.18), M['iron'])                      # anvil
cyl(0.35, 0.3, (4.6, -4.9, 0.15), M['stone'], 8); cyl(0.14, 0.25, (4.6, -4.9, 0.4), M['fire'], 6, r2=0.0)
POINTS['fires'].append((4.6, -4.9, 0.45)); POINTS['labels']['greymark_blacksmith'] = (*bs, 3.2)
Lf = bpy.data.lights.new('forge', 'POINT'); Lf.energy = 60; Lf.color = (1, 0.5, 0.2)
of = bpy.data.objects.new('forge', Lf); bpy.context.collection.objects.link(of); of.location = (4.6, -4.9, 0.9)

# the house where the husk is found: east side
hh_ = (5.6, 2.8)
house_at(*hh_, (0, 0), 2.0, 1.7, 2.2, 2, 'thatch', name='husk_house', seed=14, lit=0.0)
POINTS['labels']['husk_house'] = (*hh_, 3.8)

# ------------------------------------------------------------ town houses ---
def free(x, y, r):
    if math.hypot(x, y) < SQ_R + r + 0.2 or math.hypot(x, y) > PAL_R - 0.6 - r:
        return False
    if any(seg_dist((x, y), a, b) < 0.8 + r * 0.55 for a, b in streets):
        return False
    return all(math.hypot(x - px, y - py) > (r + pr) * 0.82 for px, py, pr in placed)


rh = random.Random(42)
for ring_r in (5.0, 6.7, 8.4, 10.1, 11.8, 13.4):
    n = int(ring_r * 2 * math.pi / 2.0)
    for i in range(n):
        a = i / n * 360 + rh.random() * 6
        x, y = P(a, ring_r)
        back = math.sin(math.radians(a - 135 + 90))   # +1 at the back (north-west), -1 at the front
        back = math.cos(math.radians(a - 135))
        storeys = 2 if back > -0.2 else 1                # keep the front low so the square stays visible
        if back > 0.6 and rh.random() < 0.5: storeys = 3
        w, d = 1.7 + rh.random() * 0.7, 1.3 + rh.random() * 0.4
        if not free(x, y, max(w, d) * 0.62):
            continue
        roof = rh.choice(['thatch', 'thatch', 'thatch_dark', 'slate'])
        house_at(x, y, (0, 0) if ring_r < 12 else P(a, PAL_R + 3), w, d,
                 0.9 * storeys + rh.random() * 0.3, storeys, roof, plaster=rh.choice(['plaster', 'plaster2']),
                 name='house', seed=100 + i + int(ring_r * 10), lit=0.45)
# yard clutter: barrels, crates, carts in front of houses
for i in range(60):
    a = rh.random() * 360; r_ = 4.2 + rh.random() * 10
    x, y = P(a, r_)
    if all(seg_dist((x, y), s, e) > 0.9 for s, e in streets) and all(math.hypot(x - px, y - py) > pr + 0.3 for px, py, pr in placed):
        (barrel if rh.random() < 0.5 else crate)(x, y)
# market stalls with striped awnings along the mill street
M['awning'] = mat('awning', ['#7a2e24', '#e9dfc4'], 'wave', 4, 0.0)
for i, t in enumerate((0.42, 0.55, 0.68)):
    sx, sy = gM[0] * t, gM[1] * t - 1.4
    box(1.2, 0.7, 0.5, (sx, sy, 0.25), M['wood']); gable_roof(1.4, 0.9, 0.35, 0.05, (sx, sy, 1.0), M['awning'], name='awning')
    for dx in (-0.6, 0.6): box(0.05, 0.05, 1.0, (sx + dx, sy - 0.35, 0.5), M['timber'])
    for k in range(3): blob(0.1, (sx - 0.3 + k * 0.3, sy, 0.55), M['leaf_o'] if k % 2 else M['linen'], seed=4000 + i * 3 + k, rough=0.3, subdiv=1)
    placed.append((sx, sy, 0.9))
# a handcart on the main street, townsfolk about
box(1.0, 0.6, 0.25, (2.0, -3.6, 0.45), M['wood'], rot=(0, 0, math.radians(45)))
cyl(0.32, 0.08, (2.3, -4.1, 0.32), M['wood'], 10, rot=(math.radians(90), 0, math.radians(45)))
for i, (fx, fy, c) in enumerate([(-1.0, -4.8, 'cloth_w'), (5.6, -1.0, 'cloth_b'), (-2.0, 3.6, 'cloth_r'), (0.8, 6.0, 'cloth_b'), (-6.0, -4.0, 'cloth_w')]):
    figure(fx, fy, M[c], s=0.95)
for (lx, ly) in [P(-45, 7.5), P(135, 7.5), P(10, 7.5), P(-45, 12.0), P(10, 12.0), P(215, 9.0)]: lantern_post(lx, ly)

# ------------------------------------------------ Vex's mill (outside, east) ---
mill = (21.8, 5.6)
timber_house(*mill, 4.2, 2.6, 2.2, rot=math.radians(-80), roof='thatch_dark', storeys=1, plaster='plaster2', chimney=False, seed=21, name='vex_mill', lit=0.7)
placed.append((*mill, 2.6))
cyl(1.2, 0.3, (19.6, 4.6, 1.3), M['wood'], 18, rot=(math.radians(90), 0, math.radians(10)), name='treadwheel')
cyl(1.0, 0.32, (19.6, 4.6, 1.3), M['timber'], 18, rot=(math.radians(90), 0, math.radians(10)))
for i in range(4):  # dye vats with the blue that won't set
    vx, vy = 23.6 + (i % 2) * 1.1, 2.4 - (i // 2) * 1.1
    cyl(0.45, 0.6, (vx, vy, 0.3), M['wood'], 10); cyl(0.4, 0.04, (vx, vy, 0.6), M['dye'], 10)
for j in range(2):  # linen drying racks
    for i in range(4): box(0.05, 0.05, 1.1, (19.8 + i * 0.7, 0.6 - j * 1.4, 0.55), M['timber'])
    box(2.2, 0.03, 0.03, (20.85, 0.6 - j * 1.4, 1.08), M['iron'])
    for i in range(6): box(0.28, 0.02, 0.5, (20.0 + i * 0.36, 0.6 - j * 1.4, 0.78), M['linen'] if (i + j) % 3 else M['cloth_b'])
figure(18.6, 2.6, M['cloth_r'], s=1.0)  # Vex at the mill gate, counting
for i in range(4): figure(17.8 + i * 0.4, 1.8 - i * 0.3, M['cloth_b'], s=0.92)  # blue coats, white jerkins
POINTS['labels'].update({'vex_mill': (*mill, 3.4), 'vex': (18.6, 2.6, 1.3)})
for (cx_, cy_) in [(25.0, 8.2), (23.2, 10.4)]:  # mill hands' cottages
    timber_house(cx_, cy_, 1.8, 1.5, 1.2, rot=math.radians(-80), roof='thatch', storeys=1, seed=int(cx_ * 7), name='cottage', lit=0.6)
    placed.append((cx_, cy_, 1.3))

# flax fields: front-right, low, rows of blue-green with fences
fields = [((18.5, -8.5), 7.0, 4.5, 15), ((24.0, -3.5), 4.0, 5.5, 15), ((13.0, -18.5), 6.5, 4.5, -30), ((20.0, -15.5), 5.0, 4.5, -30)]
for i, ((fx, fy), fw, fd, fr) in enumerate(fields):
    if not in_hex(fx, fy, R - 2.5): continue
    box(fw, fd, 0.12, (fx, fy, 0.06), M['field'], rot=(0, 0, math.radians(fr)), name='field')
    for k in range(int(fw * fd * 4)):
        lx, ly = (rnd.random() - 0.5) * fw * 0.92, (rnd.random() - 0.5) * fd * 0.92
        c, s_ = math.cos(math.radians(fr)), math.sin(math.radians(fr))
        cyl(0.07, 0.45 + rnd.random() * 0.2, (fx + lx * c - ly * s_, fy + lx * s_ + ly * c, 0.25), M['flax'], 4, r2=0.0)
POINTS['labels']['flax_farms'] = (18.5, -8.5, 1.0)
# a raided flax farm out front-left: burnt-out barn, broken fence, scattered sheaves
farm = (-9.5, -20.5)
box(5.5, 3.5, 0.12, (farm[0] - 1.5, farm[1] + 3.5, 0.06), M['field'], rot=(0, 0, math.radians(20)), name='field')
timber_house(farm[0], farm[1], 2.4, 1.8, 1.3, rot=math.radians(20), roof='thatch_dark', storeys=1, seed=77, name='farmhouse', lit=0.0)
M['burnt'] = mat('burnt', ['#0e0a0a', '#1e1614', '#2e2420'], 'noise', 10, 0.6)
for i in range(6):  # charred barn frame
    box(0.14, 0.14, 1.2 + rnd.random(), (farm[0] + 3.0 + (i % 3) * 0.9, farm[1] - 1.0 + (i // 3) * 1.2, 0.7), M['burnt'], rot=(rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0))
box(2.6, 1.6, 0.06, (farm[0] + 3.9, farm[1] - 0.4, 0.04), M['burnt'])
for i in range(12):  # broken fence
    if i in (4, 5, 9): continue
    box(0.08, 0.08, 0.6, (farm[0] - 4 + i * 0.6, farm[1] - 2.2, 0.3), M['fence'], rot=(0, rnd.uniform(-0.2, 0.2) if i % 4 == 0 else 0, 0))
box(6.8, 0.05, 0.05, (farm[0] - 0.7, farm[1] - 2.2, 0.48), M['fence'])
POINTS['labels']['raided_farm'] = (farm[0] + 1.5, farm[1], 2.4)

# ------------------------------------------------------------ the forest ---
# dense autumn + pine forest at the BACK (north / west / north-east) outside the palisade
rf = random.Random(7)
tries = 0
trees = []
while tries < 6000 and len(trees) < 230:
    tries += 1
    x, y = (rf.random() - 0.5) * 2 * R, (rf.random() - 0.5) * 2 * R
    if not in_hex(x, y, R - 1.2) or math.hypot(x, y) < PAL_R + 1.6: continue
    back = (-x + y) / math.sqrt(2)                       # distance toward the back of the view
    if back < 4.0 and not (x > 16 and y > 12): continue  # keep front and the fields open
    if any(math.hypot(x - px, y - py) < pr + 0.6 for px, py, pr in placed): continue
    if any(seg_dist((x, y), a, b) < 1.4 for a, b in roads_out): continue
    if any(math.hypot(x - tx, y - ty) < 1.5 for tx, ty in trees): continue
    trees.append((x, y))
for i, (x, y) in enumerate(trees):
    if rf.random() < 0.35: pine(x, y, 1.1 + rf.random() * 0.5)
    else: tree(x, y, 1.0 + rf.random() * 0.4, rf.choice('oorrg'), seed=1000 + i)
# a few trees inside town and by the front road
for i, (x, y) in enumerate([(-2.8, -6.6), (6.8, 6.0), (-8.0, 2.6), (14.0, -22.0), (8.0, -24.0), (-16.0, -14.0), (-19.0, -10.0), (2.0, -21.0)]):
    tree(x, y, 0.9, 'or'[i % 2], seed=2000 + i)
# rocks and bushes on the open front ground
for i in range(40):
    x, y = (rnd.random() - 0.5) * 2 * R, (rnd.random() - 0.5) * 2 * R
    if in_hex(x, y, R - 1.5) and math.hypot(x, y) > PAL_R + 1.2:
        blob(0.15 + rnd.random() * 0.25, (x, y, 0.08), M['stone'] if i % 3 else M['moss'], seed=3000 + i, rough=0.6, subdiv=1)

# a traveller's campfire by the south road
POINTS['fires'].append((6.5, -22.5, 0.2)); cyl(0.3, 0.08, (6.5, -22.5, 0.05), M['stone'], 8); cyl(0.13, 0.32, (6.5, -22.5, 0.22), M['fire'], 6, r2=0.0)
Lc = bpy.data.lights.new('camp', 'POINT'); Lc.energy = 40; Lc.color = (1, 0.55, 0.25)
oc = bpy.data.objects.new('camp', Lc); bpy.context.collection.objects.link(oc); oc.location = (6.5, -22.5, 0.7)

RES = (SIZE, int(SIZE * 0.66))
finish(66.0, target=(0, 0, 0), res=RES, shift_y=-0.02)
