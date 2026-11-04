"""Downscale a flat-colour render to chunky pixel art: each output pixel takes the most common
colour of its block (no blending), so the 4-shade palette survives exactly.

    python3 tools/pixelize_flat.py render.png out.png --width 400 [--preview 3]
"""
import sys
import numpy as np
from PIL import Image

a = sys.argv[1:]; src, dst = a[0], a[1]
W = int(a[a.index('--width') + 1]) if '--width' in a else 400
PV = int(a[a.index('--preview') + 1]) if '--preview' in a else 3
im = Image.open(src).convert('RGB')
arr = np.asarray(im).astype(np.int64)
key = (arr[..., 0] << 16) | (arr[..., 1] << 8) | arr[..., 2]
k = im.width / W; H = int(im.height / k)
out = np.zeros((H, W), np.int64)
dark = key.copy() * 0
lum = arr.sum(-1)
for y in range(H):
    y0, y1 = int(y * k), max(int(y * k) + 1, int((y + 1) * k))
    for x in range(W):
        x0, x1 = int(x * k), max(int(x * k) + 1, int((x + 1) * k))
        blk = key[y0:y1, x0:x1].ravel(); bl = lum[y0:y1, x0:x1].ravel()
        if (bl < 90).sum() * 4 >= blk.size:      # keep outlines: a quarter of the block is line -> line pixel
            out[y, x] = blk[bl.argmin()]; continue
        v, c = np.unique(blk, return_counts=True); out[y, x] = v[c.argmax()]
rgb = np.stack([(out >> 16) & 255, (out >> 8) & 255, out & 255], -1).astype(np.uint8)
img = Image.fromarray(rgb, 'RGB'); img.save(dst)
if PV: img.resize((W * PV, H * PV), Image.NEAREST).save(dst.replace('.png', f'@{PV}x.png'))
print(dst, (W, H), 'colours', len(np.unique(out)))
