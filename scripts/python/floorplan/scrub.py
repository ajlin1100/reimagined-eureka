"""Scrub watermarks, metadata, and CAD-export artifacts from floor plan SVGs.

Removes:
- <image> elements (base64 watermark JPEG banners)
- metadata <text> elements (INSITE Visual-FM, Manager - Facilities Drawings);
  keeps plan annotation text (e.g. stairwell "DN" in 039_4_0)
- groups left empty by removals (incl. the Watermark layer wrappers)
- sliver fill artifacts: bare-fill <path> elements (no stroke attribute =>
  default black fill) with degenerate bounds (min dim < 0.15 units)
- full-sheet frame paths (bounds cover the whole sheet), stroked or not
- clipPath definitions left unreferenced after removals
- namespace declarations (inkscape, xlink) when no longer referenced

Keeps everything else, including on-plan annotation (building name, script
text fills, column fills, arrowheads) and all stroked plan geometry.

Usage: scrub.py <in.svg> <out.svg>
"""
import os
import re
import sys

from fp import mat_apply, parse_path_d, parse_transform

METADATA_RE = re.compile(
    r'INSITE|Visual-FM|Facilities Drawings|DRAWING:|Last Update|Copyright',
    re.IGNORECASE)
SLIVER_MIN_DIM = 0.15   # units; below this a fill is a degenerate sliver
SHEET_TOL = 1.0         # units; bounds within this of the sheet = frame

G_OPEN_RE = re.compile(r'^\s*<g[\s>]')
G_CLOSE_RE = re.compile(r'^\s*</g\s*>\s*$')
CLIP_REF_RE = re.compile(r'url\(#(clip_\d+)\)')


def path_bounds(d, transform):
    m = parse_transform(transform)
    x0 = y0 = float('inf')
    x1 = y1 = float('-inf')
    for pl in parse_path_d(d):
        for x, y in pl:
            tx, ty = mat_apply(m, x, y)
            x0, y0 = min(x0, tx), min(y0, ty)
            x1, y1 = max(x1, tx), max(y1, ty)
    return x0, y0, x1, y1


def scrub(src, dst):
    lines = open(src, encoding='utf-8').read().splitlines()
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', lines[0])
    sheet_w, sheet_h = float(m.group(1)), float(m.group(2))

    dropped = [False] * len(lines)
    in_defs = False
    i = 0
    n_image = n_text = n_sliver = n_frame = 0
    while i < len(lines):
        line = lines[i]
        if '<defs>' in line:
            in_defs = True
        elif '</defs>' in line:
            in_defs = False
        elif '<image' in line:
            # drop through the end of the base64 block (tag ends with "/>")
            while i < len(lines):
                end = lines[i].rstrip().endswith('/>')
                dropped[i] = True
                i += 1
                if end:
                    break
            n_image += 1
            continue
        elif '<text' in line:
            content = ''
            j = i
            while j < len(lines):
                content += lines[j]
                if '</text>' in lines[j]:
                    break
                j += 1
            if METADATA_RE.search(content):
                for k in range(i, j + 1):
                    dropped[k] = True
                n_text += 1
                i = j + 1
                continue
        elif '<path' in line and not in_defs:
            d_m = re.search(r'd="([^"]*)"', line)
            t_m = re.search(r'transform="([^"]*)"', line)
            if d_m:
                x0, y0, x1, y1 = path_bounds(
                    d_m.group(1), t_m.group(1) if t_m else None)
                bw, bh = x1 - x0, y1 - y0
                is_frame = (x0 <= SHEET_TOL and y0 <= SHEET_TOL and
                            x1 >= sheet_w - SHEET_TOL and
                            y1 >= sheet_h - SHEET_TOL)
                if is_frame:
                    dropped[i] = True
                    n_frame += 1
                elif 'stroke=' not in line and min(bw, bh) < SLIVER_MIN_DIM:
                    dropped[i] = True
                    n_sliver += 1
        i += 1

    # collapse groups left empty (handles Watermark layer wrappers)
    while True:
        stack = []
        newly = []
        for i, line in enumerate(lines):
            if dropped[i]:
                continue
            if G_OPEN_RE.match(line):
                stack.append(i)
            elif G_CLOSE_RE.match(line) and stack:
                j = stack.pop()
                if all(dropped[k] for k in range(j + 1, i)):
                    newly.extend((j, i))
        if not newly:
            break
        for k in newly:
            dropped[k] = True

    kept = [line for i, line in enumerate(lines) if not dropped[i]]

    # drop clipPath definitions no longer referenced
    referenced = set()
    for line in kept:
        referenced.update(CLIP_REF_RE.findall(line))
    out = []
    i = 0
    n_clip = 0
    while i < len(kept):
        m = re.match(r'^\s*<clipPath id="(clip_\d+)">', kept[i])
        if m and m.group(1) not in referenced:
            while i < len(kept) and '</clipPath>' not in kept[i]:
                i += 1
            i += 1  # skip </clipPath>
            n_clip += 1
            continue
        out.append(kept[i])
        i += 1
    kept = out
    if n_clip and '<defs>' in kept and '</defs>' in kept:
        di, dj = kept.index('<defs>'), kept.index('</defs>')
        if all(not kept[k].strip() for k in range(di + 1, dj)):
            del kept[di:dj + 1]

    # drop namespace declarations no longer used
    body = '\n'.join(kept[1:])
    for prefix in ('inkscape', 'xlink'):
        if prefix + ':' not in body:
            kept[0] = re.sub(r'\s+xmlns:%s="[^"]*"' % prefix, '', kept[0])

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8', newline='\n').write('\n'.join(kept) + '\n')
    print('%s -> %s: %d -> %d lines (image=%d text=%d sliver=%d frame=%d '
          'clip=%d)' % (os.path.basename(src), os.path.basename(dst),
                        len(lines), len(kept), n_image, n_text, n_sliver,
                        n_frame, n_clip))


if __name__ == '__main__':
    scrub(sys.argv[1], sys.argv[2])
