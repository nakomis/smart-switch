import pytest

from board.parts import ESP32_ANTENNA, PARTS, part

# Espressif ESP32-S3-MINI-1 & MINI-1U datasheet v1.7, Table 3-1 (pin definitions):
# pad number -> pin name. The ones this board relies on, plus the GND list.
ESPRESSIF_TABLE = {"3": "3V3", "4": "IO0", "23": "IO19", "24": "IO20", "25": "IO21", "21": "IO17",
                   "34": "IO38", "39": "TXD0", "40": "RXD0", "41": "IO45", "44": "IO46", "45": "EN",
                   "7": "IO3"}
ESPRESSIF_GND = {1, 2, 42, 43} | set(range(46, 61))


def test_every_assembled_part_has_footprint_and_lcsc():
    for key, p in PARTS.items():
        assert p.footprint.pads, key
        if key in ("DEBUG", "MH", "MHN", "TESTHOLE"):
            assert p.lcsc is None, key            # board-only: never in the BOM or CPL
        else:
            assert p.lcsc.startswith("C"), key


def test_module_pin_table_matches_espressif():
    pins = part("ESP32").pins
    by_pad = {pad: name for name, pads in pins.items() for pad in pads}
    for pad, name in ESPRESSIF_TABLE.items():
        assert by_pad[pad] == name, pad
    for n in ESPRESSIF_GND:
        assert by_pad[str(n)] == "GND", n
    # pads 61-65 (thermal pad + 4 corners) are all numbered "GND" in the EasyEDA footprint
    assert sum(p.number == "GND" for p in part("ESP32").footprint.pads) == 13


def test_usb_pads_are_in_the_bottom_row_centre():
    pads = {p.number: p for p in part("ESP32").footprint.pads}
    assert pads["23"].x == 0.0 and abs(pads["24"].x - 0.85) < 1e-6
    assert pads["23"].y > 7.0 and pads["24"].y > 7.0          # bottom row, away from the antenna


def test_module_body_includes_the_antenna():
    p = part("ESP32")
    assert p.body == (-7.7, -12.8, 7.7, 7.7)                  # 15.4 x 20.5 mm
    top_pads = min(q.y - q.h / 2 for q in p.footprint.pads)
    assert ESP32_ANTENNA[3] < top_pads                       # the antenna strip holds no pads
    assert abs(ESP32_ANTENNA[3] - ESP32_ANTENNA[1] - 5.05) < 1e-6


def test_led_and_new_part_pins():
    assert part("LED").pins == {"VDD": ["1"], "DO": ["2"], "GND": ["3"], "DI": ["4"]}       # SK6812-EC20
    assert part("FET").pins == {"D": ["3"], "G": ["1"], "S": ["2"]}
    assert part("DIODE").pins == {"A": ["2"], "K": ["1"]}
    assert sorted(part("IO").pins, key=int) == [str(n) for n in range(1, 9)]
    assert sorted(part("IDC").pins, key=int) == [str(n) for n in range(1, 17)]


def test_ldo_and_esd_pins():
    assert part("LDO").pins == {"VIN": ["1"], "GND": ["2"], "EN": ["3"], "NC": ["4"], "VOUT": ["5"]}
    assert sorted(part("ESD").pins) == ["1", "2", "3", "4", "5", "6"]


def test_local_footprints():
    assert sorted(p.number for p in part("DEBUG").footprint.pads) == ["1", "2", "3", "4", "5"]
    assert part("R330").lcsc == "C25104" and part("R330").value == "330R"


def test_tht_flags():
    assert part("MH").tht and not part("ESP32").tht and not part("JST5").tht
    assert {k for k, p in PARTS.items() if p.tht and p.lcsc} == {
        "IO", "IO10", "IDC", "RELAY16", "PSU5W", "FUSEHOLD", "FUSECLIP", "MOV", "MAINSTERM", "TACT", "RFUSE",
        "C4U7HV"}


# --- Petro's parts against the makers' drawings (checked 4 Nov 2026) --------------------------

def _pads(key):
    return {p.number: p for p in part(key).footprint.pads if p.number}


def _gap(a, b):
    """Copper gap between two pads, taken as rectangles (circles' bounding boxes)."""
    dx = abs(a.x - b.x) - (a.w + b.w) / 2
    dy = abs(a.y - b.y) - (a.h + b.h) / 2
    return max(dx, dy) if min(dx, dy) < 0 else (dx ** 2 + dy ** 2) ** 0.5


def test_relay_matches_hongfa_layout():
    """HF115F 1 Form A: coil pair, then COM (inner) and NO (outer) columns 5.04 mm apart, each
    two paralleled pins; the coil is 20.16 mm from COM."""
    p = _pads("RELAY16")
    assert part("RELAY16").pins == {"COIL1": ["1"], "COIL2": ["2"], "COM": ["6", "5"], "NO": ["8", "7"]}
    assert p["5"].x - p["1"].x == pytest.approx(20.16) and p["7"].x - p["5"].x == pytest.approx(5.04)
    coil_contact = min(_gap(p[c], p[k]) for c in ("1", "2") for k in ("5", "6", "7", "8"))
    assert coil_contact > 8.0                                        # reinforced, well clear
    assert _gap(p["5"], p["7"]) >= 2.5                               # COM to NO: LIVE to LOAD


def test_irm05_matches_mean_well_drawing():
    p = _pads("PSU5W")
    assert part("PSU5W").pins == {"AC/L": ["1"], "AC/N": ["2"], "+V": ["3"], "-V": ["4"]}
    assert abs(p["1"].y - p["2"].y) == pytest.approx(10.75, abs=0.02)     # AC/L to AC/N
    assert abs(p["4"].y - p["3"].y) == pytest.approx(8.0, abs=0.02)       # -V to +V
    assert p["4"].x - p["1"].x == pytest.approx(38.5)                     # AC column to DC column
    assert p["1"].y == p["4"].y                                           # AC/L level with -V
    assert part("PSU5W").body == (-22.85, -16.57, 22.85, 8.83)


def test_tactile_switch_pairs_follow_the_circuit_diagram():
    """XUNPU TS-1002: pads 6.5 mm apart are one terminal; the button joins the pairs."""
    p = _pads("TACT")
    pins = part("TACT").pins
    assert {k: sorted(v) for k, v in pins.items()} == {"A": ["1", "2"], "B": ["3", "4"]}
    assert abs(p["1"].x - p["2"].x) == pytest.approx(6.5) and p["1"].y == p["2"].y
    assert abs(p["1"].y - p["3"].y) == pytest.approx(4.5)


def test_f1_clip_matches_littelfuse_drawing():
    """Littelfuse 122 series (01220088Z, 30 A, for the 505 series fuse): one clip, two straight
    leads 7.62 mm apart on one net, 1.98 mm holes (drilled 2.0)."""
    p = part("FUSECLIP")
    pads = p.footprint.pads
    assert p.pins == {"1": ["1"]} and len(pads) == 2
    assert pads[1].x - pads[0].x == pytest.approx(7.62)
    assert all(q.drill == 2.0 and q.kind == "thru_hole" for q in pads)


F1_CLIP_PITCH = 34.21 - 7.62          # clip centre to clip centre for a 1 1/4 in fuse (A = 1.347 in)


def test_isolator_pad_rows_need_the_barrier_exception():
    """The ISOW7743's wide-body SOIC-20 leaves 7.1 mm between its two sides: above the 3.0 mm
    reinforced clearance, below the 8 mm rule, hence the barrier exception and the slot. Pins as
    TI's ISOW7743 column (SLLSFK1C): A forward, B/C/D reverse."""
    p = _pads("ISOW")
    assert _gap(p["1"], p["20"]) == pytest.approx(7.1, abs=0.01)
    pins = part("ISOW").pins
    assert {k: pins[k] for k in ("VIO", "INA", "OUTB", "OUTC", "OUTD", "VDD", "GND1",
                                 "GND2", "VISOOUT", "VSEL", "IND", "INC", "INB", "OUTA", "VISOIN")} == {
        "VIO": ["1"], "INA": ["2"], "OUTB": ["3"], "OUTC": ["4"], "OUTD": ["5"], "VDD": ["9"],
        "GND1": ["10"], "GND2": ["11"], "VISOOUT": ["12"], "VSEL": ["13"], "IND": ["16"],
        "INC": ["17"], "INB": ["18"], "OUTA": ["19"], "VISOIN": ["20"]}


def test_shunt_is_four_terminal_with_diagonal_sense_pads():
    """Vishay WSK2512 1-4.9 mOhm: 3.30 x 2.03 current pads 1.66 mm apart; 0.76 mm sense pads
    0.51 mm beside them, on opposite long edges."""
    p = _pads("SHUNT")
    assert _gap(p["1"], p["4"]) == pytest.approx(1.66, abs=0.01)
    assert (p["1"].w, p["1"].h) == (3.3, 2.03) and p["2"].h == 0.76
    assert p["2"].x < 0 < p["3"].x and p["2"].y > 0 > p["3"].y          # diagonal
    assert _gap(p["1"], p["2"]) == pytest.approx(0.51, abs=0.01)


def test_divider_resistor_pads_hold_one_step():
    """Each 390k sees one fifth of 250 V: 50 V needs 1.2 mm (IEC 60664-1, PD2, MG III)."""
    from board.rules import creepage
    a, b = _pads("R390K").values()
    assert _gap(a, b) >= creepage(50)


def test_bl0939_pinout():
    pins = part("BL0939").pins
    assert {k: pins[k] for k in ("VDD", "IP1", "IN1", "IP2", "IN2", "VP", "GND", "ZX", "I_leak",
                                 "SEL", "RX/SDI", "TX/SDO")} == {
        "VDD": ["1"], "IP1": ["3"], "IN1": ["4"], "IP2": ["5"], "IN2": ["6"], "VP": ["7"],
        "GND": ["8"], "ZX": ["9"], "I_leak": ["10"], "SEL": ["12"], "RX/SDI": ["14"], "TX/SDO": ["15"]}
    assert not part("MHN").tht


def test_test_hole_is_one_bare_plated_hole_for_a_push_in_loop():
    """Martin's ceramic test loops are pushed in, not soldered: one plated hole, no BOM line."""
    from board.parts import TESTHOLE_DRILL
    p = part("TESTHOLE")
    assert p.lcsc is None and p.tht
    (pad,) = p.footprint.pads
    assert pad.kind == "thru_hole" and pad.number == "1"
    # Martin's calipers: two 0.3 mm legs, 1.2 mm across, sprung apart. Both go into one 0.8 mm
    # hole, squeezed together (0.6 mm), so they push outwards on the barrel and hold.
    assert TESTHOLE_DRILL == 0.8 and pad.drill == TESTHOLE_DRILL
    assert 2 * 0.35 < TESTHOLE_DRILL < 1.2               # the drawing says 0.35 mm wire; worst case
    assert pad.w == pad.h and pad.w - TESTHOLE_DRILL >= 0.8   # an annular ring of at least 0.4 mm


# --- revision B (non-isolated): the LNK306 supply, the 12 V -> 5 V buck, the SK6812 ---------------

def test_lnk306_pins_match_power_integrations_figure_3():
    """SO-8C (D package): 1 BP, 2 FB, 4 D, 5-8 S (pin 3 absent)."""
    assert part("LNK306").pins == {"BP": ["1"], "FB": ["2"], "D": ["4"], "S": ["5", "6", "7", "8"]}


def test_tps563201_pins_match_ti():
    assert part("BUCK").pins == {"GND": ["1"], "SW": ["2"], "VIN": ["3"], "VFB": ["4"], "EN": ["5"],
                                 "VBST": ["6"]}


@pytest.mark.parametrize("key", ["C4U7HV", "C220U"])
def test_electrolytics_are_polarised_pad_1_positive(key):
    """Both footprints mark pad 1 positive (the silk '+', the chamfered base)."""
    assert part(key).pins == {"+": ["1"], "-": ["2"]}


@pytest.mark.parametrize("key", ["RECT", "ES1J", "S1G"])
def test_diodes_name_anode_and_cathode(key):
    assert set(part(key).pins) == {"A", "K"}


def test_sk6812_keeps_the_led_pin_names():
    """SK6812-EC20: 1 VDD, 2 DOUT, 3 GND, 4 DIN (not the WS2812B-2020's order), named as before."""
    assert part("LED").pins == {"VDD": ["1"], "DO": ["2"], "GND": ["3"], "DI": ["4"]}
    assert part("LED").lcsc == "C2909058"


def test_fusible_resistor_is_the_local_axial_footprint():
    p = part("RFUSE")
    assert p.tht and p.lcsc == "C1394194" and len(p.footprint.pads) == 2
    (a, b) = p.footprint.pads
    assert abs(b.x - a.x) == pytest.approx(15.24) and a.drill == pytest.approx(1.0)
