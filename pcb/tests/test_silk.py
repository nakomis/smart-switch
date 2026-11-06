"""Petro's silkscreen: no reference designators (the component key PDF does that job), but
labels where a person needs them: the mains terminals' L and N, 230 V warnings on both sides, an
"entire board live" warning on both sides (rev B is non-isolated: there is no boundary to draw),
the connectors' pins and every test hole. The DRC of the placed board, with the silk, raises no
silk warnings at all."""
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


def _texts(layer=None):
    return [s for s in SILK if layer is None or (s[4] if len(s) > 4 else "F.SilkS") == layer]


def _nearest(ref, x, y):
    """The pad number of 'ref' nearest (x, y)."""
    pads = {pad.number for pad in C.instances[ref].part.footprint.pads}
    return min(pads, key=lambda n: (lambda px, py: (px - x) ** 2 + (py - y) ** 2)(*pb.pad_xy(C, P, ref, n)))


@pytest.mark.parametrize("ref", ["J1", "J2"])
def test_mains_terminals_say_which_pin_is_live_and_which_neutral(ref):
    want = {"L": {"L_IN", "L_OUT"}, "N": {"N_IN", "N_OUT"}}
    for text, net_names in want.items():
        hits = [s for s in _texts("F.SilkS") if s[0] == text
                and abs(s[1] - P.at[ref][0]) < 6 and abs(s[2] - P.at[ref][1]) < 10]
        assert len(hits) == 1, (ref, text, hits)
        assert C.net_of(ref, _nearest(ref, hits[0][1], hits[0][2])) in net_names, (ref, text)


def test_mains_warning_on_both_sides():
    for layer in ("F.SilkS", "B.SilkS"):
        assert any("230 V" in s[0] for s in _texts(layer)), layer


def test_the_board_and_j3_are_marked_live_on_both_sides():
    for layer in ("F.SilkS", "B.SilkS"):
        words = " ".join(s[0] for s in _texts(layer))
        for w in ("BOARD IS LIVE", "GND = NEUTRAL", "J3 I/O IS LIVE TOO", "UNPLUG BEFORE USB",
                  "LIVE I/O: INSIDE CASE ONLY"):
            assert w in words, (layer, w)


def test_nothing_claims_to_be_safe():
    assert not [s for s in SILK if "SAFE" in s[0] or "SELV" in s[0]]


def test_every_test_hole_is_labelled_above_on_both_sides():
    for ref, net in pb.TEST_HOLES.items():
        x, y = pb.pad_xy(C, P, ref, "1")
        for layer in ("F.SilkS", "B.SilkS"):
            near = [s for s in _texts(layer) if abs(s[1] - x) < 0.01 and abs(s[2] - y) < 2.2]
            assert len(near) == 1 and near[0][0] == pb.TEST_LABELS[net] and near[0][2] < y, (ref, layer, near)


def test_test_hole_labels_do_not_overlap_each_other():
    from board.refs import text_box
    for layer in ("F.SilkS", "B.SilkS"):
        boxes = [text_box(s[0], s[1], s[2], s[3]) for s in _texts(layer) if s[0] in pb.TEST_LABELS.values()]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], (layer, a, b)


def test_nothing_in_the_led_flange_ring():
    from board.refs import text_box
    rx0, ry0, rx1, ry1 = pb.led_ring()
    for s in _texts("F.SilkS"):
        tx0, ty0, tx1, ty1 = text_box(s[0], s[1], s[2], s[3], s[5] if len(s) > 5 else 0)
        assert tx1 <= rx0 or tx0 >= rx1 or ty1 <= ry0 or ty0 >= ry1, s


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
                user_rects=rects, hide_refs=set(C.instances), silk_avoid=pb.silk_avoid(C, P),
                corner_radius=pb.CORNER_R)
    subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all", "-o",
                    str(out / "drc.json"), str(board)], check=True, capture_output=True)
    return json.loads((out / "drc.json").read_text())


@pytest.mark.kicad
def test_drc_raises_no_silk_warnings(drc):
    silk = [(v["type"], [i["description"] for i in v["items"]]) for v in drc["violations"]
            if v["type"].startswith("silk") or v["type"].startswith("text")]
    assert silk == []
