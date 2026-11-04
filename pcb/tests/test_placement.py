"""Petro's placement: every part on the board and clear of the others, mains and SELV pads on
their own sides of the barrier, the barrier parts straddling it, the creepage inside them, the
mounting holes, the antenna, the LED ring and F1's clips."""
import math

import pytest

from board import petro_board as pb
from board.parts import ESP32_ANTENNA
from board.placement import rotate
from board.rules import MAINS_EDGE, REINFORCED, barrier_creepage

C = pb.build_petro()
P = pb.place_petro(C)
MAINS = set(pb.GROUPS)

# SMD parts low enough to sit under F1's fuse body (it is held about 4 mm up by its clips).
LOW = {"C33N", "C100N", "C1U", "C10U", "BEAD", "R1K", "R10K", "R470", "R390K"}


def _box(ref, which="body"):
    x, y, rot = P.at[ref]
    part = C.instances[ref].part
    b = part.body
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


def test_every_part_is_placed():
    assert set(P.at) == set(C.instances)


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


def test_the_antenna_overhangs_the_selv_edge():
    """Rotated 180 degrees, the module's antenna strip begins exactly at the bottom edge."""
    x, y, rot = P.at["U1"]
    assert rot == 180
    a = ESP32_ANTENNA
    y0 = y - a[3]                                      # rotate 180: the strip's inner edge
    assert y0 == pytest.approx(pb.H, abs=0.01)


def _in_mains_area(box):
    x0, x1, ny = pb.RELAY_NOTCH
    limit = ny if x0 <= (box[0] + box[2]) / 2 <= x1 else pb.MAINS_Y
    return box[3] <= limit + 1e-6


def test_mains_and_selv_pads_are_on_their_own_sides():
    """Every mains pad in the mains strip and every SELV pad in the SELV strip, except the
    barrier parts' own pads, whose spacing is their certification's (and the creepage check's)."""
    for ref in C.instances:
        if ref in pb.BARRIERS:
            continue
        for net, box in _pads(ref):
            if net in MAINS:
                assert _in_mains_area(box), (ref, net, box)
            elif net is not None:
                assert box[1] >= pb.SELV_Y - 1e-6, (ref, net, box)


@pytest.mark.parametrize("ref", pb.BARRIERS)
def test_barrier_parts_straddle_with_each_side_where_it_belongs(ref):
    pads = _pads(ref)
    hot = [b for n, b in pads if n in MAINS]
    cold = [b for n, b in pads if n not in MAINS and n is not None]
    assert hot and cold
    assert max(b[3] for b in hot) < min(b[1] for b in cold)          # mains above, SELV below
    gap = min(_gap(h, c) for h in hot for c in cold)
    assert gap >= (REINFORCED if ref != "U4" else 7.0), (ref, gap)   # the ISOW's own 7.1 mm


def test_mains_to_selv_pad_spacing_everywhere():
    """No mains pad within 8 mm of a SELV pad, except within one barrier part."""
    hot = [(r, b) for r in C.instances for n, b in _pads(r) if n in MAINS]
    cold = [(r, b) for r in C.instances for n, b in _pads(r) if n is not None and n not in MAINS]
    bad = [(rh, rc, round(_gap(bh, bc), 2)) for rh, bh in hot for rc, bc in cold
           if not (rh == rc and rh in pb.BARRIERS) and _gap(bh, bc) < REINFORCED]
    assert bad == []


def test_barrier_creepage_with_the_slot():
    assert barrier_creepage(C, P, pb.rules(), pb.slots()) == []


def test_barrier_creepage_fails_without_the_slot():
    """The control: without the slot the ISOW's 7.1 mm is short of 8 mm."""
    assert [b for b in barrier_creepage(C, P, pb.rules(), []) if b[0] == "U4"]


def test_mains_copper_is_3mm_from_the_edges_and_unplated_holes():
    for ref in C.instances:
        for net, b in _pads(ref):
            if net not in MAINS:
                continue
            assert b[0] >= MAINS_EDGE and b[1] >= MAINS_EDGE and b[2] <= pb.W - MAINS_EDGE, (ref, b)
            for h in ("H1", "H2"):
                hx, hy = pb.HOLES[h]
                r = 3.2 / 2
                assert _gap(b, (hx - r, hy - r, hx + r, hy + r)) >= MAINS_EDGE, (ref, h)


def test_holes_in_the_mains_strip_are_unplated():
    assert C.instances["H1"].part.key == C.instances["H2"].part.key == "MHN"
    assert pb.HOLES["H1"][1] < pb.MAINS_Y and pb.HOLES["H3"][1] > pb.SELV_Y


def test_f1_clips_hold_a_32mm_fuse():
    (x1, y1, _), (x2, y2, _) = P.at["XF1"], P.at["XF2"]
    assert y1 == y2 and x2 - x1 == pytest.approx(34.21 - 7.62)


def test_led_ring_is_clear():
    """The light pipe's flange seats on 2 mm of bare board round the LED: no other part's body
    or pad in the ring."""
    ring = pb.led_ring()
    for ref in C.instances:
        if ref == "D1":
            continue
        assert not _overlap(_box(ref), ring), ref
        assert not any(_overlap(b, ring) for _, b in _pads(ref)), ref


def test_neutral_runs_above_the_live_chain():
    """N's pads at both terminals are above (nearer the top edge than) their live pads, so the
    neutral band along the top never has to cross the live chain."""
    for ref in ("J1", "J2"):
        pads = {n: b for n, b in _pads(ref)}
        live = next(n for n in pads if n != "N")
        assert pads["N"][3] < pads[live][1], ref


def test_every_test_hole_is_on_the_selv_side():
    for ref in pb.TEST_HOLES:
        assert P.at[ref][1] > pb.SELV_Y + 1.0, ref


def test_supply_and_relay_test_holes_have_a_gnd_hole_at_one_pitch():
    """So a loop pair, or the probe's spring-ground tip, measures ripple and spikes honestly."""
    gnd = [P.at[r][:2] for r, n in pb.TEST_HOLES.items() if n == "GND"]
    for ref, n in pb.TEST_HOLES.items():
        if n in ("+5V", "+3V3", "COIL"):
            x, y, _ = P.at[ref]
            assert any(math.hypot(x - gx, y - gy) == pytest.approx(2.54) for gx, gy in gnd), ref
