"""Petro's routing plan, before any routing: the two router areas (SELV and the metering island)
keep 8 mm from mains copper and stay apart, the hand-routed divider chain and Kelvin pair are
where they should be, and the island has its own GND_M pour."""
import math

import pytest

from board import petro_board as pb
from board.rules import REINFORCED

C = pb.build_petro()
P = pb.place_petro(C)
MAINS_HC = [z for z in pb.mains_zones()]


def _seg_dist(px, py, a, b):
    (ax, ay), (bx, by) = a, b
    vx, vy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy)))
    return math.hypot(px - ax - t * vx, py - ay - t * vy)


def _poly_dist(pt, poly):
    return min(_seg_dist(*pt, a, b) for a, b in zip(poly, poly[1:] + poly[:1]))


def _inside(pt, poly):
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _samples(poly, step=0.5):
    out = []
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        n = max(1, int(math.hypot(bx - ax, by - ay) / step))
        out += [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(n)]
    return out


def _island_pads():
    from board.gnd import pad_boxes
    return [b for b in pad_boxes(C, P) if b[0] in pb.ISLAND]


def test_selv_area_keeps_8mm_from_every_mains_pour_and_island_pad():
    area, keep = pb.selv_area(), pb.selv_keepouts()
    for pt in _samples(area):
        if any(x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1 for _, x0, y0, x1, y1 in keep):
            continue
        for z in MAINS_HC:
            assert not _inside(pt, z.pts) and _poly_dist(pt, z.pts) >= REINFORCED - 1e-6, (pt, z.net)
        for b in _island_pads():
            d = math.hypot(max(b[1] - pt[0], 0, pt[0] - b[3]), max(b[2] - pt[1], 0, pt[1] - b[4]))
            assert d >= REINFORCED - 1e-6, (pt, b)


def test_selv_area_reaches_every_selv_pad_centre():
    from board.gnd import pad_boxes
    area = pb.selv_area()
    for b in pad_boxes(C, P):
        if b[0] is None or b[0] in pb.GROUPS:
            continue
        c = ((b[1] + b[3]) / 2, (b[2] + b[4]) / 2)
        assert _inside(c, area), (b[0], c)


def test_island_area_reaches_every_island_pad_and_stays_clear_of_selv():
    area = pb.island_area()
    for b in _island_pads():
        c = ((b[1] + b[3]) / 2, (b[2] + b[4]) / 2)
        if b[0] in ("GND_M", "SENSE") and c[0] > 50:      # the shunt's sense pads: Kelvin, by hand
            continue
        assert _inside(c, area), (b[0], c)
    selv_pads = [b for b in __import__("board.gnd").gnd.pad_boxes(C, P)
                 if b[0] is not None and b[0] not in pb.GROUPS]
    for pt in _samples(area):
        for b in selv_pads:
            d = math.hypot(max(b[1] - pt[0], 0, pt[0] - b[3]), max(b[2] - pt[1], 0, pt[1] - b[4]))
            assert d >= REINFORCED - 1e-6, (pt, b)


def test_selv_area_keeps_8mm_from_the_kelvin_pair():
    tracks, vias = pb.kelvin_route(C, P)
    keep = pb.selv_keepouts()
    for pt in _samples(pb.selv_area()):
        if any(x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1 for _, x0, y0, x1, y1 in keep):
            continue
        for t in tracks:
            assert _seg_dist(*pt, (t.x1, t.y1), (t.x2, t.y2)) - t.width / 2 >= REINFORCED - 1e-6, (pt, t.net)


def test_island_area_keeps_line_to_live_from_the_l_in_pads():
    """F1's L_IN clip is LINE; the island is LIVE: 2.5 mm, plus half a track."""
    from board.gnd import pad_boxes
    lin = [b for b in pad_boxes(C, P) if b[0] == "L_IN"]
    for pt in _samples(pb.island_area()):
        for b in lin:
            d = math.hypot(max(b[1] - pt[0], 0, pt[0] - b[3]), max(b[2] - pt[1], 0, pt[1] - b[4]))
            assert d >= 2.5 + 0.15 - 1e-6, (pt, b)


def test_island_area_keeps_off_the_divider_chain():
    from board.gnd import pad_boxes
    area = pb.island_area()
    div = [b for b in pad_boxes(C, P) if b[0] in ("DIV1", "DIV2", "DIV3", "DIV4")]
    for pt in _samples(area):
        for b in div:
            d = math.hypot(max(b[1] - pt[0], 0, pt[0] - b[3]), max(b[2] - pt[1], 0, pt[1] - b[4]))
            assert d >= 1.2 - 1e-6, (pt, b[0])


def test_divider_chain_is_hand_routed_pad_to_pad():
    tracks = pb.divider_tracks(C, P)
    assert {t.net for t in tracks} == {"DIV1", "DIV2", "DIV3", "DIV4"}
    for net in ("DIV1", "DIV2", "DIV3", "DIV4"):
        ends = {(round(t.x1, 2), round(t.y1, 2)) for t in tracks if t.net == net} | \
               {(round(t.x2, 2), round(t.y2, 2)) for t in tracks if t.net == net}
        pads = {(round(x, 2), round(y, 2)) for x, y in (pb.pad_xy(C, P, r, n) for r, n in C.nets[net])}
        assert pads <= ends, net


def test_kelvin_pair_leaves_the_shunt_stacked():
    """SENSE (B.Cu) runs directly under GND_M (F.Cu) from below the shunt to the island, so the
    loop between them encloses almost no area for the load current's field to couple into."""
    tracks, vias = pb.kelvin_route(C, P)
    sense = [t for t in tracks if t.net == "SENSE"]
    gndm = [t for t in tracks if t.net == "GND_M"]
    assert {t.layer for t in gndm} == {"F.Cu"}
    assert [v.net for v in vias] == ["SENSE"]
    common = lambda ts: {((round(t.x1, 2), round(t.y1, 2)), (round(t.x2, 2), round(t.y2, 2))) for t in ts}
    shared = common([t for t in sense if t.layer == "B.Cu"]) & common(gndm)
    run = sum(math.dist(a, b) for a, b in shared)
    assert run > 30.0
    assert (round(sense[0].x1, 2), round(sense[0].y1, 2)) == tuple(round(v, 2) for v in pb.pad_xy(C, P, "RS1", "3"))
    assert (round(gndm[0].x1, 2), round(gndm[0].y1, 2)) == tuple(round(v, 2) for v in pb.pad_xy(C, P, "RS1", "2"))
    end = (gndm[-1].x2, gndm[-1].y2)
    assert _inside(end, pb.island_area())


def test_island_has_its_own_ground_pour():
    (z,) = [z for z in pb.island_zones() if z.net == "GND_M"]
    assert set(z.layers) == {"F.Cu", "B.Cu"}
    assert z.pts == pb.island_area()
    assert z.priority < min(m.priority for m in MAINS_HC)


def test_island_keepouts_stop_tracks_escaping_towards_the_l_in_clip():
    """Freerouting lets a track leave a pad in any direction, out of its area too (a VISO_M track
    left FB1 westwards, 2.25 mm from XF1's L_IN clip). Every point up to 1 mm outside the island
    area that is nearer than 2.5 mm plus half a track to an L_IN pad is in an island keep-out."""
    from board.gnd import pad_boxes
    lin = [b for b in pad_boxes(C, P) if b[0] == "L_IN"]
    area, keep = pb.island_area(), pb.island_keepouts()
    x0 = min(x for x, _ in area) - 1.0
    for i in range(int((max(x for x, _ in area) + 1.0 - x0) / 0.2)):
        for j in range(int((max(y for _, y in area) + 1.0 - 8.0) / 0.2)):
            pt = (x0 + i * 0.2, 8.0 + j * 0.2)
            if _inside(pt, area) or _poly_dist(pt, area) > 1.0:
                continue
            near = any(math.hypot(max(b[1] - pt[0], 0, pt[0] - b[3]), max(b[2] - pt[1], 0, pt[1] - b[4]))
                       < 2.5 + 0.15 for b in lin)
            if near:
                assert any(kx0 <= pt[0] <= kx1 and ky0 <= pt[1] <= ky1 for _, kx0, ky0, kx1, ky1 in keep), pt
