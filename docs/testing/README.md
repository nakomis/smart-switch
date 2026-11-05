# Testing: the safety gates

Petro is a mains device built by hand, for Martin's own home. Nothing reaches the next stage
until the gate before it has passed and its results are written down here. **Martin does every
step that involves mains. Claude writes the procedures and records the results.**

The tracker from order to Go Live: https://claude.ai/artifact/A1f2kEu7jyYBrHbdiJMifh

| Gate | What | Mains? | Needs | Procedure |
|---|---|---|---|---|
| 1 | Design review before ordering | No | | [gate-1-design-review.md](gate-1-design-review.md) (passed 5 Nov 2026) |
| 2 | Inspection, hand-fitting, bench on USB | **No** | PETRO-3's console firmware | [gate-2-bench.md](gate-2-bench.md) |
| 2b | The supply from a bench DC supply (≤ 60 V) | **No** | Gate 2 | [gate-2b-supply.md](gate-2b-supply.md) |
| 3 | First mains power-up, closed in its case, a lamp load | Yes | Gates 2 and 2b; the V-0 case (PETRO-6); Fleet and VictoriaMetrics reporting (PETRO-3) | [gate-3-first-mains.md](gate-3-first-mains.md) |
| 4 | 10 A for an hour, then 500 relay cycles at load | Yes | Gate 3; the trip (PETRO-5) | [gate-4-load-thermal.md](gate-4-load-thermal.md) |

Run every gate on **one board first** (B1). The others follow once it has passed that gate.

## Rules for every gate

1. **The board is live whenever it's plugged in**, the relay open or closed, and so is everything
   on it: GND is neutral, and every pad, test hole, J3 and USB sit at mains potential. In a socket
   wired backwards, GND is at 230 V to earth.
2. **Mains only with the case closed**, from an **RCD-protected** socket (30 mA). Use a plug-in
   RCD unless the consumer unit's RCD is confirmed to cover that socket. Press the RCD's test
   button before each session.
3. **A socket tester first**, on every socket or extension the first time it's used.
4. **Never USB, the debug pads, the test holes or a scope with mains connected.** A laptop on USB
   ties its ground to neutral, or to live in a reversed socket. An earthed scope's ground clip on
   this board is a short to earth. The cabal's reviewers put this first.
5. **Nothing conductive runs into a powered case**: no probe leads, no thermocouples. The board
   reports its own readings over Wi-Fi (Fleet and VictoriaMetrics), and temperatures are read
   from labels that keep their maximum, after unplugging.
6. **Unplugging isn't enough before opening.** C1 and C2 hold up to 354 V DC, and **nothing
   bleeds them**: the LNK306 drains them only until it stops switching, and what is left can stay
   for hours (Gate 2b measures how much).
   1. Unplug and wait 2 minutes.
   2. Open the case **without touching the board**, and measure from the top side: **D7's banded
      (cathode) end** (VBULK1) to **TP6** (GND). Use insulated probes, one hand, the other hand
      away from the board.
   3. Below 30 V: carry on. Above it: **discharge with the discharge tool** (below) across the same
      two points for 5 seconds, then measure again.

   Never short the capacitors with a screwdriver.
7. **Stop on anything unexpected**: a smell, a sound, smoke, a fuse blowing, a reading outside its
   range, the RCD tripping. Unplug at the socket (not the unit), record what happened, and don't
   power it again until the cause is understood.
8. **Leave the mode off before every switch-off.** The mode (on, off, auto) persists in NVS and
   is the power-on state. A unit left "on" closes its relay the moment it's next plugged in, into
   whatever is on the output. Before unplugging, set it off and check `petro_relay_on` is 0.
9. **Fuses are replaced only like for like** (`docs/DESIGN.md` §5.1): F1 a 6.3×32 mm ceramic 15 A
   fast-acting, at least 1.5 kA at 250 V AC; F2 a 5×20 mm ceramic T500 mA (T1A only if Gate 3's
   inrush check calls for it). Never a glass fuse.

## Things to buy before Gates 3 and 4

| Item | For | Notes |
|---|---|---|
| Socket tester | 3, 4, Go Live | Shows reversed polarity and a missing earth |
| 30 mA plug-in RCD | 3, 4 | Unless the consumer unit's RCD is confirmed to cover the socket |
| Max-reading temperature labels | 4 | The irreversible multi-window kind, about 40–80 °C in 5 °C steps. Enough for 8 spots a run |
| K-type thermocouple | 4 | Only if the meter has a K-type input and none came with it; for the snapshot once the unit is open (the labels are the main record) |
| A 2 kW convector or fan heater | 4 | ≈ 8.7 A. Never 3 kW (13 A, above the rating). A hot air gun cycles and is a poor hour-long load |
| An incandescent lamp of 60–100 W, and a lamp holder with a lead | 3 | For the dim-bulb tester and the lamp load. An LED lamp won't limit current |
| Spare fuses | 3, 4 | F2 × 5 (T500 mA ceramic), T1A ceramic × 2, F1 × 2 |
| Nylon M3 screws | 3 | The mounting holes are unplated; nylon keeps the screws insulating |
| **A discharge tool** | 2b, 3, 4 | A 10 kΩ 5 W resistor between two insulated probes (or test leads with insulated clips), in heat-shrink. τ = RC ≈ 0.1 s, so 5 seconds empties C1 and C2. Never a screwdriver |
| **An insulation tester (500 V DC)** | 3 | The case is the only barrier, and a meter at ~1 V can't find a creepage path. A 500 V insulation tester or a PAT tester with an insulation test (buy or borrow); with aluminium foil for the outside of the case |

**A dim-bulb tester** is a lamp holder wired in series with the live of a trailing socket, inside
its own closed box: Martin builds it, or buys one. With a short anywhere, the lamp lights fully
and takes the voltage, and nothing upstream sees more than the lamp's current.

## Boards and records

- Stick a label **B1 to B5** on each board's underside, away from the mains area. Every result
  names its board.
- Results go in each gate's file, under **Results**: one table per board, with the date, what was
  measured and pass or fail. Martin can tell Claude the readings, and Claude records them.
- Photos go in `docs/testing/photos/gate-<n>/b<k>-<what>.jpg` (for example
  `photos/gate-2/b1-top.jpg`): the board top and bottom on arrival, after hand-fitting, and
  anything odd.

## What the gates need from the firmware (PETRO-3, PETRO-4 and PETRO-5)

The gates are written against these. They are the firmware's acceptance tests, so PETRO-3 builds
them first.

**USB console (Gate 2)**, on the C6's USB-Serial-JTAG at 115200 (`idf.py monitor` or any terminal),
USB only and so never with mains:

| Command | Does |
|---|---|
| `info` | Firmware version, MAC, chip revision, reset reason, the mode, the trip thresholds in force, the `prov` partition's state (keys present, never values) |
| `relay on` / `relay off` | Drives the relay |
| `relay cycle <n> <on_ms> <off_ms>` | Cycles it n times |
| `led <r> <g> <b>` | Sets the LED (0–255 each) |
| `button` | Logs presses and releases for 10 s |
| `bl` | Reads the BL0939: voltage, both currents and active power registers (raw and scaled), the CF count, its temperature, and whether each frame's checksum was good |
| `edges` | ZX and OC edges a second, over 2 s |
| `ntc` | The NTC's ADC reading and °C |
| `wifi scan` | SSIDs, channels and RSSI |
| `j3` | Toggles OUT at 1 Hz for 5 s, reads IN, scans I²C (0x08–0x77) |

**Fleet and VictoriaMetrics (Gates 3 and 4)**, pushed every 10 s. VictoriaMetrics is reached
through vmauth on Cal (home-infra #507): a plain-text push (`/api/v1/import/prometheus`, or
`/write` as tinycrypt uses) with basic auth. The user is the device's name, `petro-prod-b1` to
`-b5`, matching its Fleet Thing; its password comes from SSM `/vmauth/device-petro-prod-bN-password`
into `prov` (`metrics_url`, `metrics_user`, `metrics_pass`, as tinycrypt's `provision-key.sh`).
vmauth labels every series `host_name="petro-prod-bN"`.

| Metric | Unit |
|---|---|
| `petro_voltage_volts`, `petro_current_amps`, `petro_power_watts` | V rms, A rms, W |
| `petro_energy_kwh_total` | kWh, kept across reboots |
| `petro_board_temperature_celsius` | The NTC |
| `petro_relay_on` | 0 or 1 |
| `petro_zx_hz` | Zero crossings a second (≈ 100 on 50 Hz) |
| `petro_wifi_rssi_dbm`, `petro_uptime_seconds` | |
| `petro_resets_total{reason}` | Brown-outs show as `reason="brownout"` |
| `petro_trips_total{cause}` | Over-current or over-temperature (PETRO-5) |

**Commands through Fleet:**
- relay on/off, and the mode;
- relay cycle (n, on and off times), for Gate 4;
- a temporary trip threshold for Gate 4's trip test (PETRO-5), never persisted and gone after a
  reboot. The thresholds in force are reported in the status, so a reboot can be checked;
- a Wi-Fi **transmit-stress mode** for Gate 3's hour (continuous traffic, not one push every 10 s).

Use `idf.py monitor --no-reset` where a reset reason matters: plain `monitor` resets the C6 when
it opens.
