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
# Footprint stems and symbol names are exactly what easyeda2kicad wrote. lcsc None means a local,
# board-only footprint from footprints/local.pretty with pin name = pad number.
_TABLE = {
    "ESP32": ("ESP32-S3-MINI-1-N8", "C2913206", "BULETM-SMD_ESP32-S3-MINI-1-N8", "ESP32-S3-MINI-1-N8", True, 0),
    "JST5": ("SM05B-SRSS-G-TB", "C265419", "CONN-SMD_SM05B-SRSS-G-TB-LF-SN", "SM05B-SRSS-G-TB(LF)(SN)", True, 0),
    "ESD": ("USBLC6-2SC6", "C7519", "SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL", "USBLC6-2SC6", True, 0),
    "LDO": ("AP2112K-3.3TRG1", "C51118", "SOT-25-5_L2.9-W1.6-P0.95-LS2.8-BL", "AP2112K-3.3TRG1", True, 0),
    "PTC": ("500mA PTC", "C163512", "F1206", "1206L050YR", True, 0),
    "TVS": ("SMF5.0A", "C151296", "SOD-123F_L2.8-W1.8-LS3.7-RD", "SMF5.0A_C151296", True, 0),
    "LED": ("WS2812B-2020-V6", "C52917434", "LED-SMD_4P-L2.2-W2.0-P1.00_WS2815C-2020-4P", "WS2812B-2020-V6", True, 0),
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
    # §6.4). "local:" stems are in footprints/local.pretty: KiCad's 4-terminal WSK2512, and the
    # IRM-01 with its peg holes unplated and centred (EasyEDA's are plated, zero ring, off centre).
    "RELAY16": ("HF115F-I/005-1HS3A", "C2976795", "RELAY-TH_HF115F-XXX-1HS3", "HF115F-I_005-1HS3A", True, 0),
    "PSU5W": ("IRM-05-5", "C48603696", "PWRM-TH_IRM-05-5", "IRM-05-5", True, 0),
    "PSU1W": ("IRM-01-5", "C5656515", "local:PWRM-TH_IRM-01_MeanWell", "IRM-01-5", True, 0),
    "ISO": ("ISO7741DWR", "C571196", "SOIC-16_L10.3-W7.5-P1.27-LS10.3-BL", "ISO7741DWR", True, 0),
    "BL0939": ("BL0939", "C2836697", "SOP-16_L9.9-W3.9-P1.27-LS6.0-BL", "BL0939", True, 0),
    "FUSEHOLD": ("5x20 holder", "C187510", "FUSE-TH_65600001009", "65600001009", True, 0),
    "MOV": ("TMOV20RP275E", "C187710", "RES-TH_L23.0-W9.5-P8.50-D0.9-S4.50", "TMOV20RP275E", True, 0),
    "SHUNT": ("1mR", "C4248455", "local:R_Shunt_Vishay_WSK2512_6332Metric_T2.21mm", None, True, 0),
    "MAINSTERM": ("DG636-7.62-02P", "C2827897", "CONN-TH_DG636-7.62-02P-14-02A-H", "DG636-7.62-02P-14-02A(H)", True, 0),
    "SS34": ("SS34", "C8678", "SMA_L4.3-W2.6-LS5.2-RD", "SS34_C8678", False, 0),
    "PTC5": ("1.1A PTC", "C126818", "F1206", "1206L110THYR", True, 0),
    "TVS5": ("SMAJ5.0A", "C113952", "SMA_L4.4-W2.6-LS5.0-RD", "SMAJ5.0A_C113952", True, 0),
    "TACT": ("TS-1002 7mm", "C455095", "SW-TH_4P-L6.0-W6.0-P4.50-LS6.5_TS-1002-07026", "TS-1002-07026", True, 0),
    "NTC": ("10k NTC", "C2892547", "R0603", "KNTC0603_10KF3950", True, 0),
    "R390K": ("390k", "C17933", "R1206", "1206W4F3903T5E", True, 0),
    "R470": ("470R", "C4502", "R1206", None, True, 0),
    "DEBUG": ("Debug pads", None, "DebugPads_1x5_P2.54", None, False, 0),
    "MH": ("M3 hole", None, "MountingHole_M3_3.2mm_Pad6", None, False, 0),
    "MHN": ("M3 hole, unplated", None, "MountingHole_M3_3.2mm_NPTH", None, False, 0),
}

# Manufacturer and part number for each assembled part, for PCBWay's BOM (JLCPCB's takes the LCSC
# number alone). PCBWay buys parts anywhere, so the LCSC number goes in the notes as a source.
MFR = {
    "ESP32": ("Espressif", "ESP32-S3-MINI-1-N8"), "JST5": ("JST", "SM05B-SRSS-G-TB(LF)(SN)"),
    "ESD": ("STMicroelectronics", "USBLC6-2SC6"), "LDO": ("Diodes Inc", "AP2112K-3.3TRG1"),
    "PTC": ("Littelfuse", "1206L050YR"), "TVS": ("Littelfuse", "SMF5.0A"),
    "LED": ("Worldsemi", "WS2812B-2020-V6"), "FET": ("Alpha & Omega", "AO3400A"),
    "DIODE": ("Semtech", "1N4148W"), "IO": ("DORABO", "DB125-3.5-8P-GN-S"),
    "IDC": ("ZHOURI", "DC3-2.54-16PAS"),
    "R4K7": ("UNI-ROYAL", "0402WGF4701TCE"),
    "R5K1": ("UNI-ROYAL", "0402WGF5101TCE"), "R10K": ("UNI-ROYAL", "0402WGF1002TCE"),
    "R100K": ("UNI-ROYAL", "0402WGF1003TCE"), "R100": ("UNI-ROYAL", "0402WGF1000TCE"),
    "R330": ("UNI-ROYAL", "0402WGF3300TCE"), "C100N": ("Samsung", "CL05B104KO5NNNC"),
    "C1U": ("Samsung", "CL05A105KA5NQNC"), "C10U": ("Samsung", "CL10A106KP8NNNC"),
    "RELAY16": ("Hongfa", "HF115F-I/005-1HS3A"), "PSU5W": ("Mean Well", "IRM-05-5"),
    "PSU1W": ("Mean Well", "IRM-01-5"), "ISO": ("Texas Instruments", "ISO7741DWR"),
    "BL0939": ("Shanghai Belling", "BL0939"), "FUSEHOLD": ("Littelfuse", "65600001009"),
    "MOV": ("Littelfuse", "TMOV20RP275E"), "SHUNT": ("Vishay", "WSK25121L000FEA"),
    "MAINSTERM": ("Degson", "DG636-7.62-02P-14-02A(H)"), "SS34": ("MDD", "SS34"),
    "PTC5": ("Littelfuse", "1206L110THYR"), "TVS5": ("MDD", "SMAJ5.0A"),
    "TACT": ("XUNPU", "TS-1002-07026"), "NTC": ("KUU", "KNTC0603/10KF3950"),
    "R390K": ("UNI-ROYAL", "1206W4F3903T5E"), "R470": ("UNI-ROYAL", "1206W4F4700T5E"),
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
        "PSU1W": (-16.85, -11.1, 16.85, 11.1),    # 33.7 x 22.2
        "RELAY16": (-14.5, -6.35, 14.5, 6.35),    # 29 x 12.7, pin field taken as centred (checked at placement)
        "MOV": (-11.5, -4.75, 11.5, 4.75)}        # 23 mm disc (max), 9.5 mm thick, standing on edge
# The antenna strip of the module, in footprint coordinates (above the top pad row).
ESP32_ANTENNA = (-7.7, -12.8, 7.7, -7.75)

# 3D models (fetch_models.sh puts them in footprints/lcsc.3dshapes). Each EasyEDA footprint names its
# model and carries its offset and rotation; parts whose footprint names none get one here.
# WS2812B-2020-V6 (C52917434) has no EasyEDA model: the WS2812B-2020 one (C965555) is the same
# 2.0 x 2.0 x 0.8 mm package, and its footprint has the same pin 1-4 layout as ours to within
# 0.05 mm, with zero model offset and rotation.
LCSC_3D = HERE / "footprints" / "lcsc.3dshapes"
MODEL_OVERRIDE = {"LED": "LED-SMD_4P-L2.0-W2.0-H0.8-TL_WS2812B-2020",
                  "SHUNT": "R2512_L6.3-W3.2-H0.6"}          # EasyEDA's (C4248455) on KiCad's footprint
# Model offsets (x, y, z in mm, KiCad's model frame) that replace easyeda2kicad's where its are
# wrong, found from top and side renders: the SOT-23-6 and C0603 offsets push the bodies off their
# pads, the JST model's origin is 2 mm off its centre, and the capacitor models are centred on
# z = 0 (half inside the board), so they are lifted by half their height. The IDC header's model
# origin is 11.43 mm (4.5 pitches) and 4.57 mm off the footprint's centre.
MODEL_OFFSET = {"ESD": (0, 0, 0), "JST5": (-2.0, -0.33, 0), "IDC": (-11.43, -4.47, 0),
                "C10U": (0, 0, 0.4), "C100N": (0, 0, 0.25), "C1U": (0, 0, 0.25)}


def _load(key, row):
    value, lcsc, fp_stem, sym, extended, rot = row
    local = fp_stem.startswith("local:") or not lcsc
    fp = load_footprint((LOCAL_FP if local else LCSC_FP) / f"{fp_stem.removeprefix('local:')}.kicad_mod")
    pins = {}
    alias = ALIASES.get(key, {})
    if sym is None:     # footprint-only part: one passive pin per numbered pad, name = number
        for p in fp.pads:
            if p.number:
                pins.setdefault(alias.get(p.number, p.number), []).append(p.number)
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
