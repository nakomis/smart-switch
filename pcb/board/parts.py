"""Parts catalogue: LCSC/EasyEDA footprints and symbols (plus two local board-only footprints),
keyed by role."""
from dataclasses import dataclass
from pathlib import Path

from board.kicadlib import Footprint, load_footprint, load_symbol_pin_types, load_symbol_pins

HERE = Path(__file__).resolve().parent.parent
LCSC_FP = HERE / "footprints" / "lcsc.pretty"
LCSC_SYM = HERE / "footprints" / "lcsc.kicad_sym"
LOCAL_FP = HERE / "footprints" / "local.pretty"


@dataclass
class PartDef:
    key: str
    value: str
    lcsc: str | None         # None: a board-only footprint (test pads, mounting hole), never in BOM/CPL
    footprint: Footprint
    pins: dict
    pin_types: dict
    extended: bool
    tht: bool
    rotation_offset: float   # degrees added to placement rotation for JLCPCB CPL
    body: tuple              # (xmin, ymin, xmax, ymax): the part's real extent, for placement checks


# key: (value, lcsc, footprint file stem, symbol name, extended, rotation_offset)
# extended: JLCPCB charges a loading fee for it (an extended part; basic and "preferred extended"
# parts carry none on Economic assembly).
# Footprint stems and symbol names are exactly what easyeda2kicad wrote. lcsc None means a local,
# board-only footprint from footprints/local.pretty with pin name = pad number.
_TABLE = {
    "ESP32": ("ESP32-S3-MINI-1-N8", "C2913206", "BULETM-SMD_ESP32-S3-MINI-1-N8", "ESP32-S3-MINI-1-N8", True, 0),
    "JST5": ("SM05B-SRSS-G-TB", "C265419", "CONN-SMD_SM05B-SRSS-G-TB-LF-SN", "SM05B-SRSS-G-TB(LF)(SN)", True, 0),
    # SRV05-4 (preferred): the USBLC6-2SC6's pin layout (1/6 and 3/4 the two lines, 5 VBUS, 2 GND)
    "ESD": ("SRV05-4", "C7420376", "SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL-1", "SRV05-4_C7420376", False, 0),
    "LDO": ("AP2112K-3.3TRG1", "C51118", "SOT-25-5_L2.9-W1.6-P0.95-LS2.8-BL", "AP2112K-3.3TRG1", True, 0),
    "PTC": ("500mA PTC", "C163512", "F1206", "1206L050YR", True, 0),
    "TVS": ("SMF5.0A", "C19077497", "SOD-123FL_L2.7-W1.8-LS3.8-RD", "SMF5.0A_C19077497", False, 0),
    # SK6812-EC20 (rev B): Economic-capable, MSL 3 (the WS2812B-2020 needed Standard and baking).
    # Pins 1 VDD, 2 DOUT, 3 GND, 4 DIN: not the WS2812B's order; named DI/DO as before.
    "LED": ("SK6812-EC20", "C2909058", "LED-SMD_4P-L2.0-W2.0-BR", "SK6812-EC20", True, 0),
    "FET": ("AO3400A", "C20917", "SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR", "AO3400A", False, 0),
    "DIODE": ("1N4148W", "C81598", "SOD-123F_L2.7-W1.6-LS3.8-RD", "1N4148W_C81598", False, 0),
    "IO": ("DB125-3.5-8P-GN-S", "C5184954", "CONN-TH_8P-P3.50_DORABO_DB125-3.5-8P-GN-S", "DB125-3.5-8P-GN-S", True, 0),
    "IDC": ("DC3-2.54-16PAS", "C2977594", "IDC-TH_16P-P2.54_C3406", "DC3-2.54-16PAS", True, 0),
    "R5K1": ("5k1", "C25905", "R0402", "0402WGF5101TCE", False, 0),
    "R10K": ("10k", "C25744", "R0402", "0402WGF1002TCE", False, 0),
    "R4K7": ("4k7", "C25900", "R0402", "0402WGF4701TCE", False, 0),
    "R100K": ("100k", "C25741", "R0402", "0402WGF1003TCE", False, 0),
    "R100": ("100R", "C25076", "R0402", "0402WGF1000TCE", False, 0),
    "R330": ("330R", "C25104", "R0402", "0402WGF3300TCE", False, 0),
    "C100N": ("100nF", "C1525", "C0402", "CL05B104KO5NNNC", False, 0),
    "C1U": ("1uF", "C52923", "C0402", "CL05A105KA5NQNC", False, 0),
    "C10U": ("10uF", "C19702", "C0603", "CL10A106KP8NNNC", False, 0),
    # Petro (PETRO-2). Footprints checked against the makers' drawings, 4 Nov 2026 (DESIGN.md
    # §6.4). "local:" stems are in footprints/local.pretty (KiCad's 4-terminal WSK2512, the F1 clip).
    "RELAY16": ("HF115F-I/005-1HS3A", "C2976795", "RELAY-TH_HF115F-XXX-1HS3", "HF115F-I_005-1HS3A", True, 0),
    "PSU5W": ("IRM-05-5", "C48603696", "PWRM-TH_IRM-05-5", "IRM-05-5", True, 0),
    # ISOW7743: 4 reinforced channels (1 forward, 3 reverse) and an isolated DC-DC that powers the
    # metering island from the SELV side (TI SLLSFK1C). The LCSC stock is the F variant (outputs
    # low on lost input); the non-F ISOW7743DFMR (outputs high) is preferred, same footprint.
    "ISOW": ("ISOW7743", "C5216380", "SOIC-20_L12.8-W7.5-P1.27-LS10.3-BL", "ISOW7743FDFMR", True, 0),
    # 0603, basic (5 Nov 2026: the 0402 BLM15EX331SN1D was an extended part)
    "BEAD": ("120R@100MHz", "C14709", "L0603", "BLM18PG121SN1D_C14709", False, 0),
    "BL0939": ("BL0939", "C2836697", "SOP-16_L9.9-W3.9-P1.27-LS6.0-BL", "BL0939", True, 0),
    # F1: two clips per fuse, one footprint each (so the BOM counts two). EasyEDA has none.
    "FUSECLIP": ("6.35mm fuse clip 30A", "C206903", "local:FuseClip_Littelfuse_0122_6.35mm", None, True, 0),
    "FUSEHOLD": ("5x20 holder", "C187510", "FUSE-TH_65600001009", "65600001009", True, 0),
    "MOV": ("TMOV20RP275E", "C187710", "RES-TH_L23.0-W9.5-P8.50-D0.9-S4.50", "TMOV20RP275E", True, 0),
    "SHUNT": ("1mR", "C4248455", "local:R_Shunt_Vishay_WSK2512_6332Metric_T2.21mm", None, True, 0),
    "MAINSTERM": ("DG636-7.62-02P", "C2827897", "CONN-TH_DG636-7.62-02P-14-02A-H", "DG636-7.62-02P-14-02A(H)", True, 0),
    "SS34": ("SS34", "C8678", "SMA_L4.3-W2.6-LS5.2-RD", "SS34_C8678", False, 0),
    "PTC5": ("1.1A PTC", "C126818", "F1206", "1206L110THYR", True, 0),
    "TVS5": ("SMAJ5.0A", "C2925443", "SMA_L4.3-W2.6-LS5.0-RD", "SMAJ5.0A_C2925443", False, 0),
    "TACT": ("TS-1002 7mm", "C455095", "SW-TH_4P-L6.0-W6.0-P4.50-LS6.5_TS-1002-07026", "TS-1002-07026", True, 0),
    "NTC": ("10k NTC", "C2892547", "R0603", "KNTC0603_10KF3950", True, 0),
    "R390K": ("390k", "C17933", "R1206", "1206W4F3903T5E", True, 0),
    "R470": ("470R", "C25117", "R0402", "0402WGF4700TCE", False, 0),      # 61 mV: any size
    "R1K": ("1k", "C11702", "R0402", "0402WGF1001TCE", False, 0),
    # Revision B (non-isolated) supply: PI's LNK306 high-side buck (LNK302/304-306 datasheet,
    # Figure 5 and Component Selection), 12 V, then TI's TPS563201 12 V -> 5 V (datasheet 8.2).
    "LNK306": ("LNK306DN", "C34318", "SOIC-8_7P-L4.9-W3.9-P1.27-LS6.0-BL-PE3", "LNK306DN", True, 0),
    "RFUSE": ("10R 2W fusible", "C1394194", "local:R_Axial_FKN2WS_P15.24mm", None, True, 0),
    # JLCPCB basic (5 Nov 2026): M7 (1 kV 1 A, standard recovery) for the rectifier and the
    # feedback diode (PI's datasheet uses a 1N4005GP there); US1M (1 kV, 75 ns) for the freewheel
    # (PI: 75 ns or faster in MDCM)
    "RECT": ("M7", "C95872", "SMA_L4.3-W2.6-LS5.2-RD", "M7_C95872", False, 0),
    "FASTREC": ("US1M", "C412437", "SMA_L4.4-W2.8-LS5.4-RD", "US1MG_C412437", False, 0),
    "C4U7HV": ("4.7uF 400V", "C112482", "CAP-TH_BD8.0-P3.50-D0.6-FD", "EGW2GM4R7F12OT", True, 0),
    "L1MF": ("1mH 350mA", "C168102", "IND-SMD_L6.0-W6.0_FNR60XXS", "FNR6045S102MT", True, 0),
    "L680U": ("680uH 1A", "C48934988", "IND-SMD_L10.0-W10.0_ABG10A50M4R7", "NR1050M681N", True, 0),
    "C220U": ("220uF 25V", "C4747974", "CAP-SMD_BD6.3-L6.6-W6.6-LS7.2-FD", "RST220UF25V019", True, 0),
    "C100N6": ("100nF", "C14663", "C0603", "CC0603KRX7R9BB104", False, 0),
    "C10U50": ("10uF 50V", "C13585", "C1206", "CL31A106KBHNNNE", False, 0),
    "R13K": ("13k", "C22797", "R0603", "0603WAF1302T5E", False, 0),
    "R2K": ("2k", "C22975", "R0603", "0603WAF2001T5E", False, 0),
    "R3K3": ("3k3", "C22978", "R0603", "0603WAF3301T5E", False, 0),
    "BUCK": ("TPS563201", "C116592", "SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BR", "TPS563201DDCR", True, 0),
    "R56K": ("56k", "C23206", "R0603", "0603WAF5602T5E", False, 0),
    "R10K6": ("10k", "C25804", "R0603", "0603WAF1002T5E", False, 0),
    "L3U3": ("3.3uH", "C602030", "IND-SMD_L4.0-W4.0", "FHD4020S-3R3MT", True, 0),
    "C22U": ("22uF 25V", "C12891", "C1206", "CL31A226KAHNNNE", False, 0),
    "C33N": ("33nF", "C21117", "C0603", "CL10B333KB8NNNC", False, 0),     # X7R, basic
    # Rev B, 5 Nov 2026: the ESP32-C6 (Economic: the S3-MINI needs X-ray, so Standard) and the safe
    # I/O island on J3, across TI's reinforced isolators in the wide (DW) body: ISO7741 (SPI, 3
    # forward / 1 reverse), ISO1640 (I2C); the ISOW7743 above powers the island and carries IN/OUT.
    # local: EasyEDA's footprint (WIRELM-SMD_ESP32-C6-WROOM-1) less its 12 unnumbered 0.5 mm
    # thermal vias, which had no net and paste and mask open on both sides (solder would wick)
    "ESP32C6": ("ESP32-C6-WROOM-1-N8", "C5366877", "local:ESP32-C6-WROOM-1_NoThermalVias",
                "ESP32-C6-WROOM-1-N8", True, 0),
    "ISO7741": ("ISO7741DWR", "C571196", "SOIC-16_L10.3-W7.5-P1.27-LS10.3-BL", "ISO7741DWR", True, 0),
    "ISO1640": ("ISO1640DWR", "C5216237", "SOIC-16_L10.3-W7.5-P1.27-LS10.3-BL", "ISO1640DWR", True, 0),
    "IO10": ("DB125-3.5-10P-GN-S", "C5184956", "CONN-TH_10P-P3.50_DIBO_DB125-3.5-10P-GN-S",
             "DB125-3.5-10P-GN-S", True, 0),
    "DEBUG": ("Debug pads", None, "DebugPads_1x5_P2.54", None, False, 0),
    "MH": ("M3 hole", None, "MountingHole_M3_3.2mm_Pad6", None, False, 0),
    "MHN": ("M3 hole, unplated", None, "MountingHole_M3_3.2mm_NPTH", None, False, 0),
    # JLCPCB's assembly tooling hole, placed by us ("Added by Customer") so it lands clear of mains copper
    "TOOLING": ("tooling hole", None, "ToolingHole_1.152mm_NPTH", None, False, 0),
    # A bare plated hole for Martin's push-in ceramic test loops (inserted, never soldered).
    "TESTHOLE": ("test hole", None, "TestHole_0.8mm", None, False, 0),
}
TESTHOLE_DRILL = 0.8      # mm: both legs (0.3-0.35 mm wire, sprung 1.2 mm apart) squeezed into one hole

# Manufacturer and part number for each assembled part, for PCBWay's BOM (JLCPCB's takes the LCSC
# number alone). PCBWay buys parts anywhere, so the LCSC number goes in the notes as a source.
MFR = {
    "ESP32": ("Espressif", "ESP32-S3-MINI-1-N8"), "JST5": ("JST", "SM05B-SRSS-G-TB(LF)(SN)"),
    "ESD": ("hongjiacheng", "SRV05-4"), "LDO": ("Diodes Inc", "AP2112K-3.3TRG1"),
    "PTC": ("Littelfuse", "1206L050YR"), "TVS": ("hongjiacheng", "SMF5.0A"),
    "LED": ("OPSCO", "SK6812-EC20"), "FET": ("Alpha & Omega", "AO3400A"),
    "DIODE": ("Semtech", "1N4148W"), "IO": ("DORABO", "DB125-3.5-8P-GN-S"),
    "IDC": ("ZHOURI", "DC3-2.54-16PAS"),
    "R4K7": ("UNI-ROYAL", "0402WGF4701TCE"),
    "R5K1": ("UNI-ROYAL", "0402WGF5101TCE"), "R10K": ("UNI-ROYAL", "0402WGF1002TCE"),
    "R100K": ("UNI-ROYAL", "0402WGF1003TCE"), "R100": ("UNI-ROYAL", "0402WGF1000TCE"),
    "R330": ("UNI-ROYAL", "0402WGF3300TCE"), "C100N": ("Samsung", "CL05B104KO5NNNC"),
    "C1U": ("Samsung", "CL05A105KA5NQNC"), "C10U": ("Samsung", "CL10A106KP8NNNC"),
    "RELAY16": ("Hongfa", "HF115F-I/005-1HS3A"), "PSU5W": ("Mean Well", "IRM-05-5"),
    "ISOW": ("Texas Instruments", "ISOW7743DFMR"), "BEAD": ("Murata", "BLM18PG121SN1D"),
    "BL0939": ("Shanghai Belling", "BL0939"), "FUSEHOLD": ("Littelfuse", "65600001009"),
    "FUSECLIP": ("Littelfuse", "01220088Z"),
    "MOV": ("Littelfuse", "TMOV20RP275E"), "SHUNT": ("Vishay", "WSK25121L000FEA"),
    "MAINSTERM": ("Degson", "DG636-7.62-02P-14-02A(H)"), "SS34": ("MDD", "SS34"),
    "PTC5": ("Littelfuse", "1206L110THYR"), "TVS5": ("Liown", "SMAJ5.0A"),
    "TACT": ("XUNPU", "TS-1002-07026"), "NTC": ("KUU", "KNTC0603/10KF3950"),
    "R390K": ("UNI-ROYAL", "1206W4F3903T5E"), "R470": ("UNI-ROYAL", "0402WGF4700TCE"),
    "R1K": ("UNI-ROYAL", "0402WGF1001TCE"), "C33N": ("Samsung", "CL10B333KB8NNNC"),
    "LNK306": ("Power Integrations", "LNK306DN-TL"), "RFUSE": ("Yageo", "FKN2WSJT-52-10R"),
    "RECT": ("MDD", "M7"), "FASTREC": ("MDD", "US1MG"), "C4U7HV": ("AISHI", "EGW2GM4R7F12OT"),
    "L1MF": ("cjiang", "FNR6045S102MT"), "L680U": ("COILANK", "NR1050M681N"),
    "C220U": ("KNSCHA", "RST220UF25V019"), "C100N6": ("Yageo", "CC0603KRX7R9BB104"),
    "C10U50": ("Samsung", "CL31A106KBHNNNE"), 
    "R13K": ("UNI-ROYAL", "0603WAF1302T5E"), "R2K": ("UNI-ROYAL", "0603WAF2001T5E"),
    "R3K3": ("UNI-ROYAL", "0603WAF3301T5E"), "BUCK": ("Texas Instruments", "TPS563201DDCR"),
    "R56K": ("UNI-ROYAL", "0603WAF5602T5E"), "R10K6": ("UNI-ROYAL", "0603WAF1002T5E"),
    "L3U3": ("cjiang", "FHD4020S-3R3MT"), "C22U": ("Samsung", "CL31A226KAHNNNE"),
    "ESP32C6": ("Espressif", "ESP32-C6-WROOM-1-N8"), "ISO7741": ("Texas Instruments", "ISO7741DWR"),
    "ISO1640": ("Texas Instruments", "ISO1640DWR"), "IO10": ("DORABO", "DB125-3.5-10P-GN-S"),
}

# fetched-name -> our-name, per key. The module symbol calls GPIOn "IOn" and spells the UART0 pins
# TXD0/RXD0 (GPIO43/44), exactly as Espressif's datasheet table does; we keep those names.
#
# The relay (Hongfa's PCB layout, bottom view): the coil pair at one end; at the other, two columns
# of two paralleled pins, COM the inner column (the arm's pivot) and NO the outer. The shunt
# (Vishay WSK2512, KiCad's pad numbers): current pads I1/I2, and each end's sense pad E1/E2 on the
# opposite long edge (diagonal), E1 beside I1.
ALIASES = {
    "RELAY16": {"1": "COIL1", "2": "COIL2", "5": "COM", "6": "COM", "7": "NO", "8": "NO"},
    "SHUNT": {"1": "I1", "2": "E1", "3": "E2", "4": "I2"},
    "PSU5W": {"V+": "+V", "V-": "-V"},
    # XUNPU TS-1002 circuit diagram: the pins 6.5 mm apart are joined inside; the button closes
    # between the two pairs (4.5 mm apart).
    "TACT": {"1": "A", "2": "A", "3": "B", "4": "B"},
    # the preferred TVS diodes name their pins K/A; pad 1 is the cathode, as before
    "TVS": {"K": "1", "A": "2"}, "TVS5": {"K": "1", "A": "2"},
    # rev B: the electrolytics' pad 1 is positive (silk '+', chamfered base); S1G calls its cathode C
    "C4U7HV": {"1": "+", "2": "-"}, "C220U": {"1": "+", "2": "-"}, "FASTREC": {"C": "K"},
    "LED": {"DIN": "DI", "DOUT": "DO"},
}

# Real extents where the footprint's courtyard is smaller than the part. The EasyEDA module
# footprint's courtyard covers only the pad field (15.4 x 15.4); the module is 15.4 x 20.5 with
# the PCB antenna in the 5.05 mm beyond pads 46-60 (its silkscreen outline: y -12.8 .. 7.7).
# The connectors: their bodies, from the footprints' silk outlines and the datasheets (the EasyEDA
# courtyards are the pad fields).
BODY = {"ESP32": (-7.7, -12.8, 7.7, 7.7),
        "JST5": (-3.9, -2.79, 3.9, 3.16),      # tabs x +-3.9, signal pads to y -2.79, housing front 2.83
        "IO": (-14.0, -3.9, 14.0, 3.5),         # wire openings on the +y side
        "IDC": (-14.25, -4.52, 14.25, 4.5),     # the shroud; its key slot is on the +y side
        # Mean Well drawings (pins located from the body edges, mirrored to the top view): the
        # IRM-05's body runs well past its pins on the -y side.
        "PSU5W": (-22.85, -16.57, 22.85, 8.83),   # 45.7 x 25.4
        "RELAY16": (-14.5, -6.35, 14.5, 6.35),    # 29 x 12.7, pin field taken as centred (checked at placement)
        "MOV": (-11.5, -4.75, 11.5, 4.75),        # 23 mm disc (max), 9.5 mm thick, standing on edge
        # Degson DG636, from its silk outline: the wire openings are on the +y side
        "MAINSTERM": (-7.62, -4.6, 7.62, 7.9),
        # rev B supply, from the footprints' silk outlines (EasyEDA's courtyards are the pad fields)
        "FUSEHOLD": (-12.5, -4.95, 12.5, 4.95),   # Littelfuse 656 holder, 25 x 9.9
        "C4U7HV": (-4.0, -4.0, 4.0, 4.0),         # 8 mm can
        "C220U": (-4.45, -3.4, 4.45, 3.4),        # 6.6 mm base, pads to +-4.45
        "L680U": (-5.55, -5.0, 5.55, 5.0),        # 10 mm square, pads to +-5.55
        # the C6-WROOM-1, 18 x 25.5, from its silk outline: the PCB antenna on the -y side, past
        # the top pad row (EasyEDA's courtyard is the pad field)
        "ESP32C6": (-9.0, -15.75, 9.0, 9.85),
        "IO10": (-17.5, -3.9, 17.5, 3.5)}         # as the 8-way, two pitches longer
# The antenna strip of the module, in footprint coordinates (above the top pad row).
ESP32_ANTENNA = (-7.7, -12.8, 7.7, -7.75)
ESP32C6_ANTENNA = (-9.0, -15.75, 9.0, -9.25)

# 3D models (fetch_models.sh puts them in footprints/lcsc.3dshapes). Each EasyEDA footprint names its
# model and carries its offset and rotation; parts whose footprint names none get one here.
LCSC_3D = HERE / "footprints" / "lcsc.3dshapes"
# Assembled parts with no 3D model anywhere (EasyEDA has none, and nor does KiCad's library). The
# STEP export shows them as bare pads; the case design (PETRO-6) takes their heights from DESIGN.md.
NO_MODEL = {"FUSECLIP"}
MODEL_OVERRIDE = {
                  "SHUNT": "R2512_L6.3-W3.2-H0.6"}          # EasyEDA's (C4248455) on KiCad's footprint
# Model offsets (x, y, z in mm, KiCad's model frame) that replace easyeda2kicad's where its are
# wrong, found from top and side renders: the SOT-23-6 and C0603 offsets push the bodies off their
# pads, the JST model's origin is 2 mm off its centre, and the capacitor models are centred on
# z = 0 (half inside the board), so they are lifted by half their height. The IDC header's model
# origin is 11.43 mm (4.5 pitches) and 4.57 mm off the footprint's centre.
MODEL_OFFSET = {"MAINSTERM": (-7.62, -7.9, 0), "RELAY16": (-0.7, 0, 15.7), "FUSEHOLD": (7.2, -14.7, 5.25), "ESD": (0, 0, 0), "JST5": (-2.0, -0.33, 0), "IDC": (-11.43, -4.47, 0),
                "C10U": (0, 0, 0.4), "C100N": (0, 0, 0.25), "C1U": (0, 0, 0.25)}


def _load(key, row):
    value, lcsc, fp_stem, sym, extended, rot = row
    local = fp_stem.startswith("local:") or not lcsc
    fp = load_footprint((LOCAL_FP if local else LCSC_FP) / f"{fp_stem.removeprefix('local:')}.kicad_mod")
    pins = {}
    alias = ALIASES.get(key, {})
    if sym is None:     # footprint-only part: one passive pin per numbered pad, name = number
        for p in fp.pads:
            names = pins.setdefault(alias.get(p.number, p.number), []) if p.number else None
            if p.number and p.number not in names:       # a pad number may repeat (a clip's legs)
                names.append(p.number)
        pin_types = {p.number: "passive" for p in fp.pads if p.number}
    else:
        for name, nums in load_symbol_pins(LCSC_SYM, sym).items():
            pins.setdefault(alias.get(name, name), []).extend(nums)
        pin_types = load_symbol_pin_types(LCSC_SYM, sym)
    # Through-hole only if most numbered signal pads are drilled.
    numbered = [p for p in fp.pads if p.number]
    tht = bool(numbered) and sum(p.kind == "thru_hole" for p in numbered) * 2 > len(numbered)
    return PartDef(key, value, lcsc, fp, pins, pin_types, extended, tht, rot, BODY.get(key, fp.courtyard))


# Extended parts whose CPL rotation offset has been checked. EasyEDA-fetched footprints follow
# JLCPCB's own orientation convention, so their offset is 0. The final check is a look at
# JLCPCB's placement preview at order time.
ROTATION_CHECKED = {k for k, row in _TABLE.items() if row[4] and row[5] == 0}

PARTS = {k: _load(k, row) for k, row in _TABLE.items()}


def part(key):
    return PARTS[key]
