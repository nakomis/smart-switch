"""Rev B's routing plan: the supply's high-voltage nets and the shunt's Kelvin pair routed by hand
(each net's pads joined, every track at the rules' spacing from other groups' pads), and the
low-voltage router's area and keep-outs (clear of every mains, supply and divider pad)."""
import math

import pytest

from board import petro_board as pb
from board.dsn import ROUTER_MARGIN
from board.gnd import pad_boxes

C = pb.build_petro()
P = pb.place_petro(C)
R = pb.rules()
HAND_NETS = set(pb.PSU_NETS) | set(pb.SWNODE_NETS)


def _seg_box_dist(t, b):
    """Distance from track t's edge to box b (x0, y0, x1, y1)."""
    best = 1e9
    for i in range(41):
        x = t.x1 + (t.x2 - t.x1) * i / 40
        y = t.y1 + (t.y2 - t.y1) * i / 40
        best = min(best, math.hypot(max(b[0] - x, 0, x - b[2]), max(b[1] - y, 0, y - b[3])))
    return best - t.width / 2


def _group(net):
    return pb.GROUPS.get(net, R.rest) if net else R.rest


def _connected(net, tracks, vias):
    """Whether the tracks and vias join every pad of 'net' into one piece."""
    boxes = [b[1:] for b in pad_boxes(C, P) if b[0] == net]
    nodes = [("pad", b) for b in boxes] + [("t", t) for t in tracks if t.net == net] + \
            [("v", v) for v in vias if v.net == net]
    parent = list(range(len(nodes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def pts(n):
        kind, o = n
        if kind == "pad":
            return [((o[0] + o[2]) / 2, (o[1] + o[3]) / 2)]
        if kind == "t":
            return [(o.x1, o.y1), (o.x2, o.y2)]
        return [(o.x, o.y)]

    def touches(a, b):
        for (ka, oa), (kb, ob) in ((a, b), (b, a)):
            if ka == "pad":
                return any(oa[0] - 1e-6 <= x <= oa[2] + 1e-6 and oa[1] - 1e-6 <= y <= oa[3] + 1e-6
                           for x, y in pts((kb, ob)))
        return any(math.hypot(x1 - x2, y1 - y2) < 1e-6 for x1, y1 in pts(a) for x2, y2 in pts(b))

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if touches(nodes[i], nodes[j]):
                parent[find(i)] = find(j)
    return len({find(i) for i in range(len(nodes)) if nodes[i][0] == "pad"}) == 1


@pytest.fixture(scope="module")
def hand():
    return pb.hand_wiring(C, P)


@pytest.mark.parametrize("net", sorted(HAND_NETS))
def test_every_supply_net_is_hand_routed_pad_to_pad(hand, net):
    tracks, vias = hand
    assert _connected(net, tracks, vias), net


def test_hand_tracks_keep_the_matrix_spacing_from_other_pads(hand):
    tracks, _ = hand
    bad = []
    for t in tracks:
        g = _group(t.net)
        for net, *b in pad_boxes(C, P):
            if net == t.net or net is None:
                continue
            need = R.spacing(g, _group(net))
            d = _seg_box_dist(t, b)
            if need and d < need - 1e-6:
                bad.append((t.net, net, round(d, 2), need))
    assert bad == []


def test_the_kelvin_pair_leaves_the_shunt_through_vias_beside_its_sense_pads(hand):
    tracks, vias = hand
    for net, pad in (("GND", "2"), ("SENSE", "3")):
        px, py = pb.pad_xy(C, P, "RS1", pad)
        v = [x for x in vias if x.net == net and math.hypot(x.x - px, x.y - py) < 2.0]
        assert len(v) == 1, net
        assert any(t.net == net and t.layer == "B.Cu" for t in tracks), net


def test_the_low_voltage_area_keeps_off_every_hand_track_of_another_group(hand):
    tracks, _ = hand
    for t in tracks:
        need = R.spacing(_group(t.net), R.rest)
        if not need:
            continue
        for i in range(21):
            x = t.x1 + (t.x2 - t.x1) * i / 20
            y = t.y1 + (t.y2 - t.y1) * i / 20
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (0.7, 0.7), (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7)):
                r = t.width / 2 + need - 0.05
                if pb.in_lv(x + dx * r, y + dy * r):
                    pytest.fail(f"{t.net} track at ({x:.2f}, {y:.2f}): the area comes within {r:.2f} mm")


def test_the_low_voltage_area_keeps_off_every_mains_supply_and_divider_pad():
    """No point of the area outside the keep-outs is nearer to a pad of another group than the
    rules' spacing from the rest of the nets."""
    for net, *b in pad_boxes(C, P):
        need = R.spacing(_group(net), R.rest)
        if not need:
            continue
        for k in range(30):
            for j in range(30):
                x = b[0] - need + (b[2] - b[0] + 2 * need) * k / 29
                y = b[1] - need + (b[3] - b[1] + 2 * need) * j / 29
                d = math.hypot(max(b[0] - x, 0, x - b[2]), max(b[1] - y, 0, y - b[3]))
                if d < need - 0.05 and pb.in_lv(x, y):
                    pytest.fail(f"{net} pad at {b}: ({x:.2f}, {y:.2f}) is in the area, {d:.2f} mm away")


def test_no_keepout_covers_a_pad_its_router_must_reach():
    """Freerouting will not route to a pad inside a keep-out: the low-voltage router's keep-outs
    miss every low-voltage pad, the island router's every island pad. (The bulk capacitors' GND
    leads, 1.9 mm from their own VBULK pads, join the GND pour solidly instead: pb.OWN_LEADS.)"""
    from board.rules import _pad_box
    own_boxes = [list(_pad_box(P, r, q)) for r in pb.OWN_LEADS
                 for q in C.instances[r].part.footprint.pads if C.net_of(r, q.number) == "GND"]
    for keep, mine in ((pb.lv_keepouts(C, P), lambda n: n not in pb.GROUPS),
                       (pb.island_keepouts(C, P), lambda n: pb.GROUPS.get(n) == "SELV")):
        for net, *b in pad_boxes(C, P):
            if net is None or not mine(net) or net.startswith("NC_") or b in own_boxes:
                continue
            for _, x0, y0, x1, y1 in keep:
                gap = math.hypot(max(x0 - b[2], 0, b[0] - x1), max(y0 - b[3], 0, b[1] - y1))
                assert gap >= 0.2 + ROUTER_MARGIN, (net, b, (x0, y0, x1, y1))     # the router's power clearance


def test_the_band_between_the_two_sides_is_kept_out_of_both_routers():
    """Points in the 8 mm band, away from the isolators' pads, are in a keep-out for both."""
    from board.rules import _pad_box
    iso = [_pad_box(P, ref, pad) for ref in pb.BARRIERS for pad in C.instances[ref].part.footprint.pads]
    for keep, ys in ((pb.lv_keepouts(C, P), (pb.ISO_Y - 2.0, pb.ISO_Y, pb.ISO_Y + 2.0, 75.0)),
                     (pb.island_keepouts(C, P), (pb.ISO_Y - 2.0, pb.ISO_Y, pb.ISO_Y + 2.0))):
        for k in range(120):
            for y in ys:
                x = 1.0 + (pb.LV_ISLAND_X - 1.2) * k / 119
                if any(b[0] - 0.3 <= x <= b[2] + 0.3 and b[1] - 0.3 <= y <= b[3] + 0.3 for b in iso):
                    continue
                assert any(x0 <= x <= x1 and y0 <= y <= y1 for _, x0, y0, x1, y1 in keep), (round(x, 2), y)


def test_the_low_voltage_area_keeps_8mm_from_the_island():
    xs = [p[0] for p in pb.island_area()]
    ys = [p[1] for p in pb.island_area()]
    for k in range(200):
        for j in range(60):
            x = min(xs) - 8 + (max(xs) - min(xs) + 16) * k / 199
            y = min(ys) - 8 + (max(ys) - min(ys) + 8) * j / 59
            d = math.hypot(max(min(xs) - x, 0, x - max(xs)), max(min(ys) - y, 0, y - max(ys)))
            if d < 8.0 - 0.05:
                assert not pb._in_poly(x, y, pb.lv_area()), (round(x, 2), round(y, 2), round(d, 2))
