import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
KICAD_FP = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")

# Revision B (non-isolated) is mid-rebuild: the netlist is done (step 2), the placement (step 4)
# and the copper, routing and silk on it (step 5) are not. These modules test the placed board, so
# they wait for step 4/5, which rewrites them. Remove each from this list as its step lands.
collect_ignore = ["test_placement.py", "test_copper.py", "test_routing_plan.py", "test_silk.py",
                  "test_refs.py", "test_outputs.py"]
