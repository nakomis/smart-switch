"""A quick placement sketch (PNG): the outline, the mains/SELV limits, part bodies, and pads coloured
by potential group. For iterating on placement before writing a board.

    ./.venv/bin/python -m board.sketch out/sketch.png
"""
import sys

from PIL import Image, ImageDraw

from board.placement import rotate

COLOURS = {"LINE": (220, 40, 40), "LIVE": (240, 120, 30), "PSU": (200, 0, 200), "NEUTRAL": (40, 90, 230),
           "LOAD": (150, 70, 0), "DIV": (0, 160, 160), "SELV": (40, 160, 40), "SWNODE": (255, 120, 220),
           None: (130, 130, 130)}
S = 10                                  # pixels per mm


def _pt(x, y, margin):
    return (x + margin) * S, (y + margin) * S


def _rot_box(x, y, rot, box):
    pts = [rotate(px, py, rot) for px in (box[0], box[2]) for py in (box[1], box[3])]
    xs, ys = [x + p[0] for p in pts], [y + p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def sketch(circuit, placement, groups, path, lines=(), boxes=(), slots=(), margin=8):
    x0, y0, x1, y1 = placement.outline
    img = Image.new("RGB", (int((x1 + 2 * margin) * S), int((y1 + 2 * margin) * S)), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([_pt(x0, y0, margin), _pt(x1, y1, margin)], outline="black", width=3)
    for (ax, ay, bx, by), colour in lines:
        d.line([_pt(ax, ay, margin), _pt(bx, by, margin)], fill=colour, width=2)
    for (bx0, by0, bx1, by1), colour in boxes:
        d.rectangle([_pt(bx0, by0, margin), _pt(bx1, by1, margin)], outline=colour, width=2)
    for s in slots:
        r = s.width / 2
        d.rounded_rectangle([_pt(min(s.x1, s.x2) - r, min(s.y1, s.y2) - r, margin),
                             _pt(max(s.x1, s.x2) + r, max(s.y1, s.y2) + r, margin)], radius=r * S, fill="black")
    for ref, (x, y, rot) in placement.at.items():
        inst = circuit.instances[ref]
        b = _rot_box(x, y, rot, inst.part.body)
        d.rectangle([_pt(b[0], b[1], margin), _pt(b[2], b[3], margin)], outline=(90, 90, 90), width=1)
        for pad in inst.part.footprint.pads:
            net = circuit.net_of(ref, pad.number) if pad.number else None
            g = None if net is None else groups.get(net, "SELV")
            g = "DIV" if g and g.startswith("DIV") else g
            pb = _rot_box(x, y, rot, (pad.x - pad.w / 2, pad.y - pad.h / 2, pad.x + pad.w / 2, pad.y + pad.h / 2))
            d.rectangle([_pt(pb[0], pb[1], margin), _pt(pb[2], pb[3], margin)], fill=COLOURS[g])
        d.text(_pt(b[0] + 0.3, b[1] + 0.3, margin), ref, fill="black")
    img.save(path)
    return path


if __name__ == "__main__":
    from board import petro_board as pb
    c = pb.build_petro()
    p = pb.place_petro(c)
    print(sketch(c, p, pb.GROUPS, sys.argv[1], lines=pb.sketch_lines(), boxes=pb.keep_boxes(), slots=pb.slots()))
