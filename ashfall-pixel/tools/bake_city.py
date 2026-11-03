"""Bake an MFCG city export into an isometric tile grid for the pixel engine.

    python3 tools/bake_city.py            # all cities in CONFIG
    python3 tools/bake_city.py greymark

Input : cities/<id>.mfcg.json   (from tools/fetch_cities.mjs)
Output: map/cities/<id>.js      (window.ASHFALL_CITIES[id] = {...})

Every building polygon becomes a block of tiles with an id and a TYPE.
Story buildings (importance 'key' / 'supporting') are placed first by simple
rules in CONFIG (largest in a district, nearest the square, by a gate...);
everything else gets a generic type from its size, district and street access.
"""
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- config ---
# unit = MFCG world units per tile. Smaller = bigger, more detailed city.
CONFIG = {
    'greymark': {
        'unit': 4.5, 'margin': 70, 'fields': 'flax', 'seed': 7,
        # (catalogue id from data/story.json, type, placement rule)
        'story': [
            ('broken_compass', 'tavern', 'near_square'),
            ('harrens_place', 'cellar', 'near:broken_compass'),
            ('husk_house', 'house', 'near:harrens_place'),
            ('vex_mill', 'mill', 'outside_near_fields'),
            ('greymark_blacksmith', 'smithy', 'near_gate'),
        ],
        # story things that are not buildings: (catalogue id, rule)
        'anchors': [
            ('town_well', 'at_well'), ('ancient_ruin', 'at:harrens_place'), ('young_rift', 'at:harrens_place'),
            ('greymark_walls', 'at_gate'), ('flax_farms', 'at_field'),
        ],
    },
    'valencourt': {
        'unit': 6.0, 'margin': 60, 'fields': 'vines', 'seed': 11,
        'story': [
            ('deveraux_keep', 'keep', 'largest_in:Citadel'),
            ('stewards_quarters', 'manor', 'near:deveraux_keep'),
            ('guard_post', 'guard post', 'near_gate'),
            ('valencourt_tavern', 'tavern', 'near:guard_post'),
            ('valencourt_bakery', 'bakery', 'near:valencourt_tavern'),
            ('valencourt_blacksmith', 'smithy', 'near:guard_post'),
            ('lower_city_tavern', 'tavern', 'in_district_far:East Slums'),
            ('missing_family_house', 'house', 'near:lower_city_tavern'),
            ('excavated_cellar', 'cellar', 'in_district_far:East Slums'),
        ],
        'anchors': [
            ('valencourt_market', 'at_square'), ('mother_tree', 'at_square+'), ('valencourt_gate', 'at_gate'),
            ('valencourt_palisade', 'at_gate:1'), ('vineyards', 'at_field'), ('copper_mines', 'at:deveraux_keep'),
        ],
    },
}

GENERIC_MIX = [  # (type, weight) for small/medium buildings with street access
    ('house', 60), ('shop', 14), ('workshop', 10), ('inn', 2), ('stable', 3), ('bakery', 3), ('smithy', 2),
    ('chandlery', 2), ('weaver', 2), ('tannery', 1), ('apothecary', 1),
]


def load(cid):
    with open(os.path.join(ROOT, 'cities', f'{cid}.mfcg.json')) as f:
        d = json.load(f)
    return {f['id']: f for f in d['features']}


def poly_area(ring):
    a = 0
    for i in range(len(ring)):
        x0, y0 = ring[i]; x1, y1 = ring[(i + 1) % len(ring)]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2


def centroid(ring):
    return sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)


def point_in(pt, ring):
    x, y = pt; inside = False
    for i in range(len(ring)):
        x0, y0 = ring[i]; x1, y1 = ring[i - 1]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0:
            inside = not inside
    return inside


def bake(cid):
    cfg = CONFIG[cid]
    F = load(cid)
    rnd = random.Random(cfg['seed'])
    U, M = cfg['unit'], cfg['margin']
    blds = F['buildings']['coordinates']
    xs = [p[0] for poly in blds for p in poly[0]]; ys = [p[1] for poly in blds for p in poly[0]]
    x0, x1, y0, y1 = min(xs) - M, max(xs) + M, min(ys) - M, max(ys) + M
    W, H = int((x1 - x0) / U) + 1, int((y1 - y0) / U) + 1
    tx = lambda p: ((p[0] - x0) / U, (p[1] - y0) / U)

    # layer images, 1 px = 1 tile
    ground = Image.new('L', (W, H), ord('g')); gd = ImageDraw.Draw(ground)
    for i, poly in enumerate(F['fields']['coordinates']):
        code = 'f' if i % 3 else 'F'
        gd.polygon([tx(p) for p in poly[0]], fill=ord(code))
    for poly in F['greens']['coordinates']:
        gd.polygon([tx(p) for p in poly[0]], fill=ord('m'))
    for poly in F['squares']['coordinates']:
        gd.polygon([tx(p) for p in poly[0]], fill=ord('p'))
    for g in F['roads']['geometries']:
        gd.line([tx(p) for p in g['coordinates']], fill=ord('r'), width=max(1, round(g.get('width', 6) / U)))
    for g in F['rivers']['geometries']:
        coords = g['coordinates'] if g['type'] == 'LineString' else g['coordinates'][0]
        gd.line([tx(p) for p in coords], fill=ord('~'), width=max(2, round(g.get('width', 20) / U)))
    # streets inside town are the gaps between buildings: mark later
    for poly in F['prisms']['coordinates']:
        cx, cy = tx(centroid(poly[0])); gd.point((round(cx), round(cy)), fill=ord('W'))

    walls = Image.new('L', (W, H), 0); wd = ImageDraw.Draw(walls)
    gates = []
    wall_rings = []
    for g in F['walls']['geometries']:
        ring = g['coordinates'][0]; wall_rings.append(ring)
        pts = [tx(p) for p in ring] + [tx(ring[0])]
        wd.line(pts, fill=1, width=max(1, round(g.get('width', 6) / U)))
        for p in pts[:-1]:
            wd.ellipse([p[0] - 1.2, p[1] - 1.2, p[0] + 1.2, p[1] + 1.2], fill=2)  # towers
    # gates = where roads cross the wall
    for g in F['roads']['geometries']:
        for p in g['coordinates']:
            q = tx(p); xi, yi = round(q[0]), round(q[1])
            if 0 <= xi < W and 0 <= yi < H and walls.getpixel((xi, yi)):
                gates.append((xi, yi))
    for (xi, yi) in gates:  # open the gate (2 towers either side remain from vertices)
        wd.rectangle([xi - 1, yi - 1, xi + 1, yi + 1], fill=3)

    bmap = Image.new('I', (W, H), 0); bd = ImageDraw.Draw(bmap)
    districts = [(g.get('name', ''), g['coordinates'][0]) for g in F['districts']['geometries']]
    meta = []
    for i, poly in enumerate(blds, start=1):
        ring = poly[0]
        bd.polygon([tx(p) for p in ring], fill=i)
        c = centroid(ring)
        dname = next((n for n, r in districts if point_in(c, r)), '')
        inside = any(point_in(c, r) for r in wall_rings) if wall_rings else True
        meta.append({'id': i, 'area': poly_area(ring), 'c': c, 'district': dname, 'inside': inside})

    G = list(ground.tobytes()); B = list(bmap.get_flattened_data()) if hasattr(bmap, 'get_flattened_data') else list(bmap.getdata()); Wl = list(walls.tobytes())
    cells = []
    for k in range(W * H):
        c = chr(G[k])
        if Wl[k] == 3: c = 'r'
        elif Wl[k] == 2: c = 'T'
        elif Wl[k] == 1: c = 'w'
        if B[k] and c not in 'wT': c = 'b'
        cells.append(c)
    bid = [b if cells[k] == 'b' else 0 for k, b in enumerate(B)]

    # tile stats per building
    tiles = {}
    for k, b in enumerate(bid):
        if b: tiles.setdefault(b, []).append((k % W, k // W))
    for m in meta:
        t = tiles.get(m['id'], [])
        m['n'] = len(t)
        if t:
            m['tx'] = round(sum(p[0] for p in t) / len(t), 1); m['ty'] = round(sum(p[1] for p in t) / len(t), 1)
        else:
            m['tx'], m['ty'] = tx(m['c'])
        # street access: any 4-neighbour road/plaza/grass gap
        acc = 0
        for (x, y) in t:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < W and 0 <= yy < H and cells[yy * W + xx] in 'rp': acc += 1
        m['street'] = acc
    meta = [m for m in meta if m['n'] > 0]

    # reference points
    sq = [(k % W, k // W) for k, c in enumerate(cells) if c == 'p']
    square = (sum(p[0] for p in sq) / len(sq), sum(p[1] for p in sq) / len(sq)) if sq else (W / 2, H / 2)
    field_tiles = [(k % W, k // W) for k, c in enumerate(cells) if c in 'fF']
    dist = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])
    pos = lambda m: (m['tx'], m['ty'])

    taken = {}
    by_story = {}
    def pick(cands, key):
        cands = [m for m in cands if m['id'] not in taken]
        return min(cands, key=key) if cands else None
    for sid, typ, rule in cfg['story']:
        m = None
        if rule == 'largest':
            m = pick([x for x in meta if x['inside']], lambda x: -x['area'])
        elif rule.startswith('largest_in:'):
            d = rule.split(':', 1)[1]; m = pick([x for x in meta if x['district'] == d], lambda x: -x['area'])
        elif rule == 'near_square':
            m = pick([x for x in meta if x['n'] >= 4], lambda x: dist(pos(x), square))
        elif rule == 'near_gate' and gates:
            m = pick([x for x in meta if x['n'] >= 3], lambda x: min(dist(pos(x), g) for g in gates) + rnd.random() * 3)
        elif rule.startswith('near:'):
            ref = by_story.get(rule.split(':', 1)[1])
            if ref: m = pick([x for x in meta if x['n'] >= 3], lambda x: dist(pos(x), pos(ref)))
        elif rule == 'outside_near_fields':
            pool = [x for x in meta if not x['inside'] and x['n'] >= 4] or [x for x in meta if x['n'] >= 4]
            if field_tiles:
                m = pick(pool, lambda x: min(dist(pos(x), f) for f in field_tiles[::7]) - x['n'] * 0.2)
            else:
                m = pick(pool, lambda x: -dist(pos(x), square))
        elif rule.startswith('in_district_far:'):
            d = rule.split(':', 1)[1]; pool = [x for x in meta if x['district'] == d and x['n'] >= 3]
            m = pick(pool or meta, lambda x: -dist(pos(x), square))
        if m:
            m['type'] = typ; m['story'] = sid; taken[m['id']] = sid; by_story[sid] = m

    # anchors (story places that are not buildings)
    anchors = []
    for sid, rule in cfg.get('anchors', []):
        p = None
        if rule == 'at_well':
            w = [(k % W, k // W) for k, c in enumerate(cells) if c == 'W']; p = w[0] if w else square
        elif rule.startswith('at_square'):
            p = (square[0] + (3 if rule.endswith('+') else 0), square[1] + (-2 if rule.endswith('+') else 0))
        elif rule.startswith('at_gate') and gates:
            i = int(rule.split(':')[1]) if ':' in rule else 0; p = gates[min(i, len(gates) - 1)]
        elif rule == 'at_field' and field_tiles:
            p = min(field_tiles, key=lambda f: dist(f, square))
        elif rule.startswith('at:') and rule[3:] in by_story:
            p = pos(by_story[rule[3:]])
        if p: anchors.append({'story': sid, 'tx': round(p[0], 1), 'ty': round(p[1], 1)})

    # generic types
    types, weights = zip(*GENERIC_MIX)
    fmask = Image.frombytes('L', (W, H), bytes(255 if c in 'fF' else 0 for c in cells)).filter(ImageFilter.MaxFilter(9))
    big = sorted(m['n'] for m in meta)[int(len(meta) * 0.97)]
    small = sorted(m['n'] for m in meta)[int(len(meta) * 0.25)]
    for m in meta:
        if 'type' in m: continue
        near_field = fmask.getpixel((min(W - 1, max(0, round(m['tx']))), min(H - 1, max(0, round(m['ty']))))) > 0
        if not m['inside']:
            if near_field: m['type'] = 'farmhouse' if m['n'] > small else 'barn'
            elif m['district'] in ('East Slums',) or m['n'] <= small: m['type'] = rnd.choice(['shack', 'cottage'])
            else: m['type'] = rnd.choices(['house', 'workshop', 'stable', 'tannery'], [80, 10, 6, 4])[0]
        elif m['n'] >= big:
            m['type'] = rnd.choice(['hall', 'warehouse', 'manor'])
        elif m['district'] == 'Citadel':
            m['type'] = rnd.choice(['barracks', 'house', 'stable'])
        elif m['street'] >= 2 and m['n'] >= 4:
            m['type'] = rnd.choices(types, weights)[0]
        else:
            m['type'] = 'house'
    # heights in pixels (engine uses these directly)
    for m in meta:
        t = m['type']
        if t == 'keep': m['h'] = 26
        elif t == 'church': m['h'] = 16
        elif t in ('hall', 'manor', 'warehouse', 'mill'): m['h'] = 11
        elif t in ('shack', 'cottage', 'barn'): m['h'] = 5
        else: m['h'] = 6 + min(4, round(4 * m['n'] / max(1, big))) + rnd.randint(0, 1)

    out = {
        'id': cid, 'w': W, 'h': H, 'unit': U,
        'cells': ''.join(cells),
        'bid': bid,
        'gates': gates,
        'square': [round(square[0], 1), round(square[1], 1)],
        'anchors': anchors,
        'fields': cfg['fields'],
        'districts': sorted({m['district'] for m in meta if m['district']}),
        'buildings': [{k: m[k] for k in ('id', 'type', 'n', 'tx', 'ty', 'district', 'h', 'inside')} | ({'story': m['story']} if 'story' in m else {}) for m in meta],
        'source': 'watabou Medieval Fantasy City Generator (MFCG) export, baked by tools/bake_city.py',
    }
    os.makedirs(os.path.join(ROOT, 'map', 'cities'), exist_ok=True)
    path = os.path.join(ROOT, 'map', 'cities', f'{cid}.js')
    with open(path, 'w') as f:
        f.write('// generated by tools/bake_city.py - do not edit by hand\n')
        f.write('window.ASHFALL_CITIES = window.ASHFALL_CITIES || {};\n')
        f.write(f'window.ASHFALL_CITIES[{json.dumps(cid)}] = ')
        json.dump(out, f, separators=(',', ':'))
        f.write(';\n')
    counts = {}
    for m in meta: counts[m['type']] = counts.get(m['type'], 0) + 1
    print(f'{cid}: {W}x{H} tiles, {len(meta)} buildings, gates {len(gates)}, story {list(by_story)}')
    print('   ', dict(sorted(counts.items(), key=lambda kv: -kv[1])))


def emit_story():
    with open(os.path.join(ROOT, 'data', 'story.json')) as f:
        story = json.load(f)
    with open(os.path.join(ROOT, 'map', 'story.js'), 'w') as f:
        f.write('// generated from data/story.json by tools/bake_city.py - edit the JSON, not this file\n')
        f.write('window.ASHFALL_STORY = ')
        json.dump(story, f, ensure_ascii=False, indent=1)
        f.write(';\n')


if __name__ == '__main__':
    emit_story()
    for cid in (sys.argv[1:] or CONFIG):
        bake(cid)
