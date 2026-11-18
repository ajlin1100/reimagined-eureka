"""Render every anchor cluster's template bitmap with its assigned char,
so the whole ANCHORS table can be visually audited in one image."""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

from automap import ANCHORS, CANVAS

npz_path, glyphs_json, out_png = sys.argv[1], sys.argv[2], sys.argv[3]
z = np.load(npz_path)
bitmaps, labels = z['bitmaps'], z['labels']
data = json.load(open(glyphs_json))
glyphs = data['glyphs']

cids = sorted(ANCHORS)
cols = 12
scale = 10
cell_w, cell_h = CANVAS * scale + 8, CANVAS * scale + 26
rows = (len(cids) + cols - 1) // cols
img = Image.new('RGB', (cols * cell_w, rows * cell_h), 'white')
d = ImageDraw.Draw(img)
for k, cid in enumerate(cids):
    idx = int(np.argmax(labels == cid))
    bm = np.unpackbits(bitmaps[idx]).reshape(CANVAS, CANVAS)
    ox = (k % cols) * cell_w + 4
    oy = (k // cols) * cell_h + 4
    for y in range(CANVAS):
        for x in range(CANVAS):
            if bm[y, x]:
                d.rectangle([ox + x * scale, oy + y * scale,
                             ox + (x + 1) * scale - 1, oy + (y + 1) * scale - 1],
                            fill='black')
    g = glyphs[idx]
    d.text((ox, oy + CANVAS * scale + 2),
           '%d=%s' % (cid, ANCHORS[cid]), fill='red')
    d.text((ox, oy + CANVAS * scale + 13),
           '%s@%.0f,%.0f' % (g['file'][4:7], g['center'][0], g['center'][1]),
           fill='blue')
img.save(out_png)
print('wrote', out_png, '(%d anchors)' % len(cids))
