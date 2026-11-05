# smart-switch (Petro)

Petro is Martin's own 10 A, 230 V AC Wi-Fi smart switch: an in-line cord unit with energy
metering, one button, a status LED, Fleet MQTT and OTA, and Alexa. **It is for Martin's own home
and will never be sold or given away**: a mains device needs safety testing and UKCA marking before
anyone else can have one.

- Plane project: `PETRO` (https://plane.home.nakomis.com, alias `petro`). Branches and PR titles
  carry the ref, e.g. branch `petro-2-board`, PR `feat(pcb): board generator (PETRO-2)`.
- Martin is the project manager; Claude does the development. Never auto-merge PRs.
- It grew out of the nakostat heatlink board (STAT-75/76). Reuse its pipeline and firmware
  patterns, but copy rather than depend on them.

## Decisions (2 Nov 2026; rev B, 4–5 Nov 2026)

Rev B is **non-isolated** (decided 4 Nov 2026, for the ~£150 budget: the isolated rev A was quoted
at £240.67 for 5). The whole board, every connector and pad included, sits at mains potential. Rev
A is tag `5v-240v-separation-v1`; rev B with an isolated J3 is tag `rev-b-isolated-io`. The
reasoning is in `docs/DESIGN.md`.

| Topic | Decision |
|---|---|
| Rating | 10 A continuous, 230 V AC, resistive. Derate inductive and capacitive loads. Design margin in: a 16 A relay, and copper and terminals sized for 16 A |
| Form factor | In-line cord unit (cable in, cable out) in Martin's own printed case (PETRO-6), printed in a UL94 V-0 flame-retardant filament, with glands and cord grips. Never plain PLA or PETG for the mains enclosure. The board (120 × 80 mm with 4 mm rounded corners) sets the case's size. **Nothing conductive may leave the case** |
| Power | Non-isolated, from the mains: F2 (T500 mA), a fusible resistor and Power Integrations' **LNK306** high-side buck (12 V), then a TI **TPS563201** (5 V) and the AP2112K (3.3 V). GND is neutral, joined through a 0 Ω link (R29, the one star point); the shunt's sense pads are true Kelvin (SENSE, KGND) |
| Metering | A **BL0939** (the BL0942 is out of stock) on GND, reading a 1 mΩ Kelvin shunt **in the neutral**, east of the MOV (which returns to N_IN, so surges miss the shunt), and a 5 × 390 kΩ divider from L_IN; UART, zero cross and over-current wired straight to the ESP32 |
| MCU | **ESP32-C6-WROOM-1-N8** (JLCPCB Economic assembly; the S3-MINI's LGA needed X-ray, so Standard), antenna overhanging the edge furthest from the mains |
| I/O | J3, a 10-way 3.5 mm terminal for parts **inside the case**: 3.3 V, GND, SPI, I²C (4k7 pull-ups), IN (100k pull-down, an LP GPIO for wake) and OUT. At mains potential like everything else. USB (J4, the house connector) and the debug pads are for use **only with mains unplugged** |
| Control | One tactile button cycling **on → off → auto**. On and off are local overrides (remote relay commands are refused); auto follows MQTT and Alexa. The mode persists in NVS and doubles as the power-on state. A press with a trip latched clears the trip and leaves the relay off |
| LED | SK6812-EC20 (Economic-capable, WS2812 protocol) under a light pipe: mode, boot, Wi-Fi joining, connected, pairing, OTA, fault |
| Light sealing | The case is **opaque**, and no light may leak through cracks or joins. The light pipe runs through an opaque tunnel/boss whose **flange sits around the LED on the board**, optionally glued down with opaque glue or enamel paint. So the board keeps a **2 mm clear perimeter around the LED** (no parts, and nothing taller than the mask) for the flange to seat on; the case and board designs share the LED's position and the flange footprint |
| Assembly | JLCPCB Economic, 1 oz copper. The mains parts (J1, J2, F1's clips, F2's holder, K1, RV1, R1) are **hand-fit**: bought from authorised distributors (`docs/DESIGN.md` §3.2) and soldered by Martin (`pcb/out/petro/hand-fit.csv`) |
| Integration | MQTT/Fleet, plus Alexa Smart Home on day one (nakostat's Alexa Lambda pattern). No Home Assistant yet |
| Fuses as built | F1 and F2 bridged with solid copper links (Martin, 5 Nov 2026): the plug's 13 A fuse and R1 protect instead. Never foil. A 500 V insulation test of the case was also declined: never handle the unit plugged in (`docs/testing/README.md`) |
| Earth | Does not go through the PCB: a Wago 221 or crimp inside the case. The mounting holes are unplated, so the screws aren't live |

## Mains design rules (non-negotiable)

- 1 oz copper, the mains nets as solid pours on both layers, stitched with vias, each layer at
  least 3.5 mm wide (IPC-2221 for 8 A a layer, 16 A for the pair). The `Mains16A` net class and
  the zones' minimum width fail the build if anything thins them.
- ≥ 2.5 mm between mains potentials (L↔N, and every mains net to GND, which is neutral); the
  supply's DC bus 3.55 mm to GND and 4.35 mm to the live; the divider's steps and the LNK306's
  switching node (1.0 mm inside the converter only) by the generated matrix (`pcb/board/rules.py`);
  3 mm to the board edge and holes.
- F1: a 15 A high-breaking-capacity fuse (6.3×32 mm, 50 kA) for short circuits; the plug's 13 A
  fuse and the firmware trip (~10.5 A) cover overload. Then a 275 V AC thermally protected MOV, and
  a separate T500 mA fuse on the supply branch.
- Everything is live when plugged in: the board is only ever powered from mains **closed in its
  case**, from an RCD-protected socket. USB and the debug pads only with mains unplugged; a scope
  on a powered board only through an isolation transformer or a differential probe.

## Safety gates (PETRO-7)

1. Design review before ordering (DRC, creepage, fuse coordination, relay ratings,
   `superpowers:requesting-code-review`, `cabal` opinions).
2. Bench, USB only, mains unplugged. 2b: the supply from a bench DC supply (≤ 60 V, F2 out).
3. First mains power-up: RCD-protected socket, unit closed in its case, a dim bulb, then a lamp
   load.
4. Load and thermal: 10 A for ≥ 1 h (< 30 °C rise, nothing above ~70 °C), then hundreds of
   full-load relay cycles.

**Martin does all mains work himself; Claude writes the procedures.** Never press order or pay at
a fab: fill the baskets and stop.

The procedures and results are in `docs/testing/` (Gate 1 passed 5 Nov 2026). Its README lists
what the gates need from the firmware, the USB console commands and the `petro_*` metrics: they
are PETRO-3's acceptance tests. Devices report to Fleet **and VictoriaMetrics** (through vmauth,
with a per-device credential in `prov`, as tinycrypt). Progress from order to Go Live:
https://claude.ai/artifact/A1f2kEu7jyYBrHbdiJMifh (tick items there as they land).

## Repository layout

| Path | What's there |
|---|---|
| `pcb/` | The board generator (Python → KiCad 10), on the heatlink/tinycrypt pipeline |
| `firmware/` | ESP-IDF 5.5 firmware: `port/` portable C with pytest host tests, `esp32c6/` IDF project |
| `case/` | The enclosure and any printed internal parts |
| `docs/` | Design notes, gate procedures (`docs/testing/`), the logo |
| `infra/` | CDK (not yet: arrives with PETRO-9) |

## References

- Heatlink board pipeline: `~/repos/nakomis/nakostat-wt/stat-75-heatlink-pcb/pcb/heatlink/`
  (`DESIGN.md`, `board/`, `build.py`, `fetch_parts.sh`, `fetch_models.sh`, `tests/`), on branch
  `stat-75-heatlink-pcb` (nakomis/nakostat#57). Once merged: `~/repos/nakomis/nakostat/pcb/heatlink/`.
- Tinycrypt: `~/repos/nakomis/tinycrypt/hardware/key-board/` (original pipeline, house USB connector).
- Heatlink firmware: `~/repos/nakomis/nakostat/embedded/esp32/heatlink/`.
- Alexa pattern: nakostat `docs/alexa-setup.md` and its Alexa Lambda in `infra/`.
- ESPHome's `bl0939` component: a reference for the register map and calibration (the datasheet is Chinese only).

## Tooling

- Board: KiCad 10 CLI, Freerouting 2.5.0 (Java via asdf), Python 3.11
  (`ASDF_PYTHON_VERSION=3.11.15`) in a venv.
- Firmware: ESP-IDF 5.5, ESP32-C6 (single-core RISC-V, 160 MHz), no PSRAM, 4 MB partitions. Fleet topics `petro/<thing>/{commands,responses,status}`;
  Fleet's message shapes are not to be changed. Credentials only in the `prov` NVS partition,
  written by the provisioning script: never in the image or CloudFormation. Bump
  `firmware/esp32c6/version.txt` with every firmware change.
- Flash with `esptool --after watchdog_reset`.

## AWS credentials

- Sandbox: `AWS_PROFILE=nakom.is-sandbox` (account 975050268859)
- Production: `AWS_PROFILE=nakom.is-admin` (account 637423226886)

## Testing

- Firmware host tests: pytest over drivers built from `port/` (as in the heatlink).
- Board generator: pytest.
- Target 70 % coverage minimum. Cap test workers (`TEST_MAX_WORKERS`).

## Architecture diagrams

Source: `docs/architecture/smart-switch.drawio`, with the SVG auto-regenerated on commit by
`.githooks/pre-commit`. To activate the hook after cloning:

```bash
git config core.hooksPath .githooks
```
