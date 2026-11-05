"""Petro: the netlist, revision B (non-isolated; PETRO-2).

Martin's own device: no isolation. All the electronics are at mains potential, tied to neutral,
and nothing conductive leaves the case (docs/DESIGN.md, the safety rules). Revision A, with a
reinforced barrier, is branch 5v-240v-separation / tag 5v-240v-separation-v1.

Mains side:
  Live: J1 (line in) -> F1 (15 A HBC, in two clips XF1/XF2) -> the relay's COM; its NO -> J2.
  The MOV across live and neutral after F1. F2 (T500 mA, holder XF3) feeds the supply.
  Neutral: J1 -> the 1 mOhm Kelvin shunt RS1 -> J2. All the low-voltage circuitry's ground (GND)
  is the shunt's sense pad on the supply side: the one place GND meets neutral (a star point), so
  no load current flows in GND.

Supply (all at mains potential): PI's LNK306 high-side buck (datasheet Figure 5; the neutral-leg
  diode left out so its return is neutral): fusible resistor, half-wave rectifier, pi filter,
  12 V out. TI's TPS563201 makes 5 V from it for the existing +5V rail (diode-OR with USB), and
  the AP2112K 3.3 V from that.

Metering: the BL0939 on GND, reading the shunt (channel A metering, channel B the fast
  over-current I_leak) and the voltage through 5 x 390k from L_IN; its UART, zero cross and
  over-current wired straight to the ESP32.

Low-voltage side, as on the nakostat heatlink (STAT-75): the ESP32-C6-WROOM-1 module (Economic
  assembly: the S3-MINI needed X-ray), the house USB connector (reachable only with the case off),
  the relay driver, the button on the boot strap, the LED, the debug pads.

The safe I/O island (5 Nov 2026): J3, a 10-way terminal that may be touched, is SELV: powered and
  signalled across three reinforced isolators from the neutral-referenced side. The ISOW7743
  makes its 3.3 V (and carries IN and OUT), the ISO7741 its SPI, the ISO1640 its I2C. The island
  keeps 8 mm from everything else, with a slot under each isolator.
"""
from board.netlist import Circuit
from board.rules import HIGH_CURRENT_WIDTH, Rules

# --- GPIO ----------------------------------------------------------------------------------------
# The ESP32-C6-WROOM-1 (module datasheet v1.4): 23 GPIOs on its pins, GPIO0-13, 15-23 (16/17 are
# UART0, the debug pads). Fixed: USB D-/D+ on 12/13. Straps: GPIO9 (boot: low at reset is download
# mode) is the button, as GPIO0 was on the S3; GPIO8 must read high at reset for download mode, so
# it is the LED data with a pull-up (the LED ignores a steady high); GPIO15 (JTAG source) is a
# spare. MTMS/MTDI (4/5) set only the SDIO slave's clock edges, which nothing uses (the relay is on
# MTMS, its gate pulled down: off, and low, at reset).
# The island: I2C on LP_I2C (6/7) and its input on an LP GPIO (3), so the low-power core can poll
# sensors and the PIR can wake the chip with the main core asleep; SPI on 18-21. IN (3), OUT (23)
# and SPI are on the module's left-hand column, the island's side; LP_I2C has no other pins.
GPIO = {"BUTTON": 9, "LED": 8, "USB_DM": 12, "USB_DP": 13, "UART_TX": 16, "UART_RX": 17,
        "NTC": 0,           # board temperature, ADC1_CH0
        "ZX": 1,            # BL0939 zero cross
        "OC": 2,            # BL0939 I_leak (channel B fast over-current)
        "RELAY": 4,
        "BL_TX": 10,        # BL0939 TX -> ESP RX (UART1)
        "BL_RX": 11,        # ESP TX (UART1) -> BL0939 RX
        "SAFE_IN": 3, "SAFE_OUT": 23, "I2C_SDA": 6, "I2C_SCL": 7,
        "SPI_SCLK": 18, "SPI_MOSI": 19, "SPI_MISO": 20, "SPI_CS": 21,
        "ISO_FLT": 22}      # the ISOW7743's EN/FLT: low if the island's converter has failed
C6_GPIOS = set(range(0, 14)) | set(range(15, 24))
STRAPPING = {4, 5, 8, 9, 15}
_MODPIN = {16: "TXD0", 17: "RXD0"}


def modpin(gpio):
    return _MODPIN.get(gpio, f"IO{gpio}")


# --- connectors ----------------------------------------------------------------------------------
# J1 / J2: line in and load out (Degson DG636, 7.62 mm). Earth does not touch the board. Both
# turned so their wire openings face their end of the board (J1 left, J2 right), neutral on top.
J1_PINS = {"1": "N_IN", "2": "L_IN"}           # rotated 270: pad 1 on top
J2_PINS = {"1": "L_OUT", "2": "N_OUT"}         # rotated 90: pad 2 on top
# J4: the house USB connector (tinycrypt's J1, as on the heatlink): 1 VBUS, 2 D-, 3 D+, 4 CC,
# 5 GND; pads 6/7 are the shell tabs. Inside the case: reachable only with the case off.
USB_PINS = {"1": "VBUS_IN", "2": "USB_DM", "3": "USB_DP", "4": "CC", "5": "GND"}
DEBUG_PINS = {"1": "EN", "2": "UART_RX", "3": "UART_TX", "4": "GND", "5": "+3V3"}
# J3: the safe I/O terminal (10-way, 3.5 mm), all SELV: the island's 3.3 V and ground, SPI, I2C,
# one input (a PIR, an interrupt) and one output. J4 (the heatlink's IDC header) is gone: the C6
# has no pins left for it.
IO_PINS = {"1": "ISO_3V3", "2": "ISO_GND", "3": "ISO_SCLK", "4": "ISO_MOSI", "5": "ISO_MISO",
           "6": "ISO_CS", "7": "ISO_SDA", "8": "ISO_SCL", "9": "ISO_IN", "10": "ISO_OUT"}
# Every net of the island (J3's, and the ISOW7743's filtered supply behind its beads).
SELV_NETS = tuple(IO_PINS.values()) + ("ISO_VIN", "ISO_GIN")

# --- the mains rules (non-isolated mode: every other net sits at neutral) --------------------------
# The supply's high-voltage nets are the PSU group: after F2, at the rectified live (the switching
# node and the LNK306's BP/FB, which ride on it, included).
PSU_NETS = ("L_PSU", "L_RF", "VBULK1", "VBULK")
# The LNK306's switching node and what rides on it (BYPASS, FEEDBACK, the sampled output): functional
# insulation inside the converter, where a short only trips its current limit: 1.0 mm (rules.reduced).
SWNODE_NETS = ("SW", "BP", "FB", "FBH")
GROUPS = {"L_IN": "LINE", "L_F": "LIVE", "N_IN": "NEUTRAL", "N_OUT": "NEUTRAL", "L_OUT": "LOAD",
          "DIV1": "DIV1", "DIV2": "DIV2", "DIV3": "DIV3", "DIV4": "DIV4",
          **{n: "PSU" for n in PSU_NETS}, **{n: "SWNODE" for n in SWNODE_NETS},
          **{n: "SELV" for n in SELV_NETS}}
HIGH_CURRENT = {"L_IN", "L_F", "L_OUT", "N_IN", "N_OUT"}
BARRIERS = ("U7", "U8", "U9")                # the island's isolators: a slot under each
BL_NC = ("VT", "CF", "SCLK", "VPP")          # the BL0939's unused pins, each on an NC_ net


def rules():
    return Rules(GROUPS, high_current=HIGH_CURRENT, barriers=BARRIERS, rest="NEUTRAL", divider_top="LINE",
                 reduced={"SWNODE": 1.0}, own_leads=OWN_LEADS)


# The bulk capacitors are 400 V parts at their maker's 3.5 mm pitch: 1.9 mm between their own
# pads, which their rating covers (IPC-2221 B4 asks 0.8 mm for 325 V, coated). Nothing else on
# VBULK1/VBULK comes nearer GND than the 2.5 mm the matrix asks.
OWN_LEADS = {"C1": (1.0, ("VBULK1", "GND")), "C2": (1.0, ("VBULK", "GND"))}


def build_petro():
    c = Circuit()
    gnd, v33, v5, v12 = "GND", "+3V3", "+5V", "+12V"

    def part(key, ref):
        return c.add(key, ref)

    def two(key, ref, net1, net2):
        p = c.add(key, ref)
        c.connect(net1, (p, "1"))
        c.connect(net2, (p, "2"))
        return p

    def pins(key, ref=None, **nets):
        p = c.add(key, ref)
        for pin, n in nets.items():
            c.connect(n, (p, pin.replace("_plus", "+").replace("_minus", "-")))
        return p

    # ---- mains: live and neutral ---------------------------------------------------------------
    j1, j2 = part("MAINSTERM", "J1"), part("MAINSTERM", "J2")
    for pad, n in J1_PINS.items():
        c.connect(n, (j1, pad))
    for pad, n in J2_PINS.items():
        c.connect(n, (j2, pad))
    c.connect("L_IN", (part("FUSECLIP", "XF1"), "1"))           # F1's two clips
    c.connect("L_F", (part("FUSECLIP", "XF2"), "1"))
    two("MOV", "RV1", "L_F", "N_OUT")       # after F1 (F1 clears a MOV short); on N_OUT: a surge crosses
                                            # the 1 mR shunt (~0.02 J, within its pulse rating)
    k1 = part("RELAY16", "K1")
    c.connect("L_F", (k1, "COM"))
    c.connect("L_OUT", (k1, "NO"))
    rs = part("SHUNT", "RS1")                                   # in the neutral, Kelvin
    c.connect("N_IN", (rs, "I1"))
    c.connect("N_OUT", (rs, "I2"))
    c.connect(gnd, (rs, "E1"))                                  # the star point: GND meets N here
    c.connect("SENSE", (rs, "E2"))

    # ---- the supply: F2, then PI's LNK306 high-side buck (12 V) ----------------------------------
    two("FUSEHOLD", "XF3", "L_F", "L_PSU")                      # F2, T500 mA
    two("RFUSE", None, "L_PSU", "L_RF")                         # fusible, flameproof: inrush and fault
    pins("RECT", "D7", A="L_RF", K="VBULK1")                          # half-wave, in the live leg
    pins("C4U7HV", _plus="VBULK1", _minus=gnd)                  # pi filter: C4, L2, C5
    two("L1MF", None, "VBULK1", "VBULK")
    pins("C4U7HV", _plus="VBULK", _minus=gnd)
    u4 = part("LNK306", "U4")
    c.connect("VBULK", (u4, "D"))
    c.connect("SW", (u4, "S"))
    c.connect("BP", (u4, "BP"))
    c.connect("FB", (u4, "FB"))
    two("C100N6", None, "BP", "SW")                             # BYPASS capacitor, to SOURCE
    two("L680U", None, "SW", v12)                               # output inductor, 680 uH (>= 0.5 mH, PI MDCM)
    pins("ES1J", "D8", A=gnd, K="SW")                                 # freewheel (35 ns)
    pins("C220U", _plus=v12, _minus=gnd)
    pins("S1G", "D9", A=v12, K="FBH")                                 # feedback: samples the output...
    two("C10U50", None, "FBH", "SW")                            # ...onto C3, across SOURCE
    two("R13K", None, "FBH", "FB")                              # 1.65 V at FB: 12.4 V out
    two("R2K", None, "FB", "SW")
    two("R3K3", None, v12, gnd)                                 # pre-load (3.6 mA)

    # ---- 12 V -> 5 V: TI TPS563201 (datasheet 8.2, 5 V row) ------------------------------------
    u5 = part("BUCK", "U5")
    c.connect(v12, (u5, "VIN"), (u5, "EN"))
    c.connect(gnd, (u5, "GND"))
    c.connect("SW5", (u5, "SW"))
    c.connect("BST5", (u5, "VBST"))
    c.connect("FB5", (u5, "VFB"))
    two("C10U50", None, v12, gnd)                               # input
    two("C100N6", None, v12, gnd)
    two("C100N6", None, "BST5", "SW5")                          # bootstrap
    two("L3U3", None, "SW5", "VPSU")
    two("R54K9", None, "VPSU", "FB5")                           # 0.768 V x (1 + 54.9/10) = 4.98 V
    two("R10K6", None, "FB5", gnd)
    two("C22U", None, "VPSU", gnd)
    two("C22U", None, "VPSU", gnd)

    # ---- 5 V: the supply or USB, through a diode-OR ----------------------------------------------
    two("PTC5", "F3", "VPSU", "VPSU_F")                          # 1.1 A hold
    two("TVS5", "D4", "VPSU_F", gnd)                             # pad 1 = cathode
    d5 = part("SS34", "D5")
    c.connect("VPSU_F", (d5, "A"))
    c.connect(v5, (d5, "K"))
    two("C10U", None, "VPSU_F", gnd)
    j5 = part("JST5", "J4")
    for pad, n in USB_PINS.items():
        c.connect(n, (j5, pad))
    c.connect(gnd, (j5, "6"), (j5, "7"))
    two("PTC", "F4", "VBUS_IN", "VBUS")                          # 500 mA hold
    two("TVS", "D2", "VBUS", gnd)                                # pad 1 = cathode
    d6 = part("SS34", "D6")
    c.connect("VBUS", (d6, "A"))
    c.connect(v5, (d6, "K"))
    two("R5K1", None, "CC", gnd)                                 # Rd: chargers switch 5 V on
    u6 = part("ESD", "U6")
    c.connect("USB_DM", (u6, "1"), (u6, "6"))
    c.connect("USB_DP", (u6, "3"), (u6, "4"))
    c.connect("VBUS", (u6, "5"))
    c.connect(gnd, (u6, "2"))

    # ---- metering: the BL0939 on GND --------------------------------------------------------------
    u3 = part("BL0939", "U3")
    c.connect(v33, (u3, "VDD"))
    c.connect(gnd, (u3, "GND"), (u3, "SEL"))                     # SEL low: UART
    two("C100N", None, v33, gnd)
    # Current inputs: both channels read the shunt's sense pads through 1k / 33 nF (Belling's
    # application circuit). Channel A meters; channel B drives I_leak, the fast over-current.
    for ch, (pn, nn) in (("A", ("IAP", "IAN")), ("B", ("IBP", "IBN"))):
        k = "1" if ch == "A" else "2"
        rp, rn = c.add("R1K"), c.add("R1K")
        c.connect("SENSE", (rp, "1"))
        c.connect(pn, (rp, "2"), (u3, f"IP{k}"))
        c.connect(gnd, (rn, "1"))
        c.connect(nn, (rn, "2"), (u3, f"IN{k}"))
        two("C33N", None, pn, gnd)
        two("C33N", None, nn, gnd)
    # Voltage: L_IN (before F1: rev A hung it from the unfused neutral; the BL0939 still sees the
    # mains with F1 blown) -> 5 x 390k (1206, 50 V each) -> VP -> 470R to ground, so 61 mV rms
    # at 253 V (the BL0939's maximum is 70 mV rms), with 33 nF across. DIV1 is next to VP.
    chain = ["L_IN", "DIV4", "DIV3", "DIV2", "DIV1", "VP"]
    for a, b in zip(chain, chain[1:]):
        two("R390K", None, a, b)
    two("R470", None, "VP", gnd)
    two("C33N", None, "VP", gnd)
    c.connect("VP", (u3, "VP"))
    c.connect("BL_TX", (u3, "TX/SDO"))
    c.connect("BL_RX", (u3, "RX/SDI"))
    c.connect("ZX", (u3, "ZX"))
    c.connect("OC", (u3, "I_leak"))
    two("R10K", None, "BL_TX", v33)                             # TX needs a pull-up (datasheet)
    for pin in BL_NC:                                            # SCLK and VPP must float
        c.connect(f"NC_U3_{pin}", (u3, pin))

    # ---- 3.3 V and the module (as the heatlink) --------------------------------------------------
    u2 = part("LDO", "U2")
    c.connect(v5, (u2, "VIN"), (u2, "EN"))
    c.connect(gnd, (u2, "GND"))
    c.connect(v33, (u2, "VOUT"))
    c.no_connect(u2, "NC")
    two("C10U", None, v5, gnd)
    two("C10U", None, v33, gnd)
    two("C100N", None, v33, gnd)
    u1 = part("ESP32C6", "U1")
    c.connect(v33, (u1, "3V3"))
    c.connect(gnd, (u1, "GND"))
    two("C10U", None, v33, gnd)
    two("C100N", None, v33, gnd)
    c.connect("EN", (u1, "EN"))
    two("R10K", None, "EN", v33)
    two("C1U", None, "EN", gnd)
    for k in ("USB_DM", "USB_DP", "BL_TX", "BL_RX", "ZX", "OC", "UART_TX", "UART_RX"):
        c.connect(k, (u1, modpin(GPIO[k])))

    # Button (on -> off -> auto) on GPIO9 (the boot strap), 10k pull-up; the switch's terminals A
    # and B.
    sw = part("TACT", "SW1")
    c.connect("BUTTON", (u1, modpin(GPIO["BUTTON"])), (sw, "A"))
    c.connect(gnd, (sw, "B"))
    two("R10K", None, "BUTTON", v33)

    # Relay: 5 V coil (62 R, 80 mA) from +5V, low side switched by the AO3400A, 1N4148W flyback,
    # 100R gate and 100k pull-down (off in reset and boot).
    q1, d3 = part("FET", "Q1"), part("DIODE", "D3")
    c.connect(v5, (k1, "COIL1"), (d3, "K"))
    c.connect("COIL", (k1, "COIL2"), (d3, "A"), (q1, "D"))
    c.connect(gnd, (q1, "S"))
    c.connect("RELAY_G", (q1, "G"))
    two("R100", None, "RELAY_G", "RELAY")
    two("R100K", None, "RELAY_G", gnd)
    c.connect("RELAY", (u1, modpin(GPIO["RELAY"])))

    # LED: SK6812-EC20 on 3V3 with 100 nF, data through 330R.
    d1 = part("LED", "D1")
    c.connect(v33, (d1, "VDD"))
    c.connect(gnd, (d1, "GND"))
    c.connect("LED_DIN", (d1, "DI"))
    c.no_connect(d1, "DO")
    two("R330", None, "LED_DIN", "LED")
    c.connect("LED", (u1, modpin(GPIO["LED"])))
    two("R10K", None, "LED", v33)                               # GPIO8 strap: high at reset
    two("C100N", None, v33, gnd)

    # NTC: 10k NTC to GND under 10k to 3V3 on GPIO0 (about 1.65 V at 25 C), 100 nF across.
    c.connect("NTC", (u1, modpin(GPIO["NTC"])))
    two("NTC", "TH1", "NTC", gnd)
    two("R10K", None, "NTC", v33)
    two("C100N", None, "NTC", gnd)

    # Debug pads.
    tp = part("DEBUG", "TP1")
    for pad, n in DEBUG_PINS.items():
        c.connect(n, (tp, pad))

    # ---- the safe I/O island: J3, across three reinforced isolators ------------------------------
    # Side 1 of each isolator is this board (GND, at neutral); side 2 the island (ISO_GND).
    # ISOW7743 (TI SLLSFK1C), as rev A's metering island: power flows side 1 -> side 2. VDD 5 V ->
    # VISOOUT 3.3 V (VSEL low), up to 140 mA, the island's supply; TI's application circuit: beads
    # VISOOUT -> VISOIN and GND2 -> GISOIN, 10u + 1u + 100n on VDD and VISOOUT, 100n on VIO and
    # VISOIN. Channel A forward carries OUT, B back carries IN; C and D (back) are unused, their
    # inputs held at ISO_GND. EN/FLT pulled up (converter on) and read as a fault.
    u7 = part("ISOW", "U7")
    c.connect(v5, (u7, "VDD"))
    c.connect(v33, (u7, "VIO"), (u7, "EN_IO1"))
    c.connect(gnd, (u7, "GND1"), (u7, "GNDIO"))
    c.connect("ISO_FLT", (u7, "EN/FLT"))
    two("R10K", None, "ISO_FLT", v33)
    c.connect("ISO_FLT", (u1, modpin(GPIO["ISO_FLT"])))
    for key in ("C10U", "C1U", "C100N"):
        two(key, None, v5, gnd)
    two("C100N", None, v33, gnd)
    c.connect("ISO_3V3", (u7, "VISOOUT"))
    c.connect("ISO_GND", (u7, "GND2"), (u7, "VSEL"), (u7, "INC"), (u7, "IND"))
    two("BEAD", None, "ISO_3V3", "ISO_VIN")
    two("BEAD", None, "ISO_GND", "ISO_GIN")
    c.connect("ISO_VIN", (u7, "VISOIN"), (u7, "EN_IO2"))
    c.connect("ISO_GIN", (u7, "GISOIN"))
    for key in ("C10U", "C1U", "C100N"):
        two(key, None, "ISO_3V3", "ISO_GND")
    two("C100N", None, "ISO_VIN", "ISO_GIN")
    c.connect("SAFE_OUT", (u7, "INA"), (u1, modpin(GPIO["SAFE_OUT"])))
    c.connect("ISO_OUT", (u7, "OUTA"))
    c.connect("ISO_IN", (u7, "INB"))
    c.connect("SAFE_IN", (u7, "OUTB"), (u1, modpin(GPIO["SAFE_IN"])))
    c.connect("NC_U7_OUTC", (u7, "OUTC"))
    c.connect("NC_U7_OUTD", (u7, "OUTD"))
    two("R100K", None, "ISO_IN", "ISO_GND")                     # nothing plugged in: IN reads low

    # ISO7741 (SPI): A-C forward (SCLK, MOSI, CS), D back (MISO); both enables on.
    u8 = part("ISO7741", "U8")
    c.connect(v33, (u8, "VCC1"), (u8, "EN1"))
    c.connect(gnd, (u8, "GND1"))
    c.connect("ISO_3V3", (u8, "VCC2"), (u8, "EN2"))
    c.connect("ISO_GND", (u8, "GND2"))
    for ch, sig in (("A", "SCLK"), ("B", "MOSI"), ("C", "CS")):
        c.connect(f"SPI_{sig}", (u8, f"IN{ch}"), (u1, modpin(GPIO[f"SPI_{sig}"])))
        c.connect(f"ISO_{sig}", (u8, f"OUT{ch}"))
    c.connect("ISO_MISO", (u8, "IND"))
    c.connect("SPI_MISO", (u8, "OUTD"), (u1, modpin(GPIO["SPI_MISO"])))
    two("C100N", None, v33, gnd)
    two("C100N", None, "ISO_3V3", "ISO_GND")

    # ISO1640 (I2C, bidirectional): 4k7 pull-ups on both sides (TI's application circuit).
    u9 = part("ISO1640", "U9")
    c.connect(v33, (u9, "VCC1"))
    c.connect(gnd, (u9, "GND1"))
    c.connect("ISO_3V3", (u9, "VCC2"))
    c.connect("ISO_GND", (u9, "GND2"))
    for sig in ("SDA", "SCL"):
        c.connect(f"I2C_{sig}", (u9, f"{sig}1"), (u1, modpin(GPIO[f"I2C_{sig}"])))
        c.connect(f"ISO_{sig}", (u9, f"{sig}2"))
        two("R4K7", None, f"I2C_{sig}", v33)
        two("R4K7", None, f"ISO_{sig}", "ISO_3V3")
    # Its NC pins have no internal connection (TI: may be tied to ground). Each goes to its own
    # side's ground, so no unconnected copper sits on the barrier.
    for pad in ("2", "4", "8"):
        c.connect(gnd, (u9, "NC", pad))
    for pad in ("10", "13", "15"):
        c.connect("ISO_GND", (u9, "NC", pad))
    two("C100N", None, v33, gnd)
    two("C100N", None, "ISO_3V3", "ISO_GND")

    j3 = part("IO10", "J3")
    for pad, n in IO_PINS.items():
        c.connect(n, (j3, pad))

    # Mounting holes near the corners, all unplated: GND is at neutral, so a plated hole would put
    # the screw at mains potential. All copper keeps 3 mm from them (rules: copper to mounting holes).
    for ref in ("H1", "H2", "H3", "H4"):
        part("MHN", ref)

    # Test holes for push-in probe loops: bench use only (a 5 V supply with mains disconnected, or
    # a differential probe).
    for ref, n in TEST_HOLES.items():
        c.connect(n, (part("TESTHOLE", ref), "1"))
    return c


# Test holes: the BL0939's four signals in a row; the supplies and the relay drive,
# each beside a GND hole one pitch (2.54 mm) away, with the LED data and button bottom right.
TEST_HOLES = {"TP2": "BL_RX", "TP3": "BL_TX", "TP4": "ZX", "TP5": "OC", "TP6": "GND",
              "TP7": "+5V", "TP8": "GND", "TP9": "+3V3",
              "TP10": "COIL", "TP11": "GND", "TP12": "LED_DIN", "TP13": "BUTTON"}


# --- placement (rev B) ---------------------------------------------------------------------------
# Board 120 x 85 mm (15 mm taller than rev A, for the mains supply), in Martin's own printed case
# (PETRO-6). Mains along the top, low voltage along the bottom; cables enter at opposite ends.
#   The neutral strip along the top edge, split by the shunt RS1 above the metering corner: N_IN
#   to the west (J1), N_OUT to the east (the MOV, J2). The strip deepens to y = 10 round the shunt,
#   whose sense pads have vias in pad, so the 3.5 mm per-layer minimum holds past them.
#   The live chain J1 -> F1 -> K1 -> J2 across the middle (L_IN, L_F, L_OUT pours), with the MOV
#   above L_F's right-hand arm and F2's holder hanging below L_F's stub over the supply block.
#   The metering corner (the BL0939, its filters, the divider from L_IN) sits under the shunt,
#   between L_IN and L_F; its only copper link to the rest of the low-voltage side is the corridor
#   under F1's glass, between the clips (no mains copper there).
#   The supply (PI's LNK306 buck) in a block on the right, its high-voltage nets hand-routed.
#   Low voltage below: the ESP32 module (antenna overhanging the bottom edge), J3/J4 (internal
#   only), the button and LED (through the lid), USB (J4, facing the right-hand edge, reachable
#   only with the case off), the relay driver, the 5 V converter, the test holes.
import math  # noqa: E402

from board.kicad_pcb import S, Slot, Track, Via, Zone, solid_pads  # noqa: E402,F401
from board.placement import Placement, rotate  # noqa: E402
from board.rules import ipc2221_width  # noqa: E402

W, H = 120.0, 85.0
COPPER_OZ = 1
MAINS_Y, SELV_Y = 38.5, 41.0            # the live chain's lower edge; the low-voltage side's top
HOLES = {"H1": (4.0, 4.0), "H2": (116.0, 4.0), "H3": (4.0, H - 4.0), "H4": (116.0, H - 4.0)}
F1_CLIP_PITCH = 34.21 - 7.62            # clip centres for a 1 1/4 in fuse (Littelfuse "A")
F1_Y = 32.0
LED_RING = 2.0                          # mm of clear board round the LED (the light pipe's flange)
DY = 15.0                               # the low-voltage side's move down from rev A
TP_X, TP_PITCH, TP_ROWS = 27.5, 3.2, (42.0, 47.0, 52.0)    # the test holes' block
# The safe I/O island's barrier: the isolators' centre line, their x, and the module's edge. Their
# pad rows are 7.1 mm apart inside; a slot along the line takes creepage round its ends, and the
# isolators are 3.7 mm or more apart so the air gap between neighbours' opposite sides is 8 mm.
ISO_Y = 66.0
ISO_X = (9.5, 24.0, 37.2)
ISL_X = (2.5, 43.5)     # the island's left and right edges
U1_EDGE = 9.25          # the module's centre above the bottom edge: its antenna starts at the edge
TP_LABEL_DY = -1.9                      # each test hole's label, above it

AT = {
    # mains: terminals, the live chain, F2 (hanging below L_F's stub), the MOV, the shunt
    "J1": (8.0, 19.5, 270), "J2": (112.0, 19.5, 90),
    "XF1": (20.0, F1_Y, 0), "XF2": (20.0 + F1_CLIP_PITCH, F1_Y, 0),
    "K1": (69.0, 46.5, 90), "RV1": (74.0, 12.0, 180), "RS1": (31.0, 6.5, 0),
    "XF3": (90.0, 45.6, 0),
    # the metering corner: the divider column from L_IN, the BL0939 and its filters
    "R12": (18.0, 25.0, 90), "R13": (18.0, 20.15, 90), "R14": (18.0, 15.3, 90), "R15": (20.6, 11.6, 0),
    "R16": (24.2, 14.0, 270),
    "U3": (31.0, 20.5, 180),
    "R8": (29.05, 12.1, 90), "R9": (30.85, 12.1, 90), "R10": (32.65, 12.1, 90), "R11": (34.45, 12.1, 90),
    "C13": (29.05, 14.7, 90), "C14": (30.85, 14.7, 90), "C15": (32.65, 14.7, 90), "C16": (34.45, 14.7, 90),
    "C17": (24.6, 18.0, 90), "R17": (23.0, 18.0, 90), "C12": (37.0, 17.6, 90), "R18": (24.4, 24.4, 90),
    # the supply block: F2 holder, fusible resistor, rectifier, pi filter, LNK306 buck
    "R1": (91.0, 53.8, 180), "D7": (79.6, 56.0, 90),
    "C1": (81.5, 64.0, 0), "L1": (89.6, 64.0, 270), "C2": (97.5, 64.0, 0),
    "U4": (88.8, 73.0, 180), "C3": (92.4, 72.4, 270), "R2": (94.0, 69.4, 180), "R3": (94.0, 72.4, 270),
    "C5": (98.25, 70.8, 180), "D8": (89.0, 79.4, 180),
    "L2": (98.5, 79.15, 0), "D9": (102.9, 68.6, 90), "C4": (107.6, 77.0, 90), "R4": (108.0, 83.0, 0),
    # the 5 V converter and its output (bottom right)
    "U5": (8.0, 43.5, 0), "C6": (8.0, 40.0, 0), "C7": (12.25, 40.0, 0), "C8": (4.5, 43.5, 90),
    "L3": (13.6, 43.5, 0), "R5": (7.6, 47.0, 0), "R6": (10.6, 47.0, 0),
    "C9": (16.0, 47.2, 0), "C10": (16.0, 49.8, 0),
    "F3": (4.4, 49.2, 0), "D4": (17.6, 53.6, 0), "D5": (9.6, 52.0, 0), "C11": (4.0, 53.4, 90),
    # USB (J4 facing the right-hand edge, its protection to its left)
    "J4": (116.5, 51.5, 90), "U6": (111.0, 50.0, 0), "F4": (108.0, 52.5, 90), "D2": (105.5, 52.5, 90),
    "D6": (108.5, 58.5, 0), "R7": (112.5, 55.5, 90),
    # the safe I/O island, bottom left: J3 on the bottom edge, the isolators across the barrier
    # (side 2, the island's, facing down), their island-side parts between them and J3
    "J3": (25.85, 81.0, 0),
    "U7": (ISO_X[0], ISO_Y, 180), "U8": (ISO_X[1], ISO_Y, 180), "U9": (ISO_X[2], ISO_Y, 180),
    "FB1": (5.0, 74.0, 90), "FB2": (6.5, 74.0, 90), "C30": (8.5, 74.0, 90), "C31": (10.1, 74.0, 90),
    "C32": (11.5, 74.0, 90), "C33": (13.1, 74.0, 90), "R27": (15.5, 74.0, 90),
    "C35": (24.0, 74.0, 90), "C37": (37.2, 74.0, 90), "R29": (33.5, 74.0, 90), "R31": (40.5, 74.0, 90),
    # ... and their board-side parts above them
    "C26": (5.0, 57.6, 90), "C27": (7.0, 57.6, 90), "C28": (8.5, 57.6, 90), "C29": (12.5, 57.6, 90),
    "R26": (14.1, 57.6, 90), "C34": (24.0, 57.6, 90), "C36": (37.2, 57.6, 90),
    "R28": (32.5, 57.6, 90), "R30": (34.1, 57.6, 90),
    # the module, bottom middle (antenna past the bottom edge), its supply and EN at its right
    "U1": (65.0, H - U1_EDGE, 180),
    "C21": (75.6, 82.6, 90), "C22": (77.2, 82.6, 90), "R19": (75.6, 79.0, 90), "C23": (77.2, 79.0, 90),
    # 3.3 V, the debug pads, button and LED: the open ground above the island
    "U2": (49.0, 53.0, 0), "C18": (45.6, 53.0, 90), "C19": (52.4, 53.0, 90), "C20": (54.0, 53.0, 90),
    "TP1": (42.4, 46.5, 0),
    "SW1": (49.5, 45.6, 0), "R20": (54.8, 49.6, 90),
    "D1": (58.5, 44.5, 0), "C24": (58.0, 49.0, 90), "R23": (61.0, 49.0, 90), "R24": (56.6, 49.0, 90),
    # relay driver (between the relay's coil pins and the module) and the NTC beside it
    "R21": (59.0, 63.6, 90), "R22": (60.6, 63.6, 90), "Q1": (64.0, 63.6, 0), "D3": (69.4, 63.6, 0),
    "TH1": (74.0, 64.0, 90), "R25": (75.6, 64.0, 90), "C25": (75.0, 61.9, 0),
    **{ref: (x, y, 0) for ref, (x, y) in HOLES.items()},
    # test holes (TEST_HOLES): three rows in the open ground left of the 5 V converter, 5 mm
    # apart and on a 3.2 mm pitch so each hole's label fits above it, on both sides
    **{f"TP{7 + k}": (TP_X + TP_PITCH * k, TP_ROWS[0], 0) for k in range(3)},
    **{f"TP{10 + k}": (TP_X + TP_PITCH * k, TP_ROWS[1], 0) for k in range(4)},
    **{f"TP{2 + k}": (TP_X + TP_PITCH * k, TP_ROWS[2], 0) for k in range(5)},
}


def place_petro(c):
    missing = set(c.instances) - set(AT)
    if missing:
        raise KeyError(f"no placement for {sorted(missing)}")
    p = Placement((0.0, 0.0, W, H), {r: AT[r] for r in c.instances})
    p.courtyards = {r: i.part.body for r, i in c.instances.items()}
    return p


ISO_SLOT_W = 1.5
ISO_ROW_IN = 3.55       # the isolators' pad rows' inner edges, either side of ISO_Y
REINFORCED_GAP = 8.1    # 8 mm and a margin: each side's copper from the other side's pad row
AREA_PAD_MARGIN = 0.4   # each router's area past its own isolator pads' outer ends


def island_extent():
    """The safe I/O island (SELV), as far as its copper may reach: from 8 mm below the isolators'
    board-side pad rows down to the bottom edge, between ISL_X (8 mm and more short of the
    module's pads); only the isolators' own island-side pads stand out of it at the top. The
    board side keeps 8 mm from it (LV_ISLAND_X, LV_ISLAND_Y)."""
    top = ISO_Y - ISO_ROW_IN + REINFORCED_GAP
    x0, x1 = ISL_X
    return [(x0, top), (x1, top), (x1, H - 0.5), (x0, H - 0.5)]


def island_area():
    """The island's router area and ISO_GND pour: island_extent() reaching up just past the
    isolators' island-side pads, so the router (which takes its area for the board outline)
    sees those pads on the board. The band keep-outs hold its tracks and vias to the extent, and
    KiCad's fill holds the pour 8 mm off the board side by the rules."""
    x0, x1 = ISL_X
    top = ISO_Y + ISO_ROW_IN - AREA_PAD_MARGIN
    return [(x0, top), (x1, top), (x1, H - 0.5), (x0, H - 0.5)]


def island_keepouts(c=None, p=None, margin=0.1):
    """(layer, x0, y0, x1, y1) on both layers: the mounting holes the island's area reaches (H3,
    bottom left), all copper 3 mm off. (No keep-out over the isolators' pads: Freerouting will not
    route to a pad inside one; the areas keep the 8 mm instead.)"""
    hole = 3.2 / 2 + 3.0 + margin
    xs, ys = [p_[0] for p_ in island_area()], [p_[1] for p_ in island_area()]
    near = [(x, y) for x, y in HOLES.values()
            if min(xs) - hole < x < max(xs) + hole and min(ys) - hole < y < max(ys) + hole]
    boxes = [(x - hole, y - hole, x + hole, y + hole) for x, y in near]
    if c is not None:
        boxes += band_keepouts(c, p, "island")
    return [(layer, *b) for layer in CU for b in boxes]


def band_keepouts(c, p, side, margin=0.32):
    """Boxes (x0, y0, x1, y1) keeping one side's router out of the 8 mm band and off the other
    side, without covering any of its own pads (Freerouting will not route to a pad inside a
    keep-out, and lets a track leave a pad in any direction, out of its area too).

    side "lv": the island and the strip beside it, and the band, but for gaps round the
    isolators' board-side pads, which its tracks reach from above. side "island": the board side
    above the band, the strip, and the band but for gaps round the island-side pads."""
    from board.rules import _pad_box
    lv_y, top = LV_ISLAND_Y, island_extent()[0][1]
    x_end = LV_ISLAND_X - 0.1
    strip = (island_extent()[1][0] + 0.1, lv_y, x_end, H + 5.0)
    want_selv = side == "island"
    pads = sorted((_pad_box(p, ref, pad) for ref in BARRIERS for pad in c.instances[ref].part.footprint.pads
                   if (GROUPS.get(c.net_of(ref, pad.number)) == "SELV") == want_selv), key=lambda b: b[0])
    if side == "lv":
        row = (lv_y, max(b[3] for b in pads) + margin)          # the board-side pads poke below lv_y
        boxes = [strip, (-5.0, row[1], x_end, H + 5.0)]
    else:
        row = (min(b[1] for b in pads) - margin, top)           # the island-side pads poke above top
        boxes = [strip, (-5.0, lv_y - 6.0, x_end, row[0])]
    x = -5.0
    for b in pads:                                               # the row, but for gaps round its pads
        if b[0] - margin > x:
            boxes.append((x, row[0], b[0] - margin, row[1]))
        x = max(x, b[2] + margin)
    boxes.append((x, row[0], x_end, row[1]))
    return boxes


def in_island(x, y, keepouts=None):
    keep = island_keepouts() if keepouts is None else keepouts
    return _in_poly(x, y, island_area()) and not any(
        x0 <= x <= x1 and y0 <= y <= y1 for _, x0, y0, x1, y1 in keep)


def island_zones():
    """ISO_GND on both layers over the island, below the mains pours in priority."""
    return [Zone("ISO_GND", CU, island_area(), priority=0, clearance=0.2, min_width=0.25)]


def slots():
    """One slot under the safe I/O island's three isolators, along the barrier between their pad
    rows (7.1 mm apart) and past the outer two: every surface path from a board-side pad to an
    island pad goes round an end, which makes it more than 8 mm (rules.barrier_creepage)."""
    return [Slot(ISO_X[0] - 8.0, ISO_Y, ISO_X[2] + 7.0, ISO_Y, ISO_SLOT_W)]


def fuse_box():
    """F1's fuse body between its clips: 6.35 x 31.75 mm, held above the board by the clips."""
    cx = AT["XF1"][0] + F1_CLIP_PITCH / 2
    return (cx - 31.75 / 2, F1_Y - 3.2, cx + 31.75 / 2, F1_Y + 3.2)


def led_ring():
    from board.parts import part
    x, y, _ = AT["D1"]
    b = part("LED").body
    return (x + b[0] - LED_RING, y + b[1] - LED_RING, x + b[2] + LED_RING, y + b[3] + LED_RING)


def keep_boxes():
    return [(fuse_box(), (200, 0, 0)), (led_ring(), (0, 120, 255))]


def sketch_lines():
    """The mains pours' outlines, for the placement sketch."""
    out = []
    for net, pts in MAINS_POLYS.items():
        colour = (40, 90, 230) if net.startswith("N") else (220, 40, 40)
        out += [((a[0], a[1], b[0], b[1]), colour) for a, b in zip(pts, pts[1:] + pts[:1])]
    return out


# --- the mains copper ----------------------------------------------------------------------------
# Each high-current net is a solid pour on both layers over its own stretch, stitched. At 1 oz,
# each layer must be at least MAINS_MIN_WIDTH wide everywhere (KiCad's min_thickness drops
# anything thinner): IPC-2221's width for half the 16 A design current, so the two layers in
# parallel carry 16 A at a 20 C rise (the unit is rated 10 A).
MAINS_MIN_WIDTH = round(math.ceil(ipc2221_width(16 / 2, COPPER_OZ) / 0.05) * 0.05, 2)    # 3.5 mm
CU = ("F.Cu", "B.Cu")
MAINS_POLYS = {
    # neutral: deepened to y = 10 round the shunt (x 24.5-37.5)
    "N_IN": [(3, 3), (30.2, 3), (30.2, 10), (24.5, 10), (24.5, 8.6), (12, 8.6), (12, 19), (3, 19)],
    "N_OUT": [(31.8, 3), (117, 3), (117, 19), (106, 19), (106, 8.6), (72.5, 8.6), (72.5, 12),
              (67, 12), (67, 8.6), (37.5, 8.6), (37.5, 10), (31.8, 10)],
    "L_IN": [(3, 21), (14, 21), (14, 25.4), (20, 25.4), (20, 28.5), (27, 28.5), (27, 35.5), (3, 35.5)],
    # live after F1: one band under the relay's L_F pins (y 37.6-41.5, 2.5 mm below L_OUT and
    # above the low-voltage area) joining the main block, the MOV's arm and XF3's column; each
    # arm and corner at least MAINS_MIN_WIDTH across so the fill stays one piece
    "L_F": [(40, 17.5), (54, 17.5), (54, 13), (81, 13), (81, 19.5), (57, 19.5), (57, 32.5), (62, 32.5),
            (62, 37.6), (81.5, 37.6), (81.5, 49.5), (76, 49.5), (76, 41.5), (57, 41.5), (57, 35.5),
            (40, 35.5)],
    # load: its bottom edge on the relay's L_OUT pins' lower edge (y 35.1), its left edge just past
    # them, so the L_F band and column fit beneath and beside it
    "L_OUT": [(64.5, 26), (104, 26), (104, 20.5), (117, 20.5), (117, 35.1), (64.5, 35.1)],
}
# The bottom layer's neutral stops short of the shunt's sense vias (the shunt joins N_IN and N_OUT
# on the top layer, where its pads are).
MAINS_POLYS_BCU = {
    "N_IN": [(3, 3), (25.6, 3), (25.6, 8.6), (12, 8.6), (12, 19), (3, 19)],
    "N_OUT": [(36.4, 3), (117, 3), (117, 19), (106, 19), (106, 8.6), (72.5, 8.6), (72.5, 12),
              (67, 12), (67, 8.6), (36.4, 8.6)],
}
STITCH = {
    "N_IN": [(9, 10), (9, 13), (14, 5.6), (21, 5.6), (24, 5.6)],
    "N_OUT": [(38, 5.6), (44, 5.6), (52, 5.6), (60, 5.6), (66, 5.6), (84, 5.6), (100, 5.6),
              (110, 7.5), (109, 12)],
    "L_IN": [(6, 28), (11, 27), (11, 32), (20, 32), (8, 33)],
    "L_F": [(46.6, 32), (45, 24), (52, 27), (44, 19.5), (62, 16.5), (59, 37), (68.9, 39.6),
            (75.5, 40), (79.5, 15.5), (80.3, 48.3)],
    "L_OUT": [(69, 33.9), (69, 29), (85, 32), (95, 32), (105, 32), (113, 28), (110, 34)],
}
STITCH_VIA = (1.2, 0.6)                 # size, drill


def mains_zones():
    """The mains pours: every high-current net on both layers, solid, at least MAINS_MIN_WIDTH."""
    out = []
    for net, pts in MAINS_POLYS.items():
        bcu = MAINS_POLYS_BCU.get(net)
        layers = [(CU, pts)] if bcu is None else [(("F.Cu",), pts), (("B.Cu",), bcu)]
        for lay, poly in layers:
            out.append(Zone(net, lay, poly, solid=True, priority=1, clearance=0.2, min_width=MAINS_MIN_WIDTH))
    return out


def stitch_vias():
    size, drill = STITCH_VIA
    return [Via(net, x, y, size, drill) for net, pts in STITCH.items() for x, y in pts]


def mains_pad_extra(c):
    """Every pad on a mains pour joins it solidly (no thermal relief)."""
    return solid_pads(c, set(MAINS_POLYS))


def pad_xy(c, p, ref, number):
    """Board position of a pad's centre."""
    x, y, rot = p.at[ref]
    pad = next(q for q in c.instances[ref].part.footprint.pads if q.number == number)
    dx, dy = rotate(pad.x, pad.y, rot)
    return round(x + dx, 4), round(y + dy, 4)


def _in_poly(x, y, poly):
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


DIV_W = 0.4


def divider_tracks(c, p):
    """R12..R16 in a chain: each DIV net straight from one resistor's pad to the next's, F.Cu."""
    out = []
    for net in ("DIV1", "DIV2", "DIV3", "DIV4"):
        (a, b) = sorted(c.nets[net])
        (x1, y1), (x2, y2) = pad_xy(c, p, *a), pad_xy(c, p, *b)
        out.append(Track(net, "F.Cu", x1, y1, x2, y2, DIV_W))
    return out


HV_W, SW_W, KELVIN_W = 0.5, 0.6, 0.25
KELVIN_VIA = (0.6, 0.3)


def _route(net, layer, width, *pts):
    return [Track(net, layer, *a, *b, width) for a, b in zip(pts, pts[1:])]


def supply_tracks(c, p):
    """The LNK306 supply's high-voltage nets, by hand, on F.Cu (they keep 2.5 mm, SWNODE 1.0 mm,
    from the low-voltage nets, which the router knows nothing about)."""
    xy = lambda ref, n: pad_xy(c, p, ref, n)
    t = []
    x3 = xy("XF3", "2")
    t += _route("L_PSU", "F.Cu", HV_W, x3, (x3[0], 51.0), xy("R1", "1"))
    (rx, ry), (dx, dy) = xy("R1", "2"), xy("D7", "2")
    t += _route("L_RF", "F.Cu", HV_W, (rx, ry), (dx, ry), (dx, dy))
    k7, c1, l1a = xy("D7", "1"), xy("C1", "1"), xy("L1", "1")
    t += _route("VBULK1", "F.Cu", HV_W, k7, (k7[0], c1[1]))
    t += _route("VBULK1", "F.Cu", HV_W, (k7[0], 59.5), (l1a[0], 59.5), l1a)
    l1b, c2, d = xy("L1", "2"), xy("C2", "1"), xy("U4", "4")
    # Into C2's + pad short of its centre, and down to D along L1's pad edge: 2.5 mm from C2's
    # GND pad and 1 mm from FB.
    t += _route("VBULK", "F.Cu", HV_W, (l1b[0] + 2.6, l1b[1]), (l1b[0] + 3.9, c2[1]), (c2[0] - 0.25, c2[1]))
    t += _route("VBULK", "F.Cu", HV_W, (d[0], l1b[1]), d)
    bp, fb = xy("U4", "1"), xy("U4", "2")
    t += _route("BP", "F.Cu", HV_W, bp, xy("C3", "1"))
    r2fb, r3fb = xy("R2", "2"), xy("R3", "1")
    t += _route("FB", "F.Cu", 0.3, fb, (fb[0], 68.9), (r2fb[0], 68.9), r2fb, r3fb)
    r2h, c5h, d9k = xy("R2", "1"), xy("C5", "1"), xy("D9", "1")
    t += _route("FBH", "F.Cu", 0.3, r2h, (c5h[0], r2h[1]), c5h, d9k)
    s = sorted(xy("U4", n) for n in ("5", "6", "7", "8"))
    c3s, r3s, c5s, l2s, d8k = xy("C3", "2"), xy("R3", "2"), xy("C5", "2"), xy("L2", "1"), xy("D8", "1")
    bus = s[0][1]
    t += _route("SW", "F.Cu", SW_W, *s, (c3s[0], bus), (r3s[0], bus), (l2s[0], bus), (l2s[0], 77.0))
    t += _route("SW", "F.Cu", SW_W, (c3s[0], bus), c3s)
    t += _route("SW", "F.Cu", SW_W, (r3s[0], bus), r3s)
    t += _route("SW", "F.Cu", SW_W, (l2s[0], bus), (c5s[0], bus), c5s)
    t += _route("SW", "F.Cu", SW_W, s[-1], (d8k[0], 78.6), d8k)
    return t


def kelvin_route(c, p):
    """(tracks, vias): the shunt's sense pair. Each sense pad has a via beside it (GND below E1,
    SENSE west of E2, over the gap between the two neutral pours, so neither necks the top layer's
    N_OUT where it reaches I2; the bottom layer's neutral stops short of both) and runs down on
    B.Cu into the metering corner, where the router and the GND pour take over."""
    (gx, gy), (sx, sy) = pad_xy(c, p, "RS1", "2"), pad_xy(c, p, "RS1", "3")
    gv, sv = (gx, round(gy + 1.25, 3)), (round(sx - 1.95, 3), sy)
    t = _route("GND", "F.Cu", KELVIN_W, (gx, gy), gv)
    t += _route("GND", "B.Cu", KELVIN_W, gv, (gx, 11.2))
    t += _route("SENSE", "F.Cu", KELVIN_W, (sx, sy), sv)
    t += _route("SENSE", "B.Cu", KELVIN_W, sv, (sv[0], 11.2))
    return t, [Via("GND", *gv, *KELVIN_VIA), Via("SENSE", *sv, *KELVIN_VIA)]


def hand_wiring(c, p):
    """(tracks, vias) routed by hand: the divider chain, the supply's high-voltage nets, the
    Kelvin pair."""
    kt, kv = kelvin_route(c, p)
    return divider_tracks(c, p) + supply_tracks(c, p) + kt, kv


# --- the low-voltage router's area -----------------------------------------------------------------
# One Freerouting pass for every low-voltage net (the rest group, at neutral), in this area: the
# low-voltage side, the corridor under F1 and the metering corner, each edge 2.5 mm from the mains
# pours, and 8 mm short of the safe I/O island (bottom left). Keep-outs (lv_keepouts) round every
# pad of another group, the hand-routed supply tracks and the mounting holes keep it off what the
# router can't see.
LV_ISLAND_X = ISL_X[1] + 8.0     # island_area's right edge + 8 mm
LV_ISLAND_Y = ISO_Y + ISO_ROW_IN - REINFORCED_GAP     # 8 mm above the isolators' island-side rows
LV_AREA_Y = ISO_Y - ISO_ROW_IN + AREA_PAD_MARGIN       # the area's edge: past the board-side pads


def lv_area():
    return [(12.5, 9.0), (24.0, 9.0), (24.0, 10.6), (37.5, 10.6), (37.5, 38.0), (54.5, 38.0),
            (54.5, 44.0), (73.5, 44.0), (73.5, 52.0), (84.0, 52.0),
            (84.0, 41.0), (W - 0.5, 41.0), (W - 0.5, H - 0.5), (LV_ISLAND_X, H - 0.5),
            (LV_ISLAND_X, LV_AREA_Y), (0.5, LV_AREA_Y), (0.5, 38.0),
            (29.5, 38.0), (29.5, 26.0), (22.5, 26.0), (22.5, 22.9), (16.5, 22.9), (16.5, 18.5),
            (12.5, 18.5)]


def lv_keepouts(c, p, margin=0.1):
    """(layer, x0, y0, x1, y1) on both layers: every pad of a group with a spacing to the rest,
    grown by that spacing; every hand-routed supply and divider track, likewise (by its bounding
    box); the mounting holes."""
    from board.gnd import pad_boxes
    r = rules()
    boxes = []
    barrier = {(ref, pad.number) for ref in BARRIERS for pad in c.instances[ref].part.footprint.pads}
    island_pads = {_pad_key(c, p, ref, n) for ref, n in barrier if GROUPS.get(c.net_of(ref, n)) == "SELV"}
    for net, x0, y0, x1, y1 in pad_boxes(c, p):
        if (net, round((x0 + x1) / 2, 2), round((y0 + y1) / 2, 2)) in island_pads:
            continue            # the isolators' island-side pads: lv_area keeps 8 mm from their rows
        g = GROUPS.get(net) if net else None
        s = r.spacing(g, r.rest) if g else 0.0
        if s:
            boxes.append((x0 - s - margin, y0 - s - margin, x1 + s + margin, y1 + s + margin))
    for t in supply_tracks(c, p) + divider_tracks(c, p):
        s = r.spacing(GROUPS[t.net], r.rest) + t.width / 2 + margin
        boxes.append((min(t.x1, t.x2) - s, min(t.y1, t.y2) - s, max(t.x1, t.x2) + s, max(t.y1, t.y2) + s))
    hole = 3.2 / 2 + 3.0 + margin
    boxes += [(x - hole, y - hole, x + hole, y + hole) for x, y in HOLES.values()]
    boxes += band_keepouts(c, p, "lv")
    for v in stitch_vias():                     # the mains pours' stitching vias
        s = r.spacing(GROUPS[v.net], r.rest) + v.size / 2 + margin
        boxes.append((v.x - s, v.y - s, v.x + s, v.y + s))
    return [(layer, *b) for layer in CU for b in boxes]


def gnd_pts():
    """The GND pour's extent (both layers): the low-voltage area. The DRU keeps it 2.5 mm from
    every mains, supply and divider pad and pour (1 mm from the converter's switching node)."""
    return lv_area()


def _pad_key(c, p, ref, n):
    x, y = pad_xy(c, p, ref, n)
    return c.net_of(ref, n), round(x, 2), round(y, 2)


def in_lv(x, y, keepouts=None):
    keep = keepouts if keepouts is not None else _LV_KEEP_CACHE
    return _in_poly(x, y, lv_area()) and not any(
        x0 <= x <= x1 and y0 <= y <= y1 for _, x0, y0, x1, y1 in keep)


def _lv_keep():
    c = build_petro()
    return lv_keepouts(c, place_petro(c))


class _LazyKeep(list):
    def __iter__(self):
        if not self:
            self.extend(_lv_keep())
        return super().__iter__()


_LV_KEEP_CACHE = _LazyKeep()


def pad_extra(c):
    """Per-pad additions: every mains-pour pad joins solidly; so do SMD GND and ISO_GND pads, the
    bulk capacitors' GND leads (their thermal spokes can land on scraps of pour between the
    supply's keep-outs) and the GND test holes. (The S3's -0.18 mm paste margin on its 1.2 mm
    centre pads went with it: the C6's nine 0.8 mm pads keep Espressif's footprint as drawn.)"""
    def make(ref):
        def f(pad):
            net = c.net_of(ref, pad.number)
            extra = []
            if net in MAINS_POLYS or (net == "ISO_GND" and pad.kind == "smd") or (net == "GND" and (
                    pad.kind == "smd" or ref in ("C1", "C2", "C4") or ref in TEST_HOLES)):
                extra.append([S("zone_connect"), 2])
            return extra
        return f
    return {ref: make(ref) for ref in c.instances}


# --- silkscreen (step 9) -------------------------------------------------------------------------
# No reference designators (they ran together and mostly sat under parts; the component key PDF
# names them). Labels only where a person needs them, each where there is room: the front for
# what is used from the front, the back for the rest.
TEST_LABELS = {"BL_RX": "BRX", "BL_TX": "BTX", "ZX": "ZX", "OC": "OC", "GND": "G", "+5V": "5V",
               "+3V3": "3V3", "COIL": "COIL", "LED_DIN": "LED", "BUTTON": "BTN"}
DEBUG_LABELS = {"1": "EN", "2": "RX", "3": "TX", "4": "G", "5": "3V3"}
IO_LABELS = {"1": "3V3", "2": "G", "3": "SCK", "4": "MOSI", "5": "MISO", "6": "CS", "7": "SDA",
             "8": "SCL", "9": "IN", "10": "OUT"}
LIVE_WARNING = (88.0, 26.8)     # the "board is live" block, both sides: on the L_OUT pour, clear of pads
TITLE_AT = (92.0, 47.5)         # the title, on the back above the supply
SAFE_AT = (25.6, 75.9)          # "SAFE I/O" on both sides, between the island's parts and J3


def silk(c, p):
    """Silk entries (text, x, y, size[, layer[, rotation]])."""
    out = []
    xy = lambda ref, n: pad_xy(c, p, ref, n)
    # the mains terminals: their outlines fill the room beside the pins, so N and L go off the
    # ends, in line with their pins (N at the top on both); then which end is which, and 230 V
    for ref, label, y_n, y_l in (("J1", "SUPPLY", 10.4, 29.0), ("J2", "LOAD", 10.1, 28.4)):
        x = p.at[ref][0]
        out += [("N", x, y_n, 1.5), ("L", x, y_l, 1.5), (label, x, round(y_n - 2.2, 3), 1.0)]
    out += [("230 V AC", 8.5, 31.3, 1.2), ("MAINS", 8.5, 33.3, 1.2),
            ("230 V AC", 110.5, 31.0, 1.5), ("MAINS", 110.5, 33.6, 1.5)]
    # rev B is non-isolated: all of it is live but the safe I/O island, on both sides
    wx, wy = LIVE_WARNING
    for layer in ("F.SilkS", "B.SilkS"):
        out += [("DANGER 230 V AC", wx, wy, 1.2, layer), ("BOARD IS LIVE", wx, wy + 2.0, 1.2, layer),
                ("GND = NEUTRAL", wx, wy + 3.8, 1.0, layer), ("ONLY J3 IS SELV", wx, wy + 5.4, 1.0, layer),
                ("UNPLUG BEFORE USB", wx, wy + 6.9, 0.8, layer)]
    sx, sy = SAFE_AT
    out += [("SAFE I/O (SELV)", sx, sy, 1.0), ("SAFE I/O (SELV)", sx, sy, 1.0, "B.SilkS")]
    # test holes: the block left of the 5 V converter, each labelled above, on both sides
    for ref, net in TEST_HOLES.items():
        x, y = xy(ref, "1")
        for layer in ("F.SilkS", "B.SilkS"):
            out.append((TEST_LABELS[net], x, round(y + TP_LABEL_DY, 3), 0.8, layer))
    # the debug pads (SMD, front only): beside each, turned to fit between the pads and U1
    for n, text in DEBUG_LABELS.items():
        x, y = xy("TP1", n)
        out.append((text, round(x + 1.45, 3), y, 0.8, "F.SilkS", 90))
    # J3 on the back (the part covers the front)
    for n, text in IO_LABELS.items():
        x, y = xy("J3", n)
        out.append((text, x, round(y + 2.3, 3), 0.8, "B.SilkS"))
    out.append(("USB", AT["J4"][0], 57.0, 0.8))                       # below J4
    # the title, on the back above the supply
    tx, ty = TITLE_AT
    out += [("PETRO", tx, ty, 2.0, "B.SilkS"), ("230 V~ 10 A", tx, ty + 2.5, 1.2, "B.SilkS"),
            ("nakomis 2026", tx, ty + 4.3, 1.0, "B.SilkS")]
    return out + ref_labels(c, p, out)


# Parts without a reference label: the test holes and debug pads (labelled with their signals)
# and the mounting holes.
UNLABELLED = tuple(TEST_HOLES) + ("TP1", "H1", "H2", "H3", "H4")


def ref_labels(c, p, texts):
    """Reference designators on the front, where they fit (board/refs.py), clear of 'texts'."""
    from board.gnd import pad_boxes
    from board.refs import place_refs
    hard = [b[1:] for b in pad_boxes(c, p)] + [led_ring()]
    hard += [(min(s.x1, s.x2) - s.width / 2, min(s.y1, s.y2) - s.width / 2,
              max(s.x1, s.x2) + s.width / 2, max(s.y1, s.y2) + s.width / 2) for s in slots()]
    # the fuses themselves (not parts: they sit in XF1/XF2 and XF3), placed first, on or by them
    from board.placement import bbox
    extra = [("F1 15 A", ("XF1", "XF2"), fuse_box(), 1.0), ("F2 T500 mA", ("XF3",), bbox(p, "XF3"), 0.8)]
    labels, left = place_refs(c, p, skip=UNLABELLED, hard=hard, texts=texts, extra=extra)
    if left:
        raise ValueError(f"no room for the reference labels of {left}")
    return labels


def silk_avoid(c, p, margin=0.1):
    """Boxes the footprints' own silk must keep out of (write_board drops the lines and labels
    that cross one): every pad (the fab would clip it there anyway) and the slot."""
    from board.gnd import pad_boxes
    boxes = [(x0 - margin, y0 - margin, x1 + margin, y1 + margin) for _, x0, y0, x1, y1 in pad_boxes(c, p)]
    return boxes + [(min(s.x1, s.x2) - s.width / 2 - 0.3, min(s.y1, s.y2) - s.width / 2 - 0.3,
                     max(s.x1, s.x2) + s.width / 2 + 0.3, max(s.y1, s.y2) + s.width / 2 + 0.3) for s in slots()]


def fab_notes():
    """(text entries, user rectangles) on Dwgs.User: the antenna overhang, and the mains rule."""
    ux, uy, _ = AT["U1"]
    text = [("MODULE ANTENNA OVERHANGS THIS EDGE: INTENTIONAL", ux + 20, H + 1.5, 0.8, "Dwgs.User"),
            ("NON-ISOLATED: THE BOARD IS AT MAINS POTENTIAL (GND = NEUTRAL), BAR THE SAFE I/O ISLAND",
             W / 2, -1.5, 0.8, "Dwgs.User")]
    return text, [(ux - ANTENNA_HALF, H, ux + ANTENNA_HALF, H + ANTENNA_OVERHANG, "Dwgs.User")]


# --- hand-offs: the firmware header and the case interface -----------------------------------------
# The C6-WROOM-1's antenna strip (parts.ESP32C6_ANTENNA): 18 mm wide, 6.5 mm past the bottom edge.
ANTENNA_HALF, ANTENNA_OVERHANG = 9.0, 6.5


def pins_h():
    """The firmware header: GPIO numbers as wired on this board."""
    lines = ["/* Generated by pcb/build.py from board/petro_board.py: do not edit. */", "#pragma once", "",
             "/* Petro rev B: ESP32-C6-WROOM-1-N8 (idf.py set-target esp32c6). */",
             "/* Debug pads TP1, from the top: " + ", ".join(DEBUG_LABELS.values()) + ".",
             "   EN is the chip enable (bridge it to G to reset); RX/TX are UART0. */",
             "/* The relay is active-high (low-side FET); the button is active-low (GPIO9, also the",
             "   boot strap); the LED is on GPIO8 (a strap: pulled up). BL_TX/BL_RX are UART1 to the",
             "   BL0939; ZX is its zero cross, OC its fast over-current. */",
             "/* Rev B is NON-ISOLATED: GND is tied to neutral, so every pin and pad is at mains",
             "   potential whenever the unit is plugged in, bar the safe I/O island (J3). Bench work",
             "   (USB, test holes) with the mains unplugged only. */",
             "/* Test holes (push-in loops, bench only, mains disconnected): "
             + ", ".join(f"{ref} {net}" for ref, net in TEST_HOLES.items()) + ". */", ""]
    for k in ("RELAY", "LED", "BUTTON", "BL_TX", "BL_RX", "ZX", "OC", "NTC",
              "USB_DM", "USB_DP", "UART_TX", "UART_RX"):
        lines.append(f"#define PETRO_PIN_{k} {GPIO[k]}")
    lines += ["", "/* Safe I/O terminal J3 (SELV: isolated, safe to touch): " + ", ".join(IO_LABELS.values())
              + ". 3V3 is the isolated supply (budget ~30 mA); I2C has 4.7k pull-ups on both sides; IN",
              "   reads low with nothing connected. ISO_FLT is low if the island's converter has failed. */"]
    for k in ("SPI_SCLK", "SPI_MOSI", "SPI_MISO", "SPI_CS", "I2C_SDA", "I2C_SCL", "SAFE_IN", "SAFE_OUT",
              "ISO_FLT"):
        lines.append(f"#define PETRO_PIN_{k} {GPIO[k]}")
    return "\n".join(lines) + "\n"


def case_interface(c, p):
    """What the case (PETRO-6) needs from the board, as JSON, in board coordinates (mm, origin
    top-left, y down, top view): outline, holes, the LED and the light pipe's flange ring, the
    button, the connectors with the edge each faces, and the antenna overhang. Rev B is
    non-isolated: the board is at mains potential bar the safe I/O island, so the case treats all
    of it as live except the island, whose J3 may open to the outside; USB (J4) stays internal
    (reached with the case open, unplugged)."""
    import json
    from board.placement import bbox
    box = lambda ref: [round(v, 3) for v in bbox(p, ref)]
    ux = AT["U1"][0]
    data = {
        "board": {"width": W, "height": H, "thickness": 1.6, "origin": "top-left, y down"},
        "holes": [{"ref": r, "x": x, "y": y, "diameter": 3.2, "plated": False,
                   "note": "unplated; copper keeps 3 mm off, but use nylon screws or keep metal ones inside"}
                  for r, (x, y) in HOLES.items()],
        "led": {"x": AT["D1"][0], "y": AT["D1"][1], "part": "SK6812-EC20", "body": box("D1"),
                "flange_ring": [round(v, 3) for v in led_ring()],
                "note": f"{LED_RING} mm clear board round the LED for the light pipe's flange"},
        "button": {"x": AT["SW1"][0], "y": AT["SW1"][1], "part": "TS-1002 7 mm tactile", "body": box("SW1")},
        "connectors": {
            "J1": {"what": "mains in (L, N), 7.62 mm screw terminal", "edge": "left", "body": box("J1")},
            "J2": {"what": "mains out to the load (L, N)", "edge": "right", "body": box("J2")},
            "J3": {"what": "10-way 3.5 mm safe I/O terminal (SELV, reinforced isolation): 3V3, G, "
                           "SCK, MOSI, MISO, CS, SDA, SCL, IN, OUT", "edge": "bottom",
                   "internal_only": False, "safe": True, "body": box("J3")},
            "J4": {"what": "USB, JST SH 5-pin side entry: bench only, case off, mains unplugged",
                   "edge": "right", "internal_only": True, "body": box("J4")},
        },
        "tall_parts": {r: box(r) for r in ("K1", "XF1", "XF2", "XF3", "RV1", "L1", "L2", "C1", "C2", "C4")},
        "antenna_overhang": [ux - ANTENNA_HALF, H, ux + ANTENNA_HALF, H + ANTENNA_OVERHANG],
        "mains_area": {"whole_board": True,
                       "except": [round(v, 3) for v in (*island_extent()[0], *island_extent()[2])],
                       "note": "non-isolated: every part of the board is at mains potential when "
                               "plugged in, except the safe I/O island (the 'except' box: J3's corner); "
                               "no opening may expose anything outside it"},
    }
    return json.dumps(data, indent=2) + "\n"
