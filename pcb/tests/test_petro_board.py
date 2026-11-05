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

def test_nothing_of_rev_a_isolation_remains():
    keys = {i.part.key for i in C.instances.values()}
    assert not keys & {"PSU5W", "ESP32", "IDC"}
    assert not {"GND_M", "3V3_M", "VISO_M", "GISO_M"} & set(C.nets)


def test_rules_are_non_isolated_with_the_rest_at_neutral_and_no_barrier():
    r = pb.rules()
    assert r.rest == "NEUTRAL"
    assert "SELV" not in pb.GROUPS.values() and not r.barriers
    assert "SELV" not in r.dru()


def test_no_isolators_are_left():
    """J3 is wired straight to the ESP32 (5 Nov 2026): the isolated version is tag rev-b-isolated-io."""
    keys = {i.part.key for i in C.instances.values()}
    assert not keys & {"ISOW", "ISO7741", "ISO1640", "BEAD"}
    assert not [n for n in C.nets if n.startswith("ISO_")]


# --- J3, the I/O terminal (inside the case, at mains potential) ------------------------------------

def test_j3_carries_the_board_rails_spi_i2c_in_and_out():
    assert C.instances["J3"].part.key == "IO10"
    assert {pad: net("J3", pad) for pad in pb.IO_PINS} == pb.IO_PINS
    assert list(pb.IO_PINS.values()) == ["+3V3", "GND", "SPI_SCLK", "SPI_MOSI", "SPI_MISO",
                                         "SPI_CS", "I2C_SDA", "I2C_SCL", "IO_IN", "IO_OUT"]


def test_j3s_signals_go_straight_to_their_gpios():
    for sig in ("SPI_SCLK", "SPI_MOSI", "SPI_MISO", "SPI_CS", "I2C_SDA", "I2C_SCL", "IO_IN", "IO_OUT"):
        assert ("U1", C.instances["U1"].part.pins[pb.modpin(pb.GPIO[sig])][0]) in C.nets[sig], sig


def test_i2c_is_pulled_up_and_in_pulled_down():
    for sig in ("I2C_SDA", "I2C_SCL"):
        assert len([r for r in by_key("R4K7") if nets_of(r) == {sig, "+3V3"}]) == 1, sig
    assert len([r for r in by_key("R100K") if nets_of(r) == {"IO_IN", "GND"}]) == 1


def test_the_mains_parts_are_hand_fit():
    keys = {r: C.instances[r].part.key for r in pb.HAND_FIT}
    assert keys == {"J1": "MAINSTERM", "J2": "MAINSTERM", "XF1": "FUSECLIP", "XF2": "FUSECLIP",
                    "XF3": "FUSEHOLD", "K1": "RELAY16", "RV1": "MOV", "R1": "RFUSE"}


def test_mounting_holes_are_unplated():
    for ref in ("H1", "H2", "H3", "H4"):
        assert C.instances[ref].part.key == "MHN", ref


# --- the live and neutral paths ----------------------------------------------------------------------

def test_live_path_order():
    """J1 -> F1 -> (MOV) -> relay -> J2 on the live; the supply branch after F2, which is after F1."""
    assert net("J1", "2") == net("XF1", "1") == "L_IN"
    assert net("XF2", "1") == net("K1", "COM") == net("XF3", "1") == "L_F"
    # the MOV returns to the incoming neutral: a surge never crosses the shunt
    assert {net("RV1", "1"), net("RV1", "2")} == {"L_F", "N_IN"}
    assert net("K1", "NO") == net("J2", "1") == "L_OUT"
    assert net("XF3", "2") == "L_PSU"


def test_neutral_runs_through_the_shunt():
    assert net("J1", "1") == net("RS1", "I1") == "N_IN"
    assert net("RS1", "I2") == net("J2", "2") == "N_OUT"


def test_high_current_nets_are_the_load_path():
    assert pb.HIGH_CURRENT == {"L_IN", "L_F", "L_OUT", "N_IN", "N_OUT"}


def test_ground_meets_neutral_only_at_the_bond_and_the_sense_lines_carry_no_current():
    """The star point is R29, a 0 R link from GND to N_IN: the only part joining them, so no load
    current flows in GND. The shunt's supply-side sense pad is KGND, a Kelvin return to the
    BL0939's negative-input filters only, so the supply's own return current (the rectifier's
    charging pulses) never flows in a sense line."""
    assert net("RS1", "E1") == "KGND" and net("RS1", "E2") == "SENSE"
    assert {r for r in C.instances if {"GND", "N_IN"} <= nets_of(r)} == {"R29"}
    assert C.instances["R29"].part.key == "R0"
    assert {r for r, _ in C.nets["KGND"]} == {"RS1", "R9", "R11"}
    assert {r for r, _ in C.nets["SENSE"]} == {"RS1", "R8", "R10"}


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
    assert nets_of(by_key("L680U")[0]) == {"SW", "+12V"}
    d1 = by_key("FASTREC")[0]                       # US1M, 75 ns (PI: 75 ns or faster in MDCM)
    assert (net(d1, "A"), net(d1, "K")) == ("GND", "SW")
    assert C.instances["D9"].part.key == "RECT"     # M7, as PI's 1N4005GP feedback diode
    assert (net("D9", "A"), net("D9", "K")) == ("+12V", "FBH")
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
    top, bottom = by_key("R56K")[0], by_key("R10K6")[0]
    assert nets_of(top) == {"VPSU", "FB5"} and nets_of(bottom) == {"FB5", "GND"}
    assert 4.9 < 0.768 * (1 + 56 / 10.0) < 5.1       # 5.07 V
    assert len([r for r in by_key("C22U") if nets_of(r) == {"VPSU", "GND"}]) == 2


def test_diode_or_feeds_5v_from_the_supply_or_usb():
    d = by_key("SS34")
    assert sorted(net(r, "A") for r in d) == ["VBUS", "VPSU_F"] and {net(r, "K") for r in d} == {"+5V"}
    assert nets_of("F3") == {"VPSU", "VPSU_F"} and nets_of("F4") == {"VBUS_IN", "VBUS"}


def test_supply_high_voltage_nets_are_the_psu_bus_and_swnode_groups():
    for n in ("L_PSU", "L_RF"):
        assert pb.GROUPS[n] == "PSU", n
    for n in ("VBULK1", "VBULK"):
        assert pb.GROUPS[n] == "BUS", n
    for n in ("SW", "BP", "FB", "FBH"):
        assert pb.GROUPS[n] == "SWNODE", n
    r = pb.rules()
    assert r.spacing("PSU", "NEUTRAL") == 2.5 and r.spacing("BUS", "NEUTRAL") == 3.55
    assert r.spacing("BUS", "LIVE") == 4.35 and r.spacing("BUS", "PSU") == 4.35
    for g in ("PSU", "BUS", "NEUTRAL"):                  # inside the converter
        assert r.spacing("SWNODE", g) == pb.SWNODE_MM, g
    for g in ("LINE", "LIVE", "LOAD"):                   # never reduced to the live or the load
        assert r.spacing("SWNODE", g) == 4.35, g


# --- metering ------------------------------------------------------------------------------------------

def test_both_current_channels_read_the_shunt_by_kelvin():
    for p, n in (("IP1", "IN1"), ("IP2", "IN2")):
        rp = next(r for r, _ in C.nets[net("U3", p)] if r != "U3" and C.instances[r].part.key == "R1K")
        rn = next(r for r, _ in C.nets[net("U3", n)] if r != "U3" and C.instances[r].part.key == "R1K")
        assert "SENSE" in nets_of(rp) and "KGND" in nets_of(rn)


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


def test_the_module_is_the_c6():
    assert C.instances["U1"].part.key == "ESP32C6"
    assert net("U1", "3V3") == "+3V3" and net("U1", "GND") == "GND" and net("U1", "EN") == "EN"


def test_gpios_are_unique_and_use_only_the_c6_modules_pins():
    nums = list(pb.GPIO.values())
    assert len(nums) == len(set(nums))
    assert set(nums) <= pb.C6_GPIOS
    for k, g in pb.GPIO.items():
        assert net("U1", pb.modpin(g)) == k, k


def test_c6_fixed_pins_and_straps():
    """USB is GPIO12/13 and UART0 16/17 (fixed); the button is the boot strap GPIO9 (low at reset:
    download mode); GPIO8 must read high at reset for download mode, so the LED's data line has a
    pull-up; GPIO15 (the JTAG strap) is left alone."""
    g = pb.GPIO
    assert (g["USB_DM"], g["USB_DP"], g["UART_TX"], g["UART_RX"]) == (12, 13, 16, 17)
    assert g["BUTTON"] == 9 and g["LED"] == 8 and 15 not in g.values()
    assert len([r for r in by_key("R10K") if nets_of(r) == {"LED", "+3V3"}]) == 1
    assert g["NTC"] in range(0, 7)                                   # ADC1


def test_j3_uses_the_c6_low_power_pins_for_i2c_and_the_wake_input():
    """LP_I2C is GPIO6/7 and the LP GPIOs are 0-7: sensors can be polled, and the PIR can wake the
    chip, with the main core asleep."""
    g = pb.GPIO
    assert (g["I2C_SDA"], g["I2C_SCL"]) == (6, 7)
    assert g["IO_IN"] in range(0, 8)
    assert {g[k] for k in ("SPI_SCLK", "SPI_MOSI", "SPI_MISO", "SPI_CS")} == {18, 19, 20, 21}


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
