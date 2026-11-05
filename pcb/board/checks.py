"""Checks on a filled board that KiCad's DRC doesn't make: the high-current pours must each be one
piece on each layer, reaching every through-hole pad of their net on that layer, so the two
layers carry the current in parallel all the way (each at least the zone's min_thickness wide)."""
from collections import defaultdict

from board.placement import rotate
from board.sexpr import find, find_all, parse


def inside(pt, poly):
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def filled(board_path):
    """{(net, layer): [polygon, ...]} of a board's filled zones (after a refill and save)."""
    polys = defaultdict(list)
    for z in find_all(parse(open(board_path).read()), "zone"):
        for fp in find_all(z, "filled_polygon"):
            pts = [(float(p[1]), float(p[2])) for p in find_all(find(fp, "pts"), "xy")]
            polys[(find(z, "net")[1], find(fp, "layer")[1])].append(pts)
    return polys


def _pad_points(pad, x, y, rot, smd):
    """The pad's centre, and for an SMD pad four points inset a quarter of its size from the
    centre, so a pour that only grazes the pad fails (a through-hole pad's barrel joins both
    layers, so its centre is enough)."""
    offs = [(0.0, 0.0)] + ([(sx * pad.w / 4, sy * pad.h / 4) for sx in (-1, 1) for sy in (-1, 1)] if smd else [])
    out = []
    for ox, oy in offs:
        dx, dy = rotate(pad.x + ox, pad.y + oy, rot) if not pad.rot else \
            rotate(pad.x + rotate(ox, oy, pad.rot)[0], pad.y + rotate(ox, oy, pad.rot)[1], rot)
        out.append((x + dx, y + dy))
    return out


def pour_problems(circuit, placement, board_path, nets, layers=("F.Cu", "B.Cu")):
    """Problems (strings) with the pours of 'nets': empty when each is one piece per layer that
    covers every through-hole pad of its net (its centre) and every SMD pad on that layer (its
    centre and four inset points: the shunt's current pads carry the whole load on one layer)."""
    polys = filled(board_path)
    out = []
    for net in sorted(nets):
        for layer in layers:
            pieces = polys[(net, layer)]
            if len(pieces) != 1:
                out.append(f"{net} on {layer}: {len(pieces)} pieces")
                continue
            for ref, number in sorted(circuit.nets[net]):
                x, y, rot = placement.at[ref]
                for pad in circuit.instances[ref].part.footprint.pads:
                    smd = pad.kind == "smd" and layer in (pad.layers or ())
                    if pad.number == number and (pad.kind == "thru_hole" or smd):
                        if not all(inside(pt, pieces[0]) for pt in _pad_points(pad, x, y, rot, smd)):
                            out.append(f"{net} on {layer}: misses {ref}.{number}")
    return out
