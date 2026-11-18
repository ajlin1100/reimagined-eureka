#!/usr/bin/env python3
"""Region detection: flood-fill rooms/hallways/stairs from wall linework.

Usage: regions.py <svg> <out.json> [--words words.json] [--debug prefix]
"""
import json, math, re, sys
from collections import defaultdict

import cv2
import numpy as np

from fp import parse_svg

SCALE = 6            # px per SVG unit
LINE_PX = 6          # barrier thickness (~1 unit)
DISK_R = 4           # endpoint joint disk radius
CLOSE_PX = 3         # morphological close
MIN_REGION_PX = 300
HALLWAY_MIN_PX = 5400
EPSILON_PX = 1.2
CAVITY_MAXDIST_PX = 8    # thin regions are wall cavities unless a word rescues them
WORD_SEARCH_PX = 36

ROOM_RE = re.compile(r'^\d{4}[A-Z]{0,2}(-\d+)?$')
VOID_WORDS = {'OTB', 'OPEN TO BELOW'}
ELEV_WORDS = {'EL'}
CLOSET_WORDS = {'ME', 'TE', 'MT', 'WT', 'CU', 'DU', 'ML', 'TL', 'TT', 'W'}


def collect(svg):
    w, h, paths = parse_svg(svg)
    line = [p for p in paths if p.stroked and p.stroke_width <= 0.1]
    return w, h, line


# ---------- door seals ----------

def circle_fit(pts):
    x = np.array([p[0] for p in pts]); y = np.array([p[1] for p in pts])
    A = np.c_[2 * x, 2 * y, np.ones(len(pts))]
    b = x ** 2 + y ** 2
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy, c = sol
    r2 = c + cx * cx + cy * cy
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    res = float(np.mean(np.abs(np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r)))
    return cx, cy, r, res


def all_endpoints(paths):
    eps = []
    for p in paths:
        for poly in p.polylines:
            if poly:
                eps.append(poly[0]); eps.append(poly[-1])
    return np.array(eps) if eps else np.zeros((0, 2))


def detect_doors(paths, eps):
    """Door arc -> two spoke seals from hinge to arc endpoints.
    Returns (seals, arc_exclude): seal segments + arc polylines to drop from mask."""
    seals = []
    arc_exclude = set()   # (id(path), poly_index)
    for p in paths:
        if 'C' not in p.d and 'c' not in p.d:
            continue
        for pi, poly in enumerate(p.polylines):
            if len(poly) < 5:
                continue
            fit = circle_fit(poly)
            if not fit:
                continue
            cx, cy, r, res = fit
            if not (3 <= r <= 12 and res < 0.15 * r):
                continue
            # both endpoints must lie on the circle (rejects arcs with tails)
            for ex, ey in (poly[0], poly[-1]):
                if abs(math.hypot(ex - cx, ey - cy) - r) > 0.3 * r:
                    fit = None
                    break
            if not fit:
                continue
            angs = np.unwrap(np.array([math.atan2(y - cy, x - cx) for x, y in poly]))
            span = math.degrees(angs.max() - angs.min())
            if not (50 <= span <= 150):
                continue
            if len(eps):
                d = np.hypot(eps[:, 0] - cx, eps[:, 1] - cy).min()
                if d > 1.5:
                    continue
            seals.append(((cx, cy), tuple(poly[0])))
            seals.append(((cx, cy), tuple(poly[-1])))
            arc_exclude.add((id(p), pi))
    return seals, arc_exclude


# ---------- segment table / tread detection ----------

def build_segments(paths):
    """All linework segments: (x0,y0,x1,y1,is_cubic)."""
    segs = []
    for p in paths:
        cubic = bool('C' in p.d or 'c' in p.d)
        for poly in p.polylines:
            for a, b in zip(poly, poly[1:]):
                segs.append((a[0], a[1], b[0], b[1], cubic))
    return segs


def detect_treads(segs):
    """Tread-like segments: straight, 3-24 long, >=4 parallel neighbors at 0.5-4u,
    not wall/window parts (no long parallel line within 1.0u).
    Returns (tread_flags, tread_mids, long_segs)."""
    n = len(segs)
    P0 = np.array([(s[0], s[1]) for s in segs], dtype=np.float32)
    P1 = np.array([(s[2], s[3]) for s in segs], dtype=np.float32)
    L = np.hypot(P1[:, 0] - P0[:, 0], P1[:, 1] - P0[:, 1])
    cubic = np.array([s[4] for s in segs])
    long_idx = np.where((L >= 12) & ~cubic)[0]
    long_segs = [(tuple(P0[i]), tuple(P1[i])) for i in long_idx]
    # wall faces are longer than any tread; used by the window/wall filter
    xlong_idx = np.where((L > 24) & ~cubic)[0]

    cand = np.where((L >= 3) & (L <= 24) & ~cubic)[0]
    flags = np.zeros(n, bool)
    if len(cand) == 0:
        return flags, [], long_segs
    M = (P0[cand] + P1[cand]) / 2
    D = P1[cand] - P0[cand]
    Ll = L[cand]
    U = D / Ll[:, None]
    m = len(cand)

    # window/wall filter: drop candidates with a very long parallel line within 1.0u
    if len(xlong_idx):
        LP0, LP1 = P0[xlong_idx], P1[xlong_idx]
        LL = L[xlong_idx]
        LU = (LP1 - LP0) / LL[:, None]
        near_wall = np.zeros(m, bool)
        BLK = 500
        for i0 in range(0, m, BLK):
            sl = slice(i0, min(m, i0 + BLK))
            u = U[sl]; mm = M[sl]
            cross = np.abs(u[:, 0:1] * LU[None, :, 1] - u[:, 1:2] * LU[None, :, 0])
            parallel = cross < 0.0872
            dm = LP0[None, :, :] - mm[:, None, :]          # (b, nlong, 2)
            perp = np.abs(u[:, 0:1] * dm[:, :, 1] - u[:, 1:2] * dm[:, :, 0])
            t = u[:, 0:1] * dm[:, :, 0] + u[:, 1:2] * dm[:, :, 1]
            # projection of candidate midpoint onto long line must fall within it (+-2u)
            along_ok = (t > -2) & (t < LL[None, :] + 2)
            near_wall[sl] = (parallel & (perp < 1.0) & along_ok).any(1)
    else:
        near_wall = np.zeros(m, bool)

    # pass 1: lenient parallel-neighbor test
    cnt = np.zeros(m, np.int32)
    BLK = 500
    for i0 in range(0, m, BLK):
        sl = slice(i0, min(m, i0 + BLK))
        u = U[sl]; mm = M[sl]; ll = Ll[sl]
        cross = np.abs(u[:, 0:1] * U[None, :, 1] - u[:, 1:2] * U[None, :, 0])
        parallel = cross < 0.2588      # <15 degrees
        dm = M[None, :, :] - mm[:, None, :]
        perp = np.abs(u[:, 0:1] * dm[:, :, 1] - u[:, 1:2] * dm[:, :, 0])
        perp_ok = (perp >= 0.5) & (perp <= 5.0)
        t = u[:, 0:1] * dm[:, :, 0] + u[:, 1:2] * dm[:, :, 1]
        lo = np.maximum(-ll[:, None] / 2, t - Ll[None, :] / 2)
        hi = np.minimum(ll[:, None] / 2, t + Ll[None, :] / 2)
        ov_ok = (hi - lo) > 0.4 * np.minimum(ll[:, None], Ll[None, :])
        cnt[sl] = (parallel & perp_ok & ov_ok).sum(1)
    pre = np.where((cnt >= 2) & ~near_wall)[0]

    # pass 2: treads stack at >=6 distinct perpendicular offsets within 8u
    # (stair run); cubicle/window rows share only 2-4 distinct offsets.
    keep_local = []
    pre_M, pre_U = M[pre], U[pre]
    for k in range(len(pre)):
        u = pre_U[k]; mm = pre_M[k]
        dm = pre_M - mm
        dist = np.hypot(dm[:, 0], dm[:, 1])
        close = np.where(dist <= 8.0)[0]
        if len(close) < 5:
            continue
        cross = np.abs(u[0] * pre_U[close, 1] - u[1] * pre_U[close, 0])
        par = close[cross < 0.2588]
        perp_off = np.abs(u[0] * dm[par, 1] - u[1] * dm[par, 0])
        perp_off = np.sort(perp_off)
        distinct = 1 + int((np.diff(perp_off) > 0.3).sum()) if len(perp_off) else 0
        if distinct >= 6:
            keep_local.append(k)
    tread_idx = cand[pre[keep_local]] if keep_local else np.array([], dtype=int)
    flags[tread_idx] = True
    mids = [tuple(((P0[i] + P1[i]) / 2).tolist()) for i in tread_idx]
    return flags, mids, long_segs


# ---------- barrier mask ----------

def build_mask(w, h, paths, arc_exclude, tread_flags, seals):
    W, H = int(round(w * SCALE)), int(round(h * SCALE))
    mask = np.zeros((H, W), np.uint8)

    def px(x, y):
        return int(round(x * SCALE)), int(round(y * SCALE))

    seg_i = 0
    for p in paths:
        for pi, poly in enumerate(p.polylines):
            if (id(p), pi) in arc_exclude:
                seg_i += max(0, len(poly) - 1)
                continue
            for a, b in zip(poly, poly[1:]):
                if not tread_flags[seg_i]:
                    pa, pb = px(*a), px(*b)
                    cv2.line(mask, pa, pb, 255, LINE_PX)
                    cv2.circle(mask, pa, DISK_R, 255, -1)
                    cv2.circle(mask, pb, DISK_R, 255, -1)
                seg_i += 1
    for (hpt, apt) in seals:
        ph, pa = px(*hpt), px(*apt)
        cv2.line(mask, ph, pa, 255, LINE_PX)
        cv2.circle(mask, ph, DISK_R, 255, -1)
        cv2.circle(mask, pa, DISK_R, 255, -1)
    if CLOSE_PX:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE_PX, CLOSE_PX))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    return mask


# ---------- regions ----------

def label_at(labels, x, y):
    """Nearest nonzero component label via expanding ring search."""
    H, W = labels.shape
    cx, cy = int(round(x * SCALE)), int(round(y * SCALE))
    if 0 <= cx < W and 0 <= cy < H and labels[cy, cx] > 0:
        return int(labels[cy, cx])
    for r in range(2, WORD_SEARCH_PX + 1, 2):
        x0, x1 = max(0, cx - r), min(W - 1, cx + r)
        y0, y1 = max(0, cy - r), min(H - 1, cy + r)
        ring = np.concatenate([labels[y0, x0:x1 + 1], labels[y1, x0:x1 + 1],
                               labels[y0:y1 + 1, x0], labels[y0:y1 + 1, x1]])
        nz = ring[ring > 0]
        if nz.size:
            return int(np.bincount(nz).argmax())
    return 0


def find_regions(mask, words):
    H, W = mask.shape
    ff = mask.copy()
    flood_mask = np.zeros((H + 2, W + 2), np.uint8)
    for sx, sy in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]:
        if ff[sy, sx] == 0:
            cv2.floodFill(ff, flood_mask, (sx, sy), 128)
    exterior = (ff == 128)
    free = ((mask == 0) & ~exterior).astype(np.uint8)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(free, connectivity=8)

    comp_words = defaultdict(list)
    unplaced = []
    for wd in words:
        c = label_at(labels, wd['center'][0], wd['center'][1])
        if c > 0:
            comp_words[c].append(wd['text'])
        else:
            unplaced.append(wd['text'])

    regions = []
    for c in range(1, n):
        area = stats[c, cv2.CC_STAT_AREA]
        if area < MIN_REGION_PX:
            continue
        x, y, bw, bh = (stats[c, k] for k in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP,
                                              cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        crop = np.pad((labels[y:y + bh, x:x + bw] == c).astype(np.uint8), 1)
        dist = cv2.distanceTransform(crop, cv2.DIST_L2, 5)
        if dist.max() < CAVITY_MAXDIST_PX and not comp_words.get(c):
            continue  # wall cavity with no label inside
        cnts, _ = cv2.findContours(crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        cnt = max(cnts, key=cv2.contourArea)
        approx = cv2.approxPolyDP(cnt, EPSILON_PX, True)
        pts = [[(p[0][0] + x - 1) / SCALE, (p[0][1] + y - 1) / SCALE] for p in approx]
        regions.append({'comp': c, 'area_px': int(area), 'polygon': pts,
                        'cx': float(cents[c][0] / SCALE), 'cy': float(cents[c][1] / SCALE),
                        'words': comp_words.get(c, [])})
    placed_comps = {r['comp'] for r in regions}
    unplaced += [t for c, ts in comp_words.items() if c not in placed_comps for t in ts]
    return regions, labels, unplaced


# ---------- classification ----------

def crosses_treads(seg, mids, r):
    """Does long segment pass within 2u of >=3 tread midpoints?"""
    (x0, y0), (x1, y1) = seg
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L < 12:
        return False
    ux, uy = dx / L, dy / L
    hits = 0
    for mx, my in mids:
        t = (mx - x0) * ux + (my - y0) * uy
        if -1 <= t <= L + 1 and abs((mx - x0) * uy - (my - y0) * ux) <= 2.0:
            hits += 1
            if hits >= 3:
                return True
    return False


def classify(regions, labels, tread_mids, long_segs):
    comp_tread_mids = defaultdict(list)
    for mx, my in tread_mids:
        c = label_at(labels, mx, my)
        comp_tread_mids[c].append((mx, my))
    for r in regions:
        c = r['comp']
        ws = r['words']
        rooms = [t for t in ws if ROOM_RE.match(t)]
        label = rooms[0] if rooms else (ws[0] if ws else None)
        tmids = comp_tread_mids.get(c, [])
        is_stair = False
        if len(tmids) >= 6:
            if not rooms:
                is_stair = True
            else:
                x0 = min(p[0] for p in r['polygon']); x1 = max(p[0] for p in r['polygon'])
                y0 = min(p[1] for p in r['polygon']); y1 = max(p[1] for p in r['polygon'])
                for seg in long_segs:
                    (sx0, sy0), (sx1, sy1) = seg
                    if max(sx0, sx1) < x0 - 2 or min(sx0, sx1) > x1 + 2 or \
                       max(sy0, sy1) < y0 - 2 or min(sy0, sy1) > y1 + 2:
                        continue
                    if crosses_treads(seg, tmids, r):
                        is_stair = True
                        break
        if any(t in VOID_WORDS for t in ws):
            kind = 'void'
        elif any(t in ELEV_WORDS for t in ws):
            kind = 'elevator'
        elif is_stair:
            kind = 'stair'
        elif rooms or any(t in CLOSET_WORDS for t in ws):
            kind = 'room'
        elif r['area_px'] >= HALLWAY_MIN_PX:
            kind = 'hallway'
        else:
            kind = 'space'
        r['kind'] = kind
        r['label'] = label
        r['area'] = round(r['area_px'] / (SCALE * SCALE), 1)
        r['treads'] = len(tmids)
        for k in ('area_px', 'comp', 'words'):
            del r[k]
    return regions


def assign_ids(regions):
    counts = defaultdict(int)
    for r in regions:
        base = r['label'] if r['label'] else 'unlabeled'
        base = re.sub(r'[^A-Za-z0-9]+', '-', base).strip('-').lower() or 'unlabeled'
        counts[base] += 1
        suffix = '' if counts[base] == 1 else f'-{counts[base]}'
        r['id'] = f"{r['kind']}-{base}{suffix}"
    return regions


# ---------- debug render ----------

def debug_render(mask, labels, regions, seals, tread_mids, path, max_w=2200):
    H, W = mask.shape
    colors = {'room': (120, 200, 120), 'hallway': (220, 220, 130), 'stair': (240, 130, 130),
              'elevator': (150, 170, 240), 'void': (200, 140, 220), 'space': (160, 220, 220)}
    img = np.full((H, W, 3), 255, np.uint8)
    img[mask > 0] = (40, 40, 40)
    for r in regions:
        pts = np.array([[(x * SCALE, y * SCALE)] for x, y in r['polygon']], np.int32)
        cv2.fillPoly(img, [pts], colors.get(r['kind'], (200, 200, 200)))
    for (hpt, apt) in seals:
        cv2.line(img, (int(hpt[0] * SCALE), int(hpt[1] * SCALE)),
                 (int(apt[0] * SCALE), int(apt[1] * SCALE)), (0, 0, 255), 2)
    for mx, my in tread_mids:
        cv2.circle(img, (int(mx * SCALE), int(my * SCALE)), 4, (0, 140, 255), -1)
    sc = max_w / W
    small = cv2.resize(img, (max_w, int(H * sc)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(path, small)


# ---------- main ----------

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    opts = {a.split('=')[0][2:]: a.split('=')[1] for a in sys.argv[1:] if a.startswith('--') and '=' in a}
    svg, out_json = args[0], args[1]
    words = []
    if 'words' in opts:
        data = json.load(open(opts['words']))
        base = svg.replace('\\', '/').split('/')[-1]
        words = [w for w in data if w['file'] == base]

    w, h, paths = collect(svg)
    eps = all_endpoints(paths)
    seals, arc_exclude = detect_doors(paths, eps)
    segs = build_segments(paths)
    tread_flags, tread_mids, long_segs = detect_treads(segs)
    mask = build_mask(w, h, paths, arc_exclude, tread_flags, seals)
    regions, labels, unplaced = find_regions(mask, words)
    regions = classify(regions, labels, tread_mids, long_segs)
    regions = assign_ids(regions)

    counts = defaultdict(int)
    for r in regions:
        counts[r['kind']] += 1
    print(f"{svg}: {len(regions)} regions | " +
          " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"  seals={len(seals) // 2} doors, treads={len(tread_mids)}, unplaced words={len(unplaced)}")
    if unplaced:
        print(f"  unplaced: {unplaced[:25]}")
    stairs = [(r['label'], r['id'], r['treads']) for r in regions if r['kind'] == 'stair']
    print(f"  stairs: {stairs}")

    json.dump({'file': svg, 'regions': regions}, open(out_json, 'w'), indent=1)
    if 'debug' in opts:
        debug_render(mask, labels, regions, seals, tread_mids, opts['debug'])


if __name__ == '__main__':
    main()
