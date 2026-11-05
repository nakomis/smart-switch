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

The I/O terminal J3 (5 Nov 2026): a 10-way terminal for parts added inside the case (SPI, I2C, one
  input, one output, 3.3 V and ground), wired straight to the ESP32. It is at mains potential like
  everything else: nothing on it may leave the case. (An isolated version, J3 behind three
  reinforced isolators, is tag rev-b-isolated-io: about 75 GBP more for five boards.)
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
# J3's I/O: I2C on LP_I2C (6/7) and its input on an LP GPIO (3), so the low-power core can poll
# sensors and the PIR can wake the chip with the main core asleep; SPI on 18-21. IN (3), OUT (23)
# and SPI are on the module's left-hand column, J3's side; LP_I2C has no other pins. GPIO22 and
# GPIO15 are spare.
GPIO = {"BUTTON": 9, "LED": 8, "USB_DM": 12, "USB_DP": 13, "UART_TX": 16, "UART_RX": 17,
        "NTC": 0,           # board temperature, ADC1_CH0
        "ZX": 1,            # BL0939 zero cross
        "OC": 2,            # BL0939 I_leak (channel B fast over-current)
        "RELAY": 4,
        "BL_TX": 10,        # BL0939 TX -> ESP RX (UART1)
        "BL_RX": 11,        # ESP TX (UART1) -> BL0939 RX
        "IO_IN": 3, "IO_OUT": 23, "I2C_SDA": 6, "I2C_SCL": 7,
        "SPI_SCLK": 18, "SPI_MOSI": 19, "SPI_MISO": 20, "SPI_CS": 21}
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
# J3: the I/O terminal (10-way, 3.5 mm) for parts inside the case, straight from the ESP32: 3.3 V
# and ground, SPI, I2C, one input (a PIR, an interrupt) and one output. At mains potential, like
# the rest of the board. J4 (the heatlink's IDC header) is gone: the C6 has no pins left for it.
IO_PINS = {"1": "+3V3", "2": "GND", "3": "SPI_SCLK", "4": "SPI_MOSI", "5": "SPI_MISO",
           "6": "SPI_CS", "7": "I2C_SDA", "8": "I2C_SCL", "9": "IO_IN", "10": "IO_OUT"}

# --- the mains rules (non-isolated mode: every other net sits at neutral) --------------------------
# The supply's high-voltage nets are the PSU group: after F2, at the rectified live (the switching
# node and the LNK306's BP/FB, which ride on it, included).
PSU_NETS = ("L_PSU", "L_RF", "VBULK1", "VBULK")
# The LNK306's switching node and what rides on it (BYPASS, FEEDBACK, the sampled output): functional
# insulation inside the converter, where a short only trips its current limit: 1.0 mm (rules.reduced).
SWNODE_NETS = ("SW", "BP", "FB", "FBH")
GROUPS = {"L_IN": "LINE", "L_F": "LIVE", "N_IN": "NEUTRAL", "N_OUT": "NEUTRAL", "L_OUT": "LOAD",
          "DIV1": "DIV1", "DIV2": "DIV2", "DIV3": "DIV3", "DIV4": "DIV4",
          **{n: "PSU" for n in PSU_NETS}, **{n: "SWNODE" for n in SWNODE_NETS}}
HIGH_CURRENT = {"L_IN", "L_F", "L_OUT", "N_IN", "N_OUT"}
# Hand-fit (5 Nov 2026): the mains parts, bought from authorised distributors (DESIGN.md §3.2) and
# soldered by Martin; left off the fab's BOMs and CPL, listed in hand-fit.csv. The mains terminals,
# F1's clips, F2's holder, the relay, the MOV and the fusible resistor.
HAND_FIT = ("J1", "J2", "XF1", "XF2", "XF3", "K1", "RV1", "R1")
BL_NC = ("VT", "CF", "SCLK", "VPP")          # the BL0939's unused pins, each on an NC_ net


def rules():
    return Rules(GROUPS, high_current=HIGH_CURRENT, rest="NEUTRAL", divider_top="LINE",
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
    pins("FASTREC", "D8", A=gnd, K="SW")                              # freewheel (US1M, 75 ns)
    pins("C220U", _plus=v12, _minus=gnd)
    pins("RECT", "D9", A=v12, K="FBH")                                # feedback: samples the output...
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
    two("R56K", None, "VPSU", "FB5")                            # 0.768 V x (1 + 56/10) = 5.07 V
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

    # ---- J3, the I/O terminal: straight to the ESP32, for parts inside the case ------------------
    # 3.3 V from the AP2112K (600 mA, the module's share aside), I2C with 4k7 pull-ups, IN pulled
    # down so it reads low with nothing connected.
    for sig in ("SPI_SCLK", "SPI_MOSI", "SPI_MISO", "SPI_CS", "I2C_SDA", "I2C_SCL", "IO_IN", "IO_OUT"):
        c.connect(sig, (u1, modpin(GPIO[sig])))
    for sig in ("I2C_SDA", "I2C_SCL"):
        two("R4K7", None, sig, v33)
    two("R100K", None, "IO_IN", gnd)
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
J3_X0 = 25.85 - 4.5 * 3.5  # J3's pin 1 (10 pins on 3.5 mm, centred on the part)
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
    "L2": (98.5, 79.15, 0), "D9": (102.9, 68.6, 90), "C4": (107.6, 77.0, 90), "R4": (107.6, 70.8, 0),
    # the 5 V converter and its output (bottom right)
    "U5": (8.0, 43.5, 0), "C6": (8.0, 40.0, 0), "C7": (12.25, 40.0, 0), "C8": (4.5, 43.5, 90),
    "L3": (13.6, 43.5, 0), "R5": (7.6, 47.0, 0), "R6": (10.6, 47.0, 0),
    "C9": (16.0, 47.2, 0), "C10": (16.0, 49.8, 0),
    "F3": (4.4, 49.2, 0), "D4": (17.6, 53.6, 0), "D5": (9.6, 52.0, 0), "C11": (4.0, 53.4, 90),
    # USB (J4 facing the right-hand edge, its protection to its left)
    "J4": (116.5, 51.5, 90), "U6": (111.0, 50.0, 0), "F4": (108.0, 52.5, 90), "D2": (105.5, 52.5, 90),
    "D6": (108.5, 58.5, 0), "R7": (112.5, 55.5, 90),
    # J3, the I/O terminal, bottom left on the bottom edge; the I2C pull-ups and IN's pull-down
    # above their pins
    "J3": (25.85, 81.0, 0),
    "R26": (J3_X0 + 6 * 3.5, 74.0, 90), "R27": (J3_X0 + 7 * 3.5, 74.0, 90), "R28": (J3_X0 + 8 * 3.5, 74.0, 90),
    # the module, bottom middle (antenna past the bottom edge), its supply and EN at its right
    "U1": (66.0, H-U1_EDGE, 180),
    "C21": (76.6, 82.6, 90), "C22": (78.2, 82.6, 90), "R19": (76.6, 79.0, 90), "C23": (78.2, 79.0, 90),
    # 3.3 V, the debug pads, button and LED: the open ground above J3
    "U2": (49.0, 53.0, 0), "C18": (45.6, 53.0, 90), "C19": (52.4, 53.0, 90), "C20": (54.0, 53.0, 90),
    "TP1": (42.4, 46.5, 0),
    "SW1": (49.5, 45.6, 0), "R20": (54.8, 49.6, 90),
    "D1": (58.5, 44.5, 0), "C24": (58.0, 49.0, 90), "R23": (61.0, 49.0, 90), "R24": (56.6, 49.0, 90),
    # relay driver (between the relay's coil pins and the module) and the NTC beside it
    "R21": (59.0, 63.6, 90), "R22": (60.6, 63.6, 90), "Q1": (64.0, 63.6, 0), "D3": (69.4, 63.6, 0),
    "TH1": (78.4, 75.5, 90), "R25": (80.0, 75.5, 90), "C25": (79.2, 72.6, 0),
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


def slots():
    """No slots: rev B has no barrier on the board (it is all at neutral but the mains)."""
    return []


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
    t += _route("VBULK1", "F.Cu", HV_W, k7, (k7[0], 59.5), (k7[0], c1[1]))        # a node for the branch
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
    # ... and on into R10's sense pad (the lower one, between IBP above it and C15's ground below,
    # where the router found no room for a via): a via in the gap between R10 and R11, then F.Cu.
    (rx, ry), (nx, _) = pad_xy(c, p, "R10", "1"), pad_xy(c, p, "R11", "1")
    end = (round((rx + nx) / 2, 3), ry)
    t += _route("SENSE", "B.Cu", KELVIN_W, (sv[0], 11.2), (end[0], 11.2), end)
    t += _route("SENSE", "F.Cu", KELVIN_W, end, (rx, ry))
    return t, [Via("GND", *gv, *KELVIN_VIA), Via("SENSE", *sv, *KELVIN_VIA), Via("SENSE", *end, *KELVIN_VIA)]


def usb_ties(c, p):
    """(tracks, []): the SRV05-4's flow-through pairs, D- pin 1 to 6 and D+ pin 3 to 4, straight
    across on F.Cu; the router left D-'s two halves apart."""
    xy = lambda n: pad_xy(c, p, "U6", n)
    return (_route("USB_DM", "F.Cu", 0.25, xy("1"), xy("6")) + _route("USB_DP", "F.Cu", 0.25, xy("3"), xy("4"))), []


def ldo_ground(c, p):
    """(tracks, []): U2's GND pin to its output capacitor C19's GND pad, by hand: down between
    U2's +5V pins, across, and up past its NC pin and C19's +3V3 pad. The router left the two in
    separate pieces of pour, walled apart on both layers by tracks."""
    (gx, gy), (cx, cy) = pad_xy(c, p, "U2", "2"), pad_xy(c, p, "C19", "2")
    under, side = gy + 1.1, cx - 1.2
    return _route("GND", "F.Cu", 0.3, (gx, gy), (gx, under), (side, under), (side, cy), (cx, cy)), []


def hand_wiring(c, p):
    """(tracks, vias) routed by hand: the divider chain, the supply's high-voltage nets, the
    Kelvin pair, the regulator's ground, the USB protection's flow-through ties."""
    kt, kv = kelvin_route(c, p)
    lt, _ = ldo_ground(c, p)
    ut, _ = usb_ties(c, p)
    return divider_tracks(c, p) + supply_tracks(c, p) + kt + lt + ut, kv


# --- the low-voltage router's area -----------------------------------------------------------------
# One Freerouting pass for every low-voltage net (the rest group, at neutral), in this area: the
# low-voltage side, the corridor under F1 and the metering corner, each edge 2.5 mm from the mains
# pours. Keep-outs (lv_keepouts) round every
# pad of another group, the hand-routed supply tracks and the mounting holes keep it off what the
# router can't see.
def lv_area():
    return [(12.5, 9.0), (24.0, 9.0), (24.0, 10.6), (37.5, 10.6), (37.5, 38.0), (54.5, 38.0),
            (54.5, 44.0), (73.5, 44.0), (73.5, 52.0), (84.0, 52.0),
            (84.0, 41.0), (W - 0.5, 41.0), (W - 0.5, H - 0.5), (0.5, H - 0.5), (0.5, 38.0),
            (29.5, 38.0), (29.5, 26.0), (22.5, 26.0), (22.5, 22.9), (16.5, 22.9), (16.5, 18.5),
            (12.5, 18.5)]


def lv_keepouts(c, p, margin=0.1):
    """(layer, x0, y0, x1, y1): every pad of a group with a spacing to the rest, grown by that
    spacing, on the layers the pad is on (an SMD pad only on F.Cu: under it, B.Cu is 1.6 mm of
    FR-4 away, which the rules rightly don't count as a surface spacing, and the router needs that
    room under the supply block); every hand-routed supply and divider track likewise, on its
    layer (by its bounding box); and on both layers the mounting holes and the mains pours'
    stitching vias."""
    from board.cleanup import pad_shapes
    r = rules()
    out = []
    for net, layers, x0, y0, x1, y1 in pad_shapes(c, p):
        g = GROUPS.get(net) if net else None
        s = r.spacing(g, r.rest) if g else 0.0
        if s:
            out += [(layer, x0 - s - margin, y0 - s - margin, x1 + s + margin, y1 + s + margin)
                    for layer in CU if layer in layers]
    for t in supply_tracks(c, p) + divider_tracks(c, p):
        s = r.spacing(GROUPS[t.net], r.rest) + t.width / 2 + margin
        out.append((t.layer, min(t.x1, t.x2) - s, min(t.y1, t.y2) - s, max(t.x1, t.x2) + s, max(t.y1, t.y2) + s))
    hole = 3.2 / 2 + 3.0 + margin
    boxes = [(x - hole, y - hole, x + hole, y + hole) for x, y in HOLES.values()]
    for v in stitch_vias():                     # the mains pours' stitching vias
        s = r.spacing(GROUPS[v.net], r.rest) + v.size / 2 + margin
        boxes.append((v.x - s, v.y - s, v.x + s, v.y + s))
    return out + [(layer, *b) for layer in CU for b in boxes]


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
    """Per-pad additions: every mains-pour pad joins solidly; so does every GND pad
    (thermal spokes can land on a scrap of pour the tracks have cut off, which then counts as
    unjoined: C1's lead between the supply's keep-outs, SW1's beside the button's tracks). (The S3's -0.18 mm paste margin on its 1.2 mm
    centre pads went with it: the C6's nine 0.8 mm pads keep Espressif's footprint as drawn.)"""
    def make(ref):
        def f(pad):
            net = c.net_of(ref, pad.number)
            extra = []
            if net in MAINS_POLYS or net == "GND":
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
LIVE_IO_AT = (20.6, 75.9)       # "LIVE I/O" on both sides, above J3's left-hand pins


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
    # rev B is non-isolated: all of it is live, J3 included, on both sides
    wx, wy = LIVE_WARNING
    for layer in ("F.SilkS", "B.SilkS"):
        out += [("DANGER 230 V AC", wx, wy, 1.2, layer), ("BOARD IS LIVE", wx, wy + 2.0, 1.2, layer),
                ("GND = NEUTRAL", wx, wy + 3.8, 1.0, layer), ("J3 I/O IS LIVE TOO", wx, wy + 5.4, 1.0, layer),
                ("UNPLUG BEFORE USB", wx, wy + 6.9, 0.8, layer)]
    sx, sy = LIVE_IO_AT
    out += [("LIVE I/O: INSIDE CASE ONLY", sx, sy, 0.8), ("LIVE I/O: INSIDE CASE ONLY", sx, sy, 0.8, "B.SilkS")]
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
            ("NON-ISOLATED: THE WHOLE BOARD IS AT MAINS POTENTIAL (GND = NEUTRAL), J3 INCLUDED",
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
             "   potential whenever the unit is plugged in, J3 included. Bench work",
             "   (USB, test holes) with the mains unplugged only. */",
             "/* Test holes (push-in loops, bench only, mains disconnected): "
             + ", ".join(f"{ref} {net}" for ref, net in TEST_HOLES.items()) + ". */", ""]
    for k in ("RELAY", "LED", "BUTTON", "BL_TX", "BL_RX", "ZX", "OC", "NTC",
              "USB_DM", "USB_DP", "UART_TX", "UART_RX"):
        lines.append(f"#define PETRO_PIN_{k} {GPIO[k]}")
    lines += ["", "/* I/O terminal J3 (NOT isolated: at mains potential, for parts inside the case only): "
              + ", ".join(IO_LABELS.values()) + ".",
              "   3V3 is the board's own rail (AP2112K, 600 mA; keep J3's load to ~150 mA); I2C has 4.7k",
              "   pull-ups; IN reads low with nothing connected. */"]
    for k in ("SPI_SCLK", "SPI_MOSI", "SPI_MISO", "SPI_CS", "I2C_SDA", "I2C_SCL", "IO_IN", "IO_OUT"):
        lines.append(f"#define PETRO_PIN_{k} {GPIO[k]}")
    return "\n".join(lines) + "\n"


def case_interface(c, p):
    """What the case (PETRO-6) needs from the board, as JSON, in board coordinates (mm, origin
    top-left, y down, top view): outline, holes, the LED and the light pipe's flange ring, the
    button, the connectors with the edge each faces, and the antenna overhang. Rev B is
    non-isolated: the whole board is at mains potential, J3 included, so the case treats all of it
    as live; J3 and USB (J4) stay internal (J3 for parts mounted inside the case; USB reached with
    the case open, unplugged)."""
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
            "J3": {"what": "10-way 3.5 mm I/O terminal, NOT isolated (at mains potential): 3V3, G, "
                           "SCK, MOSI, MISO, CS, SDA, SCL, IN, OUT; for parts mounted inside the case",
                   "edge": "bottom", "internal_only": True, "safe": False, "body": box("J3")},
            "J4": {"what": "USB, JST SH 5-pin side entry: bench only, case off, mains unplugged",
                   "edge": "right", "internal_only": True, "body": box("J4")},
        },
        "tall_parts": {r: box(r) for r in ("K1", "XF1", "XF2", "XF3", "RV1", "L1", "L2", "C1", "C2", "C4")},
        "antenna_overhang": [ux - ANTENNA_HALF, H, ux + ANTENNA_HALF, H + ANTENNA_OVERHANG],
        "mains_area": {"whole_board": True,
                       "note": "non-isolated: every part of the board, J3 and whatever is wired to it "
                               "included, is at mains potential when plugged in; no opening may expose "
                               "any of it, and nothing conductive may leave the case"},
    }
    return json.dumps(data, indent=2) + "\n"
