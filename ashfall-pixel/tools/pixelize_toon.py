"""Downscale a toon render (already in palette colours) to chunky pixel art.

    python3 tools/pixelize_toon.py toon.png out.png --width 240 [--preview 4]

Each output pixel takes the most common palette colour in its block (no blur), then
top edges get a one-step rim light and the silhouette a dark outline.
"""
import json, os, sys
import numpy as np
from PIL import Image

a = sys.argv[1:]; src, dst = a[0], a[1]
W = int(a[a.index('--width') + 1]) if '--width' in a else 240
PV = int(a[a.index('--preview') + 1]) if '--preview' in a else 4
RAMP = ['#140c2a', '#1f1a4a', '#2b2c6e', '#353f8a', '#3f5a9e', '#4a7cae', '#56a8bc', '#6fd2c4', '#a8f0d8']
WARM = ['#b8423a', '#ff8a2a', '#ffc94a', '#fff0a0']
PAL = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in RAMP + WARM])
NR = len(RAMP); OUTLINE = np.array([10, 6, 20])

im = Image.open(src).convert('RGBA'); bbox = im.getbbox(); im = im.crop(bbox)
arr = np.asarray(im).astype(int)
k = im.width / W; H = int(im.height / k)
# palette index per source pixel (nearest colour), -1 = transparent
d = ((arr[..., None, :3] - PAL[None, None]) ** 2).sum(-1)
idx = np.where(arr[..., 3] >= 128, d.argmin(-1), -1)
out_idx = np.full((H, W), -1)
for y in range(H):
    y0, y1 = int(y * k), max(int(y * k) + 1, int((y + 1) * k))
    for x in range(W):
        x0, x1 = int(x * k), max(int(x * k) + 1, int((x + 1) * k))
        blk = idx[y0:y1, x0:x1].ravel()
        vals, cnt = np.unique(blk, return_counts=True)
        warm = vals >= NR
        if warm.any() and cnt[warm].sum() * 6 >= blk.size:  # keep tiny light sources visible
            out_idx[y, x] = vals[warm][cnt[warm].argmax()]
        else:
            out_idx[y, x] = vals[cnt.argmax()]
alpha = out_idx >= 0
up = np.zeros_like(alpha); up[1:] = alpha[:-1]
rim = alpha & ~up & (out_idx < NR)
out_idx = np.where(rim, np.minimum(out_idx + 2, NR - 1), out_idx)
rgb = PAL[np.clip(out_idx, 0, None)]
out = np.zeros((H, W, 4), np.uint8); out[..., :3] = rgb; out[..., 3] = alpha * 255
pad = np.pad(alpha, 1)
near = (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]) & ~alpha
out[near, :3] = OUTLINE; out[near, 3] = 255
img = Image.fromarray(out, 'RGBA'); img.save(dst)
if PV: img.resize((W * PV, H * PV), Image.NEAREST).save(dst.replace('.png', f'@{PV}x.png'))
side = src.replace('.png', '.json')
if os.path.exists(side):
    meta = json.load(open(side)); sc = W / im.width
    tr = lambda p: [round((p[0] - bbox[0]) * sc), round((p[1] - bbox[1]) * sc)]
    pts = {kk: ([tr(p) for p in v] if isinstance(v, list) else {q: tr(pp) for q, pp in v.items()}) for kk, v in meta['points'].items()}
    sid = os.path.basename(dst)[:-4]
    with open(dst.replace('.png', '.js'), 'w') as f:
        f.write('window.SCENES = window.SCENES || {};\nwindow.SCENES[%s] = %s;\n' % (json.dumps(sid), json.dumps({'w': W, 'h': H, 'points': pts})))
print(dst, (W, H))
