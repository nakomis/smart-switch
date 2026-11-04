"""Petro's netlist: the isolation structure, the live path, the Kelvin shunt, the isolator's
channels, the divider, the GPIOs and the reuse I/O."""
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


def test_check_is_clean():
    assert check(C) == []


# --- isolation -----------------------------------------------------------------------------------

def test_every_mains_net_exists_and_every_other_net_is_selv():
    assert MAINS <= set(C.nets)
    # every net touching an island or mains-only part is a mains net
    mains_only = {"J1", "J2", "XF1", "XF2", "XF3", "RV1", "RS1", "U3", "FB1", "FB2"}
    for ref in mains_only:
        assert nets_of(ref) <= MAINS, (ref, nets_of(ref) - MAINS)


def test_only_the_barrier_parts_touch_both_mains_and_selv():
    both = {r for r in C.instances if nets_of(r) & MAINS and nets_of(r) - MAINS}
    assert both == set(pb.BARRIERS) == {"U4", "K1", "PS1"}


def test_relay_coil_is_selv_and_contacts_are_mains():
    assert {net("K1", "COIL1"), net("K1", "COIL2")} == {"+5V", "COIL"}
    assert (net("K1", "COM"), net("K1", "NO")) == ("L_SH", "L_OUT")


def test_selv_psu_input_is_mains_and_output_selv():
    assert (net("PS1", "AC/L"), net("PS1", "AC/N")) == ("L_PSU", "N")
    assert (net("PS1", "+V"), net("PS1", "-V")) == ("VPSU", "GND")


def test_isolator_sides():
    """ISOW7743: pads 1-10 are side 1 (the power input, SELV), 11-20 side 2 (the island)."""
    side1 = {C.net_of("U4", str(n)) for n in range(1, 11)}
    side2 = {C.net_of("U4", str(n)) for n in range(11, 21)}
    assert not side1 & MAINS and side2 <= MAINS
    assert net("U4", "VDD") == "+5V" and net("U4", "VSEL") == "GND_M"   # 5 V in, 3.3 V out


def test_island_is_powered_only_by_the_isolator():
    """No mains PSU feeds the island: 3V3_M comes from VISOOUT alone."""
    sources = {(r, p) for r, p in C.nets["3V3_M"] if C.instances[r].part.key not in ("C10U", "C1U", "C100N", "R10K", "BEAD")}
    assert sources == {("U4", "12"), ("U3", "1")}                   # VISOOUT and the BL0939's VDD
    assert "PSU1W" not in {i.part.key for i in C.instances.values()}


@pytest.mark.parametrize("island, selv, mains_to_selv", [
    ("BL_TX_M", "BL_TX", True), ("ZX_M", "ZX", True), ("OC_M", "OC", True), ("BL_RX_M", "BL_RX", False)])
def test_isolator_channel_directions(island, selv, mains_to_selv):
    """Three channels carry the BL0939's outputs to the ESP32; one carries its RX the other way."""
    pins = {net("U4", p): p for p in C.instances["U4"].part.pins if p.startswith(("IN", "OUT"))}
    if mains_to_selv:
        assert pins[island].startswith("IN") and pins[selv].startswith("OUT")
        assert pins[island][-1] == pins[selv][-1]                   # same channel letter
    else:
        assert pins[selv].startswith("IN") and pins[island].startswith("OUT")


# --- the live path -------------------------------------------------------------------------------

def test_live_path_order():
    """J1 -> F1 -> (MOV) -> shunt -> relay -> J2; the PSUs after F2, which is after F1."""
    assert net("J1", "2") == net("XF1", "1") == "L_IN"
    assert net("XF2", "1") == net("RS1", "I1") == net("XF3", "1") == "L_F"
    assert {net("RV1", "1"), net("RV1", "2")} == {"L_F", "N"}
    assert net("RS1", "I2") == net("K1", "COM") == "L_SH"
    assert net("K1", "NO") == net("J2", "1") == "L_OUT"
    assert net("XF3", "2") == net("PS1", "AC/L") == "L_PSU"
    assert net("J1", "1") == net("J2", "2") == "N"


def test_high_current_nets_are_the_load_path():
    assert pb.HIGH_CURRENT == {"L_IN", "L_F", "L_SH", "L_OUT", "N"}
    assert not pb.HIGH_CURRENT & set(pb.ISLAND)


def test_kelvin_shunt():
    """The island's ground is the shunt's sense pad on F1's side; the other sense pad feeds both
    current channels. No load current flows in either: only the shunt's current pads carry it."""
    assert net("RS1", "E1") == "GND_M" and net("RS1", "E2") == "SENSE"
    assert {r for r, _ in C.nets["SENSE"]} - {"RS1"} == {
        r for r in C.instances if C.instances[r].part.key == "R1K" and "SENSE" in nets_of(r)}
    assert len({r for r, _ in C.nets["SENSE"]}) == 3                # the shunt and two 1k
    assert net("U4", "GND2") == "GND_M" and net("U4", "VISOOUT") == "3V3_M"   # powered across the barrier


def test_both_current_channels_read_the_shunt():
    for p, n in (("IP1", "IN1"), ("IP2", "IN2")):
        rp = next(r for r, _ in C.nets[net("U3", p)] if r != "U3" and C.instances[r].part.key == "R1K")
        rn = next(r for r, _ in C.nets[net("U3", n)] if r != "U3" and C.instances[r].part.key == "R1K")
        assert "SENSE" in nets_of(rp) and "GND_M" in nets_of(rn)


def test_voltage_divider():
    """Five 390k in series from neutral to VP, 470R to the island's ground: 61 mV at 253 V."""
    chain = ["N", "DIV1", "DIV2", "DIV3", "DIV4", "VP"]
    rs = [r for r, i in C.instances.items() if i.part.key == "R390K"]
    assert len(rs) == 5
    pairs = sorted((tuple(sorted(nets_of(r), key=chain.index)) for r in rs), key=lambda p: chain.index(p[0]))
    assert pairs == list(zip(chain, chain[1:]))
    r470 = next(r for r, i in C.instances.items() if i.part.key == "R470")
    assert nets_of(r470) == {"VP", "GND_M"}
    vp = 253 * 470 / (5 * 390e3 + 470)
    assert vp < 0.070                                              # the BL0939's 70 mV rms maximum
    assert net("U3", "VP") == "VP"


def test_bl0939_uart_mode_and_pullup():
    assert net("U3", "SEL") == "GND_M"
    pull = [r for r, i in C.instances.items() if i.part.key == "R10K" and nets_of(r) == {"BL_TX_M", "3V3_M"}]
    assert len(pull) == 1


# --- SELV ----------------------------------------------------------------------------------------

def test_diode_or_feeds_5v_from_the_psu_or_usb():
    d = [r for r, i in C.instances.items() if i.part.key == "SS34"]
    assert sorted(net(r, "A") for r in d) == ["VBUS", "VPSU_F"] and {net(r, "K") for r in d} == {"+5V"}
    assert nets_of("F3") == {"VPSU", "VPSU_F"} and nets_of("F4") == {"VBUS_IN", "VBUS"}


def test_relay_driver():
    assert net("Q1", "D") == "COIL" and net("Q1", "S") == "GND" and net("Q1", "G") == "RELAY_G"
    assert (net("D3", "K"), net("D3", "A")) == ("+5V", "COIL")
    assert net("U1", pb.modpin(pb.GPIO["RELAY"])) == "RELAY"


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
    """J3 and J4 have the heatlink's pinouts and GPIOs (nakostat pcb/heatlink), with this
    board's 5 V rail in place of its VBUS."""
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
    pulls = [r for r, i in C.instances.items() if i.part.key == "R4K7"]
    assert sorted(tuple(sorted(nets_of(r))) for r in pulls) == [("+3V3", "IO_SCL"), ("+3V3", "IO_SDA")]


def test_rules_build_for_the_board():
    r = pb.rules()
    dru = r.dru()
    for g in ("LINE", "LIVE", "PSU", "NEUTRAL", "LOAD", "DIV1", "DIV4"):
        assert f'"{g} to SELV"' in dru
    for ref in pb.BARRIERS:
        assert f'"{ref} own pads, mains to SELV"' in dru


# --- test holes for push-in probe loops (SELV only) ----------------------------------------------

def test_test_holes_cover_the_signals_worth_scoping():
    holes = {C.net_of(r, "1") for r, i in C.instances.items() if i.part.key == "TESTHOLE"}
    assert holes == set(pb.TEST_HOLES.values())
    assert {"+5V", "+3V3", "COIL", "BL_TX", "BL_RX", "ZX", "OC", "LED_DIN", "BUTTON", "GND"} <= holes


def test_test_holes_are_never_on_mains_or_island_nets():
    for ref, n in pb.TEST_HOLES.items():
        assert n not in MAINS, ref
        assert C.instances[ref].part.key == "TESTHOLE"
        assert C.net_of(ref, "1") == n


def test_refs_number_from_one_without_gaps():
    """C1, C2, … and U1…U5, as a fab and a reader expect. F is the exception: F1 and F2 are the
    fuses themselves, in holders XF1/XF2 and XF3, so the PTCs are F3 and F4."""
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
