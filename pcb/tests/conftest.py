import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# $KICAD_CLI and $KICAD_FP override the macOS install.
KICAD_CLI = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
KICAD_FP = Path(os.environ.get("KICAD_FP", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"))

# Revision B (non-isolated) is mid-rebuild: the netlist is done (step 2), the placement (step 4)
# and the copper, routing and silk on it (step 5) are not. These modules test the placed board, so
# they wait for step 4/5, which rewrites them. Remove each from this list as its step lands.
collect_ignore = [
                  ]

# Tests marked kicad run KiCad (kicad-cli's DRC, its footprint library). Without it (as in CI, which
# has no KiCad 10) they are skipped, not failed, and everything else still runs. Run them on the Mac.
HAVE_KICAD = os.access(KICAD_CLI, os.X_OK) and KICAD_FP.is_dir()


def pytest_configure(config):
    config.addinivalue_line("markers", "kicad: needs KiCad 10 (kicad-cli and its footprint library)")


def pytest_collection_modifyitems(config, items):
    if HAVE_KICAD:
        return
    skip = pytest.mark.skip(reason=f"KiCad not found ({KICAD_CLI}): set KICAD_CLI and KICAD_FP")
    for item in items:
        if "kicad" in item.keywords:
            item.add_marker(skip)
