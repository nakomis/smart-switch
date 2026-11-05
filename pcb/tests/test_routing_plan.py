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
HAND_NETS = set(pb.SUPPLY_HV_NETS) | set(pb.SWNODE_NETS)


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


def _own_lead(ref, n1, n2):
    """The reduced spacing where copper of a rated part's own net pair meets its pad (OWN_LEADS)."""
    mm, pair = pb.OWN_LEADS.get(ref, (None, ()))
    return mm if {n1, n2} == set(pair) else None


def test_hand_tracks_keep_the_matrix_spacing_from_other_pads(hand):
    from board.rules import _pad_box
    tracks, _ = hand
    pads = [(ref, C.net_of(ref, q.number), list(_pad_box(P, ref, q)))
            for ref in C.instances for q in C.instances[ref].part.footprint.pads]
    bad = []
    for t in tracks:
        g = _group(t.net)
        for ref, net, b in pads:
            if net == t.net or net is None:
                continue
            own = _own_lead(ref, t.net, net)
            need = own if own is not None else R.spacing(g, _group(net))
            d = _seg_box_dist(t, b)
            if need and d < need - 1e-6:
                bad.append((t.net, ref, net, round(d, 2), need))
    assert bad == []


def test_the_kelvin_pair_leaves_the_shunt_through_vias_beside_its_sense_pads(hand):
    tracks, vias = hand
    for net, pad in (("KGND", "2"), ("SENSE", "3")):
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
    """Freerouting will not route to a pad inside a keep-out: the router's keep-outs miss every
    low-voltage pad. (The bulk capacitors' GND
    leads, 1.9 mm from their own VBULK pads, join the GND pour solidly instead: pb.OWN_LEADS.)"""
    from board.rules import _pad_box
    own_boxes = [list(_pad_box(P, r, q)) for r in pb.OWN_LEADS
                 for q in C.instances[r].part.footprint.pads if C.net_of(r, q.number) == "GND"]
    keep = pb.lv_keepouts(C, P)
    rs1 = [list(_pad_box(P, "RS1", q)) for q in C.instances["RS1"].part.footprint.pads]   # the Kelvin pair is by hand
    for net, *b in pad_boxes(C, P):
        if net is None or net in pb.GROUPS or net.startswith("NC_") or b in own_boxes or b in rs1:
            continue
        for _, x0, y0, x1, y1 in keep:
            gap = math.hypot(max(x0 - b[2], 0, b[0] - x1), max(y0 - b[3], 0, b[1] - y1))
            assert gap >= 0.2 + ROUTER_MARGIN, (net, b, (x0, y0, x1, y1))     # the router's power clearance


def test_smd_supply_pads_keep_the_router_off_f_cu_only():
    """Under an SMD pad, B.Cu is the far side of the board: the router may use it."""
    keep = pb.lv_keepouts(C, P)
    for ref, n in (("U4", "1"), ("U4", "4"), ("R2", "1"), ("R3", "2")):        # BP, D, FBH, SW
        x, y = pb.pad_xy(C, P, ref, n)
        on = {layer for layer, x0, y0, x1, y1 in keep if x0 <= x <= x1 and y0 <= y <= y1}
        assert "F.Cu" in on and "B.Cu" not in on, (ref, n, on)


def test_the_regulator_ground_is_tied_to_its_output_capacitor_by_hand():
    """U2's GND pin to C19's GND pad, before routing: the router left them in separate pieces
    of pour, walled apart on both layers."""
    tracks, _ = pb.ldo_ground(C, P)
    assert _connected_pads("GND", tracks, [("U2", "2"), ("C19", "2")])
    others = [(net, b) for net, *b in pad_boxes(C, P) if net not in ("GND", None)]
    for t in tracks:
        for net, b in others:
            assert _seg_box_dist(t, b) >= 0.26, (net, b)          # the router's power clearance


def _connected_pads(net, tracks, pads):
    from board.rules import _pad_box
    boxes = [_pad_box(P, r, next(q for q in C.instances[r].part.footprint.pads if q.number == n)) for r, n in pads]
    pts = {(round(x, 3), round(y, 3)) for t in tracks for x, y in ((t.x1, t.y1), (t.x2, t.y2))}
    ends = lambda b: [pt for pt in pts if b[0] <= pt[0] <= b[2] and b[1] <= pt[1] <= b[3]]
    if not all(ends(b) for b in boxes):
        return False
    # the tracks form one chain: union by shared end points
    par = {pt: pt for pt in pts}

    def f(a):
        while par[a] != a:
            a = par[a]
        return a
    for t in tracks:
        a, b = (round(t.x1, 3), round(t.y1, 3)), (round(t.x2, 3), round(t.y2, 3))
        par[f(a)] = f(b)
    return len({f(ends(b)[0]) for b in boxes}) == 1


def test_the_router_area_holds_j3_and_its_resistors_whole():
    """Freerouting takes its area for the board outline: a pad that pokes out of it is a standing
    violation it cannot route to. J3 sits on the bottom edge, where the safe I/O island was."""
    from board.rules import _pad_box
    for ref in ("J3", "R26", "R27", "R28"):
        for q in C.instances[ref].part.footprint.pads:
            x0, y0, x1, y1 = _pad_box(P, ref, q)
            for x, y in ((x0 - 0.3, y0 - 0.3), (x1 + 0.3, y0 - 0.3), (x0 - 0.3, y1 + 0.3), (x1 + 0.3, y1 + 0.3)):
                assert pb._in_poly(x, y, pb.lv_area()), (ref, q.number)


@pytest.mark.parametrize("net", ["KGND", "SENSE"])
def test_the_kelvin_pair_is_complete_by_hand(net):
    """Shunt to both filter resistors, by hand: the router never touches the sense lines."""
    tracks, vias = pb.kelvin_route(C, P)
    assert _connected(net, tracks, vias), net


def test_the_kelvin_pair_never_crosses_and_keeps_off_the_live():
    """KGND and SENSE on B.Cu never cross (KGND above SENSE all the way), and both keep the 2.5 mm
    to L_F's pour and the MOV's live lead."""
    tracks, _ = pb.kelvin_route(C, P)
    bk = [t for t in tracks if t.layer == "B.Cu" and t.net == "KGND"]
    bs = [t for t in tracks if t.layer == "B.Cu" and t.net == "SENSE"]

    def cross(a, b):
        f = lambda p, q, r: (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        p1, p2, q1, q2 = (a.x1, a.y1), (a.x2, a.y2), (b.x1, b.y1), (b.x2, b.y2)
        return f(p1, p2, q1) * f(p1, p2, q2) < 0 and f(q1, q2, p1) * f(q1, q2, p2) < 0
    assert not any(cross(a, b) for a in bk for b in bs)
    lf = pb.MAINS_POLYS["L_F"]
    for t in bk + bs:
        for k in range(21):
            x, y = t.x1 + (t.x2 - t.x1) * k / 20, t.y1 + (t.y2 - t.y1) * k / 20
            d = min(math.hypot(max(min(a[0], b[0]) - x, 0, x - max(a[0], b[0])),
                               max(min(a[1], b[1]) - y, 0, y - max(a[1], b[1])))
                    for a, b in zip(lf, lf[1:] + lf[:1]))
            assert pb._in_poly(x, y, lf) is False and d - t.width / 2 >= 2.5, (t, round(d, 2))


def test_the_kelvin_vias_and_top_tracks_keep_the_routers_clearance_from_other_pads():
    tracks, vias = pb.kelvin_route(C, P)
    for kn in ("KGND", "SENSE"):
        others = [(net, b) for net, *b in pad_boxes(C, P) if net not in (kn, None)]
        for v in [v for v in vias if v.net == kn]:
            for net, b in others:
                d = math.hypot(max(b[0] - v.x, 0, v.x - b[2]), max(b[1] - v.y, 0, v.y - b[3])) - v.size / 2
                assert d >= 0.26, (kn, net, b, round(d, 3))
        for t in [t for t in tracks if t.net == kn and t.layer == "F.Cu"]:
            for net, b in others:
                if net not in pb.GROUPS:
                    assert _seg_box_dist(t, b) >= 0.26, (t, net, b)


def test_the_router_keeps_off_the_top_neutral_round_the_shunt():
    """Only the hand-routed Kelvin pair may cross the top layer's neutral round RS1."""
    x0, y0, x1, y1 = pb.SHUNT_KEEPOUT
    assert ("F.Cu", x0, y0, x1, y1) in pb.lv_keepouts(C, P)
    for ref in ("R8", "R9", "R10", "R11"):                       # the sense filters stay reachable
        for q in C.instances[ref].part.footprint.pads:
            assert pb.pad_xy(C, P, ref, q.number)[1] > y1 + 1.0, ref


def test_the_usb_protections_flow_through_pins_are_tied_by_hand():
    tracks, _ = pb.usb_ties(C, P)
    assert _connected_pads("USB_DM", [t for t in tracks if t.net == "USB_DM"], [("U6", "1"), ("U6", "6"), ("J4", "2")])
    assert _connected_pads("USB_DP", [t for t in tracks if t.net == "USB_DP"], [("U6", "3"), ("U6", "4"), ("J4", "3")])
    for t in tracks:
        for net, *b in pad_boxes(C, P):
            if net not in (t.net, None):
                assert _seg_box_dist(t, b) >= 0.26, (t.net, net, b)
