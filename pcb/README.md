# Board

The Petro board, generated as code (Python → KiCad 10) on the nakostat heatlink pipeline
(`nakostat/pcb/heatlink/`, itself from tinycrypt's), with DRC rules for mains creepage and a
`Mains16A` net class. Work item: PETRO-2, after the design decisions in PETRO-1.

The pipeline is copied, not shared: `board/` holds the generic modules, and Petro's own board
arrives as `board/petro_board.py` and `build.py`.

| Module | What it does |
|---|---|
| `board/sexpr.py` | Reads and writes KiCad s-expressions |
| `board/kicadlib.py` | Loads footprints (pads, courtyards) and symbol pin tables |
| `board/parts.py` | The parts catalogue: LCSC number, footprint, symbol, body extent, 3D model fixes, manufacturer |
| `board/netlist.py` | `Circuit` (parts and nets) and `check()` (single-pad nets, nets with several outputs, unconnected power pins) |
| `board/placement.py` | `Placement` and rotated bounding boxes |
| `board/kicad_pcb.py` | Writes `.kicad_pcb`, `.kicad_pro` (net classes) and `.kicad_dru` (mains rules) |
| `board/dsn.py`, `board/ses.py`, `board/route.py` | Specctra DSN out, Freerouting headless, SES back in |
| `board/cleanup.py` | After routing, drops vias that join only one layer and track stubs that lead nowhere |
| `board/fab.py` | BOMs (JLCPCB and PCBWay), CPL, gerbers, drill, renders, STEP |
| `board/art.py` | Turns a black-and-white PNG into a silkscreen portrait |
| `board/rules.py` | The mains rules: potential groups, fault scenarios, the working-voltage matrix, IEC 60664-1 creepage, the generated `.kicad_dru` and net classes, and the creepage check within barrier parts |

## Mains rules

Every mains net is in one potential group:

| Group | What's in it |
|---|---|
| LINE | Live before F1 |
| LIVE | Live after F1, plus the metering island |
| PSU | Live after F2 |
| NEUTRAL | Neutral |
| LOAD | The relay's output |
| DIV1–4 | The voltage divider's chain |

Every other net is SELV. Each fault scenario (relay closed or open, either fuse blown) gives every
group a potential. The worst difference between two groups is their working voltage, and IEC
60664-1 Table F.4 (pollution degree 2, material group III) turns that into a creepage distance.
`rules.py` writes the result as KiCad DRC rules, and `tests/test_rules.py` proves each rule fails a
board that breaks it.

Mains to SELV is 8 mm clearance and 8 mm creepage. There is one exception: between a certified
barrier part's own pads (the isolator, relay and PSUs), clearance may drop to 3.0 mm, IEC's
reinforced clearance at 4 kV. Creepage stays at 8 mm.

KiCad 10 doesn't check creepage between two pads of one footprint, so `barrier_creepage()` checks
those pairs itself, around any slots. Its estimate can only be shorter than the true path.

The high-current nets (N, L_IN, L_F, L_SH, L_OUT) are not tracks but solid pours on both layers,
stitched with vias (`petro_board.mains_zones()` and `stitch_vias()`). Each pour is drawn as a
generous polygon, and KiCad's fill trims it to the rules. Its `min_thickness` is half the IPC-2221
width for 16 A, so KiCad drops any neck thinner than that. `tests/test_copper.py` refills the zones
and checks that each layer, on its own, is one piece reaching every through-hole pad of its net,
so the two layers carry the current in parallel. The ground pour covers the SELV strip only.

## Setting up

```bash
cd pcb
ASDF_PYTHON_VERSION=3.11.15 python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp ~/repos/nakomis/nakostat/pcb/heatlink/freerouting/freerouting-2.5.0.jar freerouting/   # 64 MB, not committed
```

Java comes from asdf. KiCad 10 must be installed at `/Applications/KiCad/`.

- `./fetch_parts.sh` fetches any missing footprints and symbols from EasyEDA. It skips parts it
  already has, and waits 20 s between parts because EasyEDA rate-limits.
- `./fetch_models.sh` fetches the 3D models, which aren't committed.

## Tests

```bash
TEST_MAX_WORKERS=2 .venv/bin/python -m pytest -q tests
```

The generic tests run on a small fixture board (`tests/fixture_board.py`), not on Petro's board.
The routing test routes that fixture with Freerouting **in a temporary directory**. Freerouting
isn't deterministic, so a test that routed in place would overwrite `out/` (the heatlink nearly
committed a re-routed board after its order had been quoted). The board that gets ordered is
committed and tagged.
