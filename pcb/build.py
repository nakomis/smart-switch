#!/usr/bin/env python3
"""Petro board generator: circuit -> placement -> mains pours -> (route) -> board + DRC.

    ./.venv/bin/python build.py [--route] [--passes N] [--out DIR] [--step]

Routing is two Freerouting runs, each confined to one area so that the router (which knows only
plain clearances) never comes near the barrier: the SELV strip, then the metering island. The
mains copper is pours (petro_board.mains_zones), and the divider chain and the shunt's Kelvin
pair are routed by hand. Ground is pours too: a drop via beside every SMD GND/GND_M pad before
routing, stitching vias after. DRC runs with the generated mains rules (board/rules.py) and
refills the zones.

Once the board passes, the fab outputs go beside it: gerbers and drill (zipped), the JLCPCB and
PCBWay BOMs, the CPL (pick and place), renders, pins.h for the firmware and case-interface.json
for the case (PETRO-6); --step adds the STEP model (fetching the 3D models first).

Output goes to out/petro/ (the ordered build, once there is one); --out DIR writes elsewhere.
Freerouting doesn't route the same way twice, so a rebuild changes the tracks."""
import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

from board import gnd
from board import petro_board as pb
from board.checks import pour_problems
from board.cleanup import prune
from board.fab import export_step, fab, write_bom, write_bom_pcbway, write_cpl
from board.kicad_pcb import PRO, write_board
from board.netlist import check
from board.route import route
from board.rules import barrier_creepage

HERE = Path(__file__).resolve().parent
OUT = HERE / "out" / "petro"
KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
LAYERS = 2
STEM = "petro"
MASK, SILK = "Black", "White"     # gerbers carry no colour; this only makes the renders match


def drc(board, out):
    """Run DRC (refilling zones and saving them into the board); return the report."""
    subprocess.run([KICAD_CLI, "pcb", "drc", "--refill-zones", "--save-board", "--format", "json",
                    "--severity-all", "-o", str(out / "drc.json"), str(board)], check=True,
                   capture_output=True)
    return json.loads((out / "drc.json").read_text())


def netclasses():
    r = pb.rules()
    base = ([k for k in PRO["net_settings"]["classes"] if k["name"] != "Mains"],
            [k for k in PRO["net_settings"]["netclass_patterns"] if k["netclass"] != "Mains"])
    return r.dru(), *r.netclasses(base)


def two_pass_route(c, p, tmp, passes, hand_tracks, hand_vias):
    """Route the SELV nets in the SELV area, then the island nets in the island area. Returns
    the routed (tracks, vias). Each pass gets its own side's hand wiring (its ground drops; the
    island also the Kelvin pair) as fixed wiring it routes around, and keeps only what it routed
    on its own nets (the router joins a skipped net's fixed wiring up with tracks of its own).

    SELV GND is routed as a net as well as poured: otherwise the signal tracks can wall a pocket
    of pour off on both layers (it happened between U1 and J4). GND_M is left to the island pour.
    Freerouting lets a track leave a pin in any direction, out of its area too; it does so between
    the module's GND pads along the board edge, and those runs (GND only, which the pour joins
    anyway) are dropped. DRC then shows if anything is left unjoined."""
    island = set(pb.ISLAND) - {"GND_M"}
    selv = {n for n in c.nets if n not in pb.GROUPS and not n.startswith("NC_")}
    tracks, vias = [], []
    for name, nets, ground, area, keep in (
            ("selv", selv, "GND", pb.selv_area(), pb.selv_keepouts()),
            ("island", island, "GND_M", pb.island_area(), pb.island_keepouts())):
        skip = tuple(n for n in c.nets if n not in nets)
        fixed_t = [t for t in hand_tracks if t.net in nets or t.net == ground]
        fixed_v = [v for v in hand_vias if v.net in nets or v.net == ground]
        t, v = route(c, p, tmp / name, passes=passes, layers=LAYERS, route_area=area,
                     fixed_vias=fixed_v, fixed_tracks=fixed_t, layer_keepouts=keep, skip_nets=skip)
        x0, y0, x1, y1 = p.outline
        on_board = lambda x, y, m=0.45: x0 + m <= x <= x1 - m and y0 + m <= y <= y1 - m
        tracks += [x for x in t if x.net in nets and (x.net != "GND" or (on_board(x.x1, x.y1) and on_board(x.x2, x.y2)))]
        vias += [x for x in v if x.net in nets and (x.net != "GND" or on_board(x.x, x.y))]
    return tracks, vias


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", action="store_true")
    ap.add_argument("--passes", type=int, default=100)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--step", action="store_true", help="also export the STEP model")
    a = ap.parse_args()
    out = a.out.resolve()
    tmp = out / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    c = pb.build_petro()
    problems = check(c)
    if problems:
        raise SystemExit("\n".join(problems))
    p = pb.place_petro(c)

    # Hand wiring: the divider chain, the Kelvin pair, then a ground drop beside every SMD
    # GND pad (SELV) and GND_M pad (island), placed before routing so the router leaves room.
    hand_t = pb.divider_tracks(c, p)
    kt, kv = pb.kelvin_route(c, p)
    hand_t, hand_v = hand_t + kt, list(kv)
    for net, inside, skip in (("GND", pb.in_selv, ("U1",)), ("GND_M", pb.in_island, ("RS1",))):
        dt, dv, missed = gnd.drops(c, p, hand_t, hand_v, net, inside, skip=skip)
        print(f"{net} drops: {len(dv)}; no room beside: {missed or 'none'}")
        hand_t, hand_v = hand_t + dt, hand_v + dv

    tracks, vias = list(hand_t), list(hand_v)
    if a.route:
        rt, rv = two_pass_route(c, p, tmp, a.passes, hand_t, hand_v)
        pt, pv = prune(c, p, hand_t + rt, hand_v + rv, keep=hand_v, pour_nets=("GND", "GND_M"))
        tracks = hand_t + [t for t in pt if t not in hand_t]      # hand wiring always stays
        vias = hand_v + [v for v in pv if v not in hand_v]
        for net, inside in (("GND", pb.in_selv), ("GND_M", pb.in_island)):
            s = gnd.stitch(c, p, tracks, vias, net, inside)
            print(f"{net} stitching: {len(s)} vias")
            vias += s

    dru, classes, patterns = netclasses()
    board = out / f"{STEM}.kicad_pcb"
    notes, rects = pb.fab_notes()
    write_board(c, p, board, tracks, vias + pb.stitch_vias(), layers=LAYERS, mask=MASK, silkscreen=SILK,
                slots=pb.slots(), zones=pb.mains_zones() + pb.island_zones(), dru=dru,
                netclasses=classes, netclass_patterns=patterns, plane_pts=pb.gnd_pts(),
                pad_extra=pb.pad_extra(c), silk=pb.silk(c, p) + notes, user_rects=rects,
                lines=pb.boundary(c, p), hide_refs=set(c.instances), silk_avoid=pb.silk_avoid(c, p))
    d = drc(board, out)
    errors = [v for v in d["violations"] if v["severity"] == "error"]
    print(f"wrote {board}: {len(errors)} DRC errors {dict(Counter(v['type'] for v in errors))}, "
          f"{len(d['unconnected_items'])} unconnected")
    for v in errors[:40]:
        print(f"  {v['type']}: {v['description']} [{'; '.join(i['description'] for i in v['items'])}]")
    for u in d["unconnected_items"][:40]:
        print(f"  unconnected: {' / '.join(i['description'] for i in u['items'])}")
    if errors or d["unconnected_items"]:
        raise SystemExit("DRC failed")
    # Things DRC doesn't check: the mains pours must still be whole on each layer (routing next
    # to them can neck them away) and each layer's must reach every through-hole pad; and the
    # barrier parts' own pad-to-pad creepage, which KiCad doesn't check within a footprint.
    pours = pour_problems(c, p, board, pb.HIGH_CURRENT)
    creep = barrier_creepage(c, p, pb.rules(), pb.slots())
    for s in pours + [f"creepage {ref} {a}-{b}: {mm} mm" for ref, a, b, mm in creep]:
        print(f"  {s}")
    if pours or creep:
        raise SystemExit("mains checks failed")
    print("mains pours whole on both layers; barrier creepage >= 8 mm")
    silk = [v for v in d["violations"] if v["type"].startswith(("silk", "text"))]
    print(f"silk warnings: {len(silk)}")

    write_bom(c, out / "bom-jlcpcb.csv")
    write_bom_pcbway(c, out / "bom-pcbway.csv")
    write_cpl(c, p, out / "cpl.csv")
    (out / "pins.h").write_text(pb.pins_h())
    (out / "case-interface.json").write_text(pb.case_interface(c, p))
    print(f"gerbers: {fab(board, out, layers=LAYERS)}")
    if a.step:
        subprocess.run([str(HERE / "fetch_models.sh")], check=True)     # resumable, skips fetched parts
        print(f"STEP: {export_step(board, out)}")
    print(f"BOMs, CPL, pins.h, case-interface.json and renders in {out}; "
          f"order with solder mask {MASK}, silkscreen {SILK}")


if __name__ == "__main__":
    main()
