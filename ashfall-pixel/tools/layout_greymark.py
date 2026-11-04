"""Greymark BLOCKOUT from the author's sketch (data/greymark_sketch.json).

    python3 tools/layout_greymark.py      -> map/cities/greymark.js  (+ data/greymark_layout.json)

The sketch (a top-down drawing, north up) is rotated into the isometric grid so the drawing reads
the same on screen: the main gate faces the camera (front), the church is on the left, the river
runs down the left side. Low detail on purpose: simple shapes in the right places. Named SLOTS get
detailed art one asset at a time (map/assets/<slot>.png, see tools/cutout.py) and replace the blockout.

Sketch elements -> blockout:
  oval wall        -> dark timber palisade with watchtowers; main gate (south) + east gate in bone-white stone
  black strokes    -> winding cobbled streets (3 tiles); outside the wall -> dirt roads
  red              -> the river (8 tiles wide)
  church loop      -> the church compound on a hill (curtain wall, towers, gatehouse), its switchback road climbing
  market square    -> paved square with the red-water well and stalls
  blue circle      -> the mill annex: its own small wall, the mill with a water wheel on the river, dye vats
  everything else  -> houses with yards along the streets, farmland outside, forest behind
(The older straight-grid blockout is kept in tools/layout_greymark_grid.py.)
"""
import json
import math
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = json.load(open(os.path.join(ROOT, 'data', 'greymark_sketch.json')))
S = 0.21            # tiles per sketch pixel
W = H = 250
C = 125             # grid centre
OX, OY = SK['wall_oval']['cx'], SK['wall_oval']['cy']
rnd = random.Random(3)


def to_grid(p):
    """sketch pixel -> grid tile. Screen-right in iso is +x-y, screen-down is +x+y."""
    u, v = (p[0] - OX) * S, (p[1] - OY) * S
    return C + (u + v) / math.sqrt(2), C + (v - u) / math.sqrt(2)


def to_sketch(x, y):
    a, b = (x - C) * math.sqrt(2), (y - C) * math.sqrt(2)
    u, v = (a - b) / 2, (a + b) / 2
    return OX + u / S, OY + v / S


cells = [['g'] * W for _ in range(H)]
hgt = [[1] * W for _ in range(H)]
bid = [[0] * W for _ in range(H)]
buildings, anchors, slots, sprites = [], [], [], []


def inb(x, y): return 0 <= x < W and 0 <= y < H


def setc(x, y, c, only=None):
    if inb(x, y) and (only is None or cells[y][x] in only): cells[y][x] = c


def stroke(pts, width, c, only=None):
    g = [to_grid(p) for p in pts]
    r = width / 2
    for (x0, y0), (x1, y1) in zip(g, g[1:]):
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
        for k in range(n + 1):
            x, y = x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n
            for yy in range(int(y - r) - 1, int(y + r) + 2):
                for xx in range(int(x - r) - 1, int(x + r) + 2):
                    if (xx + 0.5 - x) ** 2 + (yy + 0.5 - y) ** 2 <= r * r:
                        setc(xx, yy, c, only)


def in_oval(x, y, shrink=0.0):
    u, v = to_sketch(x + 0.5, y + 0.5); o = SK['wall_oval']
    return ((u - o['cx']) / (o['rx'] - shrink)) ** 2 + ((v - o['cy']) / (o['ry'] - shrink)) ** 2 < 1


def building(x0, y0, w, d, typ, h, story=None, label=None):
    i = len(buildings) + 1
    for y in range(y0, y0 + d):
        for x in range(x0, x0 + w):
            cells[y][x] = 'b'; bid[y][x] = i
    b = {'id': i, 'type': typ, 'n': w * d, 'tx': x0 + (w - 1) / 2, 'ty': y0 + (d - 1) / 2, 'h': h, 'district': '', 'inside': True}
    if story: b['story'] = story
    buildings.append(b)
    if story or label: slots.append({'id': story or label, 'kind': typ, 'x': x0, 'y': y0, 'w': w, 'd': d})
    return b


def free(x0, y0, x1, y1, ok):
    return all(inb(x, y) and cells[y][x] in ok for y in range(y0, y1) for x in range(x0, x1))


def anchor(story, x, y): anchors.append({'story': story, 'tx': round(x, 1), 'ty': round(y, 1)})


# -------------------------------------------------------------- terrain ---
for y in range(H):
    for x in range(W):
        u, v = to_sketch(x + 0.5, y + 0.5)
        if in_oval(x, y):
            cells[y][x] = 'Y'                                     # inside the walls: yards and gardens
        elif (v < 330 and u > 200) or (u > 1010 and v < 560):
            if rnd.random() < 0.93: cells[y][x] = 'k'             # forest north and east, behind the town
        elif v > 600 and u > 450:
            band = (int(u) // 70 + int(v) // 55) % 3
            cells[y][x] = 'F' if band == 0 else 'f' if band == 1 else 'g'

stroke(SK['river'], 10.5, 'm')            # river banks
stroke(SK['river'], 8.0, '~')             # the river

# the oval wall: palisade + watchtowers
o = SK['wall_oval']
ring = [(o['cx'] + o['rx'] * math.cos(t), o['cy'] + o['ry'] * math.sin(t)) for t in [k / 720 * math.tau for k in range(721)]]
stroke(ring, 1.3, 'w')
for k in range(0, 360, 14):
    t = k / 360 * math.tau
    x, y = to_grid((o['cx'] + o['rx'] * math.cos(t), o['cy'] + o['ry'] * math.sin(t)))
    for yy in range(int(y) - 1, int(y) + 2):
        for xx in range(int(x) - 1, int(x) + 2): setc(xx, yy, 'T')

# streets: cobbles inside the walls; dirt roads out of the gates
for road in SK['roads']:
    stroke(road, 3.0, 'r', only='Ygkmw')
stroke([SK['main_gate'], (SK['main_gate'][0] + 12, 950)], 3.2, 'd', only='gkfFm')
stroke([SK['east_gate'], (1350, 300)], 3.2, 'd', only='gkfFm')
gates = {}
for gname, gp in [('gate_main', SK['main_gate']), ('gate_east', SK['east_gate'])]:
    gx, gy = to_grid(gp); gates[gname] = (round(gx), round(gy))
    for dx in range(-5, 6):
        for dy in range(-5, 6):
            xx, yy = int(gx) + dx, int(gy) + dy
            if not inb(xx, yy): continue
            if cells[yy][xx] in 'wT':
                cells[yy][xx] = 'r' if abs(dx) + abs(dy) <= 2 else 'T'   # opening + bone-white gate towers
anchor('greymark_walls', *gates['gate_main'])

# ---------------------------------------------------------- market square ---
ms = SK['market_square']
for y in range(H):
    for x in range(W):
        u, v = to_sketch(x + 0.5, y + 0.5)
        if ((u - ms['cx']) / ms['rx']) ** 2 + ((v - ms['cy']) / ms['ry']) ** 2 < 1:
            cells[y][x] = 'p'
wx, wy = to_grid((ms['cx'], ms['cy'])); cells[int(wy)][int(wx)] = 'W'; anchor('town_well', int(wx), int(wy))
for k, (du, dv) in enumerate([(-45, -12), (30, -18), (-20, 22), (45, 15)]):
    sx, sy = to_grid((ms['cx'] + du, ms['cy'] + dv)); building(int(sx), int(sy), 2, 2, 'stall', 4, label=f'stall_{k}')

# ------------------------------------------------------- church compound ---
loop = [to_grid(p) for p in SK['church']['loop']]
CX0, CY0 = int(min(p[0] for p in loop)), int(min(p[1] for p in loop))
CX1, CY1 = int(max(p[0] for p in loop)) + 1, int(max(p[1] for p in loop)) + 1
HC = ((CX0 + CX1) / 2, (CY0 + CY1) / 2)
for y in range(CY0 - 10, CY1 + 11):            # the hill the switchback road climbs
    for x in range(CX0 - 10, CX1 + 11):
        if not inb(x, y) or cells[y][x] in '~': continue
        dd = max(abs(x - HC[0]) / ((CX1 - CX0) / 2 + 10), abs(y - HC[1]) / ((CY1 - CY0) / 2 + 10))
        hgt[y][x] = max(hgt[y][x], 1 + round(max(0, 1 - dd) * 7))
if os.path.exists(os.path.join(ROOT, 'map', 'assets', 'church_compound.png')):
    for y in range(CY0, CY1 + 1):
        for x in range(CX0, CX1 + 1): cells[y][x] = 'g'; hgt[y][x] = hgt[CY1][CX1]
    sprites.append({'id': 'church_compound', 'src': 'assets/church_compound.png', 'x0': CX0, 'y0': CY0, 'x1': CX1, 'y1': CY1})
else:
    for y in range(CY0, CY1 + 1):
        for x in range(CX0, CX1 + 1):
            cells[y][x] = 'w' if x in (CX0, CX1) or y in (CY0, CY1) else 'p'
    for (tx, ty) in [(CX0, CY0), (CX1, CY0), (CX0, CY1), (CX1, CY1)]:
        for yy in range(ty - 1, ty + 2):
            for xx in range(tx - 1, tx + 2): setc(xx, yy, 'T')
    building(CX0 + 3, CY0 + 3, 11, 6, 'church', 16, story='greymark_church')
    building(CX0 + 3, CY1 - 7, 5, 4, 'hall', 8, label='priests_house')
    cells[int(HC[1]) + 1][int(HC[0]) + 2] = 'U'
slots.append({'id': 'church_compound', 'kind': 'walls', 'x': CX0, 'y': CY0, 'w': CX1 - CX0 + 1, 'd': CY1 - CY0 + 1})
anchor('greymark_church', HC[0] - 2, HC[1] - 3); anchor('church_fountain', HC[0] + 1, HC[1] + 2)

# --------------------------------------------------------- the mill annex ---
ma = SK['mill_annex']
mcx, mcy = to_grid((ma['cx'], ma['cy'])); mr = ma['r'] * S
for y in range(int(mcy - mr) - 1, int(mcy + mr) + 2):
    for x in range(int(mcx - mr) - 1, int(mcx + mr) + 2):
        if not inb(x, y) or cells[y][x] == '~': continue
        d2 = (x + 0.5 - mcx) ** 2 + (y + 0.5 - mcy) ** 2
        if d2 < (mr - 0.8) ** 2: cells[y][x] = 'p'
        elif d2 < (mr + 0.4) ** 2: cells[y][x] = 'w'
building(int(mcx) - 4, int(mcy) - 4, 8, 6, 'mill', 10, story='vex_mill')
for k in range(3): building(int(mcx) - 3 + k * 3, int(mcy) + 3, 2, 2, 'dye_vat', 3, label=f'dye_vat_{k}')
slots.append({'id': 'mill_annex', 'kind': 'walls', 'x': int(mcx - mr), 'y': int(mcy - mr), 'w': int(2 * mr), 'd': int(2 * mr)})
anchor('flax_farms', *to_grid((760, 700)))

# ------------------------------------------------------- story buildings ---
def near(sk_pt, w, d, typ, h, sid):
    x, y = to_grid(sk_pt); x, y = int(x), int(y)
    for r_ in range(0, 14):
        for dx in range(-r_, r_ + 1):
            for dy in range(-r_, r_ + 1):
                if free(x + dx - 1, y + dy - 1, x + dx + w + 1, y + dy + d + 1, 'Y'):
                    return building(x + dx, y + dy, w, d, typ, h, story=sid)


near((ms['cx'] - 10, ms['cy'] - 62), 6, 5, 'tavern', 9, 'broken_compass')
hp = near((ms['cx'] - 95, ms['cy'] - 40), 5, 5, 'cellar', 8, 'harrens_place')
if hp: anchor('ancient_ruin', hp['tx'] - 3, hp['ty'] - 3)
near((ms['cx'] + 120, ms['cy'] - 20), 5, 4, 'house', 7, 'husk_house')
near((SK['main_gate'][0] - 40, SK['main_gate'][1] - 30), 5, 4, 'smithy', 7, 'greymark_blacksmith')

# ------------------------------------------- ordinary houses along streets ---
road = {(x, y) for y in range(H) for x in range(W) if cells[y][x] == 'r'}
def near_road(x0, y0, w, d, reach=3):
    return any((x, y) in road for y in range(y0 - reach, y0 + d + reach) for x in range(x0 - reach, x0 + w + reach))
count = 0
cands = [(x, y) for y in range(0, H, 2) for x in range(0, W, 2) if cells[y][x] == 'Y']
rnd.shuffle(cands)
for (x, y) in cands:
    w, d = rnd.choice([(4, 4), (5, 4), (4, 3), (4, 5), (5, 5)])
    if free(x - 1, y - 1, x + w + 1, y + d + 1, 'Y') and near_road(x, y, w, d, 3):
        building(x, y, w, d, 'house', 3 + 2 * rnd.choice([1, 2, 2, 3])); count += 1
gx, gy = gates['gate_main']
for (x, y) in [(gx + 6, gy + 12), (gx - 7, gy + 20), (gx + 8, gy + 28)]:
    if free(x, y, x + 4, y + 4, 'gfF'): building(x, y, 4, 4, 'cottage', 5); count += 1

# ------------------------------------------------------------------ write ---
out = {
    'id': 'greymark', 'w': W, 'h': H, 'unit': 2,
    'cells': ''.join(''.join(r) for r in cells),
    'hgt': ''.join(''.join(str(min(9, v)) for v in r) for r in hgt),
    'bid': [v for r in bid for v in r],
    'gates': [list(g) for g in gates.values()], 'square': [round(wx), round(wy)], 'fields': 'flax',
    'districts': [], 'buildings': buildings, 'anchors': anchors, 'sprites': sprites,
    'source': 'hand-designed blockout from the author sketch (tools/layout_greymark.py)',
}
with open(os.path.join(ROOT, 'map', 'cities', 'greymark.js'), 'w') as f:
    f.write('// generated by tools/layout_greymark.py from data/greymark_sketch.json - the Greymark blockout\n')
    f.write('window.ASHFALL_CITIES = window.ASHFALL_CITIES || {};\nwindow.ASHFALL_CITIES["greymark"] = ')
    json.dump(out, f, separators=(',', ':')); f.write(';\n')
json.dump({'grid': [W, H], 'tile_m': 2, 'slots': slots, 'anchors': anchors, 'sprites': sprites},
          open(os.path.join(ROOT, 'data', 'greymark_layout.json'), 'w'), indent=1)
types = {}
for b in buildings: types[b['type']] = types.get(b['type'], 0) + 1
print(f'greymark blockout: {W}x{H}, {len(buildings)} buildings ({count} houses), church slot {CX0},{CY0}-{CX1},{CY1}', types)
