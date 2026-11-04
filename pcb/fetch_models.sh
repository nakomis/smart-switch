#!/usr/bin/env bash
# Fetch the 3D models (STEP + WRL) for every LCSC part into footprints/lcsc.3dshapes/.
# They are large (the module's STEP alone is megabytes), so they are not committed: build.py --step
# runs this first. The footprints already carry each model's offset and rotation.
set -euo pipefail
cd "$(dirname "$0")"
MODELS=(
  C2913206  # ESP32-S3-MINI-1-N8
  C265419   # SM05B-SRSS-G-TB
  C7420376  # SRV05-4 (SOT-23-6)
  C51118    # AP2112K (SOT-23-5)
  C163512   # 1206L050YR (1206)
  C19077497 # SMF5.0A (SOD-123FL)
  C2909058  # SK6812-EC20 (rev B LED)
  C20917    # AO3400A (SOT-23)
  C81598    # 1N4148W (SOD-123F)
  C5184954  # DB125-3.5-8P-GN-S (IO terminal)
  C2977594  # DC3-2.54-16PAS (IDC header)
  C25905    # R0402
  C1525     # C0402
  C19702    # C0603
  # Petro's own (PETRO-2)
  C596498   # BLM15 bead (L0402)
  C2836697  # BL0939 (SOP-16)
  C5216380  # ISOW7743 (SOIC-20)
  C187510   # 656 fuse holder (F2)
  C2827897  # DG636 mains terminal
  C187710   # TMOV20RP275E
  C2892547  # NTC (R0603)
  C48603696 # IRM-05-5
  C126818   # 1206L110THYR (1206)
  C17933    # 390k (R1206)
  C2976795  # HF115F relay
  C4248455  # WSK2512 shunt (R2512, on KiCad's footprint)
  C8678     # SS34 (SMA)
  C2925443  # SMAJ5.0A (SMA)
  C455095   # TS-1002 tactile switch
)
mkdir -p footprints/lcsc.3dshapes
FAILED=()
for c in "${MODELS[@]}"; do
  # resumable: skip parts already fetched (recorded per LCSC number)
  [ -f "footprints/lcsc.3dshapes/.$c" ] && continue
  sleep 20   # be polite: easyeda.com rate-limits bursts with a 403
  # --3d alone writes only the model files (into <output>.3dshapes), not the footprint
  if .venv/bin/python -c '
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
' --3d --lcsc_id="$c" --output footprints/lcsc; then
    touch "footprints/lcsc.3dshapes/.$c"
  else
    FAILED+=("$c")
  fi
done
if ((${#FAILED[@]})); then echo "FAILED: ${FAILED[*]}" >&2; exit 1; fi
