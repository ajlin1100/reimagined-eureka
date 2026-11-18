"""Align visually-verified anchor labels with cluster IDs to build a char map.

Each anchor: (file, x, y, expected text). Glyphs near (x, y) are sorted along
their reading axis and zipped with the expected characters. Prints proposed
cluster->char pairs and any conflicts.
"""
import json
import sys
from collections import defaultdict

ANCHORS = [
    ('039_1_4.svg', 65, 106, '1338'),
    ('039_1_4.svg', 158, 106, '1330'),
    ('039_1_4.svg', 234, 170, '1390'),
    ('039_1_4.svg', 425, 167, '1393'),
    ('039_1_4.svg', 1102, 107, '1570Q'),
    ('039_1_4.svg', 440, 108, '1308'),
    ('039_1_4.svg', 249, 210, '1329'),
    ('039_1_4.svg', 222, 210, '1331'),
    ('039_1_4.svg', 815, 155, 'OTB'),
    ('039_1_4.svg', 247, 116, '1326'),
    ('039_2_3.svg', 58, 104, '2333D'),
    ('039_2_3.svg', 102, 104, '2333C'),
    ('039_2_3.svg', 652, 230, '2417-3'),
    ('039_2_3.svg', 1114, 220, '2570X'),
    ('039_2_3.svg', 1100, 166, '2570Z'),
    ('039_3_0.svg', 746, 89, '3329'),
    ('039_3_0.svg', 531, 105, '3309'),
    ('039_3_0.svg', 1120, 102, '3570Q'),
    # letter anchors
    ('039_1_4.svg', 285, 140, 'MT'),
    ('039_1_4.svg', 536, 148, 'ME'),
    ('039_1_4.svg', 517, 159, 'TE'),
    ('039_1_4.svg', 564, 150, 'CU'),
    ('039_1_4.svg', 232, 147, 'EL'),
    ('039_1_4.svg', 238, 195, '1331A'),
    ('039_1_4.svg', 1100, 81, '1570P'),
    ('039_1_4.svg', 1128, 86, '1570K'),
    ('039_1_4.svg', 1193, 93, '1578R'),
    ('039_1_4.svg', 1195, 119, '1570S'),
    ('039_1_4.svg', 1195, 161, '1570U'),
    ('039_1_4.svg', 1199, 185, '1574V'),
    ('039_1_4.svg', 1150, 152, '1570G'),
    ('039_1_4.svg', 1153, 86, '1570F'),
    ('039_1_4.svg', 1079, 172, '1570N'),
    ('039_1_4.svg', 1109, 178, '1570M'),
    ('039_1_4.svg', 1151, 174, '1570E'),
    ('039_1_4.svg', 1153, 128, '1570H'),
    ('039_1_4.svg', 1195, 142, '1570B'),
    ('039_1_4.svg', 1133, 220, '1570D'),
    ('039_1_4.svg', 1156, 220, '1570T'),
    ('039_2_3.svg', 64, 247, '2333F'),
    ('039_2_3.svg', 48, 207, '2333G'),
    ('039_2_3.svg', 41, 247, '2333H'),
    ('039_2_3.svg', 134, 247, '2333N'),
    ('039_2_3.svg', 154, 247, '2333P'),
    ('039_2_3.svg', 177, 247, '2333S'),
    ('039_2_3.svg', 198, 247, '2333T'),
    ('039_2_3.svg', 185, 207, '2333R'),
    ('039_2_3.svg', 109, 207, '2333M'),
    ('039_2_3.svg', 70, 207, '2333E'),
    ('039_2_3.svg', 190, 104, '2333A'),
]

if __name__ == '__main__':
    data = json.load(open(sys.argv[1]))
    glyphs = [(g, lb) for g, lb in zip(data['glyphs'], data['labels'])]
    votes = defaultdict(set)
    for fname, x, y, text in ANCHORS:
        near = [(g, lb) for g, lb in glyphs
                if g['file'] == fname
                and abs(g['center'][0] - x) < 12 and abs(g['center'][1] - y) < 5]
        near.sort(key=lambda t: t[0]['bounds'][0])
        print('%s (%d,%d) "%s": %d glyphs' % (fname, x, y, text, len(near)))
        if len(near) != len(text):
            print('  MISMATCH: glyphs=%s' % [lb for _, lb in near])
            continue
        for (g, lb), ch in zip(near, text):
            votes[lb].add(ch)
            print('  cluster %-4d -> %s' % (lb, ch))
    print()
    print('== conflicts ==')
    for lb in sorted(votes):
        if len(votes[lb]) > 1:
            print('  cluster %d: %s' % (lb, sorted(votes[lb])))
    print('== clean ==')
    for lb in sorted(votes):
        if len(votes[lb]) == 1:
            print('  %d: %r,' % (lb, next(iter(votes[lb]))))
