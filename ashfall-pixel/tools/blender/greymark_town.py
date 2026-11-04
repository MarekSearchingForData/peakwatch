"""Greymark at full size (~450 buildings) as one isometric diorama, built from cities/greymark.plan.json.

    python3 tools/plan_town.py greymark
    <bpy-venv>/bin/python tools/blender/greymark_town.py out.png [--size 6000] [--samples 16] [--night] [--toon]

The street plan comes from the Medieval Fantasy City Generator (same layout as the city-plan
view). Every plot becomes a timber-framed house; the dark-timber palisade follows the wall
line with timber watchtowers; the gates are bone-white stone. One camera from the south-east:
the main gate road runs toward the viewer, the forest closes in at the back.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import *  # noqa: F401,F403

PLAN = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'cities', 'greymark.plan.json')))
R = 84.0                      # hexagonal slab radius
CY = 12.0                     # slab centre is pushed back (north) a little: the old north road runs long
M['dye'] = mat('dye', ['#1e2c5a', '#2a3f7a', '#3a56a0'], 'noise', 6, 0.05, 0.2)
M['field'] = mat('field', ['#2e2016', '#4a3424', '#3e5a30', '#4f7040'], 'wave', 1.5, 0.6)
M['field2'] = mat('field2', ['#2e2016', '#3a5a3a', '#4f7a52', '#6c8fb0'], 'wave', 1.5, 0.6)
M['field3'] = mat('field3', ['#3a2a1a', '#7a6a3a', '#9a8a4a', '#b8a060'], 'wave', 1.5, 0.6)
M['fence'] = mat('fence', ['#3e2a1c', '#5a3e28'], 'wave', 12, 0.2)
M['road'] = mat('road', ['#5a4030', '#7a5a3e', '#94704c'], 'noise', 3, 0.4)
M['hedge'] = mat('hedge', ['#14261a', '#1f3a26', '#2d5432'], 'noise', 8, 0.8)
M['burnt'] = mat('burnt', ['#0e0a0a', '#1e1614', '#2e2420'], 'noise', 10, 0.6)


def in_hex(x, y, rad):
    y -= CY
    for k in range(6):
        a = math.radians(60 * k)
        if x * math.cos(a) + y * math.sin(a) > rad * math.cos(math.radians(30)):
            return False
    return True


def flat_poly(pts, z, material, name='poly'):
    bm = bmesh.new()
    vs = [bm.verts.new((p[0], p[1], z)) for p in pts]
    try:
        f = bm.faces.new(vs); bmesh.ops.triangulate(bm, faces=[f])
    except ValueError:
        bm.free(); return None
    return obj_from(name, bm, material)


def strip(pts, width, z, material, name='road'):
    for a, b in zip(pts, pts[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 0.01: continue
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        box(L + width * 0.5, width, 0.05, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z), material, rot=(0, 0, ang), name=name)


# occupancy grid so trees and props never land on houses / roads
OCC = set()
def occupy(x, y, r):
    for gx in range(int((x - r) // 2), int((x + r) // 2) + 1):
        for gy in range(int((y - r) // 2), int((y + r) // 2) + 1):
            OCC.add((gx, gy))
def occupied(x, y):
    return (int(x // 2), int(y // 2)) in OCC


# ------------------------------------------------------------------- ground ---
cyl(R, 3.0, (0, CY, -1.5), M['soil'], 6, rot=(0, 0, math.radians(30)), name='slab')
cyl(R - 0.05, 0.12, (0, CY, -0.04), M['grass'], 6, rot=(0, 0, math.radians(30)), name='turf')

wall = PLAN['walls'][0]
flat_poly(wall, 0.02, M['dirt'], 'town_ground')                      # packed earth inside the palisade
for sq in PLAN['squares']:
    flat_poly(sq, 0.05, M['cobble'], 'square')
for road in PLAN['roads']:
    pts = [p for p in road if in_hex(p[0], p[1], R - 1)]
    strip(pts, 2.6, 0.06, M['road'])
    for p in pts: occupy(p[0], p[1], 1.6)
for i, f in enumerate(PLAN['fields']):
    if all(in_hex(p[0], p[1], R - 1.5) for p in f):
        flat_poly(f, 0.06, [M['field'], M['field2'], M['field2'], M['field3']][i % 4], 'field')
        xs = [p[0] for p in f]; ys = [p[1] for p in f]
        for gx in range(int(min(xs)) // 2, int(max(xs)) // 2 + 1):
            for gy in range(int(min(ys)) // 2, int(max(ys)) // 2 + 1): OCC.add((gx, gy))
POINTS['labels']['flax_farms'] = (*min((c for c in ([sum(p[0] for p in f) / len(f), sum(p[1] for p in f) / len(f)] for f in PLAN['fields'])),
                                     key=lambda c: math.hypot(c[0] - 40, c[1] + 40)), 1.0)
# patchwork farmland on the open front (south-east): flax (blue-green), wheat, fallow, hedgerows
rfm = random.Random(5)
cells = 0
for gx in range(-80, 81, 9):
    for gy in range(-80, 81, 7):
        cx_, cy_ = gx + rfm.uniform(-1, 1), gy + rfm.uniform(-1, 1)
        front = (cx_ - (cy_ - CY)) / math.sqrt(2)   # + toward the viewer
        if front < 18 or not in_hex(cx_, cy_, R - 6) or any(occupied(cx_ + dx, cy_ + dy) for dx in (-4, 0, 4) for dy in (-3, 0, 3)):
            continue
        if rfm.random() < 0.15: continue
        fw, fd = 8.0 + rfm.uniform(-0.6, 0.4), 6.0 + rfm.uniform(-0.5, 0.3)
        matf = rfm.choice([M['field2'], M['field2'], M['field3'], M['field']])
        box(fw, fd, 0.1, (cx_, cy_, 0.06), matf, name='farm')
        for k in range(int(fw * 1.2)):  # hedgerow along one edge
            blob(0.45, (cx_ - fw / 2 + k * 0.85, cy_ + fd / 2 + 0.2, 0.25), M['hedge'], seed=cells * 50 + k, rough=0.4, subdiv=1, squash=0.8)
        occupy(cx_, cy_, 5); cells += 1
print('farm cells', cells)
xs = [p[0] for p in wall]; ys = [p[1] for p in wall]
for gx in range(int(min(xs)) // 2, int(max(xs)) // 2 + 1):     # nothing wild inside the walls
    for gy in range(int(min(ys)) // 2, int(max(ys)) // 2 + 1):
        OCC.add((gx, gy))

# ---------------------------------------------------------------- palisade ---
gates = PLAN['gates']
def near_gate(x, y, r=3.0):
    return any(math.hypot(x - g[0], y - g[1]) < r for g in gates)
ring = wall + [wall[0]]
for a, b in zip(ring, ring[1:]):
    L = math.hypot(b[0] - a[0], b[1] - a[1]); n = int(L / 0.45)
    for k in range(n):
        x = a[0] + (b[0] - a[0]) * k / n; y = a[1] + (b[1] - a[1]) * k / n
        if near_gate(x, y): continue
        hh = 2.0 + rnd.random() * 0.4
        cyl(0.17, hh, (x, y, hh / 2), M['timber'], 6)
        cyl(0.17, 0.4, (x, y, hh + 0.2), M['timber'], 6, r2=0.0)
for i, (x, y) in enumerate(wall):  # timber watchtowers at the corners
    if near_gate(x, y, 4): continue
    for dx in (-0.7, 0.7):
        for dy in (-0.7, 0.7): box(0.18, 0.18, 4.2, (x + dx, y + dy, 2.1), M['timber'])
    box(1.9, 1.9, 0.18, (x, y, 3.6), M['wood']); gable_roof(2.0, 2.0, 1.0, 0.2, (x, y, 4.2), M['thatch_dark'], name='tower_roof')
for g in gates:  # bone-white stone gatehouses
    ang = math.atan2(g[1], g[0]) + math.pi / 2  # tangent to the wall
    c, s = math.cos(ang), math.sin(ang)
    for side in (-1, 1):
        x, y = g[0] + c * side * 2.3, g[1] + s * side * 2.3
        box(1.6, 1.6, 4.0, (x, y, 2.0), M['bone'], rot=(0, 0, ang))
        for cx in (-0.55, 0.55):
            for cy in (-0.55, 0.55): box(0.3, 0.3, 0.35, (x + cx * c - cy * s, y + cx * s + cy * c, 4.15), M['bone'], rot=(0, 0, ang))
    box(4.6, 1.2, 0.8, (g[0], g[1], 3.6), M['bone'], rot=(0, 0, ang))
POINTS['labels']['greymark_walls'] = (*max(gates, key=lambda g: g[0] - g[1]), 5.5)

# ------------------------------------------------------- the hill + church ---
def wall_reach(ang):
    """distance from the centre to the wall polygon along a direction"""
    best = 0
    for a, b in zip(wall, wall[1:] + wall[:1]):
        for t in [k / 20 for k in range(21)]:
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            if abs(math.atan2(y, x) - ang) < 0.08 or abs(abs(math.atan2(y, x) - ang) - math.tau) < 0.08:
                best = max(best, math.hypot(x, y))
    return best or 40
HA = math.radians(128)
HR = wall_reach(HA) * 0.52
HX, HY = math.cos(HA) * HR, math.sin(HA) * HR
HILL_R, HILL_H, TOP_R = 13.0, 7.5, 5.8
# ------------------------------------------------------------------ houses ---
story = {v: k for k, v in PLAN['story'].items()}
rh = random.Random(42)
for h in PLAN['houses']:
    x, y = h['x'], h['y']
    if not in_hex(x, y, R - 3): continue
    sid = story.get(h['id'])
    if not sid and math.hypot(x - HX, y - HY) < HILL_R + 1.0: continue  # the hill is kept clear
    inside = h['inside']
    if inside:
        storeys = 3 if h['area'] > 16 and rh.random() < 0.6 else 2 if h['area'] > 6 or rh.random() < 0.5 else 1
    else:
        storeys = 2 if h['area'] > 12 and rh.random() < 0.4 else 1
    L, D = max(1.4, h['l'] * 0.92), max(1.2, h['d'] * 0.9)
    roof = rh.choice(['thatch', 'thatch', 'thatch', 'thatch_dark', 'thatch_dark', 'slate'])
    plaster = rh.choice(['plaster', 'plaster', 'plaster2'])
    lit, chimney = 0.45, rh.random() < 0.6
    if sid == 'broken_compass': storeys, roof, lit = 2, 'thatch', 1.0
    if sid == 'harrens_place': roof, plaster = 'thatch_dark', 'plaster2'
    if sid == 'husk_house': lit = 0.0
    if sid == 'vex_mill': storeys, roof, chimney = 1, 'thatch_dark', False
    timber_house(x, y, L, D, 0.95 * storeys + rh.random() * 0.2, rot=h['a'], roof=roof, storeys=storeys, plaster=plaster,
                 chimney=chimney, lit=lit, seed=h['id'], name=sid or 'house', lite=not (inside or sid))
    occupy(x, y, max(L, D) * 0.6)
    if sid:
        POINTS['labels'][sid] = (x, y, 0.95 * storeys + D * 0.75 + 1.0)
        c, s = math.cos(h['a']), math.sin(h['a'])
        front = (x + s * (D / 2 + 1.0), y - c * (D / 2 + 1.0))       # in front of the door (local -y)
        if sid == 'broken_compass':
            box(0.08, 0.08, 1.0, (front[0], front[1], 2.0), M['iron']); box(0.7, 0.08, 0.45, (front[0], front[1], 1.45), M['wood'], rot=(0, 0, h['a']))
            figure(front[0] + 0.6, front[1], M['cloak'], hood=True, s=1.05)
            POINTS['labels']['kethric'] = (front[0] + 0.6, front[1], 1.4)
        if sid == 'harrens_place':
            box(0.8, 0.6, 0.06, (front[0], front[1], 0.07), M['wood'])  # the cellar hatch
            for k, (dx, dy, hh) in enumerate([(-2.5, 1.5, 2.0), (-3.2, 0.2, 1.2), (-2.0, 2.8, 2.6)]):  # older stones
                px, py = x + dx * c - dy * s, y + dx * s + dy * c
                box(0.7, 0.7, hh, (px, py, hh / 2), M['bone']); box(0.72, 0.72, 0.15, (px, py, hh), M['moss'])
            POINTS['labels']['ancient_ruin'] = (x - 2.5 * c, y - 2.5 * s, 3.4)
        if sid == 'greymark_blacksmith':
            box(0.45, 0.28, 0.4, (front[0], front[1], 0.2), M['iron'])
            cyl(0.4, 0.35, (front[0] + 1.0, front[1], 0.18), M['stone'], 8); cyl(0.16, 0.3, (front[0] + 1.0, front[1], 0.45), M['fire'], 6, r2=0.0)
            POINTS['fires'].append((front[0] + 1.0, front[1], 0.5))
            Lf = bpy.data.lights.new('forge', 'POINT'); Lf.energy = 80; Lf.color = (1, 0.5, 0.2)
            of = bpy.data.objects.new('forge', Lf); bpy.context.collection.objects.link(of); of.location = (front[0] + 1.0, front[1], 1.0)
        if sid == 'vex_mill':
            cyl(1.3, 0.3, (front[0], front[1], 1.4), M['wood'], 18, rot=(math.radians(90), 0, h['a']), name='treadwheel')
            for k in range(4):
                vx, vy = front[0] + 2.0 + (k % 2) * 1.1, front[1] - 1.0 - (k // 2) * 1.1
                cyl(0.45, 0.6, (vx, vy, 0.3), M['wood'], 10); cyl(0.4, 0.04, (vx, vy, 0.6), M['dye'], 10)
            for k in range(5): box(0.28, 0.02, 0.5, (front[0] - 2.0 + k * 0.36, front[1] - 1.5, 0.78), M['linen'] if k % 3 else M['cloth_b'])
            box(2.0, 0.03, 0.03, (front[0] - 1.3, front[1] - 1.5, 1.08), M['iron'])
            figure(front[0] - 0.8, front[1] + 0.2, M['cloth_r'], s=1.0)
            for k in range(4): figure(front[0] - 1.6 - k * 0.4, front[1] + 0.6, M['cloth_b'], s=0.92)
            POINTS['labels']['vex'] = (front[0] - 0.8, front[1] + 0.2, 1.4)

# the hill: grassy mound with a stone retaining wall at the top and a path winding up the front
M['water'] = mat('water', ['#1e3a5a', '#2a5a7a', '#4a8aa8'], 'noise', 5, 0.05, 0.1)
hill = cyl(HILL_R, HILL_H, (HX, HY, HILL_H / 2), M['grass'], 28, r2=TOP_R + 0.6, name='hill')
sub = hill.modifiers.new('sub', 'SUBSURF'); sub.levels = sub.render_levels = 2
cyl(TOP_R + 0.6, 0.25, (HX, HY, HILL_H + 0.05), M['cobble'], 28, name='hilltop')
for k in range(40):  # retaining wall stones round the top
    a = k / 40 * math.tau
    box(0.9, 0.5, 0.7, (HX + math.cos(a) * (TOP_R + 0.4), HY + math.sin(a) * (TOP_R + 0.4), HILL_H - 0.1), M['stone'], rot=(0, 0, a + math.pi / 2))
for k in range(22):  # switchback path toward the camera side
    t = k / 21
    a = math.radians(-45) + math.sin(t * math.pi * 3) * 0.6
    r_ = HILL_R - t * (HILL_R - TOP_R)
    box(1.6, 1.2, 0.2, (HX + math.cos(a) * r_, HY + math.sin(a) * r_, t * HILL_H + 0.1), M['road'], rot=(0, 0, a))
occupy(HX, HY, HILL_R)
# the church: bone-white stone nave, buttresses, slate roof, west bell tower with spire, gold cross
CZ = HILL_H + 0.18
cax = math.radians(128 + 90)  # nave runs across the view so its long side faces the camera
c, s_ = math.cos(cax), math.sin(cax)
def rel(dx, dy):
    return HX + dx * c - dy * s_, HY + dx * s_ + dy * c
nx, ny = rel(0.5, 0.0)
box(7.5, 3.8, 3.8, (nx, ny, CZ + 1.9), M['bone'], rot=(0, 0, cax), name='nave')
gable_roof(7.5, 3.8, 2.4, 0.3, (nx, ny, CZ + 3.8), M['slate'], rot_z=cax, name='church_roof')
for k in range(5):
    for side in (-1, 1):
        bx_, by_ = rel(-2.8 + k * 1.6, side * 2.1)
        box(0.45, 0.5, 2.8, (bx_, by_, CZ + 1.4), M['bone'], rot=(0, 0, cax))           # buttresses
        if k < 4:
            wx_, wy_ = rel(-2.0 + k * 1.6, side * 1.93)
            box(0.35, 0.06, 1.3, (wx_, wy_, CZ + 2.1), M['glass'], rot=(0, 0, cax))   # lancet windows
tx_, ty_ = rel(-4.6, 0)
box(2.6, 2.6, 9.0, (tx_, ty_, CZ + 4.5), M['bone'], rot=(0, 0, cax), name='bell_tower')
for side in (-1, 1):
    for side2 in (-1, 1):
        px_, py_ = rel(-4.6 + side * 1.0, side2 * 1.0); box(0.35, 0.35, 0.5, (px_, py_, CZ + 9.2), M['bone'])
lx_, ly_ = rel(-4.6, -1.32); box(0.6, 0.06, 1.1, (lx_, ly_, CZ + 7.4), M['iron'], rot=(0, 0, cax))   # belfry opening
cyl(1.75, 4.2, (tx_, ty_, CZ + 11.2), M['slate'], 8, r2=0.0, rot=(0, 0, cax + math.pi / 8), name='spire')
box(0.1, 0.1, 1.0, (tx_, ty_, CZ + 13.7), M['gold']); box(0.5, 0.1, 0.1, (tx_, ty_, CZ + 13.8), M['gold'], rot=(0, 0, cax))
dx_, dy_ = rel(4.3, 0); box(0.08, 1.2, 1.8, (dx_, dy_, CZ + 0.9), M['wood'], rot=(0, 0, cax))   # east door
# churchyard: headstones behind, the fountain in front (toward the camera)
for k in range(14):
    gx_, gy_ = rel(-2.5 + (k % 7) * 1.0, 3.2 + (k // 7) * 0.9)
    box(0.35, 0.12, 0.55, (gx_, gy_, CZ + 0.27), M['stone'], rot=(rnd.uniform(-0.15, 0.15), 0, cax))
fx_, fy_ = rel(0.8, -3.6)
cyl(1.35, 0.55, (fx_, fy_, CZ + 0.27), M['bone'], 8, name='fountain')
cyl(1.15, 0.06, (fx_, fy_, CZ + 0.52), M['water'], 8, name='fountain_water')
cyl(0.18, 1.3, (fx_, fy_, CZ + 0.9), M['bone'], 8); cyl(0.55, 0.18, (fx_, fy_, CZ + 1.5), M['bone'], 10, r2=0.35)
cyl(0.45, 0.05, (fx_, fy_, CZ + 1.6), M['water'], 10)
POINTS.setdefault('fountain', [])
POINTS['fountain'] += [(fx_ + 0.7 * math.cos(a), fy_ + 0.7 * math.sin(a), CZ + 0.56) for a in (0.3, 1.9, 3.5, 5.1)] + [(fx_, fy_, CZ + 1.65)]
POINTS['labels'].update({'greymark_church': (tx_, ty_, CZ + 15.0), 'church_fountain': (fx_, fy_, CZ + 2.3)})

# ------------------------------------------------------- the well + Aldren ---
wx, wy = PLAN['wells'][0] if PLAN['wells'] else (0, 0)
cyl(0.8, 0.6, (wx, wy, 0.32), M['stone'], 14, name='well')
cyl(0.65, 0.05, (wx, wy, 0.58), M['redwater'], 14, name='water')
POINTS['water'] += [(wx + 0.4 * math.cos(a), wy + 0.4 * math.sin(a), 0.62) for a in (0, 1.6, 3.2, 4.7)]
for dx in (-0.7, 0.7): box(0.1, 0.1, 1.5, (wx + dx, wy, 1.0), M['timber'])
gable_roof(1.6, 1.0, 0.4, 0.1, (wx, wy, 1.7), M['thatch_dark'], name='well_roof')
box(1.0, 0.5, 0.06, (wx + 1.4, wy - 1.0, 0.5), M['wood']); box(0.3, 0.22, 0.04, (wx + 1.3, wy - 1.0, 0.55), M['paper'])
cyl(0.05, 0.14, (wx + 1.6, wy - 0.95, 0.6), M['gold'], 8, r2=0.08)
figure(wx + 1.4, wy - 1.5, M['robe'], hood=True, s=1.1)
for i, cc in enumerate(['cloth_b', 'cloth_w', 'cloth_r', 'cloth_b', 'cloth_w', 'cloth_b', 'cloth_r', 'cloth_w', 'cloth_b']):
    figure(wx + 2.0 + i * 0.45, wy - 0.8 - i * 0.3, M[cc], s=0.95)
POINTS['labels'].update({'town_well': (wx, wy, 2.4), 'aldren': (wx + 1.4, wy - 1.5, 1.3)})
for k in range(6):
    a = k / 6 * math.tau
    lantern_post(wx + math.cos(a) * 5.5, wy + math.sin(a) * 5.5)

# ------------------------------------------------- people, carts, clutter ---
for road in PLAN['roads']:          # townsfolk and carts along the streets
    for a, b in zip(road, road[1:]):
        if rnd.random() < 0.25 and in_hex(a[0], a[1], R - 4):
            t = rnd.random(); x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            figure(x + rnd.uniform(-0.5, 0.5), y + rnd.uniform(-0.5, 0.5), M[rnd.choice(['cloth_b', 'cloth_w', 'cloth_r', 'robe'])], s=0.95)
        if rnd.random() < 0.12 and in_hex(a[0], a[1], R - 4):
            x, y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            (barrel if rnd.random() < 0.5 else crate)(x + 1.2, y + 1.2)

# --------------------------------------------------------------- the forest ---
# dense at the back (north-west), thinning toward the sides; the front stays open farmland
rf = random.Random(7)
trees = 0
TREES = set()
for i in range(90000):
    x, y = rf.uniform(-R, R), CY + rf.uniform(-R, R)
    if not in_hex(x, y, R - 2) or occupied(x, y): continue
    back = (-x + (y - CY)) / math.sqrt(2)  # + toward the back of the view
    p = 0.95 if back > 22 else 0.6 if back > 5 else 0.15 if back > -25 else 0.02
    if rf.random() > p: continue
    cell = (int(x // 2.3), int(y // 2.3))
    if cell in TREES: continue
    TREES.add(cell)
    if rf.random() < 0.35: pine(x, y, 1.7 + rf.random() * 0.8)
    else: tree(x, y, 1.5 + rf.random() * 0.7, rf.choice('oorrg'), seed=10000 + i)
    trees += 1
print('trees', trees)
# rocks on the open ground
for i in range(120):
    x, y = rnd.uniform(-R, R), CY + rnd.uniform(-R, R)
    if in_hex(x, y, R - 2) and not occupied(x, y):
        blob(0.2 + rnd.random() * 0.35, (x, y, 0.1), M['stone'] if i % 3 else M['moss'], seed=3000 + i, rough=0.6, subdiv=1)

aspect = 0.62
RES = (SIZE, int(SIZE * aspect))
finish(190.0, target=(0, CY, 0), res=RES, shift_y=-0.01)
