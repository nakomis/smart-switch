"""Petro's copper (rev B, non-isolated): solid pours on both layers for every high-current net,
stitched, never thinner than MAINS_MIN_WIDTH on either layer, clear of the edges and the holes;
a GND pour over the low-voltage area only, so there is no ground pour in the mains area. The DRC
runs on the placed board with the hand wiring (divider, supply, Kelvin pair) and the zones
refilled, so the clearances are KiCad's own, from the generated rules."""
import json
import subprocess
from collections import defaultdict

import pytest

from board import petro_board as pb
from board.kicad_pcb import PRO, write_board
from board.rules import MAINS_EDGE, _pad_box
from board.sexpr import find, find_all, parse
from conftest import KICAD_CLI

C = pb.build_petro()
P = pb.place_petro(C)


def _inside(pt, poly):
    return pb._in_poly(*pt, poly)


@pytest.fixture(scope="module")
def filled(tmp_path_factory):
    """(DRC report, {(net, layer): [filled polygons]}, board) for the placed, hand-wired board."""
    out = tmp_path_factory.mktemp("copper")
    r = pb.rules()
    base = ([k for k in PRO["net_settings"]["classes"] if k["name"] != "Mains"],
            [k for k in PRO["net_settings"]["netclass_patterns"] if k["netclass"] != "Mains"])
    classes, patterns = r.netclasses(base)
    tracks, vias = pb.hand_wiring(C, P)
    board = out / "petro.kicad_pcb"
    write_board(C, P, board, tracks, vias + pb.stitch_vias(), layers=2, slots=pb.slots(), dru=r.dru(),
                netclasses=classes, netclass_patterns=patterns, zones=pb.mains_zones(),
                pad_extra=pb.pad_extra(C), plane_pts=pb.gnd_pts(), corner_radius=pb.CORNER_R)
    subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all", "--refill-zones",
                    "--save-board", "-o", str(out / "drc.json"), str(board)], check=True, capture_output=True)
    polys = defaultdict(list)
    for z in find_all(parse(board.read_text()), "zone"):
        for fp in find_all(z, "filled_polygon"):
            pts = [(float(p[1]), float(p[2])) for p in find_all(find(fp, "pts"), "xy")]
            polys[(find(z, "net")[1], find(fp, "layer")[1])].append(pts)
    return json.loads((out / "drc.json").read_text()), polys, board


def test_every_high_current_net_pours_on_both_layers_solidly():
    zones = defaultdict(list)
    for z in pb.mains_zones():
        zones[z.net].append(z)
    assert pb.HIGH_CURRENT <= set(zones)
    for net in pb.HIGH_CURRENT:
        assert {lay for z in zones[net] for lay in z.layers} == {"F.Cu", "B.Cu"}, net
        for z in zones[net]:
            assert z.solid and z.min_width >= pb.MAINS_MIN_WIDTH, net


def test_mains_copper_is_wide_enough_for_16a_on_two_layers():
    assert pb.MAINS_MIN_WIDTH >= 3.47


def test_only_mains_nets_have_mains_pours():
    assert all(z.net in pb.GROUPS for z in pb.mains_zones())


def test_pour_outlines_keep_off_the_edges():
    for z in pb.mains_zones():
        xs, ys = [p[0] for p in z.pts], [p[1] for p in z.pts]
        assert min(xs) >= MAINS_EDGE and max(xs) <= pb.W - MAINS_EDGE, z.net
        assert min(ys) >= MAINS_EDGE and max(ys) <= pb.H - MAINS_EDGE, z.net


def test_ground_pour_is_the_low_voltage_area_and_no_mains_pour_reaches_into_it():
    assert pb.gnd_pts() == pb.lv_area()
    for z in pb.mains_zones():
        assert not any(_inside(pt, pb.lv_area()) for pt in z.pts), z.net
        assert not any(_inside(pt, z.pts) for pt in pb.gnd_pts()), z.net


def test_every_high_current_net_is_stitched_inside_its_own_pour():
    polys = {z.net: z.pts for z in pb.mains_zones() if "B.Cu" in z.layers}
    by_net = defaultdict(list)
    for v in pb.stitch_vias():
        by_net[v.net].append(v)
        assert _inside((v.x, v.y), polys[v.net]), (v.net, v.x, v.y)
    for net in pb.HIGH_CURRENT:
        assert len(by_net[net]) >= 3, net


IGNORE = {"silk_overlap", "silk_over_copper", "silk_edge_clearance", "text_height", "text_thickness",
          "lib_footprint_mismatch", "lib_footprint_issues"}


@pytest.mark.kicad
def test_drc_is_clean_apart_from_unrouted_signals(filled):
    drc, _, _ = filled
    bad = [(v["type"], v["description"], [i["description"] for i in v["items"]])
           for v in drc["violations"] if v["type"] not in IGNORE
           and not (v["type"] in ("starved_thermal", "isolated_copper")
                    and "[GND]" in v["description"] + str(v["items"]))
           and not (v["type"] == "track_dangling" and "[SENSE]" in str(v["items"]))]   # router joins it
    assert bad == []


@pytest.mark.kicad
def test_the_pours_and_hand_wiring_connect_every_mains_and_supply_pad(filled):
    drc, _, _ = filled
    nets = set(pb.MAINS_POLYS) | set(pb.SUPPLY_HV_NETS) | set(pb.SWNODE_NETS)
    stray = [u for u in drc["unconnected_items"]
             if any(f"[{n}]" in i["description"] for n in nets for i in u["items"])]
    assert stray == []


@pytest.mark.kicad
@pytest.mark.parametrize("net", sorted(pb.HIGH_CURRENT))
def test_each_layer_alone_is_one_piece_reaching_every_through_hole_pad(filled, net):
    """So the two layers really are in parallel all the way, and neither depends on the vias.
    With min_thickness at MAINS_MIN_WIDTH, each is at least that wide everywhere."""
    _, polys, _ = filled
    for layer in ("F.Cu", "B.Cu"):
        pieces = polys[(net, layer)]
        assert len(pieces) == 1, (net, layer, len(pieces))
        for ref, pad in C.nets[net]:
            for fp in C.instances[ref].part.footprint.pads:
                if fp.number == pad and fp.kind == "thru_hole":
                    b = _pad_box(P, ref, fp)
                    assert _inside(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), pieces[0]), (net, layer, ref, pad)


@pytest.mark.kicad
def test_the_ground_pour_fills_on_both_layers(filled):
    _, polys, _ = filled
    for layer in ("F.Cu", "B.Cu"):
        assert polys[("GND", layer)], layer


@pytest.mark.kicad
def test_build_check_agrees(filled):
    """board.checks.pour_problems (which build.py runs on the routed board) passes here..."""
    from board.checks import pour_problems
    _, _, board = filled
    assert pour_problems(C, P, board, pb.HIGH_CURRENT) == []


@pytest.mark.kicad
def test_build_check_catches_a_missing_pad(filled, monkeypatch):
    """...and fails when a pour misses a through-hole pad of its net."""
    from board import checks
    _, _, board = filled
    jx = P.at["J2"][0]
    real = checks.inside
    monkeypatch.setattr(checks, "inside", lambda pt, poly: False if pt[0] > jx - 10 else real(pt, poly))
    assert any("misses J2" in s for s in checks.pour_problems(C, P, board, {"L_OUT"}))




@pytest.mark.kicad
def test_build_check_catches_a_cut_mains_pour(tmp_path):
    """A real cut, refilled by KiCad: a 1 mm rule area across L_F's band under the relay, on both
    layers, leaves L_F in two pieces on each layer, which pour_problems reports. (A track there
    would be caught by the clearance rules first; this is the check for a split they allow.)"""
    from board.checks import pour_problems
    r = pb.rules()
    base = ([k for k in PRO["net_settings"]["classes"] if k["name"] != "Mains"],
            [k for k in PRO["net_settings"]["netclass_patterns"] if k["netclass"] != "Mains"])
    classes, patterns = r.netclasses(base)
    tracks, vias = pb.hand_wiring(C, P)
    cut = [("cut", [(68.5, 36.0), (69.5, 36.0), (69.5, 43.0), (68.5, 43.0)], ("F.Cu", "B.Cu"))]
    board = tmp_path / "petro.kicad_pcb"
    write_board(C, P, board, tracks, vias + pb.stitch_vias(), layers=2, slots=pb.slots(), dru=r.dru(),
                netclasses=classes, netclass_patterns=patterns, zones=pb.mains_zones(), keepouts=cut,
                pad_extra=pb.pad_extra(C), plane_pts=pb.gnd_pts(), corner_radius=pb.CORNER_R)
    subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--refill-zones", "--save-board", "-o",
                    str(tmp_path / "drc.json"), str(board)], check=True, capture_output=True)
    problems = pour_problems(C, P, board, {"L_F"})
    assert "L_F on F.Cu: 2 pieces" in problems and "L_F on B.Cu: 2 pieces" in problems, problems


def test_build_check_needs_an_smd_pad_covered_not_grazed():
    """The shunt's current pads carry the whole load on F.Cu: a pour must cover the pad's centre
    and four inset points, not just touch it."""
    from board.checks import _pad_points, inside
    pad = next(q for q in C.instances["RS1"].part.footprint.pads if q.number == "1")
    x, y, rot = P.at["RS1"]
    pts = _pad_points(pad, x, y, rot, smd=True)
    cx, cy = pts[0]
    sliver = [(cx - 0.2, cy - 0.2), (cx + 0.2, cy - 0.2), (cx + 0.2, cy + 0.2), (cx - 0.2, cy + 0.2)]
    whole = [(cx - 5, cy - 5), (cx + 5, cy - 5), (cx + 5, cy + 5), (cx - 5, cy + 5)]
    assert inside(pts[0], sliver) and not all(inside(q, sliver) for q in pts)
    assert all(inside(q, whole) for q in pts)
