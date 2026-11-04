"""Petro: the netlist (PETRO-2, step 5).

Mains side, in the order the live passes through it (docs/DESIGN.md §3):
  J1 (line in) -> F1 (15 A HBC, in two clips XF1/XF2) -> MOV across to neutral -> the 1 mOhm shunt
  RS1 -> the relay's COM; its NO -> J2 (load out). Neutral runs straight from J1 to J2.
  After F1, F2 (T500 mA, holder XF3) feeds PS1 (IRM-05-5), which makes the SELV 5 V.
  The metering island (the BL0939 U3 and side 2 of U4) floats on the live, with its ground at the
  shunt's sense pad on F1's side, so no load current flows in it. It is powered across the barrier
  by the ISOW7743's isolated converter, from the SELV 5 V (decided 4 Nov 2026: it replaces the
  IRM-01-5 and the ISO7741, which did not fit).
  The BL0939 measures the shunt (channel A for metering, channel B for its fast over-current
  output I_leak) and the voltage through a 5 x 390k divider from neutral. Four lines cross the
  ISOW7743 (reinforced): its UART both ways, zero cross and over-current.

SELV side: as on the nakostat heatlink (STAT-75), so firmware and the reuse I/O carry over:
  the ESP32-S3-MINI-1 module, its 3.3 V LDO, the house USB connector, the relay driver, the button
  on GPIO0, the WS2812B LED, the debug pads, J3 (8-way terminal) and J4 (16-way IDC) with the
  heatlink's exact pinouts. 5 V comes from PS1 or USB through a diode-OR.
"""
from board.netlist import Circuit
from board.rules import HIGH_CURRENT_WIDTH, Rules

# --- GPIO ----------------------------------------------------------------------------------------
# The heatlink's assignments wherever the function is the same; J3/J4 identical. Avoided: the
# strapping pins 45/46 (and 0/3, below), the module's flash pins (26-32 on the N8; 33-37 left
# alone too), USB (19/20) and UART0 (43/44, the debug pads).
# GPIO0 (strap: download mode when held low at reset) is the user button, as on the heatlink:
# holding it while plugging in enters the bootloader, which is useful rather than harmful.
# GPIO3 (strap: JTAG source, but only when an eFuse selects it, which it does not by default)
# is the NTC: it needs an ADC1 pin, and GPIO1-10 all go to J3/J4.
GPIO = {"RELAY": 12, "LED": 15, "BUTTON": 0, "USB_DM": 19, "USB_DP": 20,
        "UART_TX": 43, "UART_RX": 44,
        "BL_TX": 13,        # BL0939 TX -> isolator OUTA -> ESP RX (UART1)
        "BL_RX": 14,        # ESP TX (UART1) -> isolator IND -> BL0939 RX
        "ZX": 41,           # BL0939 zero cross, through the isolator
        "OC": 42,           # BL0939 I_leak (channel B fast over-current), through the isolator
        "NTC": 3,           # board temperature, ADC1_CH2
        "ISO_FLT": 47,      # ISOW7743 EN/FLT: low if its isolated converter fails
        "IO_SDA": 1, "IO_SCL": 2, "IO_4": 4, "IO_5": 5, "IO_6": 6,
        **{f"HDR_{n}": n for n in (7, 8, 9, 10, 11, 16, 17, 18, 21, 38, 39, 40)}}
STRAPPING = {0, 3, 45, 46}
FLASH = set(range(26, 38))
_MODPIN = {43: "TXD0", 44: "RXD0"}


def modpin(gpio):
    return _MODPIN.get(gpio, f"IO{gpio}")


# --- connectors ----------------------------------------------------------------------------------
# J1 / J2: line in and load out (Degson DG636, 7.62 mm). Earth does not touch the board.
J1_PINS = {"1": "L_IN", "2": "N"}
J2_PINS = {"1": "N", "2": "L_OUT"}             # rotated 270: neutral on top, as on J1
# J5: the house USB connector (tinycrypt's J1, as on the heatlink): 1 VBUS, 2 D-, 3 D+, 4 CC,
# 5 GND; pads 6/7 are the shell tabs.
USB_PINS = {"1": "VBUS_IN", "2": "USB_DM", "3": "USB_DP", "4": "CC", "5": "GND"}
DEBUG_PINS = {"1": "EN", "2": "UART_RX", "3": "UART_TX", "4": "GND", "5": "+3V3"}
# J3 and J4: the heatlink's pinouts, exactly (see its DESIGN.md "IO terminal (J3)" and "IDC
# header (J4)"). 5 V is this board's +5V rail (after the diode-OR).
IO_PINS = {"1": "+5V", "2": "GND", "3": "+3V3", "4": "IO_SDA", "5": "IO_SCL", "6": "IO_4", "7": "IO_5",
           "8": "IO_6"}
HDR_PINS = {"1": "+3V3", "2": "GND", "3": "HDR_7", "4": "HDR_8", "5": "HDR_9", "6": "HDR_10",
            "7": "HDR_11", "8": "GND", "9": "HDR_16", "10": "HDR_17", "11": "HDR_18", "12": "HDR_21",
            "13": "HDR_38", "14": "HDR_39", "15": "HDR_40", "16": "+5V"}

# --- the mains rules -----------------------------------------------------------------------------
ISLAND = ("GND_M", "GISO_M", "3V3_M", "VISO_M", "VP", "SENSE", "IAP", "IAN", "IBP", "IBN",
          "BL_TX_M", "BL_RX_M", "ZX_M", "OC_M")
ISLAND_NC = ("VT", "CF", "SCLK", "VPP")      # the BL0939's unused pins, each on an NC_ net
GROUPS = {"L_IN": "LINE", "L_F": "LIVE", "L_SH": "LIVE", "L_PSU": "PSU", "N": "NEUTRAL",
          "L_OUT": "LOAD", "DIV1": "DIV1", "DIV2": "DIV2", "DIV3": "DIV3", "DIV4": "DIV4",
          **{n: "LIVE" for n in ISLAND}, **{f"NC_U3_{p}": "LIVE" for p in ISLAND_NC}}
HIGH_CURRENT = {"L_IN", "L_F", "L_SH", "L_OUT", "N"}
BARRIERS = ("U4", "K1", "PS1")          # isolator, relay, SELV PSU: their own pads cross the barrier


def rules():
    return Rules(GROUPS, high_current=HIGH_CURRENT, barriers=BARRIERS)


def build_petro():
    c = Circuit()
    gnd, v33, v5 = "GND", "+3V3", "+5V"

    def part(key, ref):
        return c.add(key, ref)

    def two(key, ref, net1, net2):
        p = c.add(key, ref)
        c.connect(net1, (p, "1"))
        c.connect(net2, (p, "2"))
        return p

    # ---- mains: the live path -------------------------------------------------------------------
    j1, j2 = part("MAINSTERM", "J1"), part("MAINSTERM", "J2")
    for pad, net in J1_PINS.items():
        c.connect(net, (j1, pad))
    for pad, net in J2_PINS.items():
        c.connect(net, (j2, pad))
    c.connect("L_IN", (part("FUSECLIP", "XF1"), "1"))           # F1's two clips
    c.connect("L_F", (part("FUSECLIP", "XF2"), "1"))
    two("MOV", "RV1", "L_F", "N")                               # after F1: F1 clears a MOV short
    rs = part("SHUNT", "RS1")
    c.connect("L_F", (rs, "I1"))
    c.connect("L_SH", (rs, "I2"))
    c.connect("GND_M", (rs, "E1"))                              # Kelvin: the island's ground
    c.connect("SENSE", (rs, "E2"))
    k1 = part("RELAY16", "K1")
    c.connect("L_SH", (k1, "COM"))
    c.connect("L_OUT", (k1, "NO"))

    # ---- mains: the PSU branch ------------------------------------------------------------------
    two("FUSEHOLD", "XF3", "L_F", "L_PSU")                      # F2, T500 mA
    ps1 = part("PSU5W", "PS1")
    c.connect("L_PSU", (ps1, "AC/L"))
    c.connect("N", (ps1, "AC/N"))
    c.connect("VPSU", (ps1, "+V"))
    c.connect(gnd, (ps1, "-V"))

    # ---- the metering island --------------------------------------------------------------------
    # Powered across the barrier by the ISOW7743's isolated converter (3V3_M, below); its ground
    # GND_M is the shunt's sense pad on F1's side, so it floats on the live.
    u3 = part("BL0939", "U3")
    c.connect("3V3_M", (u3, "VDD"))
    c.connect("GND_M", (u3, "GND"), (u3, "SEL"))                 # SEL low: UART
    two("C100N", None, "3V3_M", "GND_M")
    # Current inputs: both channels read the shunt's sense pads through 1k / 33 nF (Belling's
    # application circuit). Channel A meters; channel B drives I_leak, the fast over-current.
    for ch, (p, n) in (("A", ("IAP", "IAN")), ("B", ("IBP", "IBN"))):
        k = "1" if ch == "A" else "2"
        rp, rn = c.add("R1K"), c.add("R1K")
        c.connect("SENSE", (rp, "1"))
        c.connect(p, (rp, "2"), (u3, f"IP{k}"))
        c.connect("GND_M", (rn, "1"))
        c.connect(n, (rn, "2"), (u3, f"IN{k}"))
        two("C33N", None, p, "GND_M")
        two("C33N", None, n, "GND_M")
    # Voltage: neutral -> 5 x 390k (1206, 50 V each) -> VP -> 470R to the island's ground, so
    # 61 mV rms at 253 V (the BL0939's maximum is 70 mV rms), with 33 nF across.
    chain = ["N", "DIV1", "DIV2", "DIV3", "DIV4", "VP"]
    for a, b in zip(chain, chain[1:]):
        two("R390K", None, a, b)
    two("R470", None, "VP", "GND_M")
    two("C33N", None, "VP", "GND_M")
    c.connect("VP", (u3, "VP"))
    c.connect("BL_TX_M", (u3, "TX/SDO"))
    c.connect("BL_RX_M", (u3, "RX/SDI"))
    c.connect("ZX_M", (u3, "ZX"))
    c.connect("OC_M", (u3, "I_leak"))
    two("R10K", None, "BL_TX_M", "3V3_M")                       # TX needs a pull-up (datasheet)
    # Unused pins (SCLK and VPP must float): each on its own NC_ net in the LIVE group, so the
    # mains rules treat them as part of the island, not as touchable SELV copper.
    for pin in ISLAND_NC:
        c.connect(f"NC_U3_{pin}", (u3, pin))

    # ---- the isolator with power: side 1 SELV (the power input), side 2 the island ---------------
    # ISOW7743 (TI SLLSFK1C): power flows from side 1 to side 2, so side 1 is SELV. Channel A is
    # the forward one (ESP32 TX -> BL0939 RX); B, C and D come back (TX, zero cross, over-current).
    # Its converter (VDD 5 V -> VISOOUT 3.3 V with VSEL low, up to 140 mA) powers the island; TI's
    # application circuit: beads VISOOUT->VISOIN and GND2->GISOIN, 10u+1u+100n on VDD and VISOOUT,
    # 100n on VIO and VISOIN. EN/FLT: pulled up (converter on), and read on GPIO47 as a fault.
    u4 = part("ISOW", "U4")
    c.connect(v5, (u4, "VDD"))
    c.connect(v33, (u4, "VIO"), (u4, "EN_IO1"))
    c.connect(gnd, (u4, "GND1"), (u4, "GNDIO"))
    c.connect("ISO_FLT", (u4, "EN/FLT"))
    two("R10K", None, "ISO_FLT", v33)
    for key in ("C10U", "C1U", "C100N"):
        two(key, None, v5, gnd)
    two("C100N", None, v33, gnd)
    c.connect("3V3_M", (u4, "VISOOUT"))
    c.connect("GND_M", (u4, "GND2"), (u4, "VSEL"))                # VSEL low: 3.3 V out
    two("BEAD", "FB1", "3V3_M", "VISO_M")
    two("BEAD", "FB2", "GND_M", "GISO_M")
    c.connect("VISO_M", (u4, "VISOIN"), (u4, "EN_IO2"))
    c.connect("GISO_M", (u4, "GISOIN"))
    for key in ("C10U", "C1U", "C100N"):
        two(key, None, "3V3_M", "GND_M")
    two("C100N", None, "VISO_M", "GISO_M")
    c.connect("BL_RX", (u4, "INA"))
    c.connect("BL_RX_M", (u4, "OUTA"))
    c.connect("BL_TX_M", (u4, "INB"))
    c.connect("BL_TX", (u4, "OUTB"))
    c.connect("ZX_M", (u4, "INC"))
    c.connect("ZX", (u4, "OUTC"))
    c.connect("OC_M", (u4, "IND"))
    c.connect("OC", (u4, "OUTD"))

    # ---- SELV 5 V: PS1 or USB, through a diode-OR ------------------------------------------------
    two("PTC5", "F3", "VPSU", "VPSU_F")                          # 1.1 A hold
    two("TVS5", "D4", "VPSU_F", gnd)                             # pad 1 = cathode
    d5 = part("SS34", "D5")
    c.connect("VPSU_F", (d5, "A"))
    c.connect(v5, (d5, "K"))
    two("C10U", None, "VPSU_F", gnd)
    j5 = part("JST5", "J5")
    for pad, net in USB_PINS.items():
        c.connect(net, (j5, pad))
    c.connect(gnd, (j5, "6"), (j5, "7"))
    two("PTC", "F4", "VBUS_IN", "VBUS")                          # 500 mA hold
    two("TVS", "D2", "VBUS", gnd)                                # pad 1 = cathode
    d6 = part("SS34", "D6")
    c.connect("VBUS", (d6, "A"))
    c.connect(v5, (d6, "K"))
    two("R5K1", None, "CC", gnd)                                 # Rd: chargers switch 5 V on
    u5 = part("ESD", "U5")
    c.connect("USB_DM", (u5, "1"), (u5, "6"))
    c.connect("USB_DP", (u5, "3"), (u5, "4"))
    c.connect("VBUS", (u5, "5"))
    c.connect(gnd, (u5, "2"))

    # ---- 3.3 V and the module (as the heatlink) --------------------------------------------------
    u2 = part("LDO", "U2")
    c.connect(v5, (u2, "VIN"), (u2, "EN"))
    c.connect(gnd, (u2, "GND"))
    c.connect(v33, (u2, "VOUT"))
    c.no_connect(u2, "NC")
    two("C10U", None, v5, gnd)
    two("C10U", None, v33, gnd)
    two("C100N", None, v33, gnd)
    u1 = part("ESP32", "U1")
    c.connect(v33, (u1, "3V3"))
    c.connect(gnd, (u1, "GND"))
    two("C10U", None, v33, gnd)
    two("C100N", None, v33, gnd)
    c.connect("EN", (u1, "EN"))
    two("R10K", None, "EN", v33)
    two("C1U", None, "EN", gnd)
    for k in ("USB_DM", "USB_DP", "BL_TX", "BL_RX", "ZX", "OC", "ISO_FLT", "UART_TX", "UART_RX"):
        c.connect(k, (u1, modpin(GPIO[k])))

    # Button (on -> off -> auto) on GPIO0, 10k pull-up; the switch's terminals A and B.
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

    # LED: WS2812B-2020 on 3V3 with 100 nF, data through 330R.
    d1 = part("LED", "D1")
    c.connect(v33, (d1, "VDD"))
    c.connect(gnd, (d1, "GND"))
    c.connect("LED_DIN", (d1, "DI"))
    c.no_connect(d1, "DO")
    two("R330", None, "LED_DIN", "LED")
    c.connect("LED", (u1, modpin(GPIO["LED"])))
    two("C100N", None, v33, gnd)

    # NTC: 10k NTC to GND under 10k to 3V3 on GPIO3 (about 1.65 V at 25 C), 100 nF across.
    c.connect("NTC", (u1, modpin(GPIO["NTC"])))
    two("NTC", "TH1", "NTC", gnd)
    two("R10K", None, "NTC", v33)
    two("C100N", None, "NTC", gnd)

    # Debug pads.
    tp = part("DEBUG", "TP1")
    for pad, net in DEBUG_PINS.items():
        c.connect(net, (tp, pad))

    # Reuse I/O: J3 and J4 as on the heatlink.
    j3, j4 = part("IO", "J3"), part("IDC", "J4")
    for pad, net in IO_PINS.items():
        c.connect(net, (j3, pad))
    for k in ("IO_SDA", "IO_SCL", "IO_4", "IO_5", "IO_6"):
        c.connect(k, (u1, modpin(GPIO[k])))
    two("R4K7", None, "IO_SDA", v33)
    two("R4K7", None, "IO_SCL", v33)
    for pad, net in HDR_PINS.items():
        c.connect(net, (j4, pad))
    for k in GPIO:
        if k.startswith("HDR_"):
            c.connect(k, (u1, modpin(GPIO[k])))

    # Mounting holes near the corners: the two in the mains strip unplated, the two in the SELV
    # strip plated, on GND.
    part("MHN", "H1")
    part("MHN", "H2")
    c.connect(gnd, (part("MH", "H3"), "1"), (part("MH", "H4"), "1"))

    # Test holes for push-in probe loops, SELV only (never the mains side or the island).
    for ref, net in TEST_HOLES.items():
        c.connect(net, (part("TESTHOLE", ref), "1"))
    return c


# Test holes: the isolator's four signals in a row below it; the supplies and the relay drive,
# each beside a GND hole one pitch (2.54 mm) away, with the LED data and button bottom right.
TEST_HOLES = {"TP2": "BL_RX", "TP3": "BL_TX", "TP4": "ZX", "TP5": "OC", "TP6": "GND",
              "TP7": "+5V", "TP8": "GND", "TP9": "+3V3",
              "TP10": "COIL", "TP11": "GND", "TP12": "LED_DIN", "TP13": "BUTTON"}


# --- placement (step 6) --------------------------------------------------------------------------
# Board 120 x 70 mm, in Martin's own printed case (PETRO-6). Mains along the top long edge, SELV
# along the bottom; cables enter at opposite ends (J1 left, J2 right).
#   Mains strip, y <= MAINS_Y: a neutral band along the top edge; a middle row (the metering
#   island, the MOV, F2); a bottom row with the live chain J1 -> F1 -> shunt -> relay COM.
#   Under the relay the mains strip goes down to RELAY_NOTCH's y, so L_SH can reach COM below NO.
#   Barrier: no copper between MAINS_Y and SELV_Y, except the barrier parts' own pads (the relay's
#   coil-to-contact gap is 17.8 mm, PS1's 38.5 mm, the ISOW7743's 7.1 mm with a slot under it).
#   SELV strip, y >= SELV_Y: the ESP32 module (antenna overhanging the bottom edge), J3 on the
#   bottom edge (a side-wall slot in the case), J4, the button and LED (through the lid), USB, the
#   relay driver, PS1's output protection.
from board.kicad_pcb import S, Slot, Track, Via, Zone, solid_pads  # noqa: E402
from board.placement import Placement, rotate  # noqa: E402

W, H = 120.0, 70.0
MAINS_Y, SELV_Y = 38.5, 46.5
RELAY_NOTCH = (60.0, 78.0, 41.5)            # x0, x1, y: the mains strip's extent under the relay
HOLES = {"H1": (4.0, 4.0), "H2": (116.0, 4.0), "H3": (4.0, 66.0), "H4": (116.0, 66.0)}
F1_CLIP_PITCH = 34.21 - 7.62                # clip centres for a 1 1/4 in fuse (Littelfuse "A")
F1_Y = 32.0
ISO_AT = (33.5, 42.5)
LED_RING = 2.0                              # mm of clear board round the LED (the light pipe's flange)

AT = {
    # mains: terminals, the live chain, F2, the MOV
    "J1": (8.0, 19.5, 90), "J2": (113.0, 19.5, 270),
    "XF1": (20.0, F1_Y, 0), "XF2": (20.0 + F1_CLIP_PITCH, F1_Y, 0),
    "RS1": (57.0, 33.5, 0), "K1": (69.0, 46.5, 90), "PS1": (86.0, 42.0, 270),
    "XF3": (62.0, 22.0, 0), "RV1": (62.0, 12.0, 180),
    # the metering island: the divider column, the BL0939 and its filters
    "R5": (18.0, 10.0, 270), "R6": (18.0, 14.8, 270), "R7": (18.0, 19.6, 270), "R8": (18.0, 24.4, 270),
    "R9": (22.0, 26.0, 0), "R10": (24.5, 13.0, 0), "C6": (24.5, 16.0, 0),
    "U3": (31.0, 19.0, 180),
    "R1": (29.05, 10.6, 90), "R2": (30.85, 10.6, 90), "R3": (32.65, 10.6, 90), "R4": (34.45, 10.6, 90),
    "C2": (29.05, 13.2, 90), "C3": (30.85, 13.2, 90), "C4": (32.65, 13.2, 90), "C5": (34.45, 13.2, 90),
    "C1": (37.5, 16.0, 90), "R11": (37.5, 21.5, 90),
    # the isolator and its island-side parts (between F1's clips, under the fuse body)
    "U4": (ISO_AT[0], ISO_AT[1], 0),
    "FB1": (29.0, 34.0, 90), "FB2": (30.5, 34.0, 90), "C11": (33.0, 34.5, 0), "C12": (36.5, 34.5, 0),
    "C13": (36.5, 32.6, 0), "C14": (33.0, 32.3, 0),
    # the isolator's SELV-side parts
    "C7": (43.0, 48.2, 0), "C8": (46.0, 48.2, 0), "C9": (48.0, 48.2, 0), "C10": (50.0, 48.2, 0),
    "R12": (52.0, 48.2, 0),
    # SELV: the module and its supply
    "U1": (16.0, 62.25, 180), "U2": (25.5, 49.0, 0),
    "C16": (17.5, 51.5, 0), "C17": (21.0, 51.5, 0), "C18": (21.0, 49.0, 0),
    "TP1": (6.0, 52.5, 0), "R14": (2.0, 49.0, 90), "C21": (3.5, 49.0, 90), "C19": (2.0, 53.0, 90),
    "C20": (3.5, 53.0, 90), "R20": (2.0, 57.0, 90), "R21": (3.5, 57.0, 90),
    # SELV: reuse I/O
    "J3": (40.0, 66.0, 0), "J4": (39.0, 56.0, 0),
    # SELV: button, LED
    "SW1": (57.9, 52.8, 0), "D1": (58.0, 59.5, 0), "C22": (56.0, 65.5, 90), "R18": (58.5, 65.5, 90),
    "R15": (61.0, 65.5, 90),
    # SELV: relay driver and NTC (below the relay)
    "Q1": (66.0, 64.5, 0), "D3": (66.0, 68.0, 0), "R16": (70.0, 64.0, 90), "R17": (71.5, 64.0, 90),
    "TH1": (74.0, 66.0, 90), "R19": (75.8, 66.0, 90), "C23": (77.0, 68.5, 0),
    # SELV: PS1's output (below PS1)
    "F3": (82.0, 67.5, 0), "D4": (88.5, 67.6, 0), "D5": (96.5, 67.6, 0), "C15": (100.8, 67.5, 90),
    # SELV: USB
    "J5": (110.0, 50.0, 0), "U5": (106.0, 56.0, 0), "F4": (111.0, 56.0, 90), "D2": (115.0, 56.0, 90),
    "D6": (110.0, 60.0, 0), "R13": (116.5, 50.0, 90),
    **{ref: (x, y, 0) for ref, (x, y) in HOLES.items()},
    # test holes (TEST_HOLES): a row under the isolator, and a 4 x 2 block bottom right
    **{f"TP{2 + k}": (41.0 + 2.54 * k, 50.2, 0) for k in range(5)},
    **{f"TP{7 + k}": (104.0 + 2.54 * k, 64.2, 0) for k in range(3)},
    **{f"TP{10 + k}": (104.0 + 2.54 * k, 66.74, 0) for k in range(4)},
}


def place_petro(c):
    missing = set(c.instances) - set(AT)
    if missing:
        raise KeyError(f"no placement for {sorted(missing)}")
    p = Placement((0.0, 0.0, W, H), {r: AT[r] for r in c.instances})
    p.courtyards = {r: i.part.body for r, i in c.instances.items()}
    return p


def slots():
    """A slot under the isolator, between its two pad rows and longer than the part, so that
    the creepage round it is more than 8 mm (checked by rules.barrier_creepage)."""
    x, y = ISO_AT
    return [Slot(x - 9.0, y, x + 9.0, y, 1.5)]


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
    x0, x1, ny = RELAY_NOTCH
    return [((0, MAINS_Y, x0, MAINS_Y), (220, 0, 0)), ((x0, MAINS_Y, x0, ny), (220, 0, 0)),
            ((x0, ny, x1, ny), (220, 0, 0)), ((x1, ny, x1, MAINS_Y), (220, 0, 0)),
            ((x1, MAINS_Y, W, MAINS_Y), (220, 0, 0)), ((0, SELV_Y, W, SELV_Y), (0, 160, 0))]


# --- the mains copper ----------------------------------------------------------------------------
# Each mains net is a solid pour on both layers, drawn as a generous polygon over its own stretch of
# the mains strip; KiCad's fill then keeps the DRU's clearances to every other net, the edges and
# the holes. Neutral is a band along the top edge with spurs down to J1, RV1, PS1 and J2; the live
# chain runs along the bottom of the strip: J1 -> F1 (XF1..XF2) -> RS1 -> K1 -> J2. Each layer's
# pour is at least half the IPC-2221 width at its narrowest (MAINS_MIN_WIDTH: KiCad's
# min_thickness drops anything thinner), so the two stitched layers together carry 16 A.
MAINS_MIN_WIDTH = HIGH_CURRENT_WIDTH / 2
CU = ("F.Cu", "B.Cu")
MAINS_POLYS = {
    "N": [(3, 3), (117, 3), (117, 19), (106, 19), (106, 8.2), (96, 8.2), (96, 23.9), (87, 23.9),
          (87, 8.2), (61, 8.2), (61, 12), (54, 12), (54, 8.2), (12, 8.2), (12, 19), (3, 19)],
    "L_IN": [(3, 21), (14, 21), (14, 28.5), (27, 28.5), (27, 35.5), (3, 35.5)],
    "L_F": [(40, 17.5), (54, 17.5), (54, 13), (69, 13), (69, 19), (57, 19), (57, 35.5), (40, 35.5)],
    "L_SH": [(57, 32.5), (62, 32.5), (62, 37.3), (77, 37.3), (77, 41.5), (60, 41.5), (60, 38.5),
             (57, 38.5)],
    "L_OUT": [(63, 26), (104, 26), (104, 20.5), (117, 20.5), (117, 38.5), (79, 38.5), (79, 36),
              (63, 36)],
    "L_PSU": [(71, 19.5), (84, 19.5), (84, 25), (71, 25)],
}
STITCH = {
    "N": [(14, 5.6), (24, 5.6), (34, 5.6), (44, 5.6), (50, 5.6), (66, 5.6), (76, 5.6), (84, 5.6),
          (100, 5.6), (9, 10), (9, 12.5), (91.5, 12), (91.5, 18), (110, 7.5), (109, 12)],
    "L_IN": [(6, 28), (11, 27), (11, 32), (20, 32), (8, 33)],
    "L_F": [(46.6, 32), (45, 24), (52, 27), (44, 19.5), (62, 16.5)],
    "L_SH": [(59, 37), (68.9, 39.6), (75.5, 40)],
    "L_OUT": [(69, 33.9), (69, 29), (85, 32), (95, 32), (105, 32), (113, 28), (110, 34)],
}
STITCH_VIA = (1.2, 0.6)                    # size, drill


def mains_zones():
    """The mains pours: every high-current net, and L_PSU (F2 to PS1), on both layers, solid."""
    return [Zone(net, CU, pts, solid=True, priority=1, clearance=0.2,
                 min_width=MAINS_MIN_WIDTH if net in HIGH_CURRENT else 0.5)
            for net, pts in MAINS_POLYS.items()]


def stitch_vias():
    size, drill = STITCH_VIA
    return [Via(net, x, y, size, drill) for net, pts in STITCH.items() for x, y in pts]


def gnd_pts():
    """The SELV ground pour's extent (both layers): the SELV strip only, so there is no ground
    pour anywhere in the mains area. The DRU keeps it 8 mm from every mains pad and pour."""
    return [(0.5, SELV_Y), (W - 0.5, SELV_Y), (W - 0.5, H - 0.5), (0.5, H - 0.5)]


def mains_pad_extra(c):
    """Every pad on a mains pour joins it solidly (no thermal relief)."""
    return solid_pads(c, set(MAINS_POLYS))


# --- routing (step 8) ----------------------------------------------------------------------------
# Freerouting runs twice, each time confined to one area: the SELV strip, then the metering
# island. Neither area comes within 8 mm of the other side's copper, so the router (which knows
# only plain clearances) can't break the barrier; KiCad's DRC with the generated rules checks
# it all afterwards. The divider chain and the shunt's Kelvin pair are routed by hand.
def pad_xy(c, p, ref, number):
    """Board position of a pad's centre."""
    x, y, rot = p.at[ref]
    pad = next(q for q in c.instances[ref].part.footprint.pads if q.number == number)
    dx, dy = rotate(pad.x, pad.y, rot)
    return round(x + dx, 4), round(y + dy, 4)


SELV_TOP = 45.2      # 8 mm (and a track's half-width) below the Kelvin pair's run at KELVIN_Y


def selv_area():
    """The SELV router's area. On the left it starts at SELV_TOP (8 mm below the Kelvin pair,
    which runs under the fuse at y = 36.9); past x = 51 it steps down round the L_SH pour's corner
    at (57, 38.5), and under the relay it keeps 8 mm below L_SH's bottom edge (41.5).
    selv_keepouts() adds the isolator's band."""
    e = 0.45
    return [(e, SELV_TOP), (51.0, SELV_TOP), (54.0, 47.0), (55.5, 49.55), (83.5, 49.55), (84.5, 47.0),
            (W - e, 47.0), (W - e, H - e), (e, H - e)]


def selv_keepouts():
    """(layer, x0, y0, x1, y1): no SELV track within 8 mm of the isolator's island-side pads
    (y <= 38.95). Its own SELV pads (from y = 46.05) are reached from below: Freerouting lets a
    track leave a pin in any direction, even out of its area, so the band must be explicit."""
    return [(layer, 19.5, SELV_TOP, 47.5, 46.75) for layer in CU]


def island_area():
    """The island router's area: the BL0939 and its filters, the isolator's island side. It keeps
    8 mm above the isolator's SELV pads (y = 38.05), clear of the divider column on the left, and
    2.5 mm (LINE to LIVE) plus a track from F1's right-hand L_IN clip pad under the fuse."""
    return [(21.2, 9.0), (39.9, 9.0), (39.9, 38.05), (27.2, 38.05), (27.2, 36.4), (28.2, 36.4),
            (28.2, 27.75), (22.4, 27.75), (22.4, 23.8), (21.2, 23.8)]


def island_keepouts():
    """(layer, x0, y0, x1, y1): no island track below the isolator's island-side pad centres,
    towards the slot and the SELV side (the pads themselves reach y = 38.95); nor out of the
    area's lower-left edges towards F1's L_IN clip (LINE to LIVE needs 2.5 mm, and Freerouting
    lets a track leave a pad in any direction: one left FB1 westwards, 2.25 mm from the clip)."""
    boxes = [(26.0, 38.25, 41.5, 43.0),           # below the isolator
             (19.0, 27.75, 28.2, 35.3),           # left of the area's lower part, down to FB1
             (19.0, 35.3, 27.2, 38.25),           # then clear of U4's pad 20 (x 27.8)
             (19.0, 23.8, 22.4, 27.75)]           # beside the step at x = 22.4
    return [(layer, *b) for layer in CU for b in boxes]


def _in_poly(x, y, poly):
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def in_selv(x, y):
    return _in_poly(x, y, selv_area()) and not any(
        x0 <= x <= x1 and y0 <= y <= y1 for _, x0, y0, x1, y1 in selv_keepouts())


def in_island(x, y):
    return _in_poly(x, y, island_area())


DIV_W = 0.4
KELVIN_W = 0.25


def divider_tracks(c, p):
    """R5..R9 in a chain: each DIV net straight from one resistor's pad to the next's, F.Cu."""
    out = []
    for net in ("DIV1", "DIV2", "DIV3", "DIV4"):
        (a, b) = sorted(c.nets[net])
        (x1, y1), (x2, y2) = pad_xy(c, p, *a), pad_xy(c, p, *b)
        out.append(Track(net, "F.Cu", x1, y1, x2, y2, DIV_W))
    return out


KELVIN_X, KELVIN_Y, KELVIN_END = 40.4, 36.9, (38.8, 14.0)


def kelvin_route(c, p):
    """(tracks, vias): the shunt's sense pair, stacked. GND_M leaves pad 2 (E1, bottom left) on
    F.Cu; SENSE leaves pad 3 (E2, top right), drops to B.Cu just above it, runs back under the
    shunt between its current pads and joins GND_M's path from below. From there they run
    together (F.Cu over B.Cu) under the fuse, up the gap between the island and F1's right clip,
    and into the island, where the router finishes them."""
    gx, gy = pad_xy(c, p, "RS1", "2")
    sx, sy = pad_xy(c, p, "RS1", "3")
    via = (sx, round(sy - 1.13, 4))
    mid = 57.0                                   # between the shunt's current pads
    common = [(gx, KELVIN_Y), (KELVIN_X, KELVIN_Y), (KELVIN_X, KELVIN_END[1]), KELVIN_END]
    seg = lambda net, layer, pts: [Track(net, layer, *a, *b, KELVIN_W) for a, b in zip(pts, pts[1:])]
    tracks = seg("SENSE", "F.Cu", [(sx, sy), via])
    tracks += seg("SENSE", "B.Cu", [via, (mid, via[1]), (mid, KELVIN_Y)] + common)
    tracks += seg("GND_M", "F.Cu", [(gx, gy)] + common)
    return tracks, [Via("SENSE", *via)]


def island_zones():
    """GND_M on both layers over the island area, below the mains pours in priority."""
    return [Zone("GND_M", CU, island_area(), priority=0, clearance=0.2, min_width=0.25)]


def pad_extra(c):
    """Per-pad additions: every mains-pour pad joins solidly; so do SMD GND and GND_M pads, the
    plated mounting holes, J3's and J4's GND pins and the GND test holes (as on the heatlink,
    where tracks otherwise leave them on one-spoke islands); U1's nine 1.2 mm centre GND pads
    get a -0.18 mm paste margin (Espressif: a full thermal pad lifts the module)."""
    def make(ref):
        def f(pad):
            net = c.net_of(ref, pad.number)
            extra = []
            if ref == "U1" and net == "GND" and abs(pad.w - 1.2) < 1e-6:
                extra.append([S("solder_paste_margin"), -0.18])
            if net in MAINS_POLYS or (net == "GND_M" and pad.kind == "smd") or (net == "GND" and (
                    pad.kind == "smd" or ref in ("H3", "H4", "J3", "J4") or ref in TEST_HOLES)):
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
IO_LABELS = {"1": "5V", "2": "G", "3": "3V3", "4": "SDA", "5": "SCL", "6": "4", "7": "5", "8": "6"}
HDR_LABELS = {n: {"+3V3": "3V3", "+5V": "5V", "GND": "G"}.get(net, net.removeprefix("HDR_"))
              for n, net in HDR_PINS.items()}
BOUNDARY_Y = (MAINS_Y + SELV_Y) / 2              # halfway across the 8 mm barrier
BOUNDARY_NOTCH_Y = (RELAY_NOTCH[2] + SELV_Y) / 2


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
            ("230 V AC", 110.5, 31.0, 1.5), ("MAINS", 110.5, 33.6, 1.5),
            ("230 V AC", 95.0, 30.0, 2.0, "B.SilkS"), ("MAINS", 95.0, 33.5, 2.0, "B.SilkS")]
    # either side of the boundary line, at the left end, on both sides
    for layer in ("F.SilkS", "B.SilkS"):
        out += [("MAINS", 12.0, BOUNDARY_Y - 1.4, 1.0, layer), ("SELV", 12.0, BOUNDARY_Y + 1.4, 1.0, layer)]
    # test holes: the row under the isolator on the back, above the holes (C7-C10 and J4 leave
    # no room in front, and J4's own labels are below);
    # the block bottom right on both sides, the top row labelled above, the bottom row below
    for ref, net in TEST_HOLES.items():
        x, y = xy(ref, "1")
        if y < 55:
            out.append((TEST_LABELS[net], x, round(y - 1.8, 3), 0.8, "B.SilkS"))
        else:
            dy = -1.7 if y < 65 else 1.65
            for layer in ("F.SilkS", "B.SilkS"):
                out.append((TEST_LABELS[net], x, round(y + dy, 3), 0.8, layer))
    # the debug pads (SMD, front only): beside each, turned to fit between the pads and U1
    for n, text in DEBUG_LABELS.items():
        x, y = xy("TP1", n)
        out.append((text, round(x + 1.45, 3), y, 0.8, "F.SilkS", 90))
    # J3 and J4 on the back (the parts cover the front)
    for n, text in IO_LABELS.items():
        x, y = xy("J3", n)
        out.append((text, x, round(y + 2.3, 3), 0.8, "B.SilkS"))
    for n, text in HDR_LABELS.items():
        x, y = xy("J4", n)
        out.append((text, x, round(y + (1.75 if int(n) % 2 else -1.75), 3), 0.8, "B.SilkS"))
    out.append(("USB", 104.5, AT["J5"][1], 0.8, "F.SilkS", 90))      # between PS1 and J5
    # the title, on the back under PS1 (no pads there)
    out += [("PETRO", 90.0, 50.5, 2.0, "B.SilkS"), ("230 V~ 10 A", 90.0, 53.5, 1.2, "B.SilkS"),
            ("nakomis 2026", 90.0, 55.7, 1.0, "B.SilkS")]
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
    hard += [(min(x0, x1) - 0.1, min(y0, y1) - 0.1, max(x0, x1) + 0.1, max(y0, y1) + 0.1)
             for x0, y0, x1, y1, layer in boundary(c, p) if layer == "F.SilkS"]
    # the fuses themselves (not parts: they sit in XF1/XF2 and XF3), placed first, on or by them
    from board.placement import bbox
    extra = [("F1 15 A", ("XF1", "XF2"), fuse_box(), 1.0), ("F2 T500 mA", ("XF3",), bbox(p, "XF3"), 0.8)]
    labels, left = place_refs(c, p, skip=UNLABELLED, hard=hard, texts=texts, extra=extra)
    if left:
        raise ValueError(f"no room for the reference labels of {left}")
    return labels


def _clip(a, b, cuts):
    """[a, b] minus the intervals in 'cuts', as a list of (lo, hi) longer than 0.5 mm."""
    out, lo = [], a
    for c0, c1 in sorted(cuts):
        if c1 <= lo or c0 >= b:
            continue
        if c0 > lo:
            out.append((lo, c0))
        lo = max(lo, c1)
    if lo < b:
        out.append((lo, b))
    return [(u, v) for u, v in out if v - u > 0.5]


def boundary(c, p, margin=0.5):
    """The mains/SELV boundary as dashed silk lines on both sides: halfway across the barrier,
    dropping under the relay's notch, broken wherever it would cross a pad, the slot or a hole,
    or (on the front) pass under a part, where it couldn't be seen and would cross the part's
    own outline."""
    from board.gnd import pad_boxes
    from board.placement import bbox
    x0, x1, _ = RELAY_NOTCH
    path = [(0.6, BOUNDARY_Y), (x0 - 4, BOUNDARY_Y), (x0 - 4, BOUNDARY_NOTCH_Y),
            (x1 + 4, BOUNDARY_NOTCH_Y), (x1 + 4, BOUNDARY_Y), (W - 0.6, BOUNDARY_Y)]
    boxes = [b[1:] for b in pad_boxes(c, p)]
    boxes += [(min(s.x1, s.x2) - s.width / 2, min(s.y1, s.y2) - s.width / 2,
               max(s.x1, s.x2) + s.width / 2, max(s.y1, s.y2) + s.width / 2) for s in slots()]
    bodies = [bbox(p, ref) for ref in c.instances]       # the parts are all on the front
    out = []
    for layer, avoid in (("F.SilkS", boxes + bodies), ("B.SilkS", boxes)):
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            if ay == by:
                cuts = [(b[0] - margin, b[2] + margin) for b in avoid if b[1] - margin < ay < b[3] + margin]
                out += [(u, ay, v, ay, layer) for u, v in _clip(min(ax, bx), max(ax, bx), cuts)]
            else:
                cuts = [(b[1] - margin, b[3] + margin) for b in avoid if b[0] - margin < ax < b[2] + margin]
                out += [(ax, u, ax, v, layer) for u, v in _clip(min(ay, by), max(ay, by), cuts)]
    return out


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
            ("230 V AC ABOVE THE DASHED LINE: 8 mm REINFORCED BARRIER", W / 2, -1.5, 0.8, "Dwgs.User")]
    return text, [(ux - 7.7, H, ux + 7.7, H + 5.05, "Dwgs.User")]


# --- hand-offs: the firmware header and the case interface -----------------------------------------
ANTENNA_OVERHANG = 5.05         # mm the module's antenna sticks out past the bottom edge


def pins_h():
    """The firmware header: GPIO numbers as wired on this board."""
    lines = ["/* Generated by pcb/build.py from board/petro_board.py: do not edit. */", "#pragma once", "",
             "/* Debug pads TP1, from the top: " + ", ".join(DEBUG_LABELS.values()) + ".",
             "   EN is the chip enable (bridge it to G to reset); RX/TX are UART0. */",
             "/* The relay is active-high (low-side FET); the button is active-low (GPIO0, also the",
             "   boot strap). ISO_FLT is low if the isolator's converter has failed. BL_TX/BL_RX are",
             "   UART1 to the BL0939 across the isolator; ZX is its zero cross, OC its fast over-current. */",
             "/* Test holes (push-in loops, SELV only, mains disconnected): "
             + ", ".join(f"{ref} {net}" for ref, net in TEST_HOLES.items()) + ". */", ""]
    for k in ("RELAY", "LED", "BUTTON", "BL_TX", "BL_RX", "ZX", "OC", "NTC", "ISO_FLT",
              "USB_DM", "USB_DP", "UART_TX", "UART_RX"):
        lines.append(f"#define PETRO_PIN_{k} {GPIO[k]}")
    lines += ["", "/* IO terminal J3: " + ", ".join(IO_LABELS.values()) + " (SDA/SCL have 4.7k pull-ups). */"]
    for k in ("IO_SDA", "IO_SCL", "IO_4", "IO_5", "IO_6"):
        lines.append(f"#define PETRO_PIN_{k} {GPIO[k]}")
    lines += ["", "/* IDC header J4 (pin: signal): "
              + ", ".join(f"{n} {t}" for n, t in HDR_LABELS.items()) + ". */"]
    for k in sorted((k for k in GPIO if k.startswith("HDR_")), key=lambda k: GPIO[k]):
        lines.append(f"#define PETRO_PIN_{k} {GPIO[k]}")
    return "\n".join(lines) + "\n"


def case_interface(c, p):
    """What the case (PETRO-6) needs from the board, as JSON, in board coordinates (mm, origin
    top-left, y down, top view): outline, holes, the LED and the light pipe's flange ring, the
    button, the connectors with the edge each faces, and the antenna overhang."""
    import json
    from board.placement import bbox
    box = lambda ref: [round(v, 3) for v in bbox(p, ref)]
    ux = AT["U1"][0]
    data = {
        "board": {"width": W, "height": H, "thickness": 1.6, "origin": "top-left, y down"},
        "holes": [{"ref": r, "x": x, "y": y, "diameter": 3.2, "plated": r in ("H3", "H4")}
                  for r, (x, y) in HOLES.items()],
        "led": {"x": AT["D1"][0], "y": AT["D1"][1], "part": "WS2812B-2020", "body": box("D1"),
                "flange_ring": [round(v, 3) for v in led_ring()],
                "note": f"{LED_RING} mm clear board round the LED for the light pipe's flange"},
        "button": {"x": AT["SW1"][0], "y": AT["SW1"][1], "part": "TS-1002 7 mm tactile", "body": box("SW1")},
        "connectors": {
            "J1": {"what": "mains in (L, N), 7.62 mm screw terminal", "edge": "left", "body": box("J1")},
            "J2": {"what": "mains out to the load (L, N)", "edge": "right", "body": box("J2")},
            "J3": {"what": "8-way 3.5 mm I/O terminal (SELV)", "edge": "bottom", "body": box("J3")},
            "J4": {"what": "16-way IDC header (SELV)", "edge": "none", "body": box("J4")},
            "J5": {"what": "USB, JST SH 5-pin (SELV)", "edge": "none", "body": box("J5")},
        },
        "tall_parts": {r: box(r) for r in ("PS1", "K1", "XF1", "XF2", "XF3", "RV1")},
        "antenna_overhang": [ux - 7.7, H, ux + 7.7, H + ANTENNA_OVERHANG],
        "mains_area": {"note": "230 V AC above the barrier: the case must keep fingers and the SELV "
                               "openings off it", "y_max": RELAY_NOTCH[2], "barrier": [MAINS_Y, SELV_Y]},
    }
    return json.dumps(data, indent=2) + "\n"
