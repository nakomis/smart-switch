"""Petro's mains copper: solid pours on both layers for every high-current net, stitched, never
thinner than half the IPC width on either layer, clear of the edges, the holes and the SELV side,
and no ground pour anywhere in the mains area. The DRC runs on the placed (unrouted) board with
the zones refilled, so the clearances are KiCad's own, from the generated rules."""
import json
import subprocess
from collections import defaultdict

import pytest

from board import petro_board as pb
from board.kicad_pcb import PRO, write_board
from board.rules import HIGH_CURRENT_WIDTH, MAINS_EDGE, _pad_box
from board.sexpr import find, find_all, parse
from conftest import KICAD_CLI

C = pb.build_petro()
P = pb.place_petro(C)


def _inside(pt, poly):
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


@pytest.fixture(scope="module")
def filled(tmp_path_factory):
    """(DRC report, {(net, layer): [filled polygons]}) for the placed board with its pours."""
    out = tmp_path_factory.mktemp("copper")
    r = pb.rules()
    base = ([k for k in PRO["net_settings"]["classes"] if k["name"] != "Mains"],
            [k for k in PRO["net_settings"]["netclass_patterns"] if k["netclass"] != "Mains"])
    classes, patterns = r.netclasses(base)
    board = out / "petro.kicad_pcb"
    write_board(C, P, board, layers=2, slots=pb.slots(), dru=r.dru(), netclasses=classes,
                netclass_patterns=patterns, zones=pb.mains_zones(), vias=pb.stitch_vias(),
                pad_extra=pb.mains_pad_extra(C), plane_pts=pb.gnd_pts())
    subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all", "--refill-zones",
                    "--save-board", "-o", str(out / "drc.json"), str(board)], check=True, capture_output=True)
    polys = defaultdict(list)
    for z in find_all(parse(board.read_text()), "zone"):
        for fp in find_all(z, "filled_polygon"):
            pts = [(float(p[1]), float(p[2])) for p in find_all(find(fp, "pts"), "xy")]
            polys[(find(z, "net")[1], find(fp, "layer")[1])].append(pts)
    return json.loads((out / "drc.json").read_text()), polys


def test_every_high_current_net_pours_on_both_layers_solidly():
    zones = {z.net: z for z in pb.mains_zones()}
    assert pb.HIGH_CURRENT <= set(zones)
    for net in pb.HIGH_CURRENT:
        assert set(zones[net].layers) == {"F.Cu", "B.Cu"}
        assert zones[net].solid
        assert zones[net].min_width >= HIGH_CURRENT_WIDTH / 2


def test_only_mains_nets_have_mains_pours():
    assert all(z.net in pb.GROUPS for z in pb.mains_zones())


def test_pour_outlines_keep_off_the_edges_and_the_selv_side():
    for z in pb.mains_zones():
        xs, ys = [p[0] for p in z.pts], [p[1] for p in z.pts]
        assert min(xs) >= MAINS_EDGE and max(xs) <= pb.W - MAINS_EDGE and min(ys) >= MAINS_EDGE, z.net
        assert max(ys) <= pb.RELAY_NOTCH[2], z.net


def test_ground_pour_stays_out_of_the_mains_area():
    assert min(y for _, y in pb.gnd_pts()) >= pb.SELV_Y


def test_every_high_current_net_is_stitched_inside_its_own_pour():
    polys = {z.net: z.pts for z in pb.mains_zones()}
    by_net = defaultdict(list)
    for v in pb.stitch_vias():
        by_net[v.net].append(v)
        assert _inside((v.x, v.y), polys[v.net]), (v.net, v.x, v.y)
    for net in pb.HIGH_CURRENT:
        assert len(by_net[net]) >= 3, net


def test_drc_is_clean_apart_from_unrouted_signals(filled):
    drc, _ = filled
    ignore = {"silk_overlap", "silk_over_copper", "silk_edge_clearance", "text_height", "text_thickness",
              "lib_footprint_mismatch", "lib_footprint_issues"}
    bad = [v for v in drc["violations"] if v["type"] not in ignore
           and not (v["type"] == "starved_thermal" and "[GND]" in v["description"] + str(v["items"]))]
    assert bad == []


def test_the_pours_connect_every_mains_pad(filled):
    drc, _ = filled
    mains = set(pb.MAINS_POLYS)
    stray = [u for u in drc["unconnected_items"]
             if any(f"[{n}]" in i["description"] for n in mains for i in u["items"])]
    assert stray == []


@pytest.mark.parametrize("net", sorted(pb.HIGH_CURRENT))
def test_each_layer_alone_is_one_piece_reaching_every_through_hole_pad(filled, net):
    """So the two layers really are in parallel all the way, and neither depends on the vias.
    With min_thickness at half the IPC width, each is at least that wide everywhere."""
    _, polys = filled
    for layer in ("F.Cu", "B.Cu"):
        pieces = polys[(net, layer)]
        assert len(pieces) == 1, (net, layer, len(pieces))
        for ref, pad in C.nets[net]:
            for fp in C.instances[ref].part.footprint.pads:
                if fp.number == pad and fp.kind == "thru_hole":
                    b = _pad_box(P, ref, fp)
                    assert _inside(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), pieces[0]), (net, layer, ref, pad)


def test_no_pour_reaches_into_the_selv_strip(filled):
    _, polys = filled
    for (net, layer), pieces in polys.items():
        if net in pb.GROUPS:
            assert max(y for pts in pieces for _, y in pts) <= pb.RELAY_NOTCH[2] + 1e-6, (net, layer)
