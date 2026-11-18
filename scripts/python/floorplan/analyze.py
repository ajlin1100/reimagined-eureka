"""Analyze path characteristics in the floor plan SVGs."""
import sys
from collections import Counter

from fp import parse_svg


def analyze(path):
    w, h, recs = parse_svg(path)
    print('== %s ==' % path.split('\\')[-1])
    print('sheet %.0fx%.0f, %d paths' % (w, h, len(recs)))

    filled = [r for r in recs if r.filled]
    stroked = [r for r in recs if r.stroked]
    print('stroked: %d, filled: %d' % (len(stroked), len(filled)))

    # Filled path size distribution (slivers vs solid fills)
    def min_dim(r):
        b = r.bounds()
        return min(b[2] - b[0], b[3] - b[1]) if b else 0

    def area(r):
        b = r.bounds()
        return (b[2] - b[0]) * (b[3] - b[1]) if b else 0

    slivers = [r for r in filled if min_dim(r) < 0.15]
    solids = [r for r in filled if min_dim(r) >= 0.15]
    print('filled slivers (min_dim<0.15): %d' % len(slivers))
    print('filled solids (min_dim>=0.15): %d' % len(solids))
    if solids:
        areas = sorted(area(r) for r in solids)
        print('  solid area range: %.2f .. %.2f' % (areas[0], areas[-1]))
        big = [r for r in solids if area(r) > 100]
        print('  solids >100 sq units: %d' % len(big))
        for r in big[:5]:
            b = r.bounds()
            print('    bounds (%.1f,%.1f)-(%.1f,%.1f)' % b)

    # Stroke width distribution
    sw = Counter(round(r.stroke_width, 3) for r in stroked)
    print('stroke widths:', dict(sorted(sw.items())))

    # Glyph candidates: small stroked paths
    def max_dim(r):
        b = r.bounds()
        return max(b[2] - b[0], b[3] - b[1]) if b else 0

    glyphs = [r for r in stroked if max_dim(r) <= 8 and r.stroke_width <= 0.3]
    print('glyph candidates (maxdim<=8, sw<=0.3): %d' % len(glyphs))
    pts = Counter(min(sum(len(pl) for pl in r.polylines), 60) for r in glyphs)
    print('  point-count hist (top):', pts.most_common(8))
    print()


if __name__ == '__main__':
    for p in sys.argv[1:]:
        analyze(p)
