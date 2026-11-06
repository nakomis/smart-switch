"""port/bl0939: frames, the full packet's checksum and layout, and the scaling for Petro's shunt
and divider."""

import pytest

VREF = 1.218


@pytest.fixture
def bl(json_tool):
    run = json_tool("petro-bl0939")
    return lambda line: run(line)[0]


def le24(v: int) -> bytes:
    return (v & 0xFFFFFF).to_bytes(3, "little")


def packet(ia_fast=0, ia=0, ib=0, v=0, ib_fast=0, a_watt=0, b_watt=0, cfa=0, cfb=0, tps1=0, tps2=0,
           header=0x55, checksum=None) -> bytes:
    """A full packet as the chip sends it (ESPHome's DataPacket layout), checksum computed here."""
    body = bytes([header]) + b"".join(le24(x) for x in (ia_fast, ia, ib, v, ib_fast, a_watt, b_watt,
                                                         cfa, cfb))
    body += tps1.to_bytes(2, "little") + b"\x00" + tps2.to_bytes(2, "little") + b"\x00"
    assert len(body) == 34
    if checksum is None:
        checksum = ~(0x55 + sum(body)) & 0xFF
    return body + bytes([checksum])


# --- frames ---------------------------------------------------------------------------------------

def test_full_read_request(bl):
    assert bl("read") == {"frame": "55aa"}


# ESPHome's BL0939_INIT, as literal bytes: a check of our write-frame checksum against frames
# known to work on real chips.
ESPHOME_INIT = [
    "a5195a5a5a33",  # soft reset
    "a51a550000eb",  # user write protection off
    "a51800100032",  # mode
    "a51bff4700f9",  # TPS control
    "a5101c180016",  # IA fast RMS control
    "a51e1c180008",  # IB fast RMS control
]


@pytest.mark.parametrize("frame", ESPHOME_INIT)
def test_write_frame_matches_esphome(bl, frame):
    reg = int(frame[2:4], 16)
    value = int(frame[8:10] + frame[6:8] + frame[4:6], 16)
    assert bl(f"write {reg:x} {value:x}") == {"frame": frame}


def test_init_sequence_is_esphome_less_fast_rms(bl):
    assert bl("init") == {"frames": ESPHOME_INIT[:4]}


# --- the full packet ------------------------------------------------------------------------------

def test_zero_packet_parses(bl):
    r = bl(f"parse {packet().hex()}")
    assert r["status"] == "ok"
    assert r["raw"]["v_rms"] == 0
    assert r["petro"]["volts"] == 0


def test_bad_checksum(bl):
    good = packet(v=1234)
    bad = good[:-1] + bytes([good[-1] ^ 0x01])
    assert bl(f"parse {bad.hex()}") == {"status": "checksum"}


def test_corrupt_byte_fails_checksum(bl):
    good = bytearray(packet(v=3_000_000, ia=100_000))
    good[10] ^= 0x40
    assert bl(f"parse {bytes(good).hex()}") == {"status": "checksum"}


def test_bad_header(bl):
    assert bl(f"parse {packet(header=0x54).hex()}") == {"status": "header"}


@pytest.mark.parametrize("n", [0, 34, 36])
def test_bad_length(bl, n):
    data = (packet() + b"\x00")[:n]
    assert bl(f"parse {data.hex()}") == {"status": "length"}


def test_every_register_in_its_place(bl):
    p = packet(ia_fast=0x010203, ia=0x040506, ib=0x070809, v=0x0A0B0C, ib_fast=0x0D0E0F,
               a_watt=0x101112, b_watt=0x131415, cfa=0x161718, cfb=0x191A1B, tps1=0x1C1D, tps2=0x1E1F)
    raw = bl(f"parse {p.hex()}")["raw"]
    assert raw == {"ia_fast_rms": 0x010203, "ia_rms": 0x040506, "ib_rms": 0x070809,
                   "v_rms": 0x0A0B0C, "ib_fast_rms": 0x0D0E0F, "a_watt": 0x101112,
                   "b_watt": 0x131415, "cfa_cnt": 0x161718, "cfb_cnt": 0x191A1B,
                   "tps1": 0x1C1D, "tps2": 0x1E1F}


def test_negative_power_is_sign_extended(bl):
    raw = bl(f"parse {packet(a_watt=-1000, b_watt=-1).hex()}")["raw"]
    assert raw["a_watt"] == -1000
    assert raw["b_watt"] == -1


# --- scaling --------------------------------------------------------------------------------------

def test_esphome_reference_circuit(bl):
    """ESPHome's direct-mode constants come back for its circuit (1 mOhm, 5 x 390k over 510R)."""
    s = bl("scale 0.001 1950000 510")
    assert s["amps"] == pytest.approx(324004 * 1 / 1.218)
    assert s["volts"] == pytest.approx(79931 * 0.51 * 1000 / (1.218 * (5 * 390 + 0.51)))
    assert s["watts"] == pytest.approx(4046 * 1 * 0.51 * 1000 / (1.218 * 1.218 * (5 * 390 + 0.51)))
    assert s["pulses_per_kwh"] == pytest.approx(
        3.6e6 * 4046 * 1 * 0.51 * 1000 / (1638.4 * 256 * 1.218 * 1.218 * (5 * 390 + 0.51)))


def test_petro_scale(bl):
    """Petro: 1 mOhm, 1.95 MOhm over 470R (about 4150:1)."""
    ratio = 470 / (1_950_000 + 470)
    s = bl("petro")
    assert 1 / ratio == pytest.approx(4150, rel=1e-3)
    assert s["volts"] == pytest.approx(79931 * 1000 * ratio / VREF)
    assert s["amps"] == pytest.approx(324004 * 1.0 / VREF)
    assert s["watts"] == pytest.approx(4046 * 1.0 * 1000 * ratio / VREF ** 2)
    assert s["volts"] == pytest.approx(15813.6, rel=1e-4)
    assert s["amps"] == pytest.approx(266013.1, rel=1e-6)


def test_petro_reading_230v_10a(bl):
    """A synthetic packet for 230 V, 10 A, 2300 W decodes to those values on Petro's scale."""
    s = bl("petro")
    v, a, w = 230.0, 10.0, 2300.0
    p = packet(v=round(v * s["volts"]), ia=round(a * s["amps"]), ib=round(a * s["amps"]),
               a_watt=round(w * s["watts"]), cfa=round(1.5 * s["pulses_per_kwh"]))
    r = bl(f"parse {p.hex()}")
    assert r["status"] == "ok"
    assert r["petro"]["volts"] == pytest.approx(v, abs=1e-3)
    assert r["petro"]["amps_a"] == pytest.approx(a, abs=1e-4)
    assert r["petro"]["amps_b"] == pytest.approx(a, abs=1e-4)
    assert r["petro"]["watts_a"] == pytest.approx(w, abs=0.01)
    assert r["petro"]["kwh_a"] == pytest.approx(1.5, abs=1e-3)


def test_253v_fits_the_register(bl):
    """The mains' top (253 V) is about 61 mV at VP, inside the BL0939's 70 mV and its 24 bits."""
    s = bl("petro")
    assert 253 * 470 / (1_950_000 + 470) * 1000 == pytest.approx(61, abs=0.5)
    assert 253 * s["volts"] < 2 ** 24


# --- temperature ----------------------------------------------------------------------------------

@pytest.mark.parametrize("tps1,celsius", [
    (0, (170 / 448) * (0 / 2 - 32) - 45),
    (300, (170 / 448) * (300 / 2 - 32) - 45),
    (0xFC00 | 300, (170 / 448) * (300 / 2 - 32) - 45),  # only the low 10 bits count
])
def test_temperature(bl, tps1, celsius):
    assert bl(f"temp {tps1}")["celsius"] == pytest.approx(celsius, abs=1e-5)


def test_room_temperature_code(bl):
    """About 22 C at TB = 417: the range Gate 2 expects."""
    assert 15 < bl("temp 417")["celsius"] < 30
    r = bl(f"parse {packet(tps1=417).hex()}")
    assert r["petro"]["celsius"] == pytest.approx(bl("temp 417")["celsius"])


# --- PETRO-5: the fast-RMS thresholds and register reads -------------------------------------------

def test_init_with_the_fast_rms_threshold_writes_both_channels(bl):
    frames = bl("init 3ce3")["frames"]
    assert frames[:4] == ESPHOME_INIT[:4]
    assert frames[4:] == [bl("write 10 3ce3")["frame"], bl("write 1e 3ce3")["frame"]]
    assert frames[4].startswith("a510e33c00") and frames[5].startswith("a51ee33c00")


def test_init_with_esphome_s_threshold_matches_esphome(bl):
    assert bl("init 181c")["frames"] == ESPHOME_INIT


def test_the_read_back_covers_every_register_the_trips_need(bl):
    checks = {reg: (value, mask) for reg, value, mask in bl("verify 3ce3")["checks"]}
    assert checks == {
        0x1A: (0x55, 0xFF),        # USR_WRPROT: writes unlocked
        0x18: (0x001000, 0xFFFF),  # MODE
        0x1B: (0x0047FF, 0xFFFF),  # TPS_CTRL: the alarms on
        0x10: (0x3CE3, 0xFFFF),    # IA fast RMS
        0x1E: (0x3CE3, 0xFFFF),    # IB fast RMS
    }
    # and what it checks is what init writes
    writes = {f[2:4]: f[4:10] for f in bl("init 3ce3")["frames"][1:]}
    for reg, (value, _) in checks.items():
        assert writes[f"{reg:02x}"] == le24(value).hex()


def test_register_read_request(bl):
    assert bl("readreg 1e") == {"frame": "551e"}


def reply(reg: int, value: int, checksum=None) -> str:
    data = le24(value)
    if checksum is None:
        checksum = ~(0x55 + reg + sum(data)) & 0xFF
    return (data + bytes([checksum])).hex()


@pytest.mark.parametrize("reg,value", [(0x1E, 0x3CE3), (0x18, 0x001000), (0x10, 0xFFFFFF), (0x00, 0)])
def test_register_reply(bl, reg, value):
    assert bl(f"parsereg {reg:x} {reply(reg, value)}") == {"status": "ok", "value": value}


def test_register_reply_bad_checksum(bl):
    good = reply(0x1E, 0x3CE3)
    bad = good[:-2] + f"{(int(good[-2:], 16) ^ 1):02x}"
    assert bl(f"parsereg 1e {bad}") == {"status": "checksum"}
    # the register is part of the checksum: a reply for another register fails
    assert bl(f"parsereg 10 {good}") == {"status": "checksum"}


def test_register_reply_wrong_length(bl):
    assert bl("parsereg 1e e33c") == {"status": "length"}
