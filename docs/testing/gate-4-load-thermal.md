# Gate 4: load and thermal

**Martin only. Always enclosed, an RCD-protected socket, nothing connected to the board but its
cords.** The unit carries close to its rating for an hour, then switches that load 500 times.

**Pass:**
- the temperature rise is **under 30 °C** at the terminals, the relay, the shunt and the tracks,
  scaled to 10 A;
- **nothing reaches about 70 °C**;
- no reset, no unexpected trip;
- the relay is as good after cycling as before.

Read the rules in [README.md](README.md) first.

## How the temperatures are measured

Nothing conductive may run into a powered case, and contact sensors on the hot spots would sit on
live metal. So the temperatures come from things already to hand:

- **A thermal logger:** a battery-powered ESP32 with the **MLX90640** (55°, 32 × 24 pixels) and a
  **BMP280**, pushing to VictoriaMetrics over Wi-Fi.
  - It is sealed in with the board, so it touches nothing outside.
  - The MLX90640 measures without contact; the BMP280 gives the air temperature.
  - Its firmware is small: on the tracker, item c13.
- **A mapping run in a test hood** (§2):
  - The 55° sensor needs about **130 mm** above the board to see all of it, and the case's lid is
    much closer. So the case's base takes a tall hood, printed in the same V-0 filament as the case,
    with the logger at the top.
  - It is still fully enclosed: the rules all hold.
  - This run **finds the hot spots** and measures each one's rise against Petro's own NTC at the
    same moment. The hood's extra air makes it run a little cool, so it doesn't pass or fail
    anything by itself.
- **The pass run in the real case** (§3): judged from Petro's NTC rise times the ratio the map
  measured. That ratio is an approximation, so the pass limit is 25 °C, not 30, to leave room for
  the difference. If the logger fits inside the real case at least 10 mm from anything live, its
  BMP280 logs the air in there too.

**Shiny metal reads far too low on infrared** (bare tin by tens of degrees). Before the mapping
run, put a small piece of Kapton tape or a dot of black permanent marker on each spot below.

| Spot | Where |
|---|---|
| T1 | J1, the live screw's head |
| T2 | J2, the live screw's head |
| T3 | F1's clip on the live input side |
| T4 | K1, the top of its case above the contacts |
| T5 | RS1 (the shunt), and the pour beside it. At about one pixel, it reads low, so watch the pour |
| T6 | The L_F pour between F1 and K1 |
| T7 | R1 (the fusible resistor) |

## Prerequisites

- [ ] Gate 3 passed on this board.
- [ ] PETRO-4 (calibrated metering) and PETRO-5 (the trip) are in the firmware.
- [ ] **The load: the oil-filled radiator**, resistive and made to run for hours.
  - Use the setting nearest **2.0–2.3 kW** (≈ 8.7–10 A), checked on the power meter.
  - Set its thermostat to **maximum**, so it doesn't cycle.
  - Its reading must stay steady for 5 minutes before the run counts.
  - **Never above 2.3 kW**, which would be over 10 A. Many radiators are 2.5 kW on full (10.9 A),
    above the rating and the 10.5 A trip.
  - The hot air gun on full heat and fan (≈ 2 kW) is the fallback, if it runs without its cut-out
    cycling, pointed at open air, never at the unit.
  - **Not the AC unit**, or any motor or compressor: they are inductive, with a large inrush, and
    this test is the resistive rating.
- [ ] A **kettle** (≈ 3 kW, 13 A), for the real trip test only (§1.6).
- [ ] The thermal logger charged and pushing to VictoriaMetrics; the hood printed.
- [ ] The discharge tool (README rule 6), a room thermometer.

## 1. The trip test (PETRO-5), before any long run

1. The chain as in Gate 3: wall → RCD → power meter → the unit → the radiator, on.
2. Relay on. Through Fleet, set a **temporary** trip threshold below the radiator's current (for
   example 5 A). It isn't saved, and a reboot clears it.
3. **Expected:**
   - the relay opens at once;
   - `petro_trips_total{cause="overcurrent"}` rises by 1;
   - the LED shows the fault colour;
   - the radiator goes off.
4. Press the button: the trip clears and **the relay stays off** (CLAUDE.md, Control).
5. Reboot the unit (switch off at the wall and on). Confirm in Fleet's status that the threshold in
   force is back to about 10.5 A. Relay on: the radiator runs without tripping.
6. **The real threshold and the fast path:**
   - Swap the radiator for the **kettle** (water in it), switched on, then relay on.
   - At 13 A, the relay must open **within a second**, through the BL0939's OC output.
   - If it doesn't, **switch off at the wall at once**: 13 A is the plug fuse's rating and above
     Petro's.
   - Clear the trip (step 4).
7. If the relay did **not** open in step 3 or 6: stop. Only the plug's 13 A fuse would be left,
   which is accepted for a stuck relay but not for firmware that doesn't trip. Fix PETRO-5 first.

## 2. The mapping run, in the hood

1. Unplugged, opened (README rule 6). Put the marks on T1–T7. Fit the hood in place of the lid,
   with the logger at the top looking down, and close it.
2. Check the logger's first frames in VictoriaMetrics show the board, with its marked spots where
   expected (the board at room temperature, the hands' warmth gone).
3. Note the room temperature. Plug in with the relay off; the radiator on at its chosen setting. Relay on.
4. Run for **at least 60 minutes**, and on until nothing has risen more than 1 °C in the last 10
   minutes (steady state). Watch every ten minutes:
   - the logger's hottest pixel and T1–T7;
   - Petro's NTC, current, resets and trips.

   **Stop** (relay off from Fleet, then off at the wall) if:
   - any pixel passes **70 °C**;
   - there is any smell or sound;
   - the current drifts upwards.
5. Note `petro_energy_kwh_total` and the power meter's kWh at the start and end.
6. Relay off and mode **off** (README rule 8). Switch off at the wall and unplug.
7. **The ratio:** for each spot, its rise ÷ the NTC's rise, at steady state. The largest is
   **the ratio** used in §3 and by PETRO-5.
8. Save the hottest frame as an image (`photos/gate-4/b<k>-thermal.png`). Note anywhere hot that
   isn't on the list.

## 3. The pass run, in the real case

1. Let it cool to room temperature. README rule 6, take the hood off, fit the real lid (the
   logger inside if it fits, ≥ 10 mm from anything live), close it.
2. Plug in with the relay off, the radiator on, relay on. Run as §2 step 4, and stop if the NTC's rise
   times the ratio passes 40 °C.
3. **The estimated hot-spot rise** = the NTC's rise at steady state × the ratio. Scale it to 10 A
   (below).
4. Just before the end, a hand on the outside of the case: note any warm spot.
5. Mode off, switch off at the wall, unplug. README rule 6, open. Point the logger at the board as
   soon as it's open, for a quick look: it reads low after the delay, so it is a check, not the
   record.

**Scaling to 10 A:** the copper's and contacts' heat goes as the current squared, so

> rise at 10 A ≈ measured rise × (10 / measured A)²

For example, a 20 °C rise at 8.7 A is about 26 °C at 10 A. **Scale only T1–T6** (the current
path); R1 (T7) and the case don't follow the load current.

**The 70 °C limit at a warm room:** a peak measured at room temperature R is judged as
peak + (35 °C − R), so a 60 °C peak in a 20 °C room counts as 75 °C.

**This step passes** if the estimated rise, scaled to 10 A, is **under 25 °C**, and room
temperature plus that rise, judged at 35 °C, is under 70 °C.

## 4. The metering comparison

From Gates 3 and 4, against the power meter:

| Load | Petro V / meter V | Petro A / meter A | Petro W / meter W |
|---|---|---|---|
| None, relay off | | — | |
| The lamp (Gate 3) | | | |
| The radiator | | | |
| **Energy over the mapping run** | Petro kWh: | Meter kWh: | Error: |

PETRO-4's calibration should bring each within ± 2 % at the radiator (the power meter's own accuracy
limits this). In the idle row Petro reads about 0 W against the meter's ~0.6 W, which is right:
the shunt doesn't carry Petro's own supply current.

## 5. The NTC and PETRO-5

PETRO-5's over-temperature threshold is set from §2's ratio, so that the NTC trips before the
hottest spot reaches 70 °C: NTC threshold = room + (70 − room) ÷ ratio, at a 35 °C room.

## 6. 500 relay cycles at load

1. Real case, closed, plugged in, the radiator on. Through Fleet: **relay cycle 500, 3 s on, 5 s off**
   (about 67 minutes).
2. Watch VictoriaMetrics:
   - `petro_relay_on` toggling;
   - no resets;
   - no trips;
   - the NTC staying below §3's figure.
3. When it finishes, let it **cool to within 1 °C of §3's starting NTC reading** (relay off, a
   few hours), so both runs start alike. Then **relay on for 30 minutes** at the radiator's load, and
   compare the NTC's rise at 30 minutes with the same point in §3's run:
   - within 3 °C: the contacts are as good as before;
   - more: the contacts have worn or a joint has degraded. Open it up (README rule 6), inspect K1's
     joints, and don't use this board until that's understood.
4. Mode off, unplug, README rule 6, open. Look for discolouration at K1 and the terminals.
   Photograph.
5. **The contact resistance, directly:** repeat Gate 2's step 5.2a (on USB, mains unplugged: relay
   on, the same current from the bench supply, the mV across the same points). More than about
   50 % up on Gate 2's figure means the contact has worn.

**Gate 4 passes** when the estimated rises are under the limits, the trip works at the lowered
and the real threshold, and the relay is unchanged after 500 cycles.

## Results

### B1

Date: · Firmware version: · Room temperature: · Load: (W, A)

| Check | Reading | Pass? | Notes |
|---|---|---|---|
| 1.3 trip at the temporary threshold; 1.4 cleared; 1.5 back after reboot | | | |
| 1.6 real trip with the kettle (time to open) | | | |
| 2 mapping run: length, current, room | | | |
| T1 J1 L rise / ratio | | | |
| T2 J2 L | | | |
| T3 F1 clip | | | |
| T4 K1 | | | |
| T5 RS1 (and its pour) | | | |
| T6 L_F pour | | | |
| T7 R1 | | | |
| Anything else hot | | | |
| The ratio | | | |
| 3 real case: NTC rise; × ratio; scaled to 10 A | | | |
| 3 case outside | | | |
| 4 metering table | | | |
| 5 NTC threshold for PETRO-5 | | | |
| 6.2 500 cycles: resets, trips | | | |
| 6.3 NTC rise at 30 min, before / after | | | |
| 6.4 inspection | | | |
| 6.5 contact mV: Gate 2 / after | | | |
