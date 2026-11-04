"""Petro's netlist, revision B (non-isolated): the live path, the shunt in the neutral, the star
point where the low-voltage ground meets neutral, PI's LNK306 buck, the TPS563201, the BL0939
wired straight to the ESP32, the divider, the GPIOs and the reuse I/O (internal only)."""
import pytest

from board import petro_board as pb
from board.netlist import check

C = pb.build_petro()
MAINS = set(pb.GROUPS)


def nets_of(ref):
    return {n for n, pads in C.nets.items() for r, _ in pads if r == ref}


def net(ref, pin):
    pads = C.instances[ref].part.pins[pin]
    got = {C.net_of(ref, p) for p in pads}
    assert len(got) == 1, (ref, pin, got)
    return got.pop()


def by_key(key):
    return sorted((r for r, i in C.instances.items() if i.part.key == key), key=lambda r: int(r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")))


def test_check_is_clean():
    assert check(C) == []


# --- no isolation left -----------------------------------------------------------------------------

def test_nothing_of_the_isolation_remains():
    keys = {i.part.key for i in C.instances.values()}
    assert not keys & {"ISOW", "PSU5W", "BEAD"}
    assert not {"GND_M", "3V3_M", "VISO_M", "GISO_M", "ISO_FLT"} & set(C.nets)
    assert "ISO_FLT" not in pb.GPIO and pb.BARRIERS == ()


def test_rules_are_non_isolated_with_the_rest_at_neutral():
    r = pb.rules()
    assert r.rest == "NEUTRAL" and "SELV" not in r.dru()


def test_mounting_holes_are_unplated():
    for ref in ("H1", "H2", "H3", "H4"):
        assert C.instances[ref].part.key == "MHN", ref


# --- the live and neutral paths ----------------------------------------------------------------------

def test_live_path_order():
    """J1 -> F1 -> (MOV) -> relay -> J2 on the live; the supply branch after F2, which is after F1."""
    assert net("J1", "2") == net("XF1", "1") == "L_IN"
    assert net("XF2", "1") == net("K1", "COM") == net("XF3", "1") == "L_F"
    assert {net("RV1", "1"), net("RV1", "2")} == {"L_F", "N_OUT"}
    assert net("K1", "NO") == net("J2", "1") == "L_OUT"
    assert net("XF3", "2") == "L_PSU"


def test_neutral_runs_through_the_shunt():
    assert net("J1", "1") == net("RS1", "I1") == "N_IN"
    assert net("RS1", "I2") == net("J2", "2") == "N_OUT"


def test_high_current_nets_are_the_load_path():
    assert pb.HIGH_CURRENT == {"L_IN", "L_F", "L_OUT", "N_IN", "N_OUT"}


def test_ground_meets_neutral_only_at_the_shunt_sense_pad():
    """The star point: GND is the shunt's sense pad on the supply side; no other part joins GND
    to N_IN, so no load current flows in the low-voltage ground."""
    assert net("RS1", "E1") == "GND" and net("RS1", "E2") == "SENSE"
    bridges = {r for r in C.instances if {"GND", "N_IN"} <= nets_of(r)}
    assert bridges == {"RS1"}


# --- the supply: PI's LNK306 high-side buck, 12 V -----------------------------------------------------

def test_input_stage_fuse_resistor_halfwave_and_pi_filter():
    rf = by_key("RFUSE")[0]
    assert nets_of(rf) == {"L_PSU", "L_RF"}
    d = by_key("RECT")[0]
    assert (net(d, "A"), net(d, "K")) == ("L_RF", "VBULK1")
    caps = by_key("C4U7HV")
    assert sorted(net(c, "+") for c in caps) == ["VBULK", "VBULK1"] and {net(c, "-") for c in caps} == {"GND"}
    l2 = by_key("L1MF")[0]
    assert nets_of(l2) == {"VBULK1", "VBULK"}


def test_lnk306_high_side_buck():
    """PI Figure 5: D to the bulk rail; S is the switching node, the reference for BP and FB;
    L1 from S to +12V; the freewheel diode from GND to S; the feedback samples the output
    through D2 onto C3 (across S), divided by R1/R3 to 1.65 V at FB."""
    u = "U4"
    assert C.instances[u].part.key == "LNK306"
    assert net(u, "D") == "VBULK" and net(u, "S") == "SW"
    bp = [r for r in by_key("C100N6") if nets_of(r) == {"BP", "SW"}]
    assert net(u, "BP") == "BP" and len(bp) == 1
    assert nets_of(by_key("L1MO")[0]) == {"SW", "+12V"}
    d1 = by_key("ES1J")[0]
    assert (net(d1, "A"), net(d1, "K")) == ("GND", "SW")
    d2 = by_key("S1G")[0]
    assert (net(d2, "A"), net(d2, "K")) == ("+12V", "FBH")
    c3 = [r for r in by_key("C10U50") if nets_of(r) == {"FBH", "SW"}]
    assert len(c3) == 1
    r1 = by_key("R13K")[0]
    r3 = by_key("R2K")[0]
    assert nets_of(r1) == {"FBH", "FB"} and nets_of(r3) == {"FB", "SW"} and net(u, "FB") == "FB"
    vout = 1.65 * (1 + 13.0 / 2.0)
    assert 12.0 <= vout <= 12.5 < 19                           # the TPS563201's absolute maximum
    c2 = by_key("C220U")[0]
    assert (net(c2, "+"), net(c2, "-")) == ("+12V", "GND")
    assert nets_of(by_key("R3K3")[0]) == {"+12V", "GND"}       # the pre-load (> 3 mA)


def test_tps563201_makes_5v_for_the_existing_rail():
    u = "U5"
    assert C.instances[u].part.key == "BUCK"
    assert net(u, "VIN") == net(u, "EN") == "+12V" and net(u, "GND") == "GND"
    assert net(u, "SW") == "SW5" and net(u, "VFB") == "FB5"
    assert nets_of(by_key("L3U3")[0]) == {"SW5", "VPSU"}
    boot = [r for r in by_key("C100N6") if nets_of(r) == {"SW5", "BST5"}]
    assert net(u, "VBST") == "BST5" and len(boot) == 1
    top, bottom = by_key("R54K9")[0], by_key("R10K6")[0]
    assert nets_of(top) == {"VPSU", "FB5"} and nets_of(bottom) == {"FB5", "GND"}
    assert 4.9 < 0.768 * (1 + 54.9 / 10.0) < 5.1
    assert len([r for r in by_key("C22U") if nets_of(r) == {"VPSU", "GND"}]) == 2


def test_diode_or_feeds_5v_from_the_supply_or_usb():
    d = by_key("SS34")
    assert sorted(net(r, "A") for r in d) == ["VBUS", "VPSU_F"] and {net(r, "K") for r in d} == {"+5V"}
    assert nets_of("F3") == {"VPSU", "VPSU_F"} and nets_of("F4") == {"VBUS_IN", "VBUS"}


def test_supply_high_voltage_nets_are_the_psu_group():
    for n in ("L_PSU", "L_RF", "VBULK1", "VBULK", "SW", "BP", "FB", "FBH"):
        assert pb.GROUPS[n] == "PSU", n


# --- metering ------------------------------------------------------------------------------------------

def test_both_current_channels_read_the_shunt_against_ground():
    for p, n in (("IP1", "IN1"), ("IP2", "IN2")):
        rp = next(r for r, _ in C.nets[net("U3", p)] if r != "U3" and C.instances[r].part.key == "R1K")
        rn = next(r for r, _ in C.nets[net("U3", n)] if r != "U3" and C.instances[r].part.key == "R1K")
        assert "SENSE" in nets_of(rp) and "GND" in nets_of(rn)


def test_voltage_divider_from_line():
    """Five 390k from L_IN (before F1, like rev A's from the unfused neutral) to VP, 470R to ground:
    61 mV at 253 V; the BL0939 still sees the mains with F1 blown. DIV1 is next to VP,
    so DIVk sits k fifths of the way from neutral to LINE (rules: divider_top="LINE")."""
    chain = ["VP", "DIV1", "DIV2", "DIV3", "DIV4", "L_IN"]
    assert pb.rules().divider_top == "LINE"
    rs = by_key("R390K")
    assert len(rs) == 5
    pairs = sorted((tuple(sorted(nets_of(r), key=chain.index)) for r in rs), key=lambda p: chain.index(p[0]))
    assert pairs == list(zip(chain, chain[1:]))
    assert nets_of(by_key("R470")[0]) == {"VP", "GND"}
    assert 253 * 470 / (5 * 390e3 + 470) < 0.070
    assert net("U3", "VP") == "VP"


def test_bl0939_is_wired_straight_to_the_esp32():
    assert net("U3", "VDD") == "+3V3" and net("U3", "GND") == net("U3", "SEL") == "GND"
    for pin, k in (("TX/SDO", "BL_TX"), ("RX/SDI", "BL_RX"), ("ZX", "ZX"), ("I_leak", "OC")):
        assert net("U3", pin) == k and net("U1", pb.modpin(pb.GPIO[k])) == k
    assert len([r for r in by_key("R10K") if nets_of(r) == {"BL_TX", "+3V3"}]) == 1


# --- the low-voltage side ---------------------------------------------------------------------------

def test_relay_driver():
    assert {net("K1", "COIL1"), net("K1", "COIL2")} == {"+5V", "COIL"}
    assert net("Q1", "D") == "COIL" and net("Q1", "S") == "GND" and net("Q1", "G") == "RELAY_G"
    assert (net("D3", "K"), net("D3", "A")) == ("+5V", "COIL")
    assert net("U1", pb.modpin(pb.GPIO["RELAY"])) == "RELAY"


def test_led_is_the_sk6812():
    assert C.instances["D1"].part.lcsc == "C2909058"
    assert (net("D1", "VDD"), net("D1", "GND"), net("D1", "DI")) == ("+3V3", "GND", "LED_DIN")


def test_gpios_avoid_flash_usb_and_debug_and_are_unique():
    nums = list(pb.GPIO.values())
    assert len(nums) == len(set(nums))
    assert not set(nums) & pb.FLASH
    assert set(nums) & pb.STRAPPING == {0, 3}                     # the button and the NTC, deliberately
    for k, g in pb.GPIO.items():
        if g in (19, 20, 43, 44):
            assert k in ("USB_DM", "USB_DP", "UART_TX", "UART_RX"), k
        assert net("U1", pb.modpin(g)) == k, k


def test_reuse_io_matches_the_heatlink():
    """J3 and J4 keep the heatlink's pinouts and GPIOs (internal only on this board)."""
    heat_io = {"1": "VBUS", "2": "GND", "3": "+3V3", "4": "IO_SDA", "5": "IO_SCL", "6": "IO_4",
               "7": "IO_5", "8": "IO_6"}
    heat_gpio = {"IO_SDA": 1, "IO_SCL": 2, "IO_4": 4, "IO_5": 5, "IO_6": 6,
                 **{f"HDR_{n}": n for n in (7, 8, 9, 10, 11, 16, 17, 18, 21, 38, 39, 40)}}
    assert {p: ("VBUS" if n == "+5V" else n) for p, n in pb.IO_PINS.items()} == heat_io
    assert pb.HDR_PINS["16"] == "+5V" and pb.HDR_PINS["1"] == "+3V3"
    assert {k: g for k, g in pb.GPIO.items() if k in heat_gpio} == heat_gpio
    for pad, n in pb.IO_PINS.items():
        assert net("J3", pad) == n
    for pad, n in pb.HDR_PINS.items():
        assert net("J4", pad) == n


# --- test holes ------------------------------------------------------------------------------------

def test_test_holes_cover_the_signals_worth_scoping():
    holes = {C.net_of(r, "1") for r, i in C.instances.items() if i.part.key == "TESTHOLE"}
    assert holes == set(pb.TEST_HOLES.values())
    assert {"+5V", "+3V3", "COIL", "BL_TX", "BL_RX", "ZX", "OC", "LED_DIN", "BUTTON", "GND"} <= holes


def test_test_holes_are_on_low_voltage_nets():
    for ref, n in pb.TEST_HOLES.items():
        assert n not in MAINS, ref
        assert C.net_of(ref, "1") == n


def test_refs_number_from_one_without_gaps():
    """C1, C2, ... as a fab and a reader expect. F is the exception: F1 and F2 are the fuses
    themselves, in holders XF1/XF2 and XF3, so the PTCs are F3 and F4."""
    import re
    from collections import defaultdict
    nums = defaultdict(list)
    for ref in C.instances:
        prefix, n = re.fullmatch(r"([A-Z]+)(\d+)", ref).groups()
        nums[prefix].append(int(n))
    for prefix, ns in nums.items():
        if prefix != "F":
            assert sorted(ns) == list(range(1, len(ns) + 1)), (prefix, sorted(ns))
    assert sorted(nums["F"]) == [3, 4]
