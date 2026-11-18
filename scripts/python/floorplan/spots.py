"""Render red-boxed glyph context crops for a list of spots/clusters, tiled.

Usage: spots.py glyphs.json out.png src_dir spec...
  spec = "f:<file>:<x>,<y>"  -> crop around (x, y) in <file>
         "c:<clusterID>"     -> crops around first instances of cluster
"""
import json
import sys

from PIL import Image, ImageDraw

from fp import parse_svg

CACHE = {}


def get_recs(path):
    if path not in CACHE:
        CACHE[path] = parse_svg(path)[2]
    return CACHE[path]


def render_spot(recs, glyphs, x0, y0, x1, y1, scale=16.0):
    w = int((x1 - x0) * scale)
    h = int((y1 - y0) * scale)
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)
    for rec in recs:
        if not rec.stroked:
            continue
        lw = max(1, int(round(rec.stroke_width * scale)))
        for pl in rec.polylines:
            pts = [((x - x0) * scale, (y - y0) * scale) for x, y in pl]
            if len(pts) >= 2:
                draw.line(pts, fill='black', width=lw, joint='curve')
    for bx, lb in glyphs:
        rect = [(bx[0] - x0) * scale, (bx[1] - y0) * scale,
                (bx[2] - x0) * scale, (bx[3] - y0) * scale]
        draw.rectangle(rect, outline='red', width=2)
        draw.text((rect[0], max(0, rect[1] - 13)), str(lb), fill='blue')
    return img


if __name__ == '__main__':
    glyphs_json, out_png, src_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    data = json.load(open(glyphs_json))
    all_g = [(g, lb) for g, lb in zip(data['glyphs'], data['labels'])]

    tiles = []
    for spec in sys.argv[4:]:
        kind, rest = spec.split(':', 1)
        if kind == 'c':
            cid = int(rest)
            spots = [(g['file'], g['center'][0], g['center'][1])
                     for g, lb in all_g if lb == cid][:2]
        else:
            fname, xy = rest.rsplit(':', 1)
            x, y = (float(v) for v in xy.split(','))
            spots = [(fname, x, y)]
        for fname, cx, cy in spots:
            recs = get_recs('%s\\%s' % (src_dir, fname))
            near = [(g['bounds'], lb) for g, lb in all_g
                    if g['file'] == fname
                    and abs(g['center'][0] - cx) < 11 and abs(g['center'][1] - cy) < 7]
            tiles.append((spec, render_spot(recs, near, cx - 10, cy - 5, cx + 10, cy + 5)))

    tw, th = tiles[0][1].size
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tw, rows * (th + 16)), 'white')
    draw = ImageDraw.Draw(sheet)
    for i, (spec, t) in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + 16)
        sheet.paste(t, (x, y + 16))
        draw.text((x + 2, y + 2), spec, fill='red')
    sheet.save(out_png)
    print('wrote', out_png, '(%d tiles)' % len(tiles))
