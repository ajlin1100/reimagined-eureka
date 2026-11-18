"""Diagnose unmapped glyphs: for each '?' word, show the unmapped glyphs'
cluster, nearest template char, and distance."""
import json
import re
import sys
from collections import Counter, defaultdict

import numpy as np

from automap import ANCHORS, MATCH_THRESHOLD, CANVAS
from words import assemble, dedup_glyphs

npz_path, glyphs_json, chars_json = sys.argv[1], sys.argv[2], sys.argv[3]
z = np.load(npz_path)
bitmaps, labels = z['bitmaps'], z['labels']
data = json.load(open(glyphs_json))
chars = json.load(open(chars_json))

pop = np.array([bin(i).count('1') for i in range(256)], dtype=np.int32)
t_chars = []
t_arr = []
for cid, ch in sorted(ANCHORS.items()):
    idx = int(np.argmax(labels == cid))
    bm = np.unpackbits(bitmaps[idx]).reshape(CANVAS, CANVAS)
    for variant in (bm, np.rot90(bm, 1), np.rot90(bm, -1)):
        t_chars.append(ch)
        t_arr.append(np.packbits(variant))
t_arr = np.stack(t_arr)

glyphs = []
for i, (g, c) in enumerate(zip(data['glyphs'], chars)):
    glyphs.append({
        'file': g['file'],
        'bounds': tuple(g['bounds']),
        'center': tuple(g['center']),
        'char': c['c'],
        'd': c['d'],
        'bar': c['b'],
        'cluster': int(labels[i]),
        'idx': i,
    })

by_file = defaultdict(list)
for g in glyphs:
    by_file[g['file']].append(g)

# map id() -> glyph for word glyph lookup
rows = []
for fname in sorted(by_file):
    m = re.search(r'039_(\d)', fname)
    floor_digit = m.group(1) if m else None
    fglyphs = dedup_glyphs(by_file[fname])
    words = assemble(fglyphs, floor_digit)
    for w in words:
        if '?' not in w['text']:
            continue
        for g in w['glyphs']:
            if g['char'] is not None or g['bar'] is not None:
                continue
            dist = pop[np.bitwise_xor(t_arr, bitmaps[g['idx']])].sum(axis=1)
            j = int(np.argmin(dist))
            rows.append((fname, w['text'], w['vertical'], g['cluster'],
                         t_chars[j], int(dist[j]),
                         round(g['center'][0]), round(g['center'][1])))

rows.sort(key=lambda r: (r[3], r[0]))
print('unmapped glyphs in ? words: %d' % len(rows))
for r in rows:
    print('  %-12s %-14s%s cl=%-4d near=%-2s d=%-3d at (%d,%d)' % (
        r[0], r[1], '[v]' if r[2] else '', r[3], r[4], r[5], r[6], r[7]))
