"""Cut a generated asset off its plain background and record where its footprint corners are.

    python3 tools/cutout.py out/ai/church_compound-codex-1.png church_compound [--tol 22]

Writes map/assets/<id>.png (transparent) and map/assets/<id>.json with the image positions of the
footprint's left, right and bottom corners (leftmost / rightmost / lowest opaque pixels), which the
engine uses to fit the sprite onto its slot in the layout.
"""
import json, os, sys
from collections import deque
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src, aid = sys.argv[1], sys.argv[2]
tol = int(sys.argv[sys.argv.index('--tol') + 1]) if '--tol' in sys.argv else 22
im = np.asarray(Image.open(src).convert('RGB')).astype(int)
H, W, _ = im.shape
border = np.concatenate([im[0], im[-1], im[:, 0], im[:, -1]])
bg = np.median(border, axis=0)
close = (np.abs(im - bg).sum(-1) <= tol * 3)
# flood fill from the borders through background-coloured pixels only
alpha = np.full((H, W), 255, np.uint8); seen = np.zeros((H, W), bool); q = deque()
for x in range(W):
    for y in (0, H - 1):
        if close[y, x]: q.append((y, x)); seen[y, x] = True
for y in range(H):
    for x in (0, W - 1):
        if close[y, x] and not seen[y, x]: q.append((y, x)); seen[y, x] = True
while q:
    y, x = q.popleft(); alpha[y, x] = 0
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ny, nx = y + dy, x + dx
        if 0 <= ny < H and 0 <= nx < W and not seen[ny, nx] and close[ny, nx]:
            seen[ny, nx] = True; q.append((ny, nx))
rgba = np.dstack([im.astype(np.uint8), alpha])
ys, xs = np.nonzero(alpha)
left = [int(xs.min()), int(ys[xs == xs.min()].mean())]
right = [int(xs.max()), int(ys[xs == xs.max()].mean())]
bottom = [int(xs[ys == ys.max()].mean()), int(ys.max())]
out = os.path.join(ROOT, 'map', 'assets', aid + '.png')
Image.fromarray(rgba, 'RGBA').save(out)
meta = {'w': W, 'h': H, 'left': left, 'right': right, 'bottom': bottom}
# embed a (max 1200 px wide) copy as a data URL: pages opened from disk may draw it AND read its pixels
import base64, io
im_small = Image.fromarray(rgba, 'RGBA'); f = min(1.0, 1200 / W)
if f < 1: im_small = im_small.resize((round(W * f), round(H * f)), Image.LANCZOS)
buf = io.BytesIO(); im_small.save(buf, 'PNG', optimize=True)
meta_js = dict(meta, src='data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode())
json.dump(meta, open(out[:-4] + '.json', 'w'))
open(out[:-4] + '.meta.js', 'w').write('window.ASSET_META = window.ASSET_META || {};\nwindow.ASSET_META[%s] = %s;\n' % (json.dumps(aid), json.dumps(meta_js)))
print(out, 'corners', left, right, bottom, 'opaque', round(alpha.mean() / 2.55), '%')
