"""Slice a sprite sheet (separate objects on a plain background) into individual sprites.

    python3 tools/slice_sheet.py out/ai/rowhouse_set-codex-1.png rowhouse_set [--min 4000]

Writes map/assets/<set>_<k>.png for each object (reading order) and map/assets/<set>.meta.js with
each variant's size, footprint corners (left/right/bottom opaque pixels) and an embedded copy.
"""
import base64, io, json, os, sys
from collections import deque
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src, sid = sys.argv[1], sys.argv[2]
MIN = int(sys.argv[sys.argv.index('--min') + 1]) if '--min' in sys.argv else 4000
im = np.asarray(Image.open(src).convert('RGB')).astype(int)
H, W, _ = im.shape
border = np.concatenate([im[0], im[-1], im[:, 0], im[:, -1]])
bg = np.median(border, axis=0)
TOL = int(sys.argv[sys.argv.index('--tol') + 1]) if '--tol' in sys.argv else 30
fg = np.abs(im - bg).sum(-1) > TOL
fg = ndimage.binary_closing(fg, iterations=6)          # bridge dark shading inside an object
fg = ndimage.binary_fill_holes(fg)
fg = ndimage.binary_opening(fg, iterations=2)          # drop speckle in the background
lab, n = ndimage.label(fg)
boxes = [[sl[0].start, sl[0].stop, sl[1].start, sl[1].stop, [i]] for i, sl in enumerate(ndimage.find_objects(lab), start=1)]
merged = True                                          # merge pieces of one object (stacked, overlapping in x)
while merged:
    merged = False
    for a in boxes:
        for b in boxes:
            if a is b: continue
            ox = min(a[3], b[3]) - max(a[2], b[2])
            gap = max(a[0], b[0]) - min(a[1], b[1])
            if ox > 0.5 * min(a[3] - a[2], b[3] - b[2]) and gap < -2:
                a[0], a[1], a[2], a[3] = min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3]); a[4] += b[4]
                boxes.remove(b); merged = True; break
        if merged: break
items = []
if '--grid' in sys.argv:   # regular grid (cols x rows): each cell is one sprite, even if it has several parts
    gc, gr = map(int, sys.argv[sys.argv.index('--grid') + 1].split('x'))
    boxes = []
    for r in range(gr):
        for c in range(gc):
            cy0, cy1, cx0, cx1 = r * H // gr, (r + 1) * H // gr, c * W // gc, (c + 1) * W // gc
            cell = fg[cy0:cy1, cx0:cx1]
            ys_, xs_ = np.nonzero(cell)
            if len(ys_) == 0: continue
            boxes.append([cy0 + ys_.min(), cy0 + ys_.max() + 1, cx0 + xs_.min(), cx0 + xs_.max() + 1, None])
    for y0, y1, x0, x1, _ in boxes:
        sl = (slice(y0, y1), slice(x0, x1)); items.append((sl, fg[sl]))
    boxes = []
for y0, y1, x0, x1, ids in boxes:
    sl = (slice(y0, y1), slice(x0, x1))
    m = np.isin(lab[sl], ids)
    m = ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=8))
    if m.sum() < MIN: continue
    items.append((sl, m))
if '--grid' not in sys.argv: items.sort(key=lambda t: (round(t[0][0].start / (H / 4)), t[0][1].start))   # rows, then left to right
variants = []
os.makedirs(os.path.join(ROOT, 'map', 'assets'), exist_ok=True)
for k, (sl, m) in enumerate(items):
    crop = im[sl].astype(np.uint8)
    rgba = np.dstack([crop, (m * 255).astype(np.uint8)])
    h, w = m.shape
    ys, xs = np.nonzero(m)
    meta = {'w': w, 'h': h,
            'left': [int(xs.min()), int(ys[xs == xs.min()].mean())],
            'right': [int(xs.max()), int(ys[xs == xs.max()].mean())],
            'bottom': [int(xs[ys == ys.max()].mean()), int(ys.max())]}
    img = Image.fromarray(rgba, 'RGBA'); img.save(os.path.join(ROOT, 'map', 'assets', f'{sid}_{k}.png'))
    small = img if w <= 420 else img.resize((420, round(h * 420 / w)), Image.LANCZOS)
    buf = io.BytesIO(); small.save(buf, 'PNG', optimize=True)
    meta['src'] = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    variants.append(meta)
    print(f'{sid}_{k}: {w}x{h}', 'bottom', meta['bottom'])
with open(os.path.join(ROOT, 'map', 'assets', f'{sid}.meta.js'), 'w') as f:
    f.write('window.ASSET_META = window.ASSET_META || {};\n')
    f.write(f'window.ASSET_META[{json.dumps(sid)}] = {{"variants": {json.dumps(variants)}}};\n')
print(len(variants), 'variants')
