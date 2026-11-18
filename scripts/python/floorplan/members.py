"""Show enlarged instance bitmaps for given clusters, tiled on one sheet."""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

CANVAS = 28

if __name__ == '__main__':
    npz_path, glyphs_json, out_png = sys.argv[1], sys.argv[2], sys.argv[3]
    cluster_ids = [int(v) for v in sys.argv[4:]]
    z = np.load(npz_path)
    bitmaps, labels = z['bitmaps'], z['labels']
    data = json.load(open(glyphs_json))
    counts = {int(k): v for k, v in data['counts'].items()}

    cell = CANVAS * 4
    per = 4  # instances per cluster
    cols = per
    rows_total = len(cluster_ids)
    label_w = 90
    img = Image.new('RGB', (label_w + cols * cell, rows_total * cell), 'white')
    draw = ImageDraw.Draw(img)
    for row, cid in enumerate(cluster_ids):
        idxs = [i for i in range(len(bitmaps)) if labels[i] == cid][:per]
        draw.text((2, row * cell + cell // 2 - 6), '%d (n=%d)' % (cid, counts.get(cid, 0)), fill='red')
        for col, i in enumerate(idxs):
            bm = np.unpackbits(bitmaps[i]).reshape(CANVAS, CANVAS) * 255
            tile = Image.fromarray(bm).resize((cell, cell), Image.NEAREST)
            img.paste(tile, (label_w + col * cell, row * cell))
    img.save(out_png)
    print('wrote', out_png)
