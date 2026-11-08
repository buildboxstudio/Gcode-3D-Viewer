"""Parser regression tests. Run: python tests/test_parser.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gcode_viewer import GCodeParser, ThumbnailExtractor

HERE = os.path.dirname(os.path.abspath(__file__))


def parse(name):
    p = GCodeParser()
    ok = p.parse(os.path.join(HERE, name))
    return p, ok


def counts(p):
    ex = sum(1 for s in p.segments if s[6] == 'extrude')
    return ex, len(p.segments) - ex


def test_cura_g92():
    # Absolute E with G92 E0 per layer: all extrusions must stay visible.
    p, ok = parse('cura_g92.gcode')
    ex, tv = counts(p)
    assert ok, 'file must parse'
    assert (ex, tv) == (6, 4), f'extrude={ex} travel={tv}'
    assert p.layers == [0.2, 0.4, 0.6], f'layers={p.layers}'
    assert p.print_time_seconds == 7530.0


def test_nospace_words():
    p, ok = parse('nospace.gcode')
    ex, tv = counts(p)
    assert ok, 'file must parse'
    assert (ex, tv) == (2, 1), f'extrude={ex} travel={tv}'


def test_zhop_not_layers():
    # Z-hop, nozzle lift and final lift must not create layers.
    p, _ = parse('zhop.gcode')
    assert p.layers == [0.3, 0.55], f'layers={p.layers}'
    assert p.slicer == 'PrusaSlicer'


def test_comment_layer_height_wins():
    p, _ = parse('zhop.gcode')
    assert p.layer_height == 0.2, \
        f'layer_height={p.layer_height} (comment must win over computed)'


def test_first_layer_no_collision():
    p, _ = parse('first_only.gcode')
    assert p.layer_height == 0.3, \
        f'layer_height={p.layer_height} (must not steal first_layer_height)'
    assert p.first_layer_height == 0.25


def test_crlf_thumbnail():
    t = ThumbnailExtractor.extract(os.path.join(HERE, 'crlf_thumb.gcode'))
    assert len(t) >= 1, 'CRLF file must still yield thumbnails'
    assert t[0][0] == 32 and t[0][1] == 32


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
        print(f'PASS {fn.__name__}')
    print(f'{len(tests)}/{len(tests)} tests passed')
