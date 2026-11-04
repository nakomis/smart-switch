"""Reference designators on the front silkscreen, placed where they fit.

Each part's label goes beside its body (above, below, right or left, then turned 90 degrees,
then a little further out), or, for a big part, on its own body. A spot is taken only if the text
clears every pad, every other part's body, every footprint's own silk outline and text, the
slots, the board edge, any keep-clear box, and every label already placed. Parts in a cluster
too tight for one label each share one ("R1-R4", or "C2,C5" when not consecutive) beside the
cluster. Anything still without a spot is returned, so a test can insist there is none."""
import math
import re

from board.placement import bbox, rotate
from board.sexpr import find, find_all

CHAR = 0.85          # the stroke font's advance per character, as a fraction of the size
SIZE = 0.8           # KiCad's minimum silk text height
BIG = 50.0           # mm^2: parts at least this big may carry their label on their own body
CLEAR = 0.2          # mm between a label and anything else


def text_box(text, x, y, size, rot=0):
    """Approximate extent (x0, y0, x1, y1) of centred stroke-font text, stroke included."""
    w = len(text) * size * CHAR + size * 0.15
    h = size * 1.15
    if round(rot) % 180 == 90:
        w, h = h, w
    return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)


def _overlap(a, b, m=0.0):
    return a[0] < b[2] + m and b[0] < a[2] + m and a[1] < b[3] + m and b[1] < a[3] + m


def footprint_silk(circuit, placement):
    """{ref: [boxes]} round each footprint's own front silk: lines, arcs, circles, rectangles,
    polygons and its user text, in board coordinates."""
    out = {}
    for ref, inst in circuit.instances.items():
        x, y, rot = placement.at[ref]
        node, boxes = inst.part.footprint.node, []

        def pt(v):
            bx, by = rotate(float(v[1]), float(v[2]), rot)
            return x + bx, y + by

        for kind in ("fp_line", "fp_arc", "fp_circle", "fp_rect", "fp_poly"):
            for g in find_all(node, kind):
                layer = find(g, "layer")
                if not layer or str(layer[1]) != "F.SilkS":
                    continue
                stroke = find(g, "stroke")
                sw = float(find(stroke, "width")[1]) if stroke and find(stroke, "width") else 0.12
                if kind == "fp_circle":
                    (cx, cy), (ex, ey) = pt(find(g, "center")), pt(find(g, "end"))
                    r = math.hypot(ex - cx, ey - cy)
                    pts = [(cx - r, cy - r), (cx + r, cy + r)]
                elif kind == "fp_poly":
                    pts = [pt(v) for v in find_all(find(g, "pts"), "xy")]
                elif kind == "fp_rect":
                    (ax, ay), (bx2, by2) = pt(find(g, "start")), pt(find(g, "end"))
                    for edge in (((ax, ay), (bx2, ay)), ((bx2, ay), (bx2, by2)),
                                 ((bx2, by2), (ax, by2)), ((ax, by2), (ax, ay))):
                        boxes.append(_seg_box(edge, sw))
                    continue
                else:
                    pts = [pt(find(g, k)) for k in ("start", "mid", "end") if find(g, k)]
                boxes.append(_seg_box(pts, sw))
        for g in find_all(node, "fp_text"):
            layer = find(g, "layer")
            if g[1] == "user" and layer and str(layer[1]) == "F.SilkS":
                font = find(find(g, "effects") or [], "font") or []
                size = (find(font, "size") or [None, 1.0])[1]
                tx, ty = pt(find(g, "at"))
                boxes.append(text_box(str(g[2]), tx, ty, float(size)))
        out[ref] = boxes
    return out


def _seg_box(pts, width):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    h = width / 2
    return (min(xs) - h, min(ys) - h, max(xs) + h, max(ys) + h)


def _candidates(box, text, size, on_body):
    """Spots for 'text' round (or on) 'box', best first: (x, y, rot)."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if on_body:
        for dy in (0, -2, 2, -4, 4):
            for dx in (0, -3, 3):
                yield cx + dx, cy + dy, 0
    w0, h0 = (lambda b: (b[2] - b[0], b[3] - b[1]))(text_box(text, 0, 0, size))
    for gap in (CLEAR, 0.5, 1.0, 1.6, 2.4, 3.2):
        for shift in (0, -1.0, 1.0, -2.0, 2.0, -3.0, 3.0):
            yield cx + shift, y0 - gap - h0 / 2, 0                  # above
            yield cx + shift, y1 + gap + h0 / 2, 0                  # below
            yield x1 + gap + w0 / 2, cy + shift, 0                  # right
            yield x0 - gap - w0 / 2, cy + shift, 0                  # left
            yield x1 + gap + h0 / 2, cy + shift, 90                 # right, turned
            yield x0 - gap - h0 / 2, cy + shift, 90                 # left, turned


def _fits(tb, own, ctx):
    x0, y0, x1, y1 = ctx["inside"]
    if not (tb[0] >= x0 and tb[1] >= y0 and tb[2] <= x1 and tb[3] <= y1):
        return False
    for b in ctx["hard"]:
        if _overlap(tb, b, CLEAR):
            return False
    for ref, b in ctx["bodies"].items():
        if ref not in own and _overlap(tb, b, 0.05):
            return False
    for ref, boxes in ctx["silk"].items():
        if any(_overlap(tb, b, CLEAR) for b in boxes):
            return False
    return not any(_overlap(tb, b, CLEAR) for b in ctx["placed"])


def _place(text, refs_, box, size, ctx, on_body=False):
    for x, y, rot in _candidates(box, text, size, on_body):
        tb = text_box(text, x, y, size, rot)
        if _fits(tb, set(refs_), ctx):
            ctx["placed"].append(tb)
            return (text, round(x, 3), round(y, 3), size, "F.SilkS", rot) if rot else \
                   (text, round(x, 3), round(y, 3), size)
    return None


def _num(ref):
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    return m.group(1), int(m.group(2))


def _group_text(group):
    prefix = _num(group[0])[0]
    nums = sorted(_num(r)[1] for r in group)
    if nums == list(range(nums[0], nums[-1] + 1)) and len(nums) > 2:
        return f"{prefix}{nums[0]}-{nums[-1]}"
    return ",".join(f"{prefix}{n}" for n in nums)


def place_refs(circuit, placement, skip=(), hard=(), texts=(), inside=None, size=SIZE, extra=()):
    """(silk entries, refs left unlabelled). hard: boxes nothing may touch (pads, slots, keep-clear
    areas, lines); texts: existing silk entries (text, x, y, size[, layer[, rot]]), front ones
    are kept clear of; extra: (text, refs, box, size) other labels to place first, on 'box' or
    beside it, over those parts' own bodies if need be (a fuse's name over its clips)."""
    ox0, oy0, ox1, oy1 = placement.outline
    ctx = {"inside": inside or (ox0 + 0.6, oy0 + 0.6, ox1 - 0.6, oy1 - 0.6), "hard": list(hard),
           "bodies": {r: bbox(placement, r) for r in circuit.instances},
           "silk": footprint_silk(circuit, placement),
           "placed": [text_box(t[0], t[1], t[2], t[3], t[5] if len(t) > 5 else 0)
                      for t in texts if (t[4] if len(t) > 4 else "F.SilkS") == "F.SilkS"]}
    todo = sorted((r for r in circuit.instances if r not in skip),
                  key=lambda r: (-_area(ctx["bodies"][r]), _num(r)))
    placed = {}                                   # ref -> (entry, its box), labelled alone
    left, fixed = [], []
    for text, owners, box, tsize in extra:
        e = _place(text, owners, box, tsize, ctx, on_body=True)
        if e is None:
            left.append(text)
        else:
            fixed.append(e)
    for ref in todo:
        body = ctx["bodies"][ref]
        big = _area(body) >= BIG
        e = _place(ref, [ref], body, 1.2 if big else size, ctx, on_body=big) if big else None
        e = e or _place(ref, [ref], body, size, ctx)
        if e:
            placed[ref] = (e, ctx["placed"][-1])
        else:
            left.append(ref)
    # A part left without room is labelled with its cluster: same prefix, bodies within 4 mm of
    # the group's box, taking back the neighbours' own labels ("R1-R4" beside the cluster).
    out, still = [], []
    left.sort(key=_num)
    while left:
        group = [left.pop(0)]
        gb = ctx["bodies"][group[0]]
        grew = True
        while grew:
            grew = False
            for r in sorted(set(placed) | set(left), key=_num):
                b = ctx["bodies"][r]
                if r not in group and _num(r)[0] == _num(group[0])[0] and _overlap(gb, b, 4.0):
                    group.append(r)
                    gb = (min(gb[0], b[0]), min(gb[1], b[1]), max(gb[2], b[2]), max(gb[3], b[3]))
                    grew = True
        for r in group:
            if r in left:
                left.remove(r)
            if r in placed:
                ctx["placed"].remove(placed.pop(r)[1])
        e = _place(_group_text(group), group, gb, size, ctx)
        if e:
            out.append(e)
        else:
            still += group
    out = fixed + [e for e, _ in placed.values()] + out
    return out, still


def _area(b):
    return (b[2] - b[0]) * (b[3] - b[1])
