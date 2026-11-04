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


def test_defaults_unchanged(tmp_path):
    _, _, pcb = _mini(tmp_path)
    assert pcb.with_suffix(".kicad_dru").read_text() == DRU
    assert not [g for g in _edge(parse(pcb.read_text())) if g[0] == "gr_arc"]
