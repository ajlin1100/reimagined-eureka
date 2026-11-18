"""Classify every glyph instance against anchor-derived templates.

Templates come from anchor clusters (anchorcheck.py ground truth), plus their
90-degree rotations to cover vertical text. Bar-shaped glyphs (aspect >= 3)
are classified geometrically as BARH/BARV and resolved to "1"/"-" by word
orientation in words.py.

Output: chars.json - list parallel to glyphs.json glyphs:
  {"c": char-or-null, "d": template distance, "b": "BARH"/"BARV"/null}
"""
import json
import sys
from collections import Counter

import numpy as np

# cluster -> char, from anchor ground truth (glyphs3.json IDs)
ANCHORS = {
    0: '1', 1: '5', 2: '2', 3: 'B', 4: '7', 5: '5', 12: 'M', 13: 'L',
    16: '0', 21: '9', 25: '5', 26: '2', 29: '3', 30: '3', 33: '3', 34: '5',
    35: 'A', 37: '3', 43: '9', 47: '0', 48: '0', 51: '0', 52: '2', 53: '3',
    54: '6', 63: '4', 70: '0', 71: '3', 74: '8', 82: '4', 93: '3', 96: 'D',
    97: 'E', 98: '0', 99: 'F', 100: 'G', 101: 'H', 102: '5', 103: 'J',
    104: '7', 105: 'K', 106: '5', 107: 'N', 114: '3', 119: 'T', 125: 'O',
    126: '6', 127: '9', 128: 'Q', 129: 'P', 130: 'R', 131: 'S', 132: 'U',
    133: 'V', 134: 'M', 135: 'E', 136: 'C', 193: '-', 225: '3', 235: 'D',
    252: '2', 267: 'C', 268: 'G', 270: 'R', 275: '7', 281: 'X', 283: 'Z',
    311: '3', 334: '3', 335: '9', 342: '9', 363: 'Q',
    # from members1.png instance inspection
    10: '4', 124: 'T', 72: '0', 27: '9', 6: '7', 140: 'M', 91: '8',
    55: '2', 42: '9', 113: '5', 44: '6', 89: '5', 205: 'W', 15: 'E',
    46: '8', 50: 'A', 158: '0', 76: '9', 137: 'WT', 84: '5', 92: '6',
    117: '8', 192: '5', 238: '6', 23: '3', 24: '2', 65: '9', 77: '9',
    122: 'B', 167: 'r', 31: 'A', 41: '9', 58: '9', 90: '6', 162: 'n',
    170: 'y', 199: '3', 217: '0', 9: '8', 38: '9',
    # from members2.png instance inspection
    45: '9', 121: 'T', 327: '0', 40: '9', 81: '8', 111: '8', 142: 'T',
    202: '9', 324: '9', 14: 'M', 118: '0', 171: '0', 180: 'e', 203: '6',
    207: 'P', 241: '6', 284: 'F', 290: '0', 320: '0', 441: '0', 20: '6',
    36: 'B', 78: '0', 85: 'AA', 141: 'C', 145: 'WT', 188: 'C', 195: 'D',
    196: 'E', 215: '0', 218: '0', 288: 'E', 19: '3', 57: '9', 60: '2',
    79: '6',
    # from diag.py context reasoning (OTB/CU/BELOW/MUNCHING/room sequences)
    120: 'O', 123: 'O', 138: 'C', 184: 'C', 139: 'U', 185: 'G', 94: 'B',
    112: '9', 110: '8', 56: '9', 22: '0', 108: '8', 80: 'B',
    # from cands.png visual identification
    7: 'F', 11: 'G', 75: '8', 83: '0', 144: 'M', 194: 'C', 197: 'F',
    198: 'G', 200: 'C', 201: 'A', 208: 'N', 210: 'L', 221: '2', 222: '9',
    224: '0', 226: 'C', 227: 'K', 232: 'G', 233: 'R', 234: 'J', 236: 'C',
    237: 'D', 240: '6', 242: '6', 243: '4', 68: '9', 86: '5', 87: '7',
    88: 'C', 143: 'C',
    # from cands2.png visual identification
    389: 'M', 350: '9', 323: '6', 423: '5', 244: '6', 274: 'C', 269: 'Q',
    250: '4', 280: 'V', 209: 'O', 258: '8', 259: '8', 260: 'G', 213: 'O',
    339: '9', 380: '0', 354: 'C', 336: '6', 206: 'O', 282: 'Y',
    # from cands3.png visual identification (floor-3 thin-stroke variants)
    390: 'C', 349: '6', 330: '9', 351: '9', 364: 'R', 365: 'S', 385: 'AA',
    376: 'C', 375: '0', 424: '0', 366: 'Y', 331: '6', 391: 'WT', 386: 'C',
    381: '8', 377: 'G', 388: 'D', 338: '9', 383: 'Q', 337: '9', 352: '6',
    347: '6', 348: '6', 325: '6', 361: 'C',
}

MATCH_THRESHOLD = 10
CANVAS = 28

if __name__ == '__main__':
    npz_path, glyphs_json, out_json = sys.argv[1], sys.argv[2], sys.argv[3]
    z = np.load(npz_path)
    bitmaps, labels = z['bitmaps'], z['labels']
    data = json.load(open(glyphs_json))
    glyphs = data['glyphs']
    counts = {int(k): v for k, v in data['counts'].items()}

    pop = np.array([bin(i).count('1') for i in range(256)], dtype=np.int32)

    # build templates: anchored cluster reps + 90-degree rotations
    t_chars = []
    t_arr = []
    for cid, ch in sorted(ANCHORS.items()):
        idx = int(np.argmax(labels == cid))
        bm = np.unpackbits(bitmaps[idx]).reshape(CANVAS, CANVAS)
        for variant in (bm, np.rot90(bm, 1), np.rot90(bm, -1)):
            t_chars.append(ch)
            t_arr.append(np.packbits(variant))
    t_arr = np.stack(t_arr)

    result = []
    unmapped_clusters = Counter()
    for i, g in enumerate(glyphs):
        x0, y0, x1, y1 = g['bounds']
        bw, bh = x1 - x0, y1 - y0
        if bw > 0 and bh > 0 and max(bw, bh) / min(bw, bh) >= 3.0:
            result.append({'c': None, 'd': 0, 'b': 'BARH' if bw > bh else 'BARV'})
            continue
        dist = pop[np.bitwise_xor(t_arr, bitmaps[i])].sum(axis=1)
        j = int(np.argmin(dist))
        if dist[j] <= MATCH_THRESHOLD:
            result.append({'c': t_chars[j], 'd': int(dist[j]), 'b': None})
        else:
            result.append({'c': None, 'd': int(dist[j]), 'b': None})
            unmapped_clusters[int(labels[i])] += 1

    with open(out_json, 'w') as fh:
        json.dump(result, fh)
    print('wrote', out_json)
    n_mapped = sum(1 for r in result if r['c'] or r['b'])
    print('mapped %d / %d instances' % (n_mapped, len(result)))
    print('unmapped clusters (by unmapped instances):')
    for cid, n in unmapped_clusters.most_common(40):
        print('  cluster %d: %d (cluster total %d)' % (cid, n, counts.get(cid, 0)))
