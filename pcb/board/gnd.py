"""Ground drops and stitching vias for a pour net, on a 2-layer board.

A drop is a via beside an SMD pad of the net, joined to it by a short F.Cu track, so the pad
reaches the B.Cu pour even where routed tracks wall it off from the F.Cu pour. Stitching vias
join the two pours on a grid wherever there is room. Both keep to an area (a predicate on x, y),
so one board can have more than one ground (Petro's SELV GND and its metering island's GND_M).
From the nakostat heatlink (heatlink_board.gnd_drops/stitch_vias), made generic."""
import math

from board.kicad_pcb import Track, Via
from board.placement import rotate

VIA = (0.6, 0.3)           # size, drill: the router's own via
EDGE_CLEAR = 0.3           # mm of board between a via's copper and the edge (the DRC's rule)
DROP_RINGS = (1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.3, 2.6, 3.0)


def pad_boxes(circuit, placement):
    """(net, xmin, ymin, xmax, ymax) for every pad, in board coordinates."""
    out = []
    for ref, inst in circuit.instances.items():
        x, y, rot = placement.at[ref]
        for pad in inst.part.footprint.pads:
            dx, dy = rotate(pad.x, pad.y, rot)
            w, h = (pad.h, pad.w) if round(pad.rot + rot) % 180 == 90 else (pad.w, pad.h)
            out.append((circuit.net_of(ref, pad.number) if pad.number else None,
                        x + dx - w / 2, y + dy - h / 2, x + dx + w / 2, y + dy + h / 2))
    return out


def _seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = 0.0 if vx == vy == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy)))
    return math.hypot(px - ax - t * vx, py - ay - t * vy)


def _box_dist(x, y, box):
    _, x0, y0, x1, y1 = box
    return math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1))


def _on_board(placement, x, y, r):
    x0, y0, x1, y1 = placement.outline
    m = r + EDGE_CLEAR
    return x0 + m <= x <= x1 - m and y0 + m <= y <= y1 - m


def _sampled(ax, ay, bx, by, n=20):
    return [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(n + 1)]


def drops(circuit, placement, tracks, vias, net, inside, clear=0.2, skip=(), width=0.3):
    """(tracks, vias, missed): a drop for every SMD pad on 'net' (but not the parts in 'skip'),
    at the first free spot on rings 1.0 to 3.0 mm round the pad centre that is 'inside' and
    clears every other net's pad and track, and every via, by 'clear'. 'missed' lists the pads
    ("REF.PAD") that found no spot."""
    size, drill = VIA
    r = size / 2
    pads = pad_boxes(circuit, placement)
    placed, lines = list(vias), list(tracks)
    out_t, out_v, missed = [], [], []
    for ref, inst in circuit.instances.items():
        if ref in skip:
            continue
        x, y, rot = placement.at[ref]
        for pad in inst.part.footprint.pads:
            if pad.kind != "smd" or circuit.net_of(ref, pad.number) != net:
                continue
            dx, dy = rotate(pad.x, pad.y, rot)
            px, py = x + dx, y + dy
            spot = None
            for dist in DROP_RINGS:
                for k in range(24):
                    a = 2 * math.pi * k / 24
                    vx, vy = px + dist * math.cos(a), py + dist * math.sin(a)
                    if not inside(vx, vy) or not _on_board(placement, vx, vy, r):
                        continue
                    ok = all(b[0] == net or _box_dist(vx, vy, b) >= r + clear for b in pads)
                    ok = ok and all(t.net == net or _seg_dist(vx, vy, t.x1, t.y1, t.x2, t.y2) >= r + t.width / 2 + clear
                                    for t in lines)
                    ok = ok and all(math.hypot(vx - v.x, vy - v.y) >= 0.8 for v in placed)
                    # the joining track must clear other nets too
                    path = _sampled(px, py, vx, vy)
                    ok = ok and all(b[0] == net or min(_box_dist(sx, sy, b) for sx, sy in path) >= width / 2 + clear
                                    for b in pads)
                    ok = ok and all(t.net == net or min(_seg_dist(sx, sy, t.x1, t.y1, t.x2, t.y2) for sx, sy in path)
                                    >= width / 2 + t.width / 2 + clear for t in lines)
                    if ok:
                        spot = (round(vx, 3), round(vy, 3))
                        break
                if spot:
                    break
            if spot is None:
                missed.append(f"{ref}.{pad.number}")
                continue
            v = Via(net, *spot, size, drill)
            t = Track(net, "F.Cu", round(px, 4), round(py, 4), spot[0], spot[1], width)
            placed.append(v)
            lines.append(t)
            out_v.append(v)
            out_t.append(t)
    return out_t, out_v, missed


def stitch(circuit, placement, tracks, vias, net, inside, pitch=2.0, clear=0.5, spacing=1.5):
    """Stitching vias on 'net' on a 'pitch' grid over the board, wherever a via is 'inside' and
    clears every pad and track by 'clear' and every via by 'spacing' (centre to centre), so that
    both pours reach it."""
    size, drill = VIA
    r = size / 2
    pads = pad_boxes(circuit, placement)
    placed, out = list(vias), []
    x0, y0, x1, y1 = placement.outline
    y = y0 + pitch / 2
    while y < y1:
        x = x0 + pitch / 2
        while x < x1:
            ok = inside(x, y) and _on_board(placement, x, y, r)
            ok = ok and all(_box_dist(x, y, b) >= r + clear for b in pads)
            ok = ok and all(_seg_dist(x, y, t.x1, t.y1, t.x2, t.y2) >= r + t.width / 2 + clear for t in tracks)
            ok = ok and all(math.hypot(x - v.x, y - v.y) >= spacing for v in placed)
            if ok:
                v = Via(net, round(x, 3), round(y, 3), size, drill)
                out.append(v)
                placed.append(v)
            x += pitch
        y += pitch
    return out
