"""Greymark BLOCKOUT: a low-res, spacious, hand-designed layout that fixes where every asset goes.

    python3 tools/layout_greymark.py      -> map/cities/greymark.js  (+ data/greymark_layout.json)

This is the "greybox" stage: simple shapes, right places, right sizes. Every story building and
landmark is a named SLOT with a footprint; detailed art (one asset at a time) is made to fit its
slot later and dropped in. Grid: 1 tile ~ 2 m. In the isometric view, small x+y is the BACK (top of
screen), large x+y the FRONT, large x-y is screen-RIGHT.

Layout (book 3.0 + the church on the hill from the drafted Ch IV):
  * church compound on a hill at the back of town: curtain wall with embattlements, corner towers,
    a gatehouse facing the square (where Kethric runs into the priest's men), church + fountain
  * the square in the middle with the red-water well; the Broken Compass and Harren's place on it
  * a dark timber palisade with watchtowers; bone-white stone gatehouses on the main gates
  * Vex's mill outside the north-east gate (screen top-right) with treadwheel, dye vats, flax fields
  * farmland in front, autumn forest behind and to the left
"""
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = H = 190
rnd = random.Random(3)
cells = [['g'] * W for _ in range(H)]
hgt = [[1] * W for _ in range(H)]
bid = [[0] * W for _ in range(H)]
buildings, anchors, slots = [], [], []


def fill(x0, y0, x1, y1, c, only=None):
    for y in range(max(0, y0), min(H, y1)):
        for x in range(max(0, x0), min(W, x1)):
            if only is None or cells[y][x] in only:
                cells[y][x] = c


def free(x0, y0, x1, y1, ok='gk'):
    return all(0 <= x < W and 0 <= y < H and cells[y][x] in ok for y in range(y0, y1) for x in range(x0, x1))


def building(x0, y0, w, d, typ, h, story=None, label=None):
    i = len(buildings) + 1
    for y in range(y0, y0 + d):
        for x in range(x0, x0 + w):
            cells[y][x] = 'b'; bid[y][x] = i
    b = {'id': i, 'type': typ, 'n': w * d, 'tx': x0 + (w - 1) / 2, 'ty': y0 + (d - 1) / 2, 'h': h, 'district': '', 'inside': True}
    if story: b['story'] = story
    buildings.append(b)
    if story or label:
        slots.append({'id': story or label, 'kind': typ, 'x': x0, 'y': y0, 'w': w, 'd': d})
    return b


def anchor(story, x, y):
    anchors.append({'story': story, 'tx': x, 'ty': y})


# ------------------------------------------------------------- terrain ---
# forest behind (top) and to the left; open farmland to the front and right
for y in range(H):
    for x in range(W):
        back = (x + y) < 120 or x < 22 or (y < 30 and x < 120)
        if back and rnd.random() < 0.92:
            cells[y][x] = 'k'

# the palisade: a big rectangle (shows as a diamond), timber stakes 'w', watchtowers 'T'
PX0, PY0, PX1, PY1 = 40, 40, 150, 150
fill(PX0, PY0, PX1 + 1, PY1 + 1, 'g')
fill(PX0 + 1, PY0 + 1, PX1, PY1, 'Y')  # inside the walls: yards/gardens by default
for x in range(PX0, PX1 + 1):
    cells[PY0][x] = cells[PY1][x] = 'w'
for y in range(PY0, PY1 + 1):
    cells[y][PX0] = cells[y][PX1] = 'w'
for k in range(PX0, PX1 + 1, 22):
    for (tx, ty) in [(k, PY0), (k, PY1), (PX0, k), (PX1, k)]:
        fill(tx - 1, ty - 1, tx + 2, ty + 2, 'T')
fill(PX1 - 1, PY1 - 1, PX1 + 2, PY1 + 2, 'T')

# streets (cobbles, 3 wide): a cross through the square + secondary streets + a ring lane
SQ = (95, 95)
def street_x(y, x0, x1, c='r'): fill(x0, y - 1, x1, y + 2, c)
def street_y(x, y0, y1, c='r'): fill(x - 1, y0, x + 2, y1, c)
street_x(95, PX0 + 1, PX1)            # main street east-west through the square
street_y(95, PY0 + 1, PY1)            # main street north-south
for v in (68, 122):
    street_x(v, PX0 + 1, PX1); street_y(v, PY0 + 1, PY1)
for v in (PX0 + 4, PX1 - 4):
    street_y(v, PY0 + 1, PY1); street_x(v, PX0 + 1, PX1)
# gates: the street ends open the wall
gates = {'gate_east': (PX1, 95), 'gate_south': (95, PY1), 'gate_north': (122, PY0)}
for g, (gx, gy) in gates.items():
    if gx == PX1 or gx == PX0:
        fill(gx - 2, gy - 3, gx + 3, gy - 1, 'T'); fill(gx - 2, gy + 2, gx + 3, gy + 4, 'T'); fill(gx, gy - 1, gx + 1, gy + 2, 'r')
    else:
        fill(gx - 3, gy - 2, gx - 1, gy + 3, 'T'); fill(gx + 2, gy - 2, gx + 4, gy + 3, 'T'); fill(gx - 1, gy, gx + 2, gy + 1, 'r')
# roads out to the edge of the map (dirt)
fill(PX1 + 1, 94, W, 97, 'd')                      # east road toward the viewer's right-front
fill(94, PY1 + 1, 97, H, 'd')                      # south road toward the viewer's left-front
fill(121, 0, 124, PY0, 'd')                        # north-east road to the mill

# the square + the town well
fill(SQ[0] - 8, SQ[1] - 8, SQ[0] + 9, SQ[1] + 9, 'p')
cells[SQ[1]][SQ[0]] = 'W'
anchor('town_well', SQ[0], SQ[1])

# --------------------------------------------- the church compound (hill) ---
CX0, CY0, CX1, CY1 = 46, 46, 82, 80
HC = ((CX0 + CX1) / 2, (CY0 + CY1) / 2)
for y in range(CY0 - 8, CY1 + 8):        # the hill: rises toward the compound
    for x in range(CX0 - 8, CX1 + 8):
        dd = max(abs(x - HC[0]) / ((CX1 - CX0) / 2 + 8), abs(y - HC[1]) / ((CY1 - CY0) / 2 + 8))
        hgt[y][x] = max(hgt[y][x], 1 + round(max(0, 1 - dd) * 9))
fill(CX0, CY0, CX1 + 1, CY1 + 1, 'p')    # paved courtyard
for x in range(CX0, CX1 + 1):
    cells[CY0][x] = cells[CY1][x] = 'w'
for y in range(CY0, CY1 + 1):
    cells[y][CX0] = cells[y][CX1] = 'w'
for (tx, ty) in [(CX0, CY0), (CX1, CY0), (CX0, CY1), (CX1, CY1)]:          # corner towers
    fill(tx - 2, ty - 2, tx + 3, ty + 3, 'T')
for (tx, ty) in [((CX0 + CX1) // 2, CY0), (CX0, (CY0 + CY1) // 2)]:        # mid-wall towers at the back
    fill(tx - 1, ty - 1, tx + 2, ty + 2, 'T')
# gatehouse on the side facing the square (+x side), the street to the square runs through it
gy = 68
fill(CX1 - 1, gy - 4, CX1 + 3, gy - 1, 'T'); fill(CX1 - 1, gy + 2, CX1 + 3, gy + 5, 'T'); fill(CX1, gy - 1, CX1 + 1, gy + 2, 'r')
anchor('church_gatehouse', CX1 + 1, gy)
slots.append({'id': 'church_compound', 'kind': 'walls', 'x': CX0, 'y': CY0, 'w': CX1 - CX0 + 1, 'd': CY1 - CY0 + 1})
building(52, 52, 18, 9, 'church', 16, story='greymark_church')                 # the church (nave + tower)
building(70, 66, 7, 6, 'hall', 8, label='priests_house')                       # the priests' quarters / barracks
building(52, 68, 6, 5, 'house', 6, label='chapter_house')
cells[72][62] = 'U'; anchor('church_fountain', 62, 72)                         # fountain in the courtyard
fill(48, 63, 51, 77, 'm')                                                       # churchyard (graves)

# ------------------------------------------------------- story buildings ---
building(SQ[0] - 15, SQ[1] + 1, 6, 5, 'tavern', 9, story='broken_compass')      # west side of the square
building(SQ[0] - 15, SQ[1] - 7, 5, 5, 'cellar', 8, story='harrens_place')       # next door, on the old stones
anchor('ancient_ruin', SQ[0] - 17, SQ[1] - 9); fill(SQ[0] - 19, SQ[1] - 11, SQ[0] - 16, SQ[1] - 8, 'T')
building(SQ[0] + 10, SQ[1] - 14, 5, 4, 'house', 7, story='husk_house')
building(PX1 - 12, 99, 6, 5, 'smithy', 7, story='greymark_blacksmith')          # by the east gate
anchor('greymark_walls', PX1, 95)
# market stalls round the square
for k, (sx, sy) in enumerate([(SQ[0] + 3, SQ[1] - 6), (SQ[0] + 6, SQ[1] - 6), (SQ[0] - 6, SQ[1] + 5), (SQ[0] + 5, SQ[1] + 5)]):
    building(sx, sy, 2, 2, 'stall', 4, label=f'stall_{k}')

# Vex's mill outside the north-east gate (screen top-right), treadwheel, dye vats, flax fields
building(112, 14, 12, 7, 'mill', 10, story='vex_mill')
building(125, 15, 3, 5, 'treadwheel', 8, label='treadwheel')
for k in range(4): building(112 + k * 3, 23, 2, 2, 'dye_vat', 3, label=f'dye_vat_{k}')
for k in range(3): building(127 + k * 4, 24, 1, 4, 'drying_rack', 4, label=f'drying_rack_{k}')
for (fx, fy, fw, fd) in [(130, 4, 22, 14), (154, 4, 22, 14), (130, 20, 22, 14), (154, 20, 26, 14)]:
    fill(fx, fy, fx + fw, fy + fd, 'f', only='gk'); fill(fx, fy + fd - 1, fx + fw, fy + fd, 'k', only='f')
anchor('flax_farms', 142, 12)

# farmland in front of town (patchwork, hedges between)
for fx in range(100, 186, 14):
    for fy in range(156, 186, 11):
        if fx + fy > 220: fill(fx, fy, fx + 12, fy + 9, rnd.choice('fFf'), only='g')
for fx in range(156, 186, 12):
    for fy in range(40, 156, 11):
        fill(fx, fy, fx + 10, fy + 9, rnd.choice('fFF'), only='g')

# ---------------------------------------------- ordinary houses on plots ---
# plots of 7x7 inside the street blocks: house 4-5 x 4 + a yard (garden 'Y'), door to the nearest street
count = 0
for by in range(PY0 + 2, PY1 - 1, 6):
    for bx in range(PX0 + 2, PX1 - 1, 6):
        w, d = rnd.choice([(4, 4), (5, 4), (4, 3), (4, 5)])
        x0, y0 = bx + rnd.randint(0, 6 - w), by + rnd.randint(0, 6 - d)
        if not free(x0, y0, x0 + w, y0 + d, ok='Y') or not free(x0 - 1, y0 - 1, x0 + w + 1, y0 + d + 1, ok='Yr'):
            continue
        storeys = rnd.choice([1, 2, 2, 2, 3])
        building(x0, y0, w, d, 'house', 3 + storeys * 2, None)
        count += 1
# a few suburbs along the roads outside the gates
for k in range(14):
    x0 = PX1 + 4 + k * 3 if k < 7 else 90 - 10 + (k - 7) * 0
    if k < 7:
        x0, y0 = PX1 + 4 + k * 5, 89 if k % 2 else 99
    else:
        x0, y0 = (89 if k % 2 else 99), PY1 + 4 + (k - 7) * 5
    w, d = 4, 4
    if free(x0, y0, x0 + w, y0 + d, ok='g'):
        building(x0, y0, w, d, 'cottage', 5); count += 1

# ----------------------------------------------------------------- write ---
out = {
    'id': 'greymark', 'w': W, 'h': H, 'unit': 2,
    'cells': ''.join(''.join(r) for r in cells),
    'hgt': ''.join(''.join(str(min(9, v)) for v in r) for r in hgt),
    'bid': [v for r in bid for v in r],
    'gates': [list(v) for v in gates.values()], 'square': list(SQ), 'fields': 'flax',
    'districts': [], 'buildings': buildings, 'anchors': anchors,
    'source': 'hand-designed blockout (tools/layout_greymark.py)',
}
os.makedirs(os.path.join(ROOT, 'map', 'cities'), exist_ok=True)
with open(os.path.join(ROOT, 'map', 'cities', 'greymark.js'), 'w') as f:
    f.write('// generated by tools/layout_greymark.py - the Greymark blockout\nwindow.ASHFALL_CITIES = window.ASHFALL_CITIES || {};\n')
    f.write('window.ASHFALL_CITIES["greymark"] = '); json.dump(out, f, separators=(',', ':')); f.write(';\n')
json.dump({'grid': [W, H], 'tile_m': 2, 'slots': slots, 'anchors': anchors, 'gates': gates}, open(os.path.join(ROOT, 'data', 'greymark_layout.json'), 'w'), indent=1)
types = {}
for b in buildings: types[b['type']] = types.get(b['type'], 0) + 1
print(f'greymark blockout: {W}x{H} tiles, {len(buildings)} buildings ({count} houses/cottages), slots {len(slots)}', types)
