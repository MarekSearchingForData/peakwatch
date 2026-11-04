"""Turn an MFCG city export into a 3D build plan for the Blender diorama.

    python3 tools/plan_town.py greymark            -> cities/greymark.plan.json

Each building polygon becomes a house footprint (centre, length, depth, facing) from its
minimum-area rectangle. Walls, gates, roads, squares, fields and the well come along.
Coordinates are converted to diorama units (x east, y north) and rotated so the main
gate road points at the camera (south-east). Story buildings are picked by the same
rules as tools/bake_city.py.
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCALE = 0.2  # MFCG units -> diorama units (a typical house ends up 2-4 units long)

STORY = {
    'greymark': [
        ('broken_compass', 'near_square', 6),
        ('harrens_place', 'near:broken_compass', 4),
        ('husk_house', 'near:harrens_place', 3),
        ('greymark_blacksmith', 'near_gate', 4),
        ('vex_mill', 'outside_near_fields', 8),
    ],
}


def centroid(r):
    return sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r)


def area(r):
    return abs(sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))) / 2


def min_rect(ring):
    """Minimum-area bounding rectangle -> (cx, cy, length, depth, angle of the long side)."""
    best = None
    for i in range(len(ring)):
        x0, y0 = ring[i]; x1, y1 = ring[(i + 1) % len(ring)]
        ang = math.atan2(y1 - y0, x1 - x0); c, s = math.cos(ang), math.sin(ang)
        us = [p[0] * c + p[1] * s for p in ring]; vs = [-p[0] * s + p[1] * c for p in ring]
        a = (max(us) - min(us)) * (max(vs) - min(vs))
        if best is None or a < best[0]:
            u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
            cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
            best = (a, cu * c - cv * s, cu * s + cv * c, u1 - u0, v1 - v0, ang)
    _, cx, cy, L, D, ang = best
    if D > L: L, D, ang = D, L, ang + math.pi / 2
    return cx, cy, L, D, ang


def inside(pt, ring):
    x, y = pt; c = False
    for i in range(len(ring)):
        x0, y0 = ring[i]; x1, y1 = ring[i - 1]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0:
            c = not c
    return c


def plan(cid):
    F = {f['id']: f for f in json.load(open(os.path.join(ROOT, 'cities', f'{cid}.mfcg.json')))['features']}
    wall = F['walls']['geometries'][0]['coordinates'][0] if F['walls']['geometries'] else None
    wc = centroid(wall) if wall else (0, 0)
    # gates: where roads cross the wall line; the road running furthest out is the main one
    gates = []
    for g in F['roads']['geometries']:
        pts = g['coordinates']
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            if wall and inside(a, wall) != inside(b, wall):
                far = max(math.hypot(p[0] - wc[0], p[1] - wc[1]) for p in pts)
                gates.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, far))
    main = max(gates, key=lambda g: g[2]) if gates else (wc[0], wc[1] + 1, 0)
    # transform: centre on the walls, flip y (MFCG y points down), rotate main gate to -45 deg (toward the camera)
    gx, gy = main[0] - wc[0], -(main[1] - wc[1])
    rot = math.radians(-45) - math.atan2(gy, gx)
    cr, sr = math.cos(rot), math.sin(rot)

    def T(p):
        x, y = (p[0] - wc[0]) * SCALE, -(p[1] - wc[1]) * SCALE
        return [round(x * cr - y * sr, 3), round(x * sr + y * cr, 3)]

    walls = [[T(p) for p in g['coordinates'][0]] for g in F['walls']['geometries']]
    gates_t = [T(g[:2]) for g in gates]
    roads = [[T(p) for p in g['coordinates']] for g in F['roads']['geometries']]
    squares = [[T(p) for p in poly[0]] for poly in F['squares']['coordinates']]
    fields = [[T(p) for p in poly[0]] for poly in F['fields']['coordinates']]
    greens = [[T(p) for p in poly[0]] for poly in F['greens']['coordinates']]
    wells = [T(centroid(poly[0])) for poly in F['prisms']['coordinates']]
    wall_t = walls[0] if walls else None
    houses = []
    for i, poly in enumerate(F['buildings']['coordinates'], start=1):
        ring = [T(p) for p in poly[0]]
        cx, cy, L, D, ang = min_rect(ring)
        houses.append({'id': i, 'x': round(cx, 3), 'y': round(cy, 3), 'l': round(L, 3), 'd': round(D, 3), 'a': round(ang, 4),
                       'area': round(area(ring), 3), 'inside': bool(wall_t and inside((cx, cy), wall_t))})
    # story picks
    sq = centroid(squares[0]) if squares else (0, 0)
    dist = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])
    field_pts = [centroid(f) for f in fields]
    taken = {}
    for sid, rule, min_area in STORY.get(cid, []):
        pool = [h for h in houses if h['id'] not in taken.values() and h['area'] >= min_area]
        if rule == 'near_square':
            key = lambda h: dist((h['x'], h['y']), sq)
        elif rule.startswith('near:') and rule[5:] in taken:
            ref = next(h for h in houses if h['id'] == taken[rule[5:]]); key = lambda h: dist((h['x'], h['y']), (ref['x'], ref['y']))
        elif rule == 'near_gate' and gates_t:
            g0 = max(gates_t, key=lambda g: g[0] - g[1]);  # the gate facing the camera key = lambda h: dist((h['x'], h['y']), g0)
        elif rule == 'outside_near_fields':
            pool = [h for h in pool if not h['inside']] or pool
            key = (lambda h: min(dist((h['x'], h['y']), f) for f in field_pts)) if field_pts else (lambda h: -dist((h['x'], h['y']), sq))
        else:
            continue
        h = min(pool, key=key); h['story'] = sid; taken[sid] = h['id']
    out = {'id': cid, 'scale': SCALE, 'walls': walls, 'gates': gates_t, 'roads': roads, 'squares': squares, 'fields': fields,
           'greens': greens, 'wells': wells, 'houses': houses, 'story': taken}
    path = os.path.join(ROOT, 'cities', f'{cid}.plan.json')
    json.dump(out, open(path, 'w'))
    xs = [h['x'] for h in houses]; ys = [h['y'] for h in houses]
    print(f'{cid}: {len(houses)} houses ({sum(h["inside"] for h in houses)} inside walls), {len(fields)} fields, {len(gates_t)} gates,'
          f' extent x {min(xs):.0f}..{max(xs):.0f} y {min(ys):.0f}..{max(ys):.0f}, story {taken}')


if __name__ == '__main__':
    for c in sys.argv[1:] or ['greymark']:
        plan(c)
