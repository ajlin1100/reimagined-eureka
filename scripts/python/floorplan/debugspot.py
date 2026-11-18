"""Render a region with glyph bounding boxes and cluster IDs overlaid."""
import json
import sys

from PIL import Image, ImageDraw

from fp import parse_svg

if __name__ == '__main__':
    glyphs_json, src, out_png = sys.argv[1], sys.argv[2], sys.argv[3]
    x0, y0, x1, y1 = (float(v) for v in sys.argv[4:8])
    scale = float(sys.argv[8]) if len(sys.argv) > 8 else 16.0

    fname = src.split('\\')[-1]
    data = json.load(open(glyphs_json))
    boxes = []
    for g, lb in zip(data['glyphs'], data['labels']):
        if g['file'] != fname:
            continue
        bx = g['bounds']
        cx, cy = g['center']
        if x0 - 2 < cx < x1 + 2 and y0 - 2 < cy < y1 + 2:
            boxes.append((bx, lb))

    _, _, recs = parse_svg(src)
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
    for bx, lb in boxes:
        rect = [(bx[0] - x0) * scale, (bx[1] - y0) * scale,
                (bx[2] - x0) * scale, (bx[3] - y0) * scale]
        draw.rectangle(rect, outline='red', width=2)
        draw.text((rect[0], rect[1] - 12), str(lb), fill='blue')
    img.save(out_png)
    print('wrote', out_png, '(%d glyphs)' % len(boxes))
