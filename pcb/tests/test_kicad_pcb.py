import json
import subprocess

import pytest
from conftest import KICAD_CLI
from fixture_board import H, W, build_mini, place_mini

from board.kicad_pcb import (DRU, MAINS_EDGE, MAINS_FUNCTIONAL, MAINS_REINFORCED, Track, Via,
                             write_board)
from board.netlist import Circuit
from board.placement import Placement
from board.sexpr import find, find_all, parse

BAD = ("courtyards_overlap", "malformed_courtyard", "invalid_outline", "lib_footprint_issues")


def _drc(path, out):
    r = subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all",
                        "-o", str(out), str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(out.read_text())


def _mini(tmp_path, **kw):
    c = build_mini()
    pl = place_mini(c)
    pcb = tmp_path / "mini.kicad_pcb"
    write_board(c, pl, pcb, layers=2, **kw)
    return c, pl, pcb


def _portrait(tmp_path):
    from PIL import Image
    img = Image.new("1", (40, 40), 0)
    for x in range(40):
        for y in range(40):
            img.putpixel((x, y), int((x // 5 + y // 5) % 2))       # a chequerboard
    png = tmp_path / "cat.png"
    img.save(png)
    return png


@pytest.mark.kicad
def test_kicad_parses_unrouted_board(tmp_path):
    _, _, pcb = _mini(tmp_path)
    drc = _drc(pcb, tmp_path / "drc.json")
    assert drc["unconnected_items"], "an unrouted board must report unconnected items"
    assert [v for v in drc["violations"] if v["type"] in BAD] == []


def test_two_layer_board_has_gnd_pours_on_both_layers(tmp_path):
    _, _, pcb = _mini(tmp_path)
    tree = parse(pcb.read_text())
    cu = [l[1] for l in find(tree, "layers")[1:] if l[2] in ("signal", "power")]
    assert cu == ["F.Cu", "B.Cu"]
    zones = [z for z in find_all(tree, "zone") if find(z, "keepout") is None]
    assert [(find(z, "net_name")[1], find(z, "layer")[1]) for z in zones] == [("GND", "F.Cu"), ("GND", "B.Cu")]


def test_keepout_rule_area_written(tmp_path):
    _, _, pcb = _mini(tmp_path, keepouts=[("band", [(0, 0), (21, 0), (21, 1), (0, 1)], ("F.Cu", "B.Cu"))])
    keep = [z for z in find_all(parse(pcb.read_text()), "zone") if find(z, "keepout") is not None]
    assert len(keep) == 1 and find(keep[0], "layers")[1:] == ["F.Cu", "B.Cu"]
    rules = {r[0]: r[1] for r in find(keep[0], "keepout")[1:]}
    assert rules == {"tracks": "not_allowed", "vias": "not_allowed", "pads": "not_allowed",
                     "copperpour": "not_allowed", "footprints": "allowed"}


def test_pour_only_keepout_blocks_nothing_but_the_pour(tmp_path):
    _, _, pcb = _mini(tmp_path, keepouts=[("band", [(0, 0), (21, 0), (21, 1), (0, 1)], ("F.Cu", "B.Cu"), True)])
    keep = [z for z in find_all(parse(pcb.read_text()), "zone") if find(z, "keepout") is not None]
    rules = {r[0]: r[1] for r in find(keep[0], "keepout")[1:]}
    assert rules == {"tracks": "allowed", "vias": "allowed", "pads": "allowed",
                     "copperpour": "not_allowed", "footprints": "allowed"}


def test_pad_extra_and_user_rects_written(tmp_path):
    from board.sexpr import Sym
    solid = {"H1": lambda pad: [[Sym("zone_connect"), 2]]}
    _, _, pcb = _mini(tmp_path, pad_extra=solid, user_rects=[(1.0, 2.0, 3.0, 4.0, "Dwgs.User")])
    text = pcb.read_text()
    assert text.count("(zone_connect 2)") == 1
    r = [g for g in find_all(parse(text), "gr_rect") if find(g, "layer")[1] == "Dwgs.User"]
    assert len(r) == 1 and find(r[0], "start")[1:] == [1.0, 2.0] and find(r[0], "end")[1:] == [3.0, 4.0]


def test_bad_layer_count(tmp_path):
    c = build_mini()
    with pytest.raises(ValueError):
        write_board(c, place_mini(c), tmp_path / "x.kicad_pcb", layers=3)


@pytest.mark.kicad
def test_pro_file_read_by_drc(tmp_path):
    """The 0.15 mm default clearance in .kicad_pro must reach DRC (net_settings.meta.version 3):
    two pads 0.1 mm apart violate it, and the report states the 0.15 mm limit."""
    c = Circuit()
    a = c.add("C100N", "C1")
    b = c.add("C100N", "C2")
    c.connect("A", (a, "1"), (b, "1"))
    c.connect("B", (a, "2"), (b, "2"))
    pl = Placement((0.0, 0.0, 10.0, 10.0), {"C1": (3.0, 5.0, 0.0), "C2": (4.44, 5.0, 0.0)})
    pcb = tmp_path / "x.kicad_pcb"
    write_board(c, pl, pcb, layers=2)
    pro = json.loads((tmp_path / "x.kicad_pro").read_text())
    assert pro["net_settings"]["meta"]["version"] == 3
    assert pro["board"]["design_settings"]["rules"]["min_clearance"] == 0.15
    drc = _drc(pcb, tmp_path / "drc.json")
    clr = [v for v in drc["violations"] if v["type"] == "clearance"]
    assert clr and "0.1500 mm" in clr[0]["description"]


def test_dnp_flag_on_synthetic_dnp(tmp_path):
    c = Circuit()
    a = c.add("C100N", "C1", dnp=True)
    b = c.add("C100N", "C2")
    c.connect("A", (a, "1"), (b, "1"))
    pl = Placement((0.0, 0.0, 10.0, 10.0), {"C1": (3.0, 5.0, 0.0), "C2": (7.0, 5.0, 0.0)})
    pcb = tmp_path / "x.kicad_pcb"
    write_board(c, pl, pcb, layers=2)
    attrs = [find(f, "attr") for f in find_all(parse(pcb.read_text()), "footprint")]
    assert sum(1 for a in attrs if "dnp" in a) == 1


def test_tracks_and_vias_written(tmp_path):
    _, _, pcb = _mini(tmp_path, tracks=[Track("GND", "F.Cu", 10, 25, 14, 25, 0.3)], vias=[Via("GND", 15, 25)])
    tree = parse(pcb.read_text())
    assert len(find_all(tree, "segment")) == 1 and len(find_all(tree, "via")) == 1


def test_back_text_is_mirrored_and_front_text_is_not(tmp_path):
    _, _, pcb = _mini(tmp_path, silk=[("BACK", 20.0, 27.0, 1.0, "B.SilkS"), ("FRONT", 20.0, 3.0, 1.0)])
    texts = find_all(parse(pcb.read_text()), "gr_text")
    back = [t for t in texts if find(t, "layer")[1] == "B.SilkS"]
    front = [t for t in texts if find(t, "layer")[1] == "F.SilkS"]
    assert [t[1] for t in back] == ["BACK"] and "FRONT" in {t[1] for t in front}
    assert all(find(find(t, "effects"), "justify") == ["justify", "mirror"] for t in back)
    assert all(find(find(t, "effects"), "justify") is None for t in front)


def test_portrait_is_on_the_back_silk_only(tmp_path):
    png = _portrait(tmp_path)
    _, _, pcb = _mini(tmp_path, art=[(png, 10.0, 18.0, 8.0, "back", [(36.0, 26.0, 3.0)])])
    tree = parse(pcb.read_text())
    art = next(f for f in find_all(tree, "footprint") if f[1].startswith("ART"))
    layers = {find(g, "layer")[1] for g in art[2:] if isinstance(g, list) and g and g[0] in
              ("fp_poly", "fp_rect", "fp_line") and find(g, "layer")}
    assert layers == {"B.SilkS"}
    # no art, no ART footprint
    (tmp_path / "noart").mkdir()
    _, _, pcb2 = _mini(tmp_path / "noart")
    assert not [f for f in find_all(parse(pcb2.read_text()), "footprint") if f[1].startswith("ART")]


def test_footprint_silk_pulled_inside_the_edge(tmp_path):
    """A part hanging over the outline keeps none of its silkscreen beyond 0.2 mm inside it."""
    from board.placement import rotate
    c = build_mini()
    pl = place_mini(c)
    pl.at["J1"] = (1.5, 15.0, 270.0)                 # the connector's housing overhangs x = 0
    pcb = tmp_path / "edge.kicad_pcb"
    write_board(c, pl, pcb, layers=2)
    j1 = next(f for f in find_all(parse(pcb.read_text()), "footprint") if find(f, "at")[1:3] == [1.5, 15.0])
    lines = [g for g in find_all(j1, "fp_line") if "SilkS" in find(g, "layer")[1]]
    assert lines
    for g in lines:
        for key in ("start", "end"):
            dx, dy = rotate(find(g, key)[1], find(g, key)[2], 270.0)
            assert 0.2 - 1e-3 <= 1.5 + dx <= W - 0.2 + 1e-3
            assert 0.2 - 1e-3 <= 15.0 + dy <= H - 0.2 + 1e-3


def test_mains_netclass_and_rules_written(tmp_path):
    _, _, pcb = _mini(tmp_path)
    pro = json.loads(pcb.with_suffix(".kicad_pro").read_text())
    ns = pro["net_settings"]
    mains = next(c for c in ns["classes"] if c["name"] == "Mains")
    assert mains["clearance"] == MAINS_FUNCTIONAL
    assert {"netclass": "Mains", "pattern": "MAINS_*"} in ns["netclass_patterns"]
    assert (MAINS_FUNCTIONAL, MAINS_REINFORCED, MAINS_EDGE) == (2.5, 8.0, 3.0)
    assert pcb.with_suffix(".kicad_dru").read_text() == DRU


def test_every_assembled_footprint_has_a_3d_model(tmp_path):
    """Every non-DNP part JLCPCB places carries a (model ...) pointing at a STEP file in
    footprints/lcsc.3dshapes (through ${KIPRJMOD}); board-only footprints (holes) have none. If
    the models have been fetched, each named file exists."""
    from board.parts import LCSC_3D
    c, pl, pcb = _mini(tmp_path)
    tree = parse(pcb.read_text())
    refs = {}
    for fp in find_all(tree, "footprint"):
        ref = next((p[2] for p in find_all(fp, "property") if p[1] == "Reference"), None)
        ref = ref or next((t[2] for t in find_all(fp, "fp_text") if t[1] == "reference"), None)
        refs[ref] = find_all(fp, "model")
    from board.parts import NO_MODEL
    fitted = [r for r, i in c.instances.items() if i.part.lcsc and not i.dnp and i.part.key not in NO_MODEL]
    assert fitted
    for r in fitted:
        models = refs[r]
        assert len(models) == 1, r
        path = models[0][1]
        assert path.startswith("${KIPRJMOD}/") and path.endswith(".step"), (r, path)
        local = (tmp_path / path.replace("${KIPRJMOD}/", "")).resolve()
        assert local.parent == LCSC_3D.resolve(), (r, local)
        if LCSC_3D.is_dir() and any(LCSC_3D.glob("*.step")):
            assert local.exists(), (r, local.name)
    for r in ("H1", "H2", "H3"):
        assert refs[r] == [], r


def test_model_offset_corrections_written(tmp_path):
    from board.parts import MODEL_OFFSET
    c, pl, pcb = _mini(tmp_path)
    tree = parse(pcb.read_text())
    checked = 0
    for fp in find_all(tree, "footprint"):
        ref = next((t[2] for t in find_all(fp, "fp_text") if t[1] == "reference"), None)
        if ref in c.instances and c.instances[ref].part.key in MODEL_OFFSET:
            got = find(find(find(fp, "model"), "offset"), "xyz")[1:]
            assert got == list(MODEL_OFFSET[c.instances[ref].part.key]), ref
            checked += 1
    assert checked >= 3                      # J1 (JST5), C1/C2 (C10U), C3 (C100N)
