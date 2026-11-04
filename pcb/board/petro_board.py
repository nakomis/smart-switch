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
from board.rules import Rules

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
J2_PINS = {"1": "L_OUT", "2": "N"}
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
GROUPS = {"L_IN": "LINE", "L_F": "LIVE", "L_SH": "LIVE", "L_PSU": "PSU", "N": "NEUTRAL",
          "L_OUT": "LOAD", "DIV1": "DIV1", "DIV2": "DIV2", "DIV3": "DIV3", "DIV4": "DIV4",
          **{n: "LIVE" for n in ISLAND}}
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
    two("C100N", "C22", "3V3_M", "GND_M")
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
    for pin in ("VT", "CF", "SCLK", "VPP"):                      # unused; SCLK and VPP float
        c.no_connect(u3, pin)

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
    u6 = part("ESD", "U6")
    c.connect("USB_DM", (u6, "1"), (u6, "6"))
    c.connect("USB_DP", (u6, "3"), (u6, "4"))
    c.connect("VBUS", (u6, "5"))
    c.connect(gnd, (u6, "2"))

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

    # Mounting holes (the Hammond 1591XXDBK's bosses): the two in the mains strip unplated, the
    # two in the SELV strip plated, on GND.
    part("MHN", "H1")
    part("MHN", "H2")
    c.connect(gnd, (part("MH", "H3"), "1"), (part("MH", "H4"), "1"))
    return c
