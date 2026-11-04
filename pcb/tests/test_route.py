import json
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import KICAD_CLI
from fixture_board import H, W, build_mini, place_mini

from board.dsn import write_dsn
from board.kicad_pcb import Track, Via, write_board
from board.netlist import Circuit
from board.placement import Placement
from board.route import FREEROUTING, route
from board.ses import read_ses
from board.sexpr import Sym

DATA = Path(__file__).parent / "data"


def _line(text, start):
    return next(l for l in text.splitlines() if l.strip().startswith(start))


def test_read_ses_converts_units_and_flips_y():
    tracks, vias = read_ses(DATA / "mini.ses")
    assert len(tracks) == 2 and len(vias) == 1
    t = tracks[0]
    assert (t.net, t.layer, t.width) == ("GND", "F.Cu", 0.15)
    assert (t.x1, t.y1, t.x2, t.y2) == (100.0, 100.0, 110.0, 100.0)
    assert (vias[0].x, vias[0].y) == (110.0, 105.0)


def test_read_ses_reports_widened_segments(tmp_path):
    ses = tmp_path / "n.ses"
    ses.write_text('(session n (routes (resolution um 1) (network_out (net A (wire (path F.Cu 100 0 0 1000 0))))))')
    rep = {}
    tracks, _ = read_ses(ses, min_width=0.15, report=rep)
    assert tracks[0].width == 0.15 and rep == {"widened": 1, "widened_mm": 1.0}


def test_dsn_two_layer_with_gnd_left_to_the_pours(tmp_path):
    c = build_mini()
    write_dsn(c, place_mini(c), tmp_path / "a.dsn", layers=2, skip_nets=("GND",))
    text = (tmp_path / "a.dsn").read_text()
    assert "(plane" not in text and "In1.Cu" not in text
    assert "(layer F.Cu (type signal))" in text and "(layer B.Cu (type signal))" in text
    assert text.count("(net ") >= len(c.nets)
    assert "(class gnd GND" not in text and '(class power "+3V3" VBUS' in text
    assert _line(text, "(net GND").count("-") == 1        # one pin: nothing for the router to do


def test_dsn_boundary_is_the_route_area(tmp_path):
    c = build_mini()
    area = [(2.0, 1.0), (38.0, 1.0), (38.0, 29.0), (2.0, 29.0)]
    write_dsn(c, place_mini(c), tmp_path / "a.dsn", layers=2, route_area=area)
    line = next(l for l in (tmp_path / "a.dsn").read_text().splitlines() if "(boundary" in l)
    nums = [int(v) for v in line.replace(")", " ").split()[4:]]
    xs = [x / 1000 for x in nums[0::2]]
    ys = [-y / 1000 for y in nums[1::2]]
    assert (min(xs), max(xs), min(ys), max(ys)) == (2.0, 38.0, 1.0, 29.0)


def test_dsn_repeated_pad_numbers_get_unique_pin_ids(tmp_path):
    """The module's footprint numbers 13 pads "GND"; each needs its own DSN pin id."""
    c = Circuit()
    u = c.add("ESP32", "U1")
    cap = c.add("C100N", "C1")
    c.connect("GND", (u, "GND"), (cap, "2"))
    c.connect("+3V3", (u, "3V3"), (cap, "1"))
    pl = Placement((0.0, 0.0, 30.0, 30.0), {"U1": (15.0, 17.0, 0.0), "C1": (3.0, 3.0, 0.0)})
    write_dsn(c, pl, tmp_path / "b.dsn", layers=2)
    text = (tmp_path / "b.dsn").read_text()
    img = next(l for l in text.splitlines() if "(image U1_img" in l)
    assert img.count(' GND ') == 1 and ' GND_13 ' in img and ' GND_14 ' not in img
    gnd = _line(text, "(net GND")
    assert "U1-GND_13" in gnd and "U1-GND " in gnd and "U1-46" in gnd


def test_dsn_carries_fixed_wiring_and_via_keepouts(tmp_path):
    c = build_mini()
    t = [Track("GND", "F.Cu", 20.0, 17.0, 20.0, 19.0, 0.3)]
    v = [Via("GND", 20.0, 19.0)]
    write_dsn(c, place_mini(c), tmp_path / "a.dsn", layers=2, fixed_tracks=t, fixed_vias=v,
              via_keepouts=[(10.0, 20.0, 15.0, 25.0)], skip_nets=("GND",))
    text = (tmp_path / "a.dsn").read_text()
    assert text.count("(type protect)") == 1 and text.count("(type fix)") == 1
    assert text.count("(via_keepout") == 2                 # one per layer


@pytest.mark.skipif(not FREEROUTING.exists() or not shutil.which("java"), reason="Freerouting or Java missing")
def test_freerouting_routes_the_fixture_drc_clean(tmp_path):
    """Integration (about 30 s): route the fixture board in a temporary directory, never in out/
    (Freerouting is not deterministic, so routing in place would overwrite an ordered board),
    then check KiCad's DRC finds nothing unconnected and no errors."""
    c = build_mini()
    p = place_mini(c)
    tracks, vias = route(c, p, tmp_path / "route", passes=20, layers=2, skip_nets=("GND",))
    assert tracks
    assert (tmp_path / "route" / "freerouting.log").stat().st_size > 0
    pcb = tmp_path / "mini.kicad_pcb"
    # Every GND pad joins the pours solidly, as on the heatlink: with thermal reliefs, a pad
    # walled in by tracks gets fewer than two spokes and DRC reports starved_thermal.
    def gnd_solid(ref):
        return lambda pad: [[Sym("zone_connect"), 2]] if c.net_of(ref, pad.number) == "GND" else []
    solid = {r: gnd_solid(r) for r in c.instances}
    write_board(c, p, pcb, tracks, vias, layers=2, pad_extra=solid)
    subprocess.run([KICAD_CLI, "pcb", "drc", "--refill-zones", "--format", "json", "--severity-all",
                    "-o", str(tmp_path / "drc.json"), str(pcb)], check=True, capture_output=True)
    drc = json.loads((tmp_path / "drc.json").read_text())
    assert drc["unconnected_items"] == [], drc["unconnected_items"]
    assert [v["type"] for v in drc["violations"] if v["severity"] == "error"] == []
