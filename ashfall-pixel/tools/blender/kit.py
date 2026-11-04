"""Shared Blender kit for Ashfall dioramas (import with `from kit import *`).

Originally the Greymark square script; see greymark_square.py / greymark_town.py.

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
TOON = '--toon' in args or '--flat' in args  # flat palette shading: every face gets an exact palette colour
FLAT = '--flat' in args    # simple daytime style: 4 hand-picked shades per material
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


def timber_house(x, y, w, d, h, rot=0.0, roof='thatch', storeys=2, plaster='plaster', chimney=True, lit=0.5, seed=0, name='house', lite=False):
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
            n = 1 if lite else max(2, int(length / 0.55))
            for i in range(n + 1):
                t = -length / 2 + i * length / n
                if face == 0: p = (t, -dd / 2 - 0.02, z0 + sh / 2)
                elif face == 1: p = (t, dd / 2 + 0.02, z0 + sh / 2)
                elif face == 2: p = (-ww / 2 - 0.02, t, z0 + sh / 2)
                else: p = (ww / 2 + 0.02, t, z0 + sh / 2)
                box(T if face < 2 else T, T if face < 2 else T, sh, p, M['timber'], parent=root)
                # diagonal brace in alternating panels
                if not lite and i < n and (i + s) % 2 == 0:
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
            for i in range(1 if lite else max(1, int(length / 1.1))):
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


# simple daytime style: per material [shadow, mid, lit, highlight]
FLAT_RAMPS = {
    'grass': ['#3a5a2a', '#4f7a34', '#62903c', '#78a648'], 'soil': ['#3a2618', '#523822', '#6a4a2c', '#80603a'],
    'cobble': ['#5a5652', '#7a746c', '#968e84', '#b0a89a'], 'dirt': ['#6a4a2e', '#86603c', '#a07a4c', '#b8925e'],
    'road': ['#6a4a2e', '#86603c', '#a07a4c', '#b8925e'], 'plaster': ['#a8987a', '#cfc0a0', '#e8dcc0', '#f6eedc'],
    'plaster2': ['#9a8466', '#bca684', '#d4c09c', '#e6d6b4'], 'timber': ['#24160e', '#3a2416', '#4e3220', '#62422c'],
    'wood': ['#4a2e1a', '#6a4428', '#8a5c34', '#a87440'], 'fence': ['#4a2e1a', '#6a4428', '#8a5c34', '#a87440'],
    'thatch': ['#6a5028', '#8a6c34', '#a88a44', '#c4a656'], 'thatch_dark': ['#4a3820', '#64502c', '#806838', '#9a8046'],
    'slate': ['#2e3640', '#404a58', '#56626e', '#6e7a86'], 'stone': ['#5a5a5a', '#76746e', '#928e86', '#aca69c'],
    'bone': ['#a8a090', '#c8c0ae', '#e0d8c6', '#f2ecdc'], 'moss': ['#2e4a22', '#3e6030', '#527a3c', '#6a9448'],
    'iron': ['#1e1e22', '#2e2e34', '#40404a', '#54545e'], 'leaf_o': ['#8a3a18', '#b8541f', '#e0762b', '#f4a04a'],
    'leaf_r': ['#6a1e18', '#9a2e22', '#c4482c', '#e06a3a'], 'leaf_g': ['#1e3a22', '#2d5432', '#3f6e3a', '#5a8a42'],
    'hedge': ['#1e3a22', '#2d5432', '#3f6e3a', '#5a8a42'], 'bark': ['#2e1e14', '#3e2a1c', '#52382a', '#664838'],
    'flax': ['#3a5a5a', '#4f7a7a', '#6c9ab0', '#8ab8c8'], 'field': ['#3e2c1c', '#523a26', '#6a4c30', '#80603a'],
    'field2': ['#3a5a46', '#4a7058', '#5e8a6c', '#7aa88a'], 'field3': ['#8a7034', '#a88a44', '#c4a656', '#dcc070'],
    'robe': ['#1c1c22', '#2a2a32', '#3a3a44', '#4a4a56'], 'cloak': ['#2a1e26', '#3b2a3a', '#4e3448', '#62405a'],
    'cloth_b': ['#2a3a5a', '#3a5078', '#5a70a0', '#7a90c0'], 'cloth_w': ['#8a8478', '#b8b0a0', '#d8d0c0', '#eee8da'],
    'cloth_r': ['#5a1e1a', '#7a2e24', '#9a4030', '#b8583e'], 'skin': ['#a8785a', '#c48e6a', '#d9a77c', '#ecc49a'],
    'paper': ['#c8bca0', '#d8ccb0', '#efe6d0', '#fff8e8'], 'linen': ['#8a8478', '#b8b0a0', '#d8d0c0', '#eee8da'],
    'dye': ['#1e2c5a', '#2a3f7a', '#3a56a0', '#5070c0'], 'water': ['#2a5a7a', '#3a7aa0', '#5aa0c0', '#8ac8e0'],
    'awning': ['#7a2e24', '#a8432f', '#c85a3a', '#e9dfc4'], 'burnt': ['#0e0a0a', '#1e1614', '#2e2420', '#3e322c'],
}
FLAT_WARM = {'glass': '#ffd060', 'lamp': '#fff0a0', 'fire': '#ff8a2a', 'redwater': '#a8342e', 'gold': '#e8c050'}


def toonify(m):
    nt = m.node_tree; N = nt.nodes; L = nt.links
    for n in list(N): N.remove(n)
    out = N.new('ShaderNodeOutputMaterial'); em = N.new('ShaderNodeEmission'); L.new(em.outputs[0], out.inputs['Surface'])
    name = m.name
    warm = FLAT_WARM if FLAT else TOON_WARM
    if name in warm:
        em.inputs['Color'].default_value = hexc(warm[name]); return
    base, pat, sc = TOON_BASE.get(name, (3, None, 0))
    ramp_cols = TOON_RAMP
    if FLAT:  # 4 shades: mid face = index 1-2, light step -1..+2, pattern line -1
        ramp_cols = FLAT_RAMPS.get(name, FLAT_RAMPS['stone']); base = 1
        if pat == 'noise': pat = None  # flat style: no speckle on grass, leaves, dirt
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
    lvl = math('FLOOR', math('ADD', math('MULTIPLY', dot.outputs['Value'], 2.0 if FLAT else 3.0), 0.5))
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
    n_ = len(ramp_cols)
    fac = math('DIVIDE', math('ADD', lvl, 0.5), float(n_))
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.interpolation = 'CONSTANT'
    el = ramp.color_ramp.elements
    el[0].position = 0.0; el[0].color = hexc(ramp_cols[0]); el[1].position = (n_ - 1) / n_; el[1].color = hexc(ramp_cols[-1])
    for i in range(1, n_ - 1):
        e = el.new(i / n_); e.color = hexc(ramp_cols[i])
    L.new(fac, ramp.inputs['Fac']); L.new(ramp.outputs['Color'], em.inputs['Color'])



# ------------------------------------------------------------ finishing ---
def finish(ortho_scale, target=(0.0, 0.0, 0.0), res=None, shift_y=0.0):
    """Light, camera (classic 2:1 iso from the south-east), optional toon, overlay points, render."""
    import json
    from bpy_extras.object_utils import world_to_camera_view
    rx, ry = res or (SIZE, SIZE)
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 5.2; sun.color = (1.0, 0.78, 0.55); sun.angle = math.radians(3)
    so = bpy.data.objects.new('sun', sun); bpy.context.collection.objects.link(so)
    so.rotation_euler = (math.radians(55), 0, math.radians(-35))  # low warm dusk light from the left
    if NIGHT:
        sun.energy = 4.5; sun.color = (0.85, 0.92, 1.0); bg.inputs['Strength'].default_value = 0.35
        so.rotation_euler = (math.radians(42), 0, math.radians(-15))
    cam = bpy.data.cameras.new('cam'); cam.type = 'ORTHO'; cam.ortho_scale = ortho_scale; cam.shift_y = shift_y
    cam.clip_end = 500
    co = bpy.data.objects.new('cam', cam); bpy.context.collection.objects.link(co); scene.camera = co
    co.rotation_euler = (math.radians(60), 0, math.radians(45))  # 60 deg tilt, 45 deg turn = 2:1 isometric
    d = 120
    tx, ty, tz = target
    co.location = (tx + d * math.sin(math.radians(60)) * math.sin(math.radians(45)), ty - d * math.sin(math.radians(60)) * math.cos(math.radians(45)), tz + d * math.cos(math.radians(60)))
    if TOON:
        for m in bpy.data.materials: toonify(m)
        for ob in bpy.data.objects:
            if ob.type == 'LIGHT': ob.hide_render = True
        bg.inputs['Strength'].default_value = 0.0
        scene.cycles.samples = 4; scene.cycles.use_denoising = False
        scene.render.filter_size = 0.01; scene.view_settings.exposure = 0.0
    bpy.context.view_layer.update()
    for kind, o, off in TRACK:
        POINTS[kind].append(tuple(o.matrix_world.translation + Vector(off)))
    def to_px(p):
        v = world_to_camera_view(scene, co, Vector(p))
        return [round(v.x * rx, 1), round((1 - v.y) * ry, 1)]
    proj = {k: ([to_px(p) for p in v] if isinstance(v, list) else {kk: to_px(pp) for kk, pp in v.items()}) for k, v in POINTS.items()}
    with open(OUT.replace('.png', '.json'), 'w') as f:
        json.dump({'size': [rx, ry], 'points': proj}, f)
    scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)
    print('rendered', OUT)
