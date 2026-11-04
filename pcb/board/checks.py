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


def pour_problems(circuit, placement, board_path, nets, layers=("F.Cu", "B.Cu")):
    """Problems (strings) with the pours of 'nets': empty when each is one piece per layer that
    covers the centre of every through-hole pad of its net."""
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
                    if pad.number == number and pad.kind == "thru_hole":
                        dx, dy = rotate(pad.x, pad.y, rot)
                        if not inside((x + dx, y + dy), pieces[0]):
                            out.append(f"{net} on {layer}: misses {ref}.{number}")
    return out
