"""Floor plan SVG pipeline: parse, render, scrub, analyze.

The source SVGs are CAD (INSITE Visual-FM) exports via PDF/Inkscape:
- All geometry is <path> elements; text labels are stroke-font letterforms.
- Transforms are matrix(...) on paths and enclosing <g> elements.
- Path commands used: M, L, H, V, C, Z (absolute).
"""
import math
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

SVG_NS = 'http://www.w3.org/2000/svg'
NS = '{%s}' % SVG_NS

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mat_mul(m1, m2):
    """Compose two SVG matrices: result = m1 * m2 (apply m2 first)."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def mat_apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def parse_transform(s):
    if not s:
        return IDENTITY
    m = IDENTITY
    for name, args in re.findall(r'(matrix|translate|scale|rotate)\(([^)]*)\)', s):
        vals = [float(v) for v in re.split(r'[,\s]+', args.strip()) if v]
        if name == 'matrix':
            t = tuple(vals)
        elif name == 'translate':
            t = (1.0, 0.0, 0.0, 1.0, vals[0], vals[1] if len(vals) > 1 else 0.0)
        elif name == 'scale':
            t = (vals[0], 0.0, 0.0, vals[1] if len(vals) > 1 else vals[0], 0.0, 0.0)
        else:  # rotate
            ang = math.radians(vals[0])
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            t = (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
        m = mat_mul(m, t)
    return m


NUM = r'-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'
TOKEN_RE = re.compile(r'([MmLlHhVvCcZz])|(' + NUM + r')')


def parse_path_d(d):
    """Parse path data into flattened polylines (absolute, local coords).

    Returns list of polylines; each polyline is [(x, y), ...].
    Cubic curves are flattened by recursive subdivision.
    """
    tokens = TOKEN_RE.findall(d)
    i = 0
    cmd = None
    x = y = 0.0
    start_x = start_y = 0.0
    polylines = []
    current = None

    def next_num():
        nonlocal i
        v = float(tokens[i][1])
        i += 1
        return v

    def flatten_cubic(p0, p1, p2, p3, depth=0):
        dx, dy = p3[0] - p0[0], p3[1] - p0[1]
        d1 = abs((p1[0] - p3[0]) * dy - (p1[1] - p3[1]) * dx)
        d2 = abs((p2[0] - p3[0]) * dy - (p2[1] - p3[1]) * dx)
        if (d1 + d2) ** 2 < 0.05 * (dx * dx + dy * dy) or depth > 12:
            return [p3]
        p01 = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        p12 = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        p23 = ((p2[0] + p3[0]) / 2, (p2[1] + p3[1]) / 2)
        p012 = ((p01[0] + p12[0]) / 2, (p01[1] + p12[1]) / 2)
        p123 = ((p12[0] + p23[0]) / 2, (p12[1] + p23[1]) / 2)
        p0123 = ((p012[0] + p123[0]) / 2, (p012[1] + p123[1]) / 2)
        return (flatten_cubic(p0, p01, p012, p0123, depth + 1)
                + flatten_cubic(p0123, p123, p23, p3, depth + 1))

    while i < len(tokens):
        tok = tokens[i]
        if tok[0]:
            cmd = tok[0]
            i += 1
            if cmd in 'Zz':
                if current is not None and current[-1] != (start_x, start_y):
                    current.append((start_x, start_y))
                continue
        if cmd is None:
            break
        if cmd == 'M':
            x, y = next_num(), next_num()
            start_x, start_y = x, y
            current = [(x, y)]
            polylines.append(current)
            cmd = 'L'  # implicit lineto follows
        elif cmd == 'm':
            x += next_num()
            y += next_num()
            start_x, start_y = x, y
            current = [(x, y)]
            polylines.append(current)
            cmd = 'l'
        elif cmd == 'L':
            x, y = next_num(), next_num()
            current.append((x, y))
        elif cmd == 'l':
            x += next_num()
            y += next_num()
            current.append((x, y))
        elif cmd == 'H':
            x = next_num()
            current.append((x, y))
        elif cmd == 'h':
            x += next_num()
            current.append((x, y))
        elif cmd == 'V':
            y = next_num()
            current.append((x, y))
        elif cmd == 'v':
            y += next_num()
            current.append((x, y))
        elif cmd == 'C':
            x1, y1, x2, y2, x3, y3 = (next_num() for _ in range(6))
            current.extend(flatten_cubic((x, y), (x1, y1), (x2, y2), (x3, y3)))
            x, y = x3, y3
        elif cmd == 'c':
            x1, y1, x2, y2, x3, y3 = (next_num() for _ in range(6))
            current.extend(flatten_cubic((x, y), (x + x1, y + y1), (x + x2, y + y2), (x + x3, y + y3)))
            x, y = x + x3, y + y3
        else:
            raise ValueError('unhandled path command %r' % cmd)
    return polylines


class PathRec:
    __slots__ = ('polylines', 'stroke_width', 'stroked', 'filled', 'd', 'matrix', 'clip')

    def __init__(self, polylines, stroke_width, stroked, filled, d, matrix, clip):
        self.polylines = polylines
        self.stroke_width = stroke_width
        self.stroked = stroked
        self.filled = filled
        self.d = d
        self.matrix = matrix
        self.clip = clip

    def bounds(self):
        xs = [p[0] for pl in self.polylines for p in pl]
        ys = [p[1] for pl in self.polylines for p in pl]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def parse_svg(path):
    """Parse SVG into (width, height, [PathRec]) with transforms baked in."""
    tree = ET.parse(path)
    root = tree.getroot()
    width = float(root.get('width'))
    height = float(root.get('height'))
    records = []

    def walk(el, ctm, clip):
        for child in el:
            tag = child.tag
            if tag.startswith(NS):
                tag = tag[len(NS):]
            if tag in ('defs', 'clipPath'):
                continue
            m = mat_mul(ctm, parse_transform(child.get('transform')))
            cl = child.get('clip-path') or clip
            if tag == 'path':
                d = child.get('d')
                polylines = parse_path_d(d)
                polylines = [[mat_apply(m, px, py) for px, py in pl] for pl in polylines]
                stroke = child.get('stroke')
                fill = child.get('fill')
                sw = float(child.get('stroke-width') or 1.0)
                stroked = stroke is not None and stroke != 'none'
                filled = not (fill == 'none') and not stroked
                records.append(PathRec(polylines, sw, stroked, filled, d, m, cl))
            elif tag in ('g', 'svg'):
                walk(child, m, cl)
            # text/image elements are skipped (metadata or handled separately)

    walk(root, IDENTITY, None)
    return width, height, records


def render(width, height, records, out_png, scale=2.0, draw_filled=False):
    """Rasterize stroked paths to a PNG for inspection."""
    img = Image.new('RGB', (int(width * scale), int(height * scale)), 'white')
    draw = ImageDraw.Draw(img)
    for rec in records:
        if not rec.stroked:
            if not draw_filled:
                continue
            for pl in rec.polylines:
                pts = [(x * scale, y * scale) for x, y in pl]
                if len(pts) >= 2:
                    draw.polygon(pts, fill='black')
            continue
        w = max(1, int(round(rec.stroke_width * scale)))
        for pl in rec.polylines:
            pts = [(x * scale, y * scale) for x, y in pl]
            if len(pts) >= 2:
                draw.line(pts, fill='black', width=w, joint='curve')
    img.save(out_png)
    return out_png


def render_crop(records, out_png, x0, y0, x1, y1, scale=8.0):
    """Rasterize a rectangular region (unit coords) at high zoom."""
    w = int((x1 - x0) * scale)
    h = int((y1 - y0) * scale)
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)
    for rec in records:
        if not rec.stroked:
            continue
        lw = max(1, int(round(rec.stroke_width * scale)))
        for pl in rec.polylines:
            pts = [((x - x0) * scale, (y - y0) * scale) for x, y in pl]
            if len(pts) >= 2:
                draw.line(pts, fill='black', width=lw, joint='curve')
    img.save(out_png)
    return out_png


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'render':
        src, out = sys.argv[2], sys.argv[3]
        scale = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0
        w, h, recs = parse_svg(src)
        print('parsed %d paths (%.0fx%.0f)' % (len(recs), w, h))
        render(w, h, recs, out, scale)
        print('wrote', out)
    elif cmd == 'crop':
        src, out = sys.argv[2], sys.argv[3]
        x0, y0, x1, y1 = (float(v) for v in sys.argv[4:8])
        scale = float(sys.argv[8]) if len(sys.argv) > 8 else 8.0
        _, _, recs = parse_svg(src)
        render_crop(recs, out, x0, y0, x1, y1, scale)
        print('wrote', out)
