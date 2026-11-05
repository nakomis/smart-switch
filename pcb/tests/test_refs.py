"""Reference designators on Petro's front silk, placed where they fit: each beside its part (or on
a big part's own body), clear of pads, other parts, footprint outlines and every other label; parts
in a cluster too tight for one each share a group label ("R1-R4"). The DRC of the whole silk
(tests/test_silk.py) shows no overlaps."""
import re

from board import petro_board as pb
from board import refs
from board.placement import bbox

C = pb.build_petro()
P = pb.place_petro(C)
SILK = pb.silk(C, P)
LABELLED = set(C.instances) - set(pb.UNLABELLED)


def _expand(text):
    """'R1-R4' -> R1..R4; 'C2,C5' -> C2, C5; 'U1' -> U1."""
    out = []
    for part in text.split(","):
        m = re.fullmatch(r"([A-Z]+)(\d+)-(?:[A-Z]+)?(\d+)", part)
        if m:
            out += [f"{m.group(1)}{n}" for n in range(int(m.group(2)), int(m.group(3)) + 1)]
        else:
            out.append(part)
    return out


def _ref_labels():
    return [s for s in SILK if all(r in C.instances for r in _expand(s[0]))]


def test_text_box_turns_with_the_text():
    x0, y0, x1, y1 = refs.text_box("R10", 10.0, 10.0, 0.8)
    assert x1 - x0 > y1 - y0
    rx0, ry0, rx1, ry1 = refs.text_box("R10", 10.0, 10.0, 0.8, 90)
    assert abs((rx1 - rx0) - (y1 - y0)) < 1e-9 and abs((ry1 - ry0) - (x1 - x0)) < 1e-9


def test_every_part_is_labelled_once():
    seen = [r for s in _ref_labels() for r in _expand(s[0])]
    assert sorted(seen) == sorted(LABELLED)


def test_labels_are_on_the_front_beside_their_parts():
    for s in _ref_labels():
        assert (s[4] if len(s) > 4 else "F.SilkS") == "F.SilkS", s
        tx0, ty0, tx1, ty1 = refs.text_box(s[0], s[1], s[2], s[3], s[5] if len(s) > 5 else 0)
        boxes = [bbox(P, ref) for ref in _expand(s[0])]          # a group: beside the cluster
        bx0, by0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        bx1, by1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        gap = max(bx0 - tx1, tx0 - bx1, by0 - ty1, ty0 - by1, 0)
        assert gap < 4.0, (s, gap)


def test_labels_do_not_overlap_each_other():
    boxes = [refs.text_box(s[0], s[1], s[2], s[3], s[5] if len(s) > 5 else 0)
             for s in SILK if (s[4] if len(s) > 4 else "F.SilkS") == "F.SilkS"]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], (a, b)
