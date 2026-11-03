"""Greymark square as a 3D diorama, rendered for a pre-rendered isometric pixel look.

Run with Blender's Python module (bpy 5.x):
    <venv-with-bpy>/bin/python tools/blender/greymark_diorama.py [out.png] [--size 1400] [--samples 32]

Everything is built from code: a hexagonal floating slab, cobbled square, the red
town well with Aldren's ledger table, timber-framed thatched houses, the Broken
Compass, Vex's mill with its treadwheel, a dark-timber palisade with a bone-white
stone gate, autumn trees, barrels, crates, lanterns. Then tools/pixelize.py turns
the render into pixel art (downscale, palette, outlines).
"""
import math
import random
import sys

import bpy
import bmesh
from mathutils import Vector

args = sys.argv[1:]
OUT = next((a for a in args if a.endswith('.png')), '/tmp/greymark_render.png')
SIZE = int(args[args.index('--size') + 1]) if '--size' in args else 1400
SAMPLES = int(args[args.index('--samples') + 1]) if '--samples' in args else 32
NIGHT = '--night' in args  # cool moonlight for the limited-palette night style
TOON = '--toon' in args    # flat palette shading: every face gets an exact palette colour
rnd = random.Random(1337)
POINTS = {'lamps': [], 'fires': [], 'chimneys': [], 'windows': [], 'water': [], 'labels': {}}
TRACK = []  # (kind, object, offset) resolved after the scene is built

# ------------------------------------------------------------------ scene ---
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x = SIZE
scene.render.resolution_y = SIZE
scene.render.filter_size = 0.8
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.view_settings.exposure = 0.2

world = bpy.data.worlds.new('World'); scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs['Color'].default_value = (0.20, 0.24, 0.36, 1)  # dusk sky fill
bg.inputs['Strength'].default_value = 1.4

# ------------------------------------------------------------- materials ---
MATS = {}


def hexc(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x ** 2.2 for x in c) + (1,)  # sRGB -> linear


def mat(name, colors, tex='noise', scale=6.0, bump=0.3, rough=0.85, emit=None, emit_strength=0.0, detail=6.0):
    """Material = colour ramp driven by a procedural texture (+ bump)."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    bsdf = N['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = rough
    coord = N.new('ShaderNodeTexCoord')
    if tex == 'voronoi':
        t = N.new('ShaderNodeTexVoronoi'); t.inputs['Scale'].default_value = scale; out = t.outputs['Distance']
    elif tex == 'wave':
        t = N.new('ShaderNodeTexWave'); t.inputs['Scale'].default_value = scale; t.inputs['Distortion'].default_value = 6
        t.inputs['Detail'].default_value = detail; out = t.outputs['Fac']
    elif tex == 'brick':
        t = N.new('ShaderNodeTexBrick'); t.inputs['Scale'].default_value = scale
        t.inputs['Color1'].default_value = (1, 1, 1, 1); t.inputs['Color2'].default_value = (0.7, 0.7, 0.7, 1)
        t.inputs['Mortar'].default_value = (0, 0, 0, 1); out = t.outputs['Color']
    else:
        t = N.new('ShaderNodeTexNoise'); t.inputs['Scale'].default_value = scale; t.inputs['Detail'].default_value = detail
        out = t.outputs['Fac']
    L.new(coord.outputs['Object'], t.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB')
    el = ramp.color_ramp.elements
    el[0].color = hexc(colors[0]); el[1].color = hexc(colors[-1])
    for i, c in enumerate(colors[1:-1], start=1):
        e = el.new(i / (len(colors) - 1)); e.color = hexc(c)
    ramp.color_ramp.interpolation = 'CONSTANT'  # banded colours read as pixel clusters
    if tex == 'brick':
        sep = N.new('ShaderNodeRGBToBW'); L.new(out, sep.inputs['Color']); out = sep.outputs['Val']
    L.new(out, ramp.inputs['Fac'])
    L.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    if bump:
        b = N.new('ShaderNodeBump'); b.inputs['Strength'].default_value = bump
        L.new(out, b.inputs['Height']); L.new(b.outputs['Normal'], bsdf.inputs['Normal'])
    if emit:
        bsdf.inputs['Emission Color'].default_value = hexc(emit)
        bsdf.inputs['Emission Strength'].default_value = emit_strength
    MATS[name] = m
    return m


M = {
    'grass': mat('grass', ['#1f3a26', '#2d5432', '#3f6e3a', '#5a8a42', '#7aa04a'], 'noise', 9, 0.4),
    'soil': mat('soil', ['#1e1410', '#33221a', '#4a3324', '#5e4430'], 'wave', 3, 0.6),
    'cobble': mat('cobble', ['#2c2a2c', '#5c5652', '#7a726a', '#8f877c'], 'voronoi', 14, 0.9),
    'dirt': mat('dirt', ['#4a3324', '#6a4a30', '#86603c'], 'noise', 10, 0.5),
    'plaster': mat('plaster', ['#b8ab92', '#d2c6aa', '#e2d8c0'], 'noise', 18, 0.15),
    'plaster2': mat('plaster2', ['#a89272', '#c2ad88', '#d4c29e'], 'noise', 18, 0.15),
    'timber': mat('timber', ['#1e140e', '#2e1e14', '#3e2a1c'], 'wave', 20, 0.3),
    'wood': mat('wood', ['#3e2618', '#5a3820', '#7a5230'], 'wave', 12, 0.3),
    'thatch': mat('thatch', ['#2e2214', '#4e3c22', '#6e5630', '#8e7442', '#b09858'], 'wave', 7, 1.6, detail=14),
    'thatch_dark': mat('thatch_dark', ['#1c160e', '#2e2418', '#4a3a24', '#5e4a2e', '#7a6440'], 'wave', 7, 1.6, detail=14),
    'slate': mat('slate', ['#1a1e24', '#2c343e', '#3e4852', '#56606a'], 'brick', 9, 0.8),
    'stone': mat('stone', ['#3c4046', '#5c636a', '#7e858a', '#9aa0a2'], 'voronoi', 8, 0.8),
    'bone': mat('bone', ['#a8a090', '#cfc6b4', '#e9dfc4'], 'voronoi', 6, 0.5),
    'moss': mat('moss', ['#2a3a1e', '#3e5428', '#55703a'], 'noise', 20, 0.6),
    'redwater': mat('redwater', ['#4a141c', '#7e2229', '#a8342e'], 'noise', 4, 0.05, 0.15, '#b8423a', 0.6),
    'glass': mat('glass', ['#ffc94a', '#ff9a3a'], 'noise', 4, 0, 0.5, '#ffb050', 6.0),
    'lamp': mat('lamp', ['#ffe08a', '#ffc94a'], 'noise', 4, 0, 0.5, '#ffd070', 25.0),
    'fire': mat('fire', ['#ffcf5a', '#ff8a2a'], 'noise', 4, 0, 0.5, '#ff8a2a', 30.0),
    'iron': mat('iron', ['#1a1a1e', '#2c2c32', '#3e3e46'], 'noise', 10, 0.2, 0.5),
    'leaf_o': mat('leaf_o', ['#5a1c10', '#8a2e18', '#b84a1f', '#e0762b', '#f4ae4c'], 'noise', 7, 0.9),
    'leaf_r': mat('leaf_r', ['#3a1010', '#6a1c18', '#9a2e22', '#c4482c'], 'noise', 7, 0.9),
    'leaf_g': mat('leaf_g', ['#14261a', '#1f3a26', '#2d5432', '#4a6e34'], 'noise', 7, 0.9),
    'bark': mat('bark', ['#1e140e', '#2e2016', '#3e2c1e'], 'wave', 30, 0.6),
    'flax': mat('flax', ['#3a5a3a', '#4f7a52', '#6c8fb0', '#8aa6c8'], 'noise', 30, 0.5),
    'robe': mat('robe', ['#1c1c22', '#2a2a32', '#3a3a44'], 'noise', 12, 0.2),
    'cloak': mat('cloak', ['#2a1e26', '#3b2a3a', '#4e3448'], 'noise', 12, 0.2),
    'cloth_b': mat('cloth_b', ['#2a3a5a', '#3a5078', '#5a70a0'], 'noise', 12, 0.2),
    'cloth_w': mat('cloth_w', ['#a8a090', '#d8d0c0'], 'noise', 12, 0.2),
    'cloth_r': mat('cloth_r', ['#5a1e1a', '#7a2e24'], 'noise', 12, 0.2),
    'skin': mat('skin', ['#a8785a', '#d9a77c'], 'noise', 12, 0.1),
    'paper': mat('paper', ['#d8ccb0', '#efe6d0'], 'noise', 30, 0.1),
    'gold': mat('gold', ['#8a6a20', '#d9b350', '#ffe08a'], 'noise', 20, 0.2, 0.3),
    'linen': mat('linen', ['#c8c0b0', '#e8e0d0', '#6c8fb0'], 'noise', 6, 0.1),
}


# ------------------------------------------------------------- geometry ---
def obj_from(mesh_name, bm, material, loc=(0, 0, 0), rot_z=0.0):
    me = bpy.data.meshes.new(mesh_name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(mesh_name, me); bpy.context.collection.objects.link(o)
    o.location = loc; o.rotation_euler[2] = rot_z
    if material: me.materials.append(material)
    return o


def box(sx, sy, sz, loc, material, rot=(0, 0, 0), name='box', parent=None):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    o = obj_from(name, bm, material, loc)
    o.rotation_euler = rot
    if parent: o.parent = parent
    return o


def cyl(r, h, loc, material, verts=12, r2=None, rot=(0, 0, 0), name='cyl', parent=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r if r2 is None else r2, depth=h)
    o = obj_from(name, bm, material, loc); o.rotation_euler = rot
    if parent: o.parent = parent
    return o


def blob(r, loc, material, seed=0, rough=0.35, subdiv=2, name='blob', squash=1.0):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    rr = random.Random(seed)
    for v in bm.verts:
        k = 1 + (rr.random() - 0.5) * rough
        v.co = Vector((v.co.x * k, v.co.y * k, v.co.z * k * squash))
    o = obj_from(name, bm, material, loc)
    for f in o.data.polygons: f.use_smooth = False
    return o


def gable_roof(w, d, h, overhang, loc, material, rot_z=0.0, name='roof'):
    """Gable roof prism: ridge along local X. w = length, d = depth."""
    W, D = w / 2 + overhang, d / 2 + overhang
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in [(-W, -D, 0), (W, -D, 0), (W, D, 0), (-W, D, 0), (-W, 0, h), (W, 0, h)]]
    bm.faces.new([v[0], v[1], v[5], v[4]]); bm.faces.new([v[2], v[3], v[4], v[5]])
    bm.faces.new([v[0], v[4], v[3]]); bm.faces.new([v[1], v[2], v[5]]); bm.faces.new([v[0], v[3], v[2], v[1]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # thickness for chunky thatch eaves
    o = obj_from(name, bm, material, loc, rot_z)
    sol = o.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.16
    if material.name.startswith('thatch'):  # lumpy straw: subdivide + displace
        sub = o.modifiers.new('sub', 'SUBSURF'); sub.subdivision_type = 'SIMPLE'; sub.levels = sub.render_levels = 4
        tx = bpy.data.textures.new(name + '_n', 'CLOUDS'); tx.noise_scale = 0.18
        dsp = o.modifiers.new('disp', 'DISPLACE'); dsp.texture = tx; dsp.strength = 0.07
    ridge = box(w + 2 * overhang, 0.12, 0.12, (0, 0, h + 0.05), M['timber'], name=name + '_ridge'); ridge.parent = o
    return o


def timber_house(x, y, w, d, h, rot=0.0, roof='thatch', storeys=2, plaster='plaster', chimney=True, lit=0.5, seed=0, name='house'):
    rr = random.Random(seed)
    root = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(root)
    root.location = (x, y, 0); root.rotation_euler[2] = rot
    sh = h / storeys
    # stone plinth
    box(w + 0.1, d + 0.1, 0.25, (0, 0, 0.125), M['stone'], parent=root)
    for s in range(storeys):
        jet = 0.12 * s  # upper storeys jut out
        ww, dd, z0 = w + jet, d + jet, 0.25 + s * sh
        box(ww, dd, sh, (0, 0, z0 + sh / 2), M[plaster], parent=root)
        T = 0.07
        # sill + plate beams
        for zz in (z0 + 0.03, z0 + sh - 0.03):
            box(ww + 0.04, T, T, (0, -dd / 2 - 0.01, zz), M['timber'], parent=root)
            box(ww + 0.04, T, T, (0, dd / 2 + 0.01, zz), M['timber'], parent=root)
            box(T, dd + 0.04, T, (-ww / 2 - 0.01, 0, zz), M['timber'], parent=root)
            box(T, dd + 0.04, T, (ww / 2 + 0.01, 0, zz), M['timber'], parent=root)
        # posts + braces on all four faces
        for face in range(4):
            length = ww if face < 2 else dd
            n = max(2, int(length / 0.55))
            for i in range(n + 1):
                t = -length / 2 + i * length / n
                if face == 0: p = (t, -dd / 2 - 0.02, z0 + sh / 2)
                elif face == 1: p = (t, dd / 2 + 0.02, z0 + sh / 2)
                elif face == 2: p = (-ww / 2 - 0.02, t, z0 + sh / 2)
                else: p = (ww / 2 + 0.02, t, z0 + sh / 2)
                box(T if face < 2 else T, T if face < 2 else T, sh, p, M['timber'], parent=root)
                # diagonal brace in alternating panels
                if i < n and (i + s) % 2 == 0:
                    ang = math.atan2(sh * 0.9, length / n) * (1 if (i % 4 == 0) else -1)
                    mid = t + length / n / 2
                    L = math.hypot(sh * 0.9, length / n)
                    if face < 2:
                        yy = -dd / 2 - 0.025 if face == 0 else dd / 2 + 0.025
                        box(L, 0.05, 0.05, (mid, yy, z0 + sh / 2), M['timber'], rot=(0, -ang, 0), parent=root)
                    else:
                        xx = -ww / 2 - 0.025 if face == 2 else ww / 2 + 0.025
                        box(0.05, L, 0.05, (xx, mid, z0 + sh / 2), M['timber'], rot=(ang, 0, 0), parent=root)
        # windows
        for face in (0, 2):
            length = ww if face == 0 else dd
            for i in range(max(1, int(length / 1.1))):
                t = -length / 2 + (i + 0.5) * length / max(1, int(length / 1.1))
                glow = M['glass'] if rr.random() < lit else M['iron']
                if face == 0: p = (t + 0.15, -dd / 2 - 0.04, z0 + sh * 0.55); sz = (0.26, 0.04, 0.3)
                else: p = (-ww / 2 - 0.04, t + 0.15, z0 + sh * 0.55); sz = (0.04, 0.26, 0.3)
                wo = box(*sz, p, glow, parent=root)
                if glow is M['glass']: TRACK.append(('windows', wo, (0, 0, 0)))
    # door
    box(0.36, 0.06, 0.62, (-w / 4, -d / 2 - 0.05, 0.25 + 0.31), M['wood'], parent=root)
    # roof
    top = 0.25 + storeys * sh
    rmat = M['thatch'] if roof == 'thatch' else (M['thatch_dark'] if roof == 'thatch_dark' else M['slate'])
    r = gable_roof(w + 0.12 * (storeys - 1), d + 0.12 * (storeys - 1), d * 0.75, 0.22, (0, 0, top), rmat, name=name + '_roof'); r.parent = root
    if chimney:
        ch = box(0.3, 0.3, 1.1, (w * 0.3, d * 0.15, top + 0.45), M['stone'], parent=root)
        TRACK.append(('chimneys', ch, (0, 0, 0.6)))
    return root


def tree(x, y, s=1.0, kind='o', seed=0):
    rr = random.Random(seed)
    cyl(0.12 * s, 1.4 * s, (x, y, 0.7 * s), M['bark'], 7, r2=0.07 * s)
    leaf = {'o': M['leaf_o'], 'r': M['leaf_r'], 'g': M['leaf_g']}[kind]
    for i in range(7):
        a = rr.random() * math.tau; d = rr.random() * 0.55 * s
        blob((0.45 + rr.random() * 0.3) * s, (x + math.cos(a) * d, y + math.sin(a) * d, (1.6 + rr.random() * 0.8) * s), leaf, seed=seed * 13 + i, rough=0.5, subdiv=2)


def pine(x, y, s=1.0):
    cyl(0.08 * s, 0.6 * s, (x, y, 0.3 * s), M['bark'], 6)
    for i in range(4):
        cyl((0.7 - i * 0.14) * s, 0.7 * s, (x, y, (0.8 + i * 0.45) * s), M['leaf_g'], 8, r2=0.0)


def figure(x, y, robe, head=True, s=1.0, hood=False, rot=0.0):
    cyl(0.17 * s, 0.62 * s, (x, y, 0.31 * s), robe, 8, r2=0.1 * s)
    blob(0.1 * s, (x, y, 0.72 * s), M['skin'] if not hood else robe, rough=0.1, subdiv=1)
    if hood: cyl(0.12 * s, 0.16 * s, (x, y, 0.78 * s), robe, 8, r2=0.03 * s)


def barrel(x, y):
    cyl(0.17, 0.42, (x, y, 0.21), M['wood'], 10, r2=0.17)
    for z in (0.08, 0.34): cyl(0.178, 0.03, (x, y, z), M['iron'], 10)


def crate(x, y, rz=0.0, s=0.32):
    box(s, s, s, (x, y, s / 2), M['wood'], rot=(0, 0, rz))


def lantern_post(x, y, h=1.5):
    cyl(0.04, h, (x, y, h / 2), M['iron'], 6)
    box(0.35, 0.04, 0.04, (x + 0.15, y, h), M['iron'])
    box(0.12, 0.12, 0.18, (x + 0.3, y, h - 0.14), M['lamp'])
    POINTS['lamps'].append((x + 0.3, y, h - 0.14))
    L = bpy.data.lights.new('lamp', 'POINT'); L.energy = 18; L.color = (1.0, 0.72, 0.4); L.shadow_soft_size = 0.2
    o = bpy.data.objects.new('lamp', L); bpy.context.collection.objects.link(o); o.location = (x + 0.3, y, h - 0.3)


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

# ---------------------------------------------------------- light + cam ---
sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 5.2; sun.color = (1.0, 0.78, 0.55); sun.angle = math.radians(3)
if NIGHT:
    sun.energy = 4.5; sun.color = (0.85, 0.92, 1.0)
    bg.inputs['Strength'].default_value = 0.35
so = bpy.data.objects.new('sun', sun); bpy.context.collection.objects.link(so)
so.rotation_euler = (math.radians(55), 0, math.radians(-35))  # low warm dusk light from the left
if NIGHT: so.rotation_euler = (math.radians(42), 0, math.radians(-15))  # moon: lit tops + left faces, dark right faces

cam = bpy.data.cameras.new('cam'); cam.type = 'ORTHO'; cam.ortho_scale = 21.0; cam.shift_y = -0.05
co = bpy.data.objects.new('cam', cam); bpy.context.collection.objects.link(co); scene.camera = co
# classic 2:1 isometric: 60 deg tilt, 45 deg turn
co.rotation_euler = (math.radians(60), 0, math.radians(45))
d = 40
co.location = (d * math.sin(math.radians(60)) * math.sin(math.radians(45)), -d * math.sin(math.radians(60)) * math.cos(math.radians(45)), d * math.cos(math.radians(60)) + 0.4)

# ------------------------------------------------------------ toon mode ---
# Replace every material with flat emission in an exact palette colour:
#   colour = ramp[base + 2 (top face) / +1 (left face) / 0 (right face) - pattern line]
# Patterns (bricks, planks, thatch rows, cobbles) are object-space textures -> one level darker.
TOON_RAMP = ['#140c2a', '#1f1a4a', '#2b2c6e', '#353f8a', '#3f5a9e', '#4a7cae', '#56a8bc', '#6fd2c4', '#a8f0d8']
TOON_WARM = {'glass': '#ffc94a', 'lamp': '#fff0a0', 'fire': '#ff8a2a', 'redwater': '#b8423a', 'gold': '#ffc94a'}
TOON_BASE = {  # name: (base level, pattern, pattern scale); final = base + light step (-3..+3)
    'grass': (1, 'noise', 3), 'soil': (2, 'wave', 3), 'cobble': (2, 'voronoi', 7), 'dirt': (1, 'noise', 4),
    'plaster': (4, None, 0), 'plaster2': (3, None, 0), 'timber': (0, None, 0), 'wood': (1, 'wave', 8),
    'thatch': (2, 'rows', 9), 'thatch_dark': (1, 'rows', 9), 'slate': (1, 'brick', 5), 'stone': (2, 'brick', 4),
    'bone': (4, 'brick', 3), 'moss': (2, 'noise', 6), 'iron': (0, None, 0), 'leaf_o': (2, 'noise', 3), 'leaf_r': (2, 'noise', 3),
    'leaf_g': (0, 'noise', 3), 'bark': (0, None, 0), 'flax': (3, None, 0), 'robe': (0, None, 0), 'cloak': (1, None, 0),
    'cloth_b': (3, None, 0), 'cloth_w': (5, None, 0), 'cloth_r': (2, None, 0), 'skin': (5, None, 0), 'paper': (7, None, 0), 'linen': (6, None, 0),
}


def toonify(m):
    nt = m.node_tree; N = nt.nodes; L = nt.links
    for n in list(N): N.remove(n)
    out = N.new('ShaderNodeOutputMaterial'); em = N.new('ShaderNodeEmission'); L.new(em.outputs[0], out.inputs['Surface'])
    name = m.name
    if name in TOON_WARM:
        em.inputs['Color'].default_value = hexc(TOON_WARM[name]); return
    base, pat, sc = TOON_BASE.get(name, (3, None, 0))
    geo = N.new('ShaderNodeNewGeometry'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Normal'], sep.inputs[0])
    def math(op, a, b=None):
        n = N.new('ShaderNodeMath'); n.operation = op
        for i, v in enumerate((a, b)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: L.new(v, n.inputs[i])
        return n.outputs[0]
    # quantised light: moon from above / screen-left -> tops brightest, left faces mid, right faces dark
    dot = N.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
    L.new(geo.outputs['Normal'], dot.inputs[0]); dot.inputs[1].default_value = (-0.25, -0.5, 0.83)
    lvl = math('FLOOR', math('ADD', math('MULTIPLY', dot.outputs['Value'], 3.0), 0.5))
    lvl = math('ADD', lvl, float(base))
    if pat:
        tc = N.new('ShaderNodeTexCoord')
        if pat == 'brick':
            t = N.new('ShaderNodeTexBrick'); t.inputs['Scale'].default_value = sc; t.inputs['Mortar Size'].default_value = 0.05
            L.new(tc.outputs['Object'], t.inputs['Vector']); line = math('GREATER_THAN', t.outputs['Fac'], 0.5)
        elif pat == 'rows':
            t = N.new('ShaderNodeTexWave'); t.wave_type = 'BANDS'; t.bands_direction = 'Z'; t.inputs['Scale'].default_value = sc
            t.inputs['Distortion'].default_value = 1.5; L.new(tc.outputs['Object'], t.inputs['Vector']); line = math('LESS_THAN', t.outputs['Fac'], 0.22)
        elif pat == 'wave':
            t = N.new('ShaderNodeTexWave'); t.inputs['Scale'].default_value = sc; L.new(tc.outputs['Object'], t.inputs['Vector']); line = math('LESS_THAN', t.outputs['Fac'], 0.2)
        elif pat == 'voronoi':
            t = N.new('ShaderNodeTexVoronoi'); t.feature = 'DISTANCE_TO_EDGE'; t.inputs['Scale'].default_value = sc
            L.new(tc.outputs['Object'], t.inputs['Vector']); line = math('LESS_THAN', t.outputs['Distance'], 0.06)
        else:
            t = N.new('ShaderNodeTexNoise'); t.inputs['Scale'].default_value = sc; L.new(tc.outputs['Object'], t.inputs['Vector'])
            line = math('LESS_THAN', t.outputs['Fac'], 0.38)
        lvl = math('SUBTRACT', lvl, line)
    n_ = len(TOON_RAMP)
    fac = math('DIVIDE', math('ADD', lvl, 0.5), float(n_))
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.interpolation = 'CONSTANT'
    el = ramp.color_ramp.elements
    el[0].position = 0.0; el[0].color = hexc(TOON_RAMP[0]); el[1].position = (n_ - 1) / n_; el[1].color = hexc(TOON_RAMP[-1])
    for i in range(1, n_ - 1):
        e = el.new(i / n_); e.color = hexc(TOON_RAMP[i])
    L.new(fac, ramp.inputs['Fac']); L.new(ramp.outputs['Color'], em.inputs['Color'])


if TOON:
    for m in bpy.data.materials: toonify(m)
    for ob in bpy.data.objects:
        if ob.type == 'LIGHT': ob.hide_render = True
    bg.inputs['Strength'].default_value = 0.0
    scene.cycles.samples = 4; scene.cycles.use_denoising = False
    scene.render.filter_size = 0.01
    scene.view_settings.exposure = 0.0

# project tracked points into render pixels for the animation overlay
import json
from bpy_extras.object_utils import world_to_camera_view
bpy.context.view_layer.update()
for kind, o, off in TRACK:
    p = o.matrix_world.translation + Vector(off)
    POINTS[kind].append(tuple(p))
def to_px(p):
    v = world_to_camera_view(scene, co, Vector(p))
    return [round(v.x * SIZE, 1), round((1 - v.y) * SIZE, 1)]
proj = {k: ([to_px(p) for p in v] if isinstance(v, list) else {kk: to_px(pp) for kk, pp in v.items()}) for k, v in POINTS.items()}
with open(OUT.replace('.png', '.json'), 'w') as f:
    json.dump({'size': SIZE, 'points': proj}, f)

scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print('rendered', OUT)
