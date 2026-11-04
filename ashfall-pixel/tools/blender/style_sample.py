"""A small, spacious corner of Greymark to judge an art style before building the whole town.

    <bpy-venv>/bin/python tools/blender/style_sample.py out.png --flat [--size 1600]

Simple style rules: flat colours (4 shades per material), dark outlines (Freestyle), wide
streets, yards and gardens between houses, ground that fills the frame (no void, nothing floating).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import *  # noqa: F401,F403

for nm, cols in [('road', ['#6a4a2e', '#86603c', '#a07a4c']), ('hedge', ['#1e3a22', '#2d5432']), ('fence', ['#4a2e1a', '#6a4428']),
                 ('field2', ['#3a5a46', '#4a7058']), ('field3', ['#8a7034', '#a88a44']), ('water', ['#2a5a7a', '#5aa0c0'])]:
    M[nm] = mat(nm, cols, 'noise', 4, 0.1)

# ground that runs past the frame on every side
box(120, 120, 0.2, (0, 0, -0.1), M['grass'], name='ground')
# a wide main street (cobbles) with a dirt lane branching off
box(40, 3.2, 0.06, (0, -1.0, 0.03), M['cobble'], rot=(0, 0, math.radians(0)), name='street')
box(3.0, 26, 0.05, (-1.5, 9.0, 0.025), M['road'], name='lane')
# the little square with the well
cyl(3.2, 0.07, (5.5, -1.0, 0.035), M['cobble'], 16)
cyl(0.8, 0.6, (5.5, -1.0, 0.3), M['stone'], 12); cyl(0.66, 0.05, (5.5, -1.0, 0.58), M['redwater'], 12)
for dx in (-0.7, 0.7): box(0.12, 0.12, 1.5, (5.5 + dx, -1.0, 0.95), M['timber'])
gable_roof(1.6, 1.0, 0.45, 0.1, (5.5, -1.0, 1.7), M['thatch_dark'], name='well_roof')
figure(6.9, -2.2, M['robe'], hood=True, s=1.1)
for i, c in enumerate(['cloth_b', 'cloth_w', 'cloth_r', 'cloth_b']):
    figure(8.0 + i * 0.6, -1.6 - i * 0.35, M[c], s=1.0)

# houses on generous plots: house + yard + fence + a garden or a tree
plots = [(-9.0, 3.4, 0, 'thatch'), (-3.6, 3.6, 0, 'slate'), (3.0, 4.2, 0, 'thatch_dark'),
         (-8.0, -5.6, math.pi, 'thatch'), (-1.8, -5.8, math.pi, 'thatch_dark'), (11.0, 3.8, 0, 'thatch'),
         (-6.0, 11.5, math.pi / 2, 'thatch'), (3.2, 11.0, -math.pi / 2, 'slate')]
for i, (x, y, rot, roof) in enumerate(plots):
    w, d = 3.2, 2.3
    storeys = 2 if i % 3 != 2 else 1
    timber_house(x, y, w, d, 1.0 * storeys + 0.2, rot=rot, roof=roof, storeys=storeys, seed=i + 1, lit=0.4)
    # back yard: picket fence round a garden plot
    c, s = math.cos(rot), math.sin(rot)
    def rel(dx, dy): return x + dx * c - dy * s, y + dx * s + dy * c
    for k in range(9):
        px, py = rel(-2.2 + k * 0.55, 3.6); box(0.1, 0.1, 0.55, (px, py, 0.28), M['fence'])
    for k in range(5):
        for side in (-1, 1):
            px, py = rel(side * 2.2, 1.6 + k * 0.5); box(0.1, 0.1, 0.55, (px, py, 0.28), M['fence'])
    gx, gy = rel(0.0, 2.6)
    box(3.6, 1.6, 0.08, (gx, gy, 0.04), M['field2'] if i % 2 else M['soil'], rot=(0, 0, rot))
    for k in range(6):  # cabbage rows
        px, py = rel(-1.4 + k * 0.56, 2.6); blob(0.18, (px, py, 0.2), M['leaf_g'], seed=i * 10 + k, rough=0.3, subdiv=1)
    if i % 2 == 0:
        tx, ty = rel(3.0, 1.2); tree(tx, ty, 0.9, 'or'[i % 4 == 0], seed=i)
    bx, by = rel(1.9, -1.6); barrel(bx, by)

# a few big trees and a hedge on the edge of town
for i, (tx, ty, k) in enumerate([(-14, 8, 'o'), (14, 10, 'r'), (16, -6, 'o'), (-15, -3, 'g'), (8, 14, 'o')]):
    tree(tx, ty, 1.3, k, seed=50 + i)
for k in range(16):
    blob(0.5, (12 + k * 0.8 * 0.0, -8 - k * 0.0, 0.3), M['hedge'], seed=200 + k, rough=0.3, subdiv=1) if False else None
lantern_post(1.5, -3.2); lantern_post(9.5, 1.2)

# Freestyle outlines: dark, ~1 output pixel thick after downscaling
scene.render.use_freestyle = True
scene.render.line_thickness_mode = 'ABSOLUTE'
vl = scene.view_layers[0]; vl.use_freestyle = True
fs = vl.freestyle_settings; fs.crease_angle = math.radians(140)
ls = fs.linesets[0] if fs.linesets else fs.linesets.new('lines')
ls.select_by_visibility = True; ls.select_by_edge_types = True
ls.select_silhouette = True; ls.select_border = True; ls.select_crease = True
ls.linestyle = ls.linestyle or bpy.data.linestyles.new('ink')
ls.linestyle.color = (0.06, 0.04, 0.03); ls.linestyle.thickness = max(1.0, SIZE / 520)

finish(30.0, target=(1.0, 2.0, 0), res=(SIZE, int(SIZE * 0.66)))
