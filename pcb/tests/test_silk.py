"""Petro's silkscreen: no reference designators (the component key PDF does that job), but
labels where a person needs them: the mains terminals' L and N, 230 V warnings on both sides, the
mains/SELV boundary dashed across the barrier, the connectors' pins and every test hole. The DRC
of the placed board, with the silk, raises no silk warnings at all."""
import json
import subprocess

import pytest

from board import gnd
from board import petro_board as pb
from board.kicad_pcb import PRO, write_board
from conftest import KICAD_CLI

C = pb.build_petro()
P = pb.place_petro(C)
SILK = pb.silk(C, P)
LINES = pb.boundary(C, P)


def _texts(layer=None):
    return [s for s in SILK if layer is None or (s[4] if len(s) > 4 else "F.SilkS") == layer]


def _nearest(ref, x, y):
    """The pad number of 'ref' nearest (x, y)."""
    pads = {pad.number for pad in C.instances[ref].part.footprint.pads}
    return min(pads, key=lambda n: (lambda px, py: (px - x) ** 2 + (py - y) ** 2)(*pb.pad_xy(C, P, ref, n)))


@pytest.mark.parametrize("ref", ["J1", "J2"])
def test_mains_terminals_say_which_pin_is_live_and_which_neutral(ref):
    want = {"L": {"L_IN", "L_OUT"}, "N": {"N"}}
    for text, net_names in want.items():
        hits = [s for s in _texts("F.SilkS") if s[0] == text
                and abs(s[1] - P.at[ref][0]) < 6 and abs(s[2] - P.at[ref][1]) < 10]
        assert len(hits) == 1, (ref, text, hits)
        assert C.net_of(ref, _nearest(ref, hits[0][1], hits[0][2])) in net_names, (ref, text)


def test_mains_warning_on_both_sides():
    for layer in ("F.SilkS", "B.SilkS"):
        assert any("230 V" in s[0] for s in _texts(layer)), layer


def test_every_test_hole_is_labelled_with_its_signal():
    for ref, net in pb.TEST_HOLES.items():
        x, y = pb.pad_xy(C, P, ref, "1")
        near = [s for s in SILK if abs(s[1] - x) < 0.01 and abs(s[2] - y) < 2.2]
        assert near and all(s[0] == pb.TEST_LABELS[net] for s in near), (ref, near)


def test_the_boundary_is_drawn_on_both_sides_inside_the_barrier():
    x0, x1, notch_y = pb.RELAY_NOTCH
    for layer in ("F.SilkS", "B.SilkS"):
        segs = [s for s in LINES if s[4] == layer]
        assert sum(abs(s[2] - s[0]) + abs(s[3] - s[1]) for s in segs) > 50, layer      # broken under parts and at pads
        for ax, ay, bx, by, _ in segs:
            for x, y in ((ax, ay), (bx, by)):
                top = notch_y if x0 - 4 <= x <= x1 + 4 else pb.MAINS_Y
                assert top < y < pb.SELV_Y, (x, y)


def test_the_boundary_keeps_off_pads_and_the_slot():
    boxes = [b[1:] for b in gnd.pad_boxes(C, P)]
    boxes += [(min(s.x1, s.x2) - s.width / 2, min(s.y1, s.y2) - s.width / 2,
               max(s.x1, s.x2) + s.width / 2, max(s.y1, s.y2) + s.width / 2) for s in pb.slots()]
    for ax, ay, bx, by, _ in LINES:
        for bx0, by0, bx1, by1 in boxes:
            m = 0.3
            assert (max(ax, bx) < bx0 - m or min(ax, bx) > bx1 + m
                    or max(ay, by) < by0 - m or min(ay, by) > by1 + m), ((ax, ay, bx, by), (bx0, by0, bx1, by1))


def test_nothing_in_the_led_flange_ring():
    rx0, ry0, rx1, ry1 = pb.led_ring()
    for s in _texts("F.SilkS"):
        assert not (rx0 - 1 < s[1] < rx1 + 1 and ry0 - 1 < s[2] < ry1 + 1), s


@pytest.fixture(scope="module")
def drc(tmp_path_factory):
    out = tmp_path_factory.mktemp("silk")
    r = pb.rules()
    base = ([k for k in PRO["net_settings"]["classes"] if k["name"] != "Mains"],
            [k for k in PRO["net_settings"]["netclass_patterns"] if k["netclass"] != "Mains"])
    classes, patterns = r.netclasses(base)
    notes, rects = pb.fab_notes()
    board = out / "petro.kicad_pcb"
    write_board(C, P, board, layers=2, slots=pb.slots(), dru=r.dru(), netclasses=classes,
                netclass_patterns=patterns, zones=pb.mains_zones(), vias=pb.stitch_vias(),
                pad_extra=pb.mains_pad_extra(C), plane_pts=pb.gnd_pts(), silk=SILK + notes,
                user_rects=rects, lines=LINES, hide_refs=set(C.instances), silk_avoid=pb.silk_avoid(C, P))
    subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all", "-o",
                    str(out / "drc.json"), str(board)], check=True, capture_output=True)
    return json.loads((out / "drc.json").read_text())


def test_drc_raises_no_silk_warnings(drc):
    silk = [(v["type"], [i["description"] for i in v["items"]]) for v in drc["violations"]
            if v["type"].startswith("silk") or v["type"].startswith("text")]
    assert silk == []
