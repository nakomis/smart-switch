"""Writer extensions for a mains board: internal slots, copper zones of any shape on chosen layers,
solid pad connections, and the DRU and net classes as parameters (step 3 generates them)."""
import json
import subprocess

import pytest
from conftest import KICAD_CLI
from fixture_board import build_mini, place_mini

from board.kicad_pcb import DRU, MIN_SLOT, Slot, Zone, merge_pad_extra, solid_pads, write_board
from board.sexpr import find, find_all, parse


def _drc(pcb, tmp_path, save=False):
    args = [KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all", "-o", str(tmp_path / "drc.json")]
    if save:
        args[3:3] = ["--refill-zones", "--save-board"]
    subprocess.run(args + [str(pcb)], check=True, capture_output=True)
    return json.loads((tmp_path / "drc.json").read_text())


def _mini(tmp_path, **kw):
    c = build_mini()
    p = place_mini(c)
    pcb = tmp_path / "m.kicad_pcb"
    write_board(c, p, pcb, layers=2, **kw)
    return c, p, pcb


def _zone_net(z):
    """KiCad 10 saves a zone's net as (net "name"); the writer also emits (net_name ...)."""
    nn = find(z, "net_name")
    return nn[1] if nn else find(z, "net")[1]


def _edge(tree):
    return [g for g in tree if isinstance(g, list) and g and g[0] in ("gr_line", "gr_arc")
            and find(g, "layer") and find(g, "layer")[1] == "Edge.Cuts"]


def test_slot_is_a_stadium_on_edge_cuts(tmp_path):
    _, _, pcb = _mini(tmp_path, slots=[Slot(10.0, 27.0, 30.0, 27.0, 2.0)])
    tree = parse(pcb.read_text())
    edge = _edge(tree)
    assert sorted(g[0] for g in edge) == ["gr_arc", "gr_arc", "gr_line", "gr_line"]
    lines = [g for g in edge if g[0] == "gr_line"]
    ys = sorted({find(g, "start")[2] for g in lines})
    assert ys == [26.0, 28.0]                                     # 2 mm wide about y = 27
    arcs = [g for g in edge if g[0] == "gr_arc"]
    assert sorted(find(a, "mid")[1] for a in arcs) == [9.0, 31.0]  # round ends, radius 1 mm


@pytest.mark.kicad
def test_slot_drc_accepts_the_outline_and_keeps_pours_off_it(tmp_path):
    _, _, pcb = _mini(tmp_path, slots=[Slot(10.0, 27.0, 30.0, 27.0, 2.0)])
    drc = _drc(pcb, tmp_path, save=True)
    assert not [v for v in drc["violations"] if v["type"] in ("invalid_outline", "malformed_courtyard")]
    tree = parse(pcb.read_text())
    filled = 0
    for z in find_all(tree, "zone"):
        for fp in find_all(z, "filled_polygon"):
            for xy in find(fp, "pts")[1:]:
                x, y = xy[1], xy[2]
                gap = ((x - min(max(x, 10.0), 30.0)) ** 2 + (y - 27.0) ** 2) ** 0.5 - 1.0
                assert gap > 0.3 - 0.01, (x, y, gap)       # the 0.3 mm copper-to-edge minimum
                filled += 1
    assert filled


def test_vertical_slot(tmp_path):
    _, _, pcb = _mini(tmp_path, slots=[Slot(38.0, 8.0, 38.0, 20.0, 1.5)])
    lines = [g for g in _edge(parse(pcb.read_text())) if g[0] == "gr_line"]
    assert sorted({find(g, "start")[1] for g in lines}) == [37.25, 38.75]


def test_slot_narrower_than_the_mill_is_refused(tmp_path):
    with pytest.raises(ValueError):
        _mini(tmp_path, slots=[Slot(10.0, 27.0, 30.0, 27.0, MIN_SLOT - 0.1)])


@pytest.mark.kicad
def test_polygon_zone_on_both_layers_with_solid_pads(tmp_path):
    l_shape = [(10.0, 18.0), (30.0, 18.0), (30.0, 21.0), (16.0, 21.0), (16.0, 26.0), (10.0, 26.0)]
    _, _, pcb = _mini(tmp_path, zones=[Zone("+3V3", ("F.Cu", "B.Cu"), l_shape, solid=True, priority=2,
                                            clearance=0.5, min_width=0.4)])
    tree = parse(pcb.read_text())
    z = next(z for z in find_all(tree, "zone") if _zone_net(z) == "+3V3")
    assert find(z, "layers")[1:] == ["F.Cu", "B.Cu"]
    assert find(z, "connect_pads")[1] == "yes" and find(find(z, "connect_pads"), "clearance")[1] == 0.5
    assert find(z, "priority")[1] == 2 and find(z, "min_thickness")[1] == 0.4
    assert [(p[1], p[2]) for p in find(find(z, "polygon"), "pts")[1:]] == l_shape
    _drc(pcb, tmp_path, save=True)
    z = next(z for z in find_all(parse(pcb.read_text()), "zone") if _zone_net(z) == "+3V3")
    assert {find(f, "layer")[1] for f in find_all(z, "filled_polygon")} == {"F.Cu", "B.Cu"}


def test_thermal_zone_by_default(tmp_path):
    _, _, pcb = _mini(tmp_path, zones=[Zone("+3V3", ("F.Cu",), [(10, 18), (30, 18), (30, 26), (10, 26)])])
    z = next(z for z in find_all(parse(pcb.read_text()), "zone") if _zone_net(z) == "+3V3")
    assert find(z, "layer")[1] == "F.Cu"
    assert len(find(z, "connect_pads")) == 2                       # no "yes": thermal reliefs


def test_zone_on_an_unknown_net_is_refused(tmp_path):
    with pytest.raises(KeyError):
        _mini(tmp_path, zones=[Zone("NOPE", ("F.Cu",), [(0, 0), (1, 0), (1, 1)])])


def test_solid_pads_marks_only_pads_on_the_named_nets():
    c = build_mini()
    extra = solid_pads(c, {"GND"})
    assert set(extra) == {"J1", "U1", "C1", "C2", "C3", "D1", "H1", "H2"}
    pads = {p.number: p for p in c.instances["U1"].part.footprint.pads}
    assert extra["U1"](pads["2"]) == [["zone_connect", 2]]        # GND
    assert extra["U1"](pads["5"]) == []                            # VOUT


def test_merge_pad_extra_concatenates_per_pad():
    c = build_mini()
    paste = {"U1": lambda pad: [["solder_paste_margin", -0.1]]}
    merged = merge_pad_extra(solid_pads(c, {"GND"}), paste)
    pads = {p.number: p for p in c.instances["U1"].part.footprint.pads}
    assert merged["U1"](pads["2"]) == [["zone_connect", 2], ["solder_paste_margin", -0.1]]
    assert merged["U1"](pads["5"]) == [["solder_paste_margin", -0.1]]
    assert "C1" in merged and "U1" in merged


@pytest.mark.kicad
def test_dru_and_netclasses_are_parameters(tmp_path):
    dru = '(version 1)\n(rule "x"\n  (constraint clearance (min 1mm))\n  (condition "A.hasNetclass(\'Hot\')"))\n'
    classes = [{"name": "Default", "clearance": 0.15, "track_width": 0.15, "via_diameter": 0.6, "via_drill": 0.3},
               {"name": "Hot", "clearance": 1.0, "track_width": 2.0, "via_diameter": 1.2, "via_drill": 0.6}]
    _, _, pcb = _mini(tmp_path, dru=dru, netclasses=classes,
                      netclass_patterns=[{"netclass": "Hot", "pattern": "VBUS"}])
    assert pcb.with_suffix(".kicad_dru").read_text() == dru
    ns = json.loads(pcb.with_suffix(".kicad_pro").read_text())["net_settings"]
    assert [c["name"] for c in ns["classes"]] == ["Default", "Hot"]
    assert ns["netclass_patterns"] == [{"netclass": "Hot", "pattern": "VBUS"}]
    drc = _drc(pcb, tmp_path)                                      # KiCad reads the custom rules
    assert not [v for v in drc["violations"] if v["type"] == "invalid_drc_rule"]


def _gnd_outlines(pcb):
    out = []
    for z in find_all(parse(pcb.read_text()), "zone"):
        if _zone_net(z) == "GND":
            out.append([(p[1], p[2]) for p in find_all(find(find(z, "polygon"), "pts"), "xy")])
    return out


def test_ground_pour_outline_is_a_parameter(tmp_path):
    pts = [(1.0, 15.0), (39.0, 15.0), (39.0, 29.0), (1.0, 29.0)]
    _, _, pcb = _mini(tmp_path, plane_pts=pts)
    outlines = _gnd_outlines(pcb)
    assert len(outlines) == 2 and all(o == pts for o in outlines)


def test_ground_pour_covers_the_board_by_default(tmp_path):
    _, p, pcb = _mini(tmp_path)
    for o in _gnd_outlines(pcb):
        assert min(y for _, y in o) < p.outline[1] + 1 and max(y for _, y in o) > p.outline[3] - 1


def test_modern_footprints_get_their_reference_and_value(tmp_path):
    """KiCad 7+ footprints carry (property "Reference" "REF**") rather than fp_text."""
    from board.netlist import Circuit
    from board.placement import Placement
    c = Circuit()
    c.add("SHUNT", ref="RS1")
    pcb = tmp_path / "s.kicad_pcb"
    write_board(c, Placement((0, 0, 20, 20), {"RS1": (10, 10, 90)}), pcb, layers=2)
    fp = find(parse(pcb.read_text()), "footprint")
    props = {p[1]: p for p in find_all(fp, "property")}
    assert props["Reference"][2] == "RS1"
    assert props["Value"][2] == c.instances["RS1"].value
    assert "REF**" not in pcb.read_text()


def test_defaults_unchanged(tmp_path):
    _, _, pcb = _mini(tmp_path)
    assert pcb.with_suffix(".kicad_dru").read_text() == DRU
    assert not [g for g in _edge(parse(pcb.read_text())) if g[0] == "gr_arc"]



def test_dashed_silk_lines(tmp_path):
    """lines: (x0, y0, x1, y1, layer) as dashed graphic lines, for the mains boundary."""
    _, _, pcb = _mini(tmp_path, lines=[(1.0, 2.0, 11.0, 2.0, "F.SilkS"), (1.0, 3.0, 1.0, 9.0, "B.SilkS")])
    got = [(tuple(find(g, "start")[1:]), tuple(find(g, "end")[1:]), find(g, "layer")[1],
            find(find(g, "stroke"), "type")[1]) for g in find_all(parse(pcb.read_text()), "gr_line")]
    assert ((1.0, 2.0), (11.0, 2.0), "F.SilkS", "dash") in got
    assert ((1.0, 3.0), (1.0, 9.0), "B.SilkS", "dash") in got


def test_silk_avoid_drops_footprint_user_text_over_a_box_but_keeps_the_rest():
    """A library footprint's own silk labels (the IRM-05-5's AC/L beside its pin) are dropped
    when they overlap a silk_avoid box (a pad), like its lines; text elsewhere stays."""
    from board.kicad_pcb import _drop_silk
    fp = parse('(footprint "X" (at 10 10)'
               ' (fp_text user "AC/L" (at 1.6 1.1) (layer "F.SilkS") (effects (font (size 1 1))))'
               ' (fp_text user "+V" (at -5 -5) (layer "F.SilkS") (effects (font (size 1 1))))'
               ' (fp_text user "fab" (at 1.6 1.1) (layer "F.Fab") (effects (font (size 1 1)))))')
    _drop_silk(fp, 10.0, 10.0, 0, [(8.9, 8.9, 11.1, 11.1)])      # a 2.2 mm pad at (10, 10)
    assert [t[2] for t in find_all(fp, "fp_text")] == ["+V", "fab"]
