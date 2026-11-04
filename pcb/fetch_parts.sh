#!/usr/bin/env bash
# Fetch footprints + symbols for every LCSC part into footprints/lcsc.*
set -euo pipefail
cd "$(dirname "$0")"
PARTS=(
  C2913206  # ESP32 (ESP32-S3-MINI-1-N8)
  C265419   # JST5 (SM05B-SRSS-G-TB)
  C51118    # LDO (AP2112K-3.3TRG1)
  C163512   # PTC (1206L050YR)
  C52917434 # LED (WS2812B-2020-V6)
  C20917    # FET (AO3400A)
  C81598    # DIODE (1N4148W)
  C5184954  # IO (DB125-3.5-8P-GN-S, 8-way 3.5 mm screw terminal)
  # Petro's own (PETRO-2). Safety-critical parts are bought from authorised distributors; these
  # LCSC numbers are for the footprints and for parts the fab may place.
  C2976795  # RELAY16 (Hongfa HF115F-I/005-1HS3A, 16 A, reinforced coil-contact)
  C48603696 # PSU5W (Mean Well IRM-05-5)
  C5216380  # ISOW (TI ISOW7743FDFMR; the non-F ISOW7743DFMR shares the footprint and is preferred)
  C2836697  # BL0939 (SOP-16)
  C187510   # FUSEHOLD (Littelfuse 656 holder, 65600001009, for F2)
  C187710   # MOV (Littelfuse TMOV20RP275E)
  C4248455  # SHUNT (Vishay WSK25121L000FEA, 1 mOhm Kelvin)
  C2827897  # MAINSTERM (Degson DG636-7.62-02P)
  C8678     # SS34 (diode-OR)
  C126818   # PTC5 (1206L110THYR, 1.1 A hold)
  C455095   # TACT (TS-1002, 7 mm)
  C2892547  # NTC (10 k, 0603)
  C17933    # R390K (1206, 200 V: the voltage divider, five in series)
  C596498   # BEAD (Murata BLM15EX331SN1D, 330 R at 100 MHz, 700 mA: TI's ISOW774x beads)
  C11702    # R1K (0402: the BL0939 input filters)
  C2977594  # IDC (DC3-2.54-16PAS, 16-way boxed header)
  C25905    # R5K1
  C25744    # R10K
  C25900    # R4K7 (I2C pull-ups on the IO terminal)
  C25104    # R330 (LED data series resistor)
  C25076    # R100 (relay FET gate)
  C25741    # R100K (relay FET gate pull-down)
  C1525     # C100N
  C52923    # C1U
  C19702    # C10U
  # JLCPCB basic / preferred swaps (no loading fee on Economic assembly), 4 Nov 2026
  C21117    # C33N (Samsung CL10B333KB8NNNC, 0603 X7R, basic)
  C25117    # R470 (0402WGF4700TCE, basic)
  C19077497 # TVS (SMF5.0A, preferred)
  C2925443  # TVS5 (SMAJ5.0A, preferred)
  C7420376  # ESD (SRV05-4, preferred: same SOT-23-6 layout as the USBLC6-2SC6)
  # Revision B (non-isolated), 4 Nov 2026: PI's LNK306 high-side buck (datasheet Figure 5, 12 V),
  # the 12 V -> 5 V converter (TI TPS563201, datasheet section 8.2), and the SK6812-EC20 LED
  C34318    # LNK306DN-TL (SO-8C)
  C1394194  # RF1: Yageo FKN2WSJT-52-10R, 10 R 2 W fusible flameproof (the 8.2 R C3405813 has no EasyEDA data)
  C144860   # D3: Vishay S1M-E3, 1 A 1 kV rectifier
  C112482   # C4/C5: AISHI EGW2GM4R7F12OT, 4.7 uF 400 V 105 C
  C168102   # L2: 1 mH 350 mA pi-filter inductor
  C232830   # D1: onsemi ES1J, 600 V 1 A ultrafast (35 ns)
  C37485    # L1: SXN SMDRI127-102MT, 1 mH, Isat 1 A
  C4747974  # C2: 220 uF 25 V
  C14663    # 100 nF 0603 50 V (BYPASS, TPS563201 boot)
  C13585    # 10 uF 50 V 1206 (feedback hold, buck input)
  C85102    # D2: Diodes Inc S1G-13-F, glass passivated
  C22797    # 13k 0603 (LNK feedback, top)
  C22975    # 2k 0603 (LNK feedback, bottom)
  C22978    # 3k3 0603 (LNK pre-load)
  C116592   # TPS563201DDCR, 12 V -> 5 V
  C23077    # 54k9 0603 (TPS563201 feedback, top)
  C25804    # 10k 0603 (TPS563201 feedback, bottom)
  C602030   # 3.3 uH 4x4 (TPS563201)
  C12891    # 22 uF 25 V 1206 (TPS563201 output)
  C2909058  # SK6812-EC20 LED
)
# easyeda.com's CloudFront returns 403 for easyeda2kicad's default User-Agent, so run it
# through a one-line wrapper that sends a neutral UA instead.
FAILED=()
for c in "${PARTS[@]}"; do
  # resumable: skip parts whose symbol is already in the library
  grep -q "\"$c\"" footprints/lcsc.kicad_sym 2>/dev/null && continue
  sleep 20   # be polite: easyeda.com rate-limits bursts with a 403
  .venv/bin/python -c '
import sys
from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
_init = EasyedaApi.__init__
def init(self):
    _init(self)
    self.headers["User-Agent"] = "petro-board-fetch"
EasyedaApi.__init__ = init
from easyeda2kicad.__main__ import main
sys.argv[0] = "easyeda2kicad"
sys.exit(main())
' --symbol --footprint --lcsc_id="$c" --output footprints/lcsc --overwrite || FAILED+=("$c")
done
if ((${#FAILED[@]})); then echo "FAILED: ${FAILED[*]}" >&2; exit 1; fi
