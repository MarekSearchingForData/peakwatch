"""Chunky limited-palette pixel style (night ramp + warm accents, ordered dither, rim light).

    python3 tools/pixelize_style.py render.png out.png --width 200 [--preview 4] [--palette night|dusk]

Style target: reference/style-target-night-castle.png — big pixels, ~8-colour hue-shifted
ramp, bright top-edge rim lights, dark outline, Bayer dithering, tiny warm light sources.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

a = sys.argv[1:]
src, dst = a[0], a[1]
W = int(a[a.index('--width') + 1]) if '--width' in a else 200
PV = int(a[a.index('--preview') + 1]) if '--preview' in a else 4
PAL = a[a.index('--palette') + 1] if '--palette' in a else 'night'

hx = lambda h: np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)
RAMPS = {  # dark -> light, hue shifts from indigo to teal like the target
    'night': ['#140c2a', '#1f1a4a', '#2b2c6e', '#353f8a', '#3f5a9e', '#4a7cae', '#56a8bc', '#6fd2c4', '#a8f0d8'],
    'dusk':  ['#120a1c', '#231634', '#36224a', '#4a305a', '#5e4266', '#7a5a6e', '#9a7a72', '#c0a080', '#e8d0a0'],
}
RAMP = [hx(c) for c in RAMPS[PAL]]
WARM = [hx(c) for c in ['#6a1c18', '#b8423a', '#ff8a2a', '#ffc94a', '#fff0a0']]  # torches, windows, red well
OUTLINE = hx('#0a0614')
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0

im = Image.open(src).convert('RGBA')
bbox = im.getbbox(); im = im.crop(bbox)
H = round(im.height * W / im.width); scale = W / im.width
small = np.asarray(im.resize((W, H), Image.BOX)).astype(float)
rgb, alpha = small[..., :3], small[..., 3] >= 128

# luminance -> ramp level (with a little contrast boost), warm light sources kept as accents
lum = (0.3 * rgb[..., 0] + 0.55 * rgb[..., 1] + 0.15 * rgb[..., 2]) / 255.0
lum = np.clip((lum - 0.04) / 0.62, 0, 1) ** 0.85
mx, mn = rgb.max(-1), rgb.min(-1)
sat = (mx - mn) / np.maximum(mx, 1)
warm = (rgb[..., 0] > rgb[..., 2] * 1.5) & (sat > 0.4) & (mx > 205)           # only emissive lamps, windows, fire
red = (rgb[..., 0] > rgb[..., 1] * 1.8) & (rgb[..., 0] > 90) & (sat > 0.55)     # the red well water

n = len(RAMP)
yy, xx = np.mgrid[0:H, 0:W]
t = lum * (n - 1)
# clean shapes first: majority (mode) filter on the undithered levels removes texture speckle
base = np.clip(np.round(t).astype(int), 0, n - 1)
from scipy import ndimage  # noqa: E402
def mode3(x):
    v = x.astype(int); return np.bincount(v, minlength=n).argmax()
base = ndimage.generic_filter(base, mode3, size=3, mode='nearest')
frac = t - np.round(t)  # dither only where the value sits between two levels
lvl = base + (np.abs(frac) > 0.3) * np.sign(frac) * (BAYER[yy % 4, xx % 4] < np.abs(frac) - 0.1)
lvl = np.clip(lvl.astype(int), 1, n - 2)

# rim light: a pixel whose upper (or upper-left) neighbour is empty or much darker gets lifted
up = np.zeros_like(alpha); up[1:] = alpha[:-1]
lvl_up = np.full_like(lvl, -9); lvl_up[1:] = lvl[:-1]
rim = alpha & (~up | (lvl_up <= lvl - 2))
lvl = np.where(rim, np.minimum(lvl + 2, n - 1), lvl)

out = np.zeros((H, W, 4), np.uint8)
ramp_arr = np.array(RAMP)
out[..., :3] = ramp_arr[lvl]
wl = np.clip((lum * 4).astype(int) + 1, 1, 4)
out[..., :3] = np.where(warm[..., None], np.array(WARM)[wl], out[..., :3])
out[..., :3] = np.where(red[..., None] & ~warm[..., None], np.array(WARM)[np.clip(wl - 2, 0, 1)], out[..., :3])
out[..., 3] = np.where(alpha, 255, 0)
# outline around the silhouette
pad = np.pad(alpha, 1)
near = (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]) & ~alpha
out[near] = np.append(OUTLINE, 255)

img = Image.fromarray(out, 'RGBA'); img.save(dst)
if PV: img.resize((W * PV, H * PV), Image.NEAREST).save(dst.replace('.png', f'@{PV}x.png'))
side = src.replace('.png', '.json')
if os.path.exists(side):
    meta = json.load(open(side)); tr = lambda p: [round((p[0] - bbox[0]) * scale), round((p[1] - bbox[1]) * scale)]
    pts = {k: ([tr(p) for p in v] if isinstance(v, list) else {kk: tr(pp) for kk, pp in v.items()}) for k, v in meta['points'].items()}
    data = {'w': W, 'h': H, 'points': pts}
    sid = os.path.basename(dst)[:-4]
    with open(dst.replace('.png', '.js'), 'w') as f:
        f.write('window.SCENES = window.SCENES || {};\nwindow.SCENES[%s] = %s;\n' % (json.dumps(sid), json.dumps(data)))
print(dst, (W, H), PAL, 'colours', len(np.unique(out[alpha][:, :3], axis=0)))
