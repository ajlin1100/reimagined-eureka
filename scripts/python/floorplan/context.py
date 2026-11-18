"""Render context crops around instances of a glyph cluster, tiled into one image."""
import json
import sys

from PIL import Image

from fp import parse_svg, render_crop

CACHE = {}


def get_recs(path):
    if path not in CACHE:
        CACHE[path] = parse_svg(path)[2]
    return CACHE[path]


if __name__ == '__main__':
    glyphs_json = sys.argv[1]
    cluster_id = int(sys.argv[2])
    out_png = sys.argv[3]
    src_dir = sys.argv[4]
    max_tiles = int(sys.argv[5]) if len(sys.argv) > 5 else 12

    data = json.load(open(glyphs_json))
    tiles = []
    for g, lb in zip(data['glyphs'], data['labels']):
        if lb != cluster_id:
            continue
        cx, cy = g['center']
        recs = get_recs('%s\\%s' % (src_dir, g['file']))
        tmp = out_png + '.tmp.png'
        render_crop(recs, tmp, cx - 10, cy - 5, cx + 10, cy + 5, scale=10)
        tiles.append(Image.open(tmp).copy())
        if len(tiles) >= max_tiles:
            break
    if not tiles:
        print('no instances')
        sys.exit(1)
    tw, th = tiles[0].size
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tw, rows * th), 'white')
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * tw, (i // cols) * th))
    sheet.save(out_png)
    print('wrote', out_png, '(%d tiles)' % len(tiles))
