# Gate 4: load and thermal

**Martin only. Case closed, an RCD-protected socket, nothing connected to the board but its
cords.** The unit carries close to its rating for an hour, then switches that load 500 times.

**Pass:**
- the temperature rise is **under 30 °C** at the terminals, the relay, the shunt and the tracks,
  scaled to 10 A;
- **nothing reaches about 70 °C**;
- no reset, no unexpected trip;
- the relay is as good after cycling as before.

Read the rules in [README.md](README.md) first.

## Prerequisites

- [ ] Gate 3 passed on this board.
- [ ] PETRO-4 (calibrated metering) and PETRO-5 (the trip) are in the firmware.
- [ ] The load: a 2 kW convector or fan heater, its thermostat at **maximum** so it doesn't cycle,
  on its highest setting (≈ 8.7 A). **Never 3 kW** (13 A). If a second load brings the total
  nearer 10 A, check the total on the power meter first: it must stay **under 10.5 A**, or the
  trip opens.
- [ ] The temperature labels, the meter (and its K-type thermocouple, if it has one), a room
  thermometer.
- [ ] The discharge tool (README rule 6), and a 500 W load for step 1.6 (another heater on low, or
  the hot air gun briefly).

## 1. The trip test (PETRO-5), before any long run

1. The chain as in Gate 3: wall → RCD → power meter → the unit → the heater, heater on.
2. Relay on. Through Fleet, set a **temporary** trip threshold below the heater's current (for
   example 5 A). It isn't saved, and a reboot clears it.
3. **Expected:**
   - the relay opens at once;
   - `petro_trips_total{cause="overcurrent"}` rises by 1;
   - the LED shows the fault colour;
   - the heater is off.
4. Press the button: the trip clears and **the relay stays off** (CLAUDE.md, Control).
5. Reboot the unit (switch off at the wall and on). Confirm in Fleet's status that the threshold in
   force is back to about 10.5 A. Relay on: the heater runs without tripping.
6. **The real threshold and the fast path:** add a 500 W load to the heater on a short extension
   (≈ 10.9 A on the power meter). Relay on: **the relay opens within a second** at the real
   ~10.5 A, through the BL0939's OC output. Clear it (step 4) and take the extra load off.
7. If the relay did **not** open in step 3 or 6: stop. Only the plug's 13 A fuse would be left, which is
   accepted for a stuck relay but not for firmware that doesn't trip. Fix PETRO-5 first.

## 2. Labels on

Unplugged, opened (README rule 6). Fit a temperature label to each of these, flat and pressed
down. A label must not cover the LED's 2 mm ring or anything the case presses on.

| Spot | Where |
|---|---|
| T1 | J1, the live screw's body |
| T2 | J2, the live screw's body |
| T3 | F1, the hotter clip (the live input side) |
| T4 | K1, the top of its case, above the contact end |
| T5 | RS1 (the shunt), or the pour beside it if it's too small |
| T6 | The L_F pour, top side, between F1 and K1 |
| T7 | R1 (the fusible resistor) |
| T8 | The inside of the case wall nearest K1 |

Photograph them (`photos/gate-4/b<k>-labels-before.jpg`), then close the case.

## 3. The load run: at least an hour

1. Note the room temperature. Plug in with the relay off; the heater on at maximum.
2. Relay on. Note the start time, `petro_current_amps` and the power meter's amps (≈ 8.7 A).
3. Watch VictoriaMetrics every ten minutes:
   - `petro_board_temperature_celsius`;
   - `petro_current_amps`;
   - `petro_resets_total`;
   - `petro_trips_total`.

   **Stop** (relay off from Fleet, then off at the wall) if:
   - the NTC passes **50 °C** on B1's first run (the NTC under-reads the hot spots by a ratio not
     yet known; once §5 has measured it, set this limit from the ratio for later runs);
   - there is any smell or sound;
   - the case is too hot to keep a hand on;
   - the current drifts upwards.
4. Run for **at least 60 minutes**, and on until the NTC has risen less than 1 °C over the last 10
   minutes (steady state).
5. Just before the end, put a hand on the case. Note any warm spot, and measure it with an IR
   thermometer if you have one (plastic reads well).
6. Note `petro_energy_kwh_total` and the power meter's kWh at the start and end of the run.
7. Relay off and mode **off** (README rule 8); switch off at the wall, unplug. Then README rule 6:
   wait, open without touching the board, check C1 (D7's cathode to TP6), discharge if needed.
8. **Read every label** (its highest changed window) and photograph them
   (`b<k>-labels-after.jpg`). Then, with the thermocouple if you have one, measure T1–T7 quickly.
   Note how long after unplugging: these read low, which is why the labels are the record.

**Scaling to 10 A:** the copper's and contacts' heat goes as the current squared, so

> rise at 10 A ≈ measured rise × (10 / measured A)²

For example, a 20 °C rise at 8.7 A is about 26 °C at 10 A. The pass limits apply to the scaled
figure. **Scale only T1–T6** (the current path). R1 (T7), the case wall (T8) and the relay's coil
don't follow the load current: use their rises as measured.

**The 70 °C limit at a warm room:** a peak measured at room temperature R is judged as
peak + (35 °C − R), so a 60 °C peak in a 20 °C room counts as 75 °C.

## 4. The metering comparison

From Gates 3 and 4, against the power meter:

| Load | Petro V / meter V | Petro A / meter A | Petro W / meter W |
|---|---|---|---|
| None, relay off | | — | |
| The 60 W lamp | | | |
| The heater | | | |
| **Energy over the run** | Petro kWh: | Meter kWh: | Error: |

PETRO-4's calibration should bring each within ± 2 % at the heater (the power meter's own
accuracy limits this). In the idle row Petro reads about 0 W against the meter's ~0.6 W, which is
right: the shunt doesn't carry Petro's own supply current.

## 5. The NTC's calibration

The NTC (TH1) sits beside the relay on the board and under-reads the hot spots
(`docs/DESIGN.md` §4).

| | Rise at the end of the run |
|---|---|
| The NTC | |
| T4 (K1) | |
| The hottest of T1–T7 | |

Ratio = hottest rise / NTC rise. PETRO-5's over-temperature threshold is set from this ratio, so
that the NTC trips before the hottest spot reaches 70 °C.

## 6. 500 relay cycles at load

1. Close up, plug in, heater on. Through Fleet: **relay cycle 500, 3 s on, 5 s off** (about 67
   minutes).
2. Watch VictoriaMetrics:
   - `petro_relay_on` toggling;
   - no resets;
   - no trips;
   - the NTC staying below the hour-long run's figure.
3. When it finishes, let the unit **cool to within 1 °C of step 3's starting NTC reading**
   (relay off, a few hours), so both runs start alike. Then **relay on for 30 minutes** at the
   heater's load, and compare the NTC's rise at 30 minutes with the same point in step 3's run:
   - within 3 °C: the contacts are as good as before;
   - more: the contacts have worn or a joint has degraded. Open it up (README rule 6), inspect K1's
     joints, and don't use this board until that's understood.
4. Mode off, unplug, README rule 6, open. Look for discolouration at K1 and the terminals.
   Photograph.
5. **The contact resistance, directly:** repeat Gate 2's step 5.2a (on USB, mains unplugged: relay
   on, the same current from the bench supply, the mV across the same points). More than about
   50 % up on Gate 2's figure means the contact has worn.

**Gate 4 passes** when the scaled rises are under 30 °C, nothing reaches about 70 °C, the trip
works, and the relay is unchanged after 500 cycles.

## Results

### B1

Date: · Firmware version: · Room temperature: · Load: (heater, W, A)

| Check | Reading | Pass? | Notes |
|---|---|---|---|
| 1 trip at the temporary threshold; cleared; threshold back after reboot | | | |
| 3 run length; current; NTC start / end | | | |
| T1 J1 L (peak, rise, scaled to 10 A) | | | |
| T2 J2 L | | | |
| T3 F1 clip | | | |
| T4 K1 | | | |
| T5 RS1 | | | |
| T6 L_F pour | | | |
| T7 R1 | | | |
| T8 case wall | | | |
| Case outside (hand / IR) | | | |
| Snapshot after opening (minutes after unplugging; readings) | | | |
| 4 metering table | | | |
| 5 NTC ratio | | | |
| 6 500 cycles: resets, trips | | | |
| 6.3 NTC rise at 30 min, before / after cycling | | | |
| 6.4 inspection | | | |
| 6.5 contact mV: Gate 2 / after cycling | | | |
| 1.6 real trip at ~10.9 A | | | |
