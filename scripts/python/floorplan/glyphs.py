"""Cluster stroke-font glyph paths across floor plans and build a reading atlas.

Glyph instances are small stroked paths (stroke-width 0.12/0.18) - the CAD
stroke-font letterforms. Characters may consist of several paths (e.g. "A" is
two legs plus a crossbar), so paths are first merged into composite characters
via connected components on segment distance. Clustering is done on normalized
raster bitmaps so tiny coordinate wiggles between instances of the same
character don't matter.
"""
import json
import math
import sys
from collections import defaultdict

import numpy as np
from PIL import Image, ImageDraw

from fp import parse_svg

CANVAS = 28  # glyph bitmap size (px)
HAMMING_THRESHOLD = 8  # bits out of CANVAS*CANVAS
MERGE_DIST = 0.4  # max gap between strokes of one character, in SVG units


# ---- geometry helpers ----

def _pt_seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _segs_intersect(a, b, c, d):
    def orient(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return (v > 1e-12) - (v < -1e-12)

    o1, o2 = orient(a, b, c), orient(a, b, d)
    o3, o4 = orient(c, d, a), orient(c, d, b)
    return o1 != o2 and o3 != o4


def seg_seg_dist(a, b, c, d):
    if _segs_intersect(a, b, c, d):
        return 0.0
    return min(
        _pt_seg_dist(a[0], a[1], c[0], c[1], d[0], d[1]),
        _pt_seg_dist(b[0], b[1], c[0], c[1], d[0], d[1]),
        _pt_seg_dist(c[0], c[1], a[0], a[1], b[0], b[1]),
        _pt_seg_dist(d[0], d[1], a[0], a[1], b[0], b[1]),
    )


def path_segments(polylines):
    segs = []
    for pl in polylines:
        for i in range(len(pl) - 1):
            segs.append((pl[i], pl[i + 1]))
    return segs


# ---- glyph extraction and character merging ----

def extract_glyphs(path):
    """Extract glyph candidate paths, merge into characters, return char dicts."""
    w, h, recs = parse_svg(path)
    cands = []
    for idx, r in enumerate(recs):
        if not r.stroked or not (0.1 <= r.stroke_width <= 0.3):
            continue
        b = r.bounds()
        if b is None:
            continue
        bw, bh = b[2] - b[0], b[3] - b[1]
        if max(bw, bh) > 10 or max(bw, bh) < 0.2:
            continue
        if sum(len(pl) for pl in r.polylines) > 64:
            continue
        a, bb, c, d, e, f = r.matrix
        orient = round(math.degrees(math.atan2(bb, a)) / 90) % 4
        cands.append({
            'idx': idx,
            'bounds': list(b),
            'orient': orient,
            'polylines': r.polylines,
            'segs': path_segments(r.polylines),
        })

    # union-find over candidates, linked when strokes nearly touch
    parent = list(range(len(cands)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        pi, pj = find(i), find(j)
        if pi != pj:
            parent[pi] = pj

    # spatial hash on expanded bounds
    cell = 8.0
    grid = defaultdict(list)
    for i, g in enumerate(cands):
        b = g['bounds']
        x0, y0 = int((b[0] - MERGE_DIST) // cell), int((b[1] - MERGE_DIST) // cell)
        x1, y1 = int((b[2] + MERGE_DIST) // cell), int((b[3] + MERGE_DIST) // cell)
        for gx in range(x0, x1 + 1):
            for gy in range(y0, y1 + 1):
                grid[(gx, gy)].append(i)
    seen_pairs = set()
    for ids in grid.values():
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                i, j = ids[x], ids[y]
                if (i, j) in seen_pairs:
                    continue
                seen_pairs.add((i, j))
                bi, bj = cands[i]['bounds'], cands[j]['bounds']
                if (bi[0] > bj[2] + MERGE_DIST or bj[0] > bi[2] + MERGE_DIST
                        or bi[1] > bj[3] + MERGE_DIST or bj[1] > bi[3] + MERGE_DIST):
                    continue
                close = False
                for s1 in cands[i]['segs']:
                    for s2 in cands[j]['segs']:
                        if seg_seg_dist(s1[0], s1[1], s2[0], s2[1]) <= MERGE_DIST:
                            close = True
                            break
                    if close:
                        break
                if close:
                    union(i, j)

    groups = defaultdict(list)
    for i in range(len(cands)):
        groups[find(i)].append(i)

    chars = []
    for members in groups.values():
        polylines = []
        x0 = y0 = 1e9
        x1 = y1 = -1e9
        for m in members:
            polylines.extend(cands[m]['polylines'])
            b = cands[m]['bounds']
            x0, y0 = min(x0, b[0]), min(y0, b[1])
            x1, y1 = max(x1, b[2]), max(y1, b[3])
        chars.append({
            'file': path.split('\\')[-1],
            'bounds': (x0, y0, x1, y1),
            'center': ((x0 + x1) / 2, (y0 + y1) / 2),
            'orient': cands[members[0]]['orient'],
            'polylines': polylines,
        })
    return chars


def rasterize(glyph):
    """Render glyph shape centered on a CANVAS x CANVAS bitmap."""
    b = glyph['bounds']
    bw = max(b[2] - b[0], 1e-6)
    bh = max(b[3] - b[1], 1e-6)
    scale = (CANVAS - 8) / max(bw, bh)
    img = Image.new('L', (CANVAS, CANVAS), 0)
    draw = ImageDraw.Draw(img)
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    for pl in glyph['polylines']:
        pts = [((x - cx) * scale + CANVAS / 2, (y - cy) * scale + CANVAS / 2) for x, y in pl]
        if len(pts) >= 2:
            draw.line(pts, fill=255, width=2, joint='curve')
    return np.array(img, dtype=np.uint8)


def cluster(glyphs):
    """Greedy Hamming clustering. Returns (labels, rep_bitmaps, packed_bitmaps)."""
    bitmaps = [np.packbits(rasterize(g)) for g in glyphs]
    labels = np.full(len(glyphs), -1, dtype=np.int32)
    reps = []
    pop = np.array([bin(i).count('1') for i in range(256)], dtype=np.int32)
    for i in range(len(glyphs)):
        if not reps:
            labels[i] = 0
            reps.append(bitmaps[i])
            continue
        rep_arr = np.stack(reps)
        dist = pop[np.bitwise_xor(rep_arr, bitmaps[i])].sum(axis=1)
        j = int(np.argmin(dist))
        if dist[j] <= HAMMING_THRESHOLD:
            labels[i] = j
        else:
            labels[i] = len(reps)
            reps.append(bitmaps[i])
    return (labels,
            [np.unpackbits(r).reshape(CANVAS, CANVAS) * 255 for r in reps],
            bitmaps)


def build_atlas(glyphs, labels, reps, out_png, max_clusters=400):
    counts = defaultdict(int)
    for lb in labels:
        counts[int(lb)] += 1
    order = sorted(counts, key=lambda k: -counts[k])[:max_clusters]
    cell = CANVAS * 3
    label_h = 14
    cols = 20
    rows = (len(order) + cols - 1) // cols
    img = Image.new('RGB', (cols * cell, rows * (cell + label_h)), 'white')
    draw = ImageDraw.Draw(img)
    for slot, cid in enumerate(order):
        r, c = divmod(slot, cols)
        rep = Image.fromarray(reps[cid]).resize((cell, cell), Image.NEAREST)
        img.paste(rep, (c * cell, r * (cell + label_h)))
        draw.text((c * cell + 2, r * (cell + label_h) + cell + 1),
                  '%d (n=%d)' % (cid, counts[cid]), fill='red')
    img.save(out_png)
    return counts, order


if __name__ == '__main__':
    out_png = sys.argv[1]
    out_json = sys.argv[2]
    srcs = sys.argv[3:]
    all_glyphs = []
    for s in srcs:
        g = extract_glyphs(s)
        print('%s: %d characters' % (s.split('\\')[-1], len(g)))
        all_glyphs.extend(g)
    print('total: %d' % len(all_glyphs))
    labels, reps, bitmaps = cluster(all_glyphs)
    print('clusters: %d' % len(reps))
    counts, order = build_atlas(all_glyphs, labels, reps, out_png)
    data = {
        'glyphs': [{k: g[k] for k in ('file', 'bounds', 'center', 'orient')} for g in all_glyphs],
        'labels': [int(x) for x in labels],
        'counts': {str(k): v for k, v in counts.items()},
    }
    with open(out_json, 'w') as fh:
        json.dump(data, fh)
    np.savez_compressed(out_json.replace('.json', '.npz'),
                        bitmaps=np.stack(bitmaps), labels=labels)
    print('wrote', out_png, 'and', out_json)
