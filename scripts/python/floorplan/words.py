"""Assemble words from instance-classified glyph characters (chars.json).

Text on the plans is axis-aligned but can read left-to-right, top-to-bottom,
or bottom-to-top. We run horizontal and vertical line assemblies and resolve
conflicts by preferring longer words.

Bars resolve by word orientation: BARH -> '-' in horizontal words, '1' in
vertical words; BARV -> '1' in horizontal words, '-' in vertical words.

Double-printed labels (same glyph printed twice ~0.3-0.5 units apart) are
deduped at glyph level: centers < 0.9 units apart -> keep best classification.

Vertical words are emitted in the direction that best matches the room
number pattern (floor digit first) or a known label vocabulary.

Post-assembly:
- normalize(): digit/letter lookalike fixes via LABEL_VOCAB and fuzzy
  "OPEN TO BELOW" matching.
- split_space_words(): space-joined words are split back into separate
  labels unless the phrase is "OPEN TO BELOW".
- merge_room_parts(): adjacent fragments on the same baseline are merged
  when the combination forms a valid room number (fixes labels split by
  an over-wide gap).
"""
import json
import re
import sys
from collections import defaultdict

JOIN_GAP = 3.2   # max gap between chars in a word, SVG units
SPACE_GAP = 2.0  # gap above which a space is inserted
LINE_TOL = 1.8   # baseline grouping tolerance
DEDUP_DIST = 0.9 # glyph center distance for double-print dedup
MERGE_GAP = 6.0  # max gap for room-part merging

ROOM_RE = re.compile(r'^\d{4}[A-Z]{0,2}(-\d+)?$')
LABEL_VOCAB = {'UP', 'DN', 'OTB', 'ME', 'TE', 'MT', 'WT', 'CU', 'DU', 'ML',
               'EL', 'TL', 'TT', 'W', 'OPEN', 'TO', 'BELOW'}


def glyph_char(g, vertical):
    if g['bar'] == 'BARH':
        return '1' if vertical else '-'
    if g['bar'] == 'BARV':
        return '-' if vertical else '1'
    return g['char'] if g['char'] is not None else '?'


def dedup_glyphs(glyphs):
    """Collapse double-printed glyphs: same character printed twice with a
    ~0.3-0.5 unit offset. Keep the better classification (mapped beats
    unmapped, then lower template distance)."""
    kept = []
    for g in sorted(glyphs, key=lambda g: (g['center'][0], g['center'][1])):
        for i, h in enumerate(kept):
            if (abs(g['center'][0] - h['center'][0]) < DEDUP_DIST and
                    abs(g['center'][1] - h['center'][1]) < DEDUP_DIST):
                rank = lambda x: (x['char'] is None and x['bar'] is None,
                                  x['d'])
                if rank(g) < rank(h):
                    kept[i] = g
                break
        else:
            kept.append(g)
    return kept


def direction_score(text, floor_digit):
    if floor_digit and ROOM_RE.match(text) and text[0] == floor_digit:
        return 3
    if text in LABEL_VOCAB:
        return 2
    if text[:1].isdigit():
        return 1
    return 0


def fix_direction(w, floor_digit):
    if not w['vertical']:
        return
    rev = w['text'][::-1]
    if direction_score(rev, floor_digit) > direction_score(w['text'],
                                                           floor_digit):
        w['text'] = rev


def levenshtein(a, b):
    dp = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, len(b) + 1):
            prev, dp[j] = dp[j], min(dp[j] + 1, dp[j - 1] + 1,
                                     prev + (a[i - 1] != b[j - 1]))
    return dp[len(b)]


def normalize(w):
    """Fix systematic lookalike misreads using the known label vocabulary."""
    text = w['text']
    if ROOM_RE.match(text) or text in LABEL_VOCAB:
        return
    sub = text.replace('0', 'O')
    if sub in LABEL_VOCAB:
        w['text'] = sub
        return
    if len(text) >= 8 and levenshtein(sub, 'OPEN TO BELOW') <= 3:
        w['text'] = 'OPEN TO BELOW'
        return
    # fuzzy single-word vocab match (e.g. "?PEN"->"OPEN", "T?"->"TO");
    # only when exactly one vocab word is within the distance limit
    if '?' in text and 2 <= len(text) <= 6:
        limit = 1 if len(text) <= 4 else 2
        hits = [v for v in LABEL_VOCAB
                if abs(len(v) - len(text)) <= limit
                and levenshtein(text, v) <= limit]
        if len(hits) == 1:
            w['text'] = hits[0]


def word_from_frags(frags, vertical):
    frags = [(g, f) for g, f in frags if g is not None]
    glyphs = [g for g, _ in frags]
    text = ''.join(frag for _, frag in frags)
    x0 = min(g['bounds'][0] for g in glyphs)
    y0 = min(g['bounds'][1] for g in glyphs)
    x1 = max(g['bounds'][2] for g in glyphs)
    y1 = max(g['bounds'][3] for g in glyphs)
    return {
        'text': text,
        'bounds': (x0, y0, x1, y1),
        'center': ((x0 + x1) / 2, (y0 + y1) / 2),
        'vertical': vertical,
        'glyphs': glyphs,
        'frags': frags,
        'n': len(glyphs),
    }


def split_space_words(words):
    """Split space-joined words back into separate labels, unless the
    phrase normalized to "OPEN TO BELOW"."""
    out = []
    for w in words:
        if ' ' not in w['text'] or w['text'] == 'OPEN TO BELOW':
            out.append(w)
            continue
        parts = [[]]
        for g, frag in w['frags']:
            if g is None:
                parts.append([])
            else:
                parts[-1].append((g, frag))
        for part in parts:
            if part:
                out.append(word_from_frags(part, w['vertical']))
    return out


def merge_room_parts(words, floor_digit):
    """Merge adjacent same-baseline fragments when the combination forms a
    valid room number and at least one fragment is not a valid room number
    on its own (fixes labels split by an over-wide gap)."""
    if not floor_digit:
        return words
    out = list(words)
    changed = True
    while changed:
        changed = False
        for i, a in enumerate(out):
            if a['vertical']:
                continue
            for j, b in enumerate(out):
                if i == j or b['vertical']:
                    continue
                if abs(a['center'][1] - b['center'][1]) > LINE_TOL:
                    continue
                left, right = (a, b) if a['bounds'][0] <= b['bounds'][0] \
                    else (b, a)
                gap = right['bounds'][0] - left['bounds'][2]
                if gap < 0 or gap > MERGE_GAP:
                    continue
                text = left['text'] + right['text']
                if '?' in text:
                    continue
                if not (ROOM_RE.match(text) and text[0] == floor_digit):
                    continue
                if ROOM_RE.match(left['text']) and ROOM_RE.match(right['text']):
                    continue
                merged = word_from_frags(left['frags'] + right['frags'],
                                         False)
                out.remove(left)
                out.remove(right)
                out.append(merged)
                changed = True
                break
            if changed:
                break
    return out


def dedup_words(words):
    """Drop duplicate words (same text, centers within 2 units) left over
    when the glyph-level dedup missed a double-printed label."""
    out = []
    for w in sorted(words, key=lambda w: -w['n']):
        for v in out:
            if (v['text'] == w['text'] and
                    abs(v['center'][0] - w['center'][0]) < 2.0 and
                    abs(v['center'][1] - w['center'][1]) < 2.0):
                break
        else:
            out.append(w)
    return out


def assemble_line(group, vertical):
    """Sort a same-baseline group along the reading axis and emit words."""
    if vertical:
        group.sort(key=lambda g: g['bounds'][1])
    else:
        group.sort(key=lambda g: g['bounds'][0])
    words = []
    cur = []
    cur_end = None
    for g in group:
        start = g['bounds'][1] if vertical else g['bounds'][0]
        if cur and start - cur_end > JOIN_GAP:
            words.append(cur)
            cur = []
        if cur and start - cur_end > SPACE_GAP:
            cur.append((None, ' '))
        cur.append((g, glyph_char(g, vertical)))
        cur_end = max(g['bounds'][3] if vertical else g['bounds'][2],
                      cur_end if cur_end is not None else -1e9)
    if cur:
        words.append(cur)
    return words


def assemble(glyphs, floor_digit=None):
    """Return list of word dicts: text, bounds, center, vertical, frags."""
    # horizontal baselines: group by y center
    by_y = sorted(glyphs, key=lambda g: g['center'][1])
    h_groups = []
    for g in by_y:
        for grp in h_groups:
            if abs(grp[0]['center'][1] - g['center'][1]) < LINE_TOL:
                grp.append(g)
                break
        else:
            h_groups.append([g])
    # vertical baselines: group by x center
    by_x = sorted(glyphs, key=lambda g: g['center'][0])
    v_groups = []
    for g in by_x:
        for grp in v_groups:
            if abs(grp[0]['center'][0] - g['center'][0]) < LINE_TOL:
                grp.append(g)
                break
        else:
            v_groups.append([g])

    candidates = []
    for vertical, groups in ((False, h_groups), (True, v_groups)):
        for grp in groups:
            for frags in assemble_line(grp, vertical):
                frags = [(g, f) for g, f in frags if f != ' ' or g is None]
                glyphs_only = [g for g, f in frags if g is not None]
                if not glyphs_only:
                    continue
                w = word_from_frags(frags, vertical)
                w['text'] = ''.join(f for _, f in frags)
                w['frags'] = frags
                candidates.append(w)
    # conflict resolution: prefer more glyphs, then horizontal
    candidates.sort(key=lambda w: (-w['n'], w['vertical']))
    used = set()
    words = []
    for w in candidates:
        ids = [id(g) for g in w['glyphs']]
        if any(gid in used for gid in ids):
            continue
        used.update(ids)
        words.append(w)
    for w in words:
        fix_direction(w, floor_digit)
        normalize(w)
    words = split_space_words(words)
    words = merge_room_parts(words, floor_digit)
    words = dedup_words(words)
    words.sort(key=lambda w: (w['bounds'][1], w['bounds'][0]))
    return words


if __name__ == '__main__':
    glyphs_json, chars_json, out_json = sys.argv[1], sys.argv[2], sys.argv[3]
    data = json.load(open(glyphs_json))
    chars = json.load(open(chars_json))
    glyphs = []
    for g, c in zip(data['glyphs'], chars):
        glyphs.append({
            'file': g['file'],
            'bounds': tuple(g['bounds']),
            'center': tuple(g['center']),
            'char': c['c'],
            'd': c['d'],
            'bar': c['b'],
        })
    by_file = defaultdict(list)
    for g in glyphs:
        by_file[g['file']].append(g)
    all_words = []
    for fname in sorted(by_file):
        m = re.search(r'039_(\d)', fname)
        floor_digit = m.group(1) if m else None
        words = assemble(dedup_glyphs(by_file[fname]), floor_digit)
        n_bad = sum(1 for w in words if '?' in w['text'])
        mismatches = [w['text'] for w in words
                      if re.match(r'^\d{4}', w['text']) and floor_digit
                      and w['text'][0] != floor_digit]
        print('== %s: %d words (%d with ?, %d floor mismatches) ==' % (
            fname, len(words), n_bad, len(mismatches)))
        for w in words:
            print('  %-22s at (%.0f,%.0f)%s%s' % (
                w['text'], w['center'][0], w['center'][1],
                ' [v]' if w['vertical'] else '',
                ' ?' if '?' in w['text'] else ''))
        if mismatches:
            print('  floor mismatches: %s' % ', '.join(mismatches[:20]))
        for w in words:
            all_words.append({
                'file': fname,
                'text': w['text'],
                'bounds': w['bounds'],
                'center': w['center'],
                'vertical': w['vertical'],
            })
    with open(out_json, 'w') as fh:
        json.dump(all_words, fh)
    print('wrote %s (%d words)' % (out_json, len(all_words)))
