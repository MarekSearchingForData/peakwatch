"""Turn a high-res render into pixel art: area-downscale, limited palette, dark outline.

    python3 tools/pixelize.py in.png out.png --width 480 --colors 48 [--preview 2]
"""
import json
import os
import sys
from PIL import Image

a = sys.argv[1:]
src, dst = a[0], a[1]
W = int(a[a.index('--width') + 1]) if '--width' in a else 480
NC = int(a[a.index('--colors') + 1]) if '--colors' in a else 48
PV = int(a[a.index('--preview') + 1]) if '--preview' in a else 0
OUTLINE = (14, 11, 18, 255)

im = Image.open(src).convert('RGBA')
bbox = im.getbbox()
im = im.crop(bbox)
H = round(im.height * W / im.width)
scale = W / im.width
small = im.resize((W, H), Image.BOX)
px = small.load()
for y in range(H):  # hard alpha
    for x in range(W):
        r, g, b, al = px[x, y]
        px[x, y] = (r, g, b, 255 if al >= 128 else 0)
# palette from opaque pixels only, no dithering (clean pixel clusters)
rgb = Image.new('RGB', small.size, (0, 0, 0)); rgb.paste(small, mask=small.split()[3])
q = rgb.quantize(colors=NC, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert('RGB')
out = Image.new('RGBA', small.size, (0, 0, 0, 0)); out.paste(q, mask=small.split()[3])
op = out.load(); alpha = small.split()[3].load()
for y in range(H):  # 1px outline around the silhouette
    for x in range(W):
        if alpha[x, y]: continue
        if any(0 <= x + dx < W and 0 <= y + dy < H and alpha[x + dx, y + dy] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            op[x, y] = OUTLINE
out.save(dst)
side = src.replace('.png', '.json')
if os.path.exists(side):  # carry overlay points into the pixel image's coordinates
    meta = json.load(open(side))
    tr = lambda p: [round((p[0] - bbox[0]) * scale), round((p[1] - bbox[1]) * scale)]
    pts = {k: ([tr(p) for p in v] if isinstance(v, list) else {kk: tr(pp) for kk, pp in v.items()}) for k, v in meta['points'].items()}
    data = {'w': W, 'h': H, 'points': pts}
    json.dump(data, open(dst.replace('.png', '.json'), 'w'))
    sid = os.path.basename(dst)[:-4]  # also as a script, so pages opened from disk can load it
    with open(dst.replace('.png', '.js'), 'w') as f:
        f.write('window.SCENES = window.SCENES || {};\nwindow.SCENES[%s] = %s;\n' % (json.dumps(sid), json.dumps(data)))
if PV:
    out.resize((W * PV, H * PV), Image.NEAREST).save(dst.replace('.png', f'@{PV}x.png'))
print(dst, out.size, 'colours', NC)
