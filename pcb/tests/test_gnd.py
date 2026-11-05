"""Ground drops and stitching (board/gnd.py), generic over the net and the area they may use, on
the fixture board."""
import math

from fixture_board import build_mini, place_mini

from board.gnd import drops, pad_boxes, stitch
from board.kicad_pcb import Track, Via

C = build_mini()
P = place_mini(C)
EVERYWHERE = lambda x, y: 1.0 < x < 39.0 and 1.0 < y < 29.0


def _smd_pads(net):
    return [(r, p.number) for r, i in C.instances.items() for p in i.part.footprint.pads
            if p.kind == "smd" and C.net_of(r, p.number) == net]


def test_pad_boxes_cover_every_copper_pad():
    boxes = pad_boxes(C, P)
    assert len(boxes) == sum(len(i.part.footprint.pads) for i in C.instances.values())
    assert all(b[1] < b[3] and b[2] < b[4] for b in boxes)


def test_a_drop_beside_every_smd_pad_of_the_net():
    tracks, vias, missed = drops(C, P, [], [], "GND", EVERYWHERE)
    assert missed == []
    assert len(vias) == len(tracks) == len(_smd_pads("GND"))
    assert all(v.net == "GND" and t.net == "GND" and t.layer == "F.Cu" for v, t in zip(vias, tracks))


def test_drops_clear_other_nets_pads_tracks_and_each_other():
    other = [Track("+3V3", "F.Cu", 18.0, 18.0, 30.0, 18.0, 0.3)]
    tracks, vias, _ = drops(C, P, other, [], "GND", EVERYWHERE, clear=0.2)
    for v in vias:
        for b in pad_boxes(C, P):
            if b[0] != "GND":
                d = math.hypot(max(b[1] - v.x, 0, v.x - b[3]), max(b[2] - v.y, 0, v.y - b[4]))
                assert d >= v.size / 2 + 0.2 - 1e-9
        assert abs(v.y - 18.0) >= v.size / 2 + 0.15 + 0.2 - 1e-9 or not 18.0 <= v.x <= 30.0
    for a in vias:
        assert all(a is b or math.hypot(a.x - b.x, a.y - b.y) >= 0.8 for b in vias)


def test_drops_stay_inside_their_area():
    left = lambda x, y: 1.0 < x < 22.0 and 1.0 < y < 29.0
    _, vias, missed = drops(C, P, [], [], "GND", left)
    assert vias and all(left(v.x, v.y) for v in vias)
    assert missed           # the pads right of x = 22 find no spot


def test_skip_leaves_a_part_alone():
    _, vias, _ = drops(C, P, [], [], "GND", EVERYWHERE, skip=("U1",))
    assert len(vias) == len(_smd_pads("GND")) - sum(1 for r, _ in _smd_pads("GND") if r == "U1")


def test_stitching_fills_free_board_on_a_grid_and_keeps_clear():
    taken = [Via("GND", 10.0, 25.0)]
    vias = stitch(C, P, [], taken, "GND", EVERYWHERE, pitch=2.0, clear=0.5)
    assert len(vias) > 20
    assert all(v.net == "GND" and EVERYWHERE(v.x, v.y) for v in vias)
    for v in vias:
        assert math.hypot(v.x - 10.0, v.y - 25.0) >= 1.5
        for b in pad_boxes(C, P):
            d = math.hypot(max(b[1] - v.x, 0, v.x - b[3]), max(b[2] - v.y, 0, v.y - b[4]))
            assert d >= v.size / 2 + 0.5 - 1e-9


def test_stitching_avoids_tracks():
    t = Track("DATA", "B.Cu", 2.0, 27.0, 38.0, 27.0, 0.3)
    vias = stitch(C, P, [t], [], "GND", EVERYWHERE, pitch=1.0, clear=0.5)
    assert all(abs(v.y - 27.0) >= 0.3 + 0.15 + 0.5 - 1e-9 for v in vias)


def test_drops_and_stitching_keep_their_copper_off_the_board_edge():
    """A via's copper must stay EDGE_CLEAR (0.3 mm, the DRC's copper-to-edge rule) inside the
    outline, however generous 'inside' is (J5's shell tabs at the edge drew drops 0.19 mm off it)."""
    from board.gnd import EDGE_CLEAR, VIA
    anywhere = lambda x, y: True
    x0, y0, x1, y1 = P.outline
    m = VIA[0] / 2 + EDGE_CLEAR
    _, vias, _ = drops(C, P, [], [], "GND", anywhere)
    vias += stitch(C, P, [], vias, "GND", anywhere)
    assert vias
    for v in vias:
        assert x0 + m - 1e-9 <= v.x <= x1 - m + 1e-9 and y0 + m - 1e-9 <= v.y <= y1 - m + 1e-9, (v.x, v.y)


# --- orphan pour pieces: a via where a piece has none -----------------------------------------
def test_orphan_vias_stitch_a_front_piece_with_no_via_to_the_back_pour():
    from board.gnd import orphan_vias
    front = [[(0, 0), (4, 0), (4, 4), (0, 4)], [(10, 0), (20, 0), (20, 10), (10, 10)]]
    back = [[(-5, -5), (30, -5), (30, 30), (-5, 30)]]
    have = [Via("GND", 15.0, 5.0)]                                  # the big front piece has one
    new = orphan_vias({"F.Cu": front, "B.Cu": back}, have, [], "GND")
    assert len(new) == 1 and new[0].net == "GND"
    v = new[0]
    assert 0.65 <= v.x <= 3.35 and 0.65 <= v.y <= 3.35              # inside the small piece, room round it


def test_orphan_vias_skip_pieces_with_a_through_hole_pad_or_no_back_pour_under_them():
    from board.gnd import orphan_vias
    front = [[(0, 0), (4, 0), (4, 4), (0, 4)], [(10, 0), (14, 0), (14, 4), (10, 4)]]
    back = [[(9, -1), (15, -1), (15, 5), (9, 5)]]                   # only under the second
    new = orphan_vias({"F.Cu": front, "B.Cu": back}, [], [(12.0, 2.0)], "GND")   # ...which has a pad
    assert new == []
