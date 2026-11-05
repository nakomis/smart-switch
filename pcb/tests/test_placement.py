"""Petro's placement, revision B (non-isolated): every part on the board and clear of the others,
every pair of pads on different parts as far apart as the working-voltage matrix needs (the rest
at neutral), all copper 3 mm from the mounting holes, the antenna, the LED ring and F1's clips."""
import math

import pytest

from board import petro_board as pb
from board.parts import ESP32C6_ANTENNA as ESP32_ANTENNA
from board.placement import rotate
from board.rules import MAINS_EDGE

C = pb.build_petro()
P = pb.place_petro(C)
R = pb.rules()

# SMD parts low enough to sit under F1's fuse body (it is held about 4 mm up by its clips).
LOW = {"C33N", "C100N", "C1U", "C10U", "R1K", "R10K", "R470", "R390K", "C100N6"}


def _box(ref):
    x, y, rot = P.at[ref]
    b = C.instances[ref].part.body
    pts = [rotate(px, py, rot) for px in (b[0], b[2]) for py in (b[1], b[3])]
    return (x + min(p[0] for p in pts), y + min(p[1] for p in pts),
            x + max(p[0] for p in pts), y + max(p[1] for p in pts))


def _pads(ref):
    """(net, box) of every copper pad of ref, in board coordinates."""
    x, y, rot = P.at[ref]
    out = []
    for pad in C.instances[ref].part.footprint.pads:
        if pad.kind == "np_thru_hole":
            continue
        corners = [rotate(px, py, rot) for px in (pad.x - pad.w / 2, pad.x + pad.w / 2)
                   for py in (pad.y - pad.h / 2, pad.y + pad.h / 2)]
        out.append((C.net_of(ref, pad.number) if pad.number else None,
                    (x + min(c[0] for c in corners), y + min(c[1] for c in corners),
                     x + max(c[0] for c in corners), y + max(c[1] for c in corners))))
    return out


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _gap(a, b):
    dx = max(a[0] - b[2], 0.0, b[0] - a[2])
    dy = max(a[1] - b[3], 0.0, b[1] - a[3])
    return math.hypot(dx, dy)


def _group(net):
    return pb.GROUPS.get(net, R.rest) if net else R.rest


def test_every_part_is_placed():
    assert set(P.at) == set(C.instances)


def test_board_is_120_by_85():
    assert P.outline == (0.0, 0.0, 120.0, 85.0)


def test_bodies_do_not_overlap():
    refs = sorted(C.instances)
    bad = [(a, b) for i, a in enumerate(refs) for b in refs[i + 1:] if _overlap(_box(a), _box(b))]
    assert bad == []


def test_only_low_parts_sit_under_the_fuse():
    f = pb.fuse_box()
    under = [r for r in C.instances if _overlap(_box(r), f) and not r.startswith("XF")]
    assert all(C.instances[r].part.key in LOW for r in under), under


def test_everything_is_on_the_board_except_the_antenna():
    for ref in C.instances:
        b = _box(ref)
        if ref == "U1":
            b = (b[0], b[1], b[2], b[3] - (ESP32_ANTENNA[3] - ESP32_ANTENNA[1]))
        assert b[0] >= -1e-6 and b[1] >= -1e-6 and b[2] <= pb.W + 1e-6 and b[3] <= pb.H + 1e-6, (ref, b)


def test_the_antenna_overhangs_the_bottom_edge():
    x, y, rot = P.at["U1"]
    assert rot == 180
    assert y - ESP32_ANTENNA[3] == pytest.approx(pb.H, abs=0.01)


def test_pads_of_different_parts_keep_the_matrix_spacing():
    """Every pair of pads on different parts, on nets of different potential groups, at least
    the creepage for their working voltage apart (the rest of the nets at neutral)."""
    pads = [(ref, net, box) for ref in C.instances for net, box in _pads(ref)]
    bad = []
    for i, (ra, na, ba) in enumerate(pads):
        ga = _group(na)
        for rb, nb, bb in pads[i + 1:]:
            if ra == rb or na == nb:
                continue
            gb = _group(nb)
            need = R.spacing(ga, gb)
            if need and _gap(ba, bb) < need - 1e-6:
                bad.append((ra, na, rb, nb, round(_gap(ba, bb), 2), need))
    assert bad == []


def test_all_copper_keeps_3mm_from_the_mounting_holes():
    for h, (hx, hy) in pb.HOLES.items():
        assert C.instances[h].part.key == "MHN"
        r = 3.2 / 2 + MAINS_EDGE
        for ref in C.instances:
            if ref == h:
                continue
            for net, b in _pads(ref):
                d = math.hypot(max(b[0] - hx, 0, hx - b[2]), max(b[1] - hy, 0, hy - b[3]))
                assert d >= r - 1e-6, (h, ref, net, round(d, 2))


def test_mains_pads_keep_3mm_from_the_edges():
    for ref in C.instances:
        for net, b in _pads(ref):
            if net in pb.GROUPS and pb.GROUPS[net] != "SELV":           # the island may reach the edge
                assert min(b[0], b[1], pb.W - b[2], pb.H - b[3]) >= MAINS_EDGE - 1e-6, (ref, net)


def test_f1_clips_hold_a_32mm_fuse():
    a, b = P.at["XF1"], P.at["XF2"]
    assert b[0] - a[0] == pytest.approx(pb.F1_CLIP_PITCH) and a[1] == b[1]


def test_led_ring_is_clear():
    ring = pb.led_ring()
    for ref in C.instances:
        if ref != "D1":
            assert not _overlap(_box(ref), ring), ref


def test_the_shunt_sits_in_the_neutral_strip_with_n_in_west():
    (x1, _), (x2, _) = pb.pad_xy(C, P, "RS1", "1"), pb.pad_xy(C, P, "RS1", "4")
    assert C.net_of("RS1", "1") == "N_IN" and x1 < x2
    assert P.at["RS1"][1] < 10


def test_every_test_hole_is_on_a_low_voltage_net():
    for ref, net in pb.TEST_HOLES.items():
        assert net not in pb.GROUPS


# --- the safe I/O island ------------------------------------------------------------------------

def _poly_dist(b, poly):
    """Distance from box b to an axis-aligned rectangle given as a 4-point polygon."""
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return math.hypot(max(min(xs) - b[2], 0, b[0] - max(xs)), max(min(ys) - b[3], 0, b[1] - max(ys)))


def test_every_island_pad_is_in_the_island():
    area = pb.island_area()
    for ref in C.instances:
        for net, b in _pads(ref):
            if pb.GROUPS.get(net) == "SELV":
                assert _poly_dist(b, area) == 0 and pb._in_poly((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, area), (ref, net)


def test_everything_else_keeps_8mm_from_the_island():
    """Bar the isolators' own board-side pads, which the slot takes care of."""
    area = pb.island_area()
    for ref in C.instances:
        for net, b in _pads(ref):
            if pb.GROUPS.get(net) == "SELV":
                continue
            if ref in pb.BARRIERS:
                assert _poly_dist(b, area) >= 7.1 - 1e-6, (ref, net)
            else:
                assert _poly_dist(b, area) >= 8.0 - 1e-6, (ref, net, round(_poly_dist(b, area), 2))


def test_the_isolators_face_the_island_across_the_slot():
    (slot,) = pb.slots()
    for ref in pb.BARRIERS:
        for net, b in _pads(ref):
            cy = (b[1] + b[3]) / 2
            assert (cy > pb.ISO_Y) == (pb.GROUPS.get(net) == "SELV"), (ref, net)
            assert b[1] - (slot.y1 + slot.width / 2) >= 1.0 - 1e-6 or (slot.y1 - slot.width / 2) - b[3] >= 1.0 - 1e-6
        x0, _, x1, _ = _box(ref)
        assert min(slot.x1, slot.x2) < x0 and max(slot.x1, slot.x2) > x1, ref


def test_j3_opens_onto_the_bottom_edge():
    x0, y0, x1, y1 = _box("J3")
    assert pb.H - 0.6 <= y1 <= pb.H and P.at["J3"][2] == 0      # wire openings on its +y side
