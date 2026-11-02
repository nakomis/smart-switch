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

## Decisions (2 Nov 2026)

| Topic | Decision |
|---|---|
| Rating | 10 A continuous, 230 V AC, resistive. Derate inductive and capacitive loads. Design margin in: a 16 A relay |
| Form factor | In-line cord unit (cable in, cable out) in a bought UL94 V-0 ABS/PC junction box with glands and cord grips. Never PLA or PETG for the mains enclosure |
| Power | Mains, through two Mean Well modules: an **IRM-05-5** (1 A) for the SELV side, and an **IRM-01-5** whose output is tied to live, powering the mains-side metering (with a second IRM-05-5 as the fallback). Everything after the IRM-05-5 is SELV. **Never** a non-isolated dropper or buck for the SELV supply. Safety-critical parts come only from authorised distributors (see `docs/DESIGN.md` §3.2) |
| Metering | Option A: a 1 mΩ Kelvin shunt and a divider, with the metering chip on the mains side and its UART crossing through a reinforced wide-body isolator (ISO7721DW; never the basic-rated B variant) |
| MCU | ESP32-S3-MINI-1-N8, soldered directly, antenna overhanging the edge furthest from the mains |
| Control | One tactile button cycling **on → off → auto**. On and off are local overrides (remote relay commands are refused); auto follows MQTT and Alexa. The mode persists in NVS and doubles as the power-on state. A press with a trip latched clears the trip and leaves the relay off |
| LED | WS2812B-2020 under a light pipe: mode, boot, Wi-Fi joining, connected, pairing, OTA, fault |
| Light sealing | The case is **opaque**, and no light may leak through cracks or joins. The light pipe runs through an opaque tunnel/boss whose **flange sits around the LED on the board**, optionally glued down with opaque glue or enamel paint. So the board keeps a **2 mm clear perimeter around the LED** (no parts, and nothing taller than the mask) for the flange to seat on; the case and board designs share the LED's position and the flange footprint |
| Integration | MQTT/Fleet, plus Alexa Smart Home on day one (nakostat's Alexa Lambda pattern). No Home Assistant yet |
| Earth | Does not go through the PCB: a Wago 221 or crimp inside the case |

## Mains design rules (non-negotiable)

- 2 oz copper; a `Mains10A` net class with a minimum width in the DRC, so the build fails if
  routing thins a mains track; solid pours on both layers for mains nets, stitched with vias.
- 8 mm reinforced mains↔SELV; ≥ 2.5 mm functional L↔N (more where there's room); 3 mm to the board
  edge and holes; no ground pour in the mains area; slots under the relay and PSU where they help.
- A 10 A fuse, a 275 V AC MOV after it, and a separate T500 mA fuse on the PSU branch.
- The relay must itself bridge the SELV/mains boundary: reinforced coil-to-contact insulation
  (≥ 8 mm creepage, 4–5 kV).

## Safety gates (PETRO-7)

1. Design review before ordering (DRC, creepage, fuse coordination, relay ratings,
   `superpowers:requesting-code-review`, `cabal` opinions).
2. Bench, USB only, no mains.
3. First mains power-up: RCD-protected socket, unit closed in its case, a lamp load.
4. Load and thermal: 10 A for ≥ 1 h (< 30 °C rise, nothing above ~70 °C), then hundreds of
   full-load relay cycles.

**Martin does all mains work himself; Claude writes the procedures.** Never press order or pay at
a fab: fill the baskets and stop.

## Repository layout

| Path | What's there |
|---|---|
| `pcb/` | The board generator (Python → KiCad 10), on the heatlink/tinycrypt pipeline |
| `firmware/` | ESP-IDF 5.5 firmware: `port/` portable C with pytest host tests, `esp32s3/` IDF project |
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
- ESPHome's `bl0942` component: a reference for the register map and calibration.

## Tooling

- Board: KiCad 10 CLI, Freerouting 2.5.0 (Java via asdf), Python 3.11
  (`ASDF_PYTHON_VERSION=3.11.15`) in a venv.
- Firmware: ESP-IDF 5.5, ESP32-S3, no PSRAM, 4 MB partitions, **160 MHz** (avoids the dual-core
  miscompute issue in `~/CLAUDE.md`). Fleet topics `petro/<thing>/{commands,responses,status}`;
  Fleet's message shapes are not to be changed. Credentials only in the `prov` NVS partition,
  written by the provisioning script: never in the image or CloudFormation. Bump
  `firmware/esp32s3/version.txt` with every firmware change.
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
