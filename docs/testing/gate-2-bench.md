# Gate 2: on the bench, USB only

**Mains is never connected during this gate.** No cord goes on J1 or J2. The board runs from USB
alone (J4, the house connector), which powers the 5 V and 3.3 V rails, the C6, the relay's coil,
the LED and the BL0939. The 12 V supply stays dead; Gate 2b tests it.

Read the rules in [README.md](README.md) first. Run this on B1, then on the others.

**Needs:**
- the meter;
- a 90–100 W soldering iron with a large chisel tip, and ideally a preheater (a hot plate, or the
  hot air gun on low from underneath);
- flux, isopropyl alcohol and a stiff brush;
- a loupe or a phone camera on macro;
- the purple house USB cable;
- a laptop with ESP-IDF 5.5;
- PETRO-3's firmware with the USB console (`docs/testing/README.md` lists its commands).

## 1. Incoming inspection (unpowered)

Photograph the top and bottom (`photos/gate-2/b<k>-top.jpg`, `-bottom.jpg`), then check with the
loupe:

| # | Check | Expected |
|---|---|---|
| 1.1 | U1 (the C6 module) | Its pads under the castellations: no bridges, especially along the bottom row and the centre pad |
| 1.2 | Orientation of U3 (BL0939), U4 (LNK306), U5 (TPS563201), U2 (AP2112K), U6 (SRV05-4) | Pin 1 matches the silk dot |
| 1.3 | Polarity of D7 and D9 (M7), D8 (US1M), D3 (1N4148W), D5 and D6 (SS34), D2 and D4 (TVS) | The band matches the silk |
| 1.4 | C1 and C2 (4.7 µF 400 V cans) | The stripe (−) on the GND side; leads soldered on the underside |
| 1.5 | RS1 (the shunt) | All four pads soldered; no bridge between the sense pads (inner) and the current pads (outer) |
| 1.6 | R29 (0 Ω, the GND–neutral bond) | Present and soldered |
| 1.7 | The divider, R12–R16 (5 × 390 kΩ 1206) and R17 | All present; nothing between the pads |
| 1.8 | The board surface | No solder balls, splashes or whiskers anywhere in the mains area or the supply's gaps |

## 2. Dead checks, before hand-fitting (unpowered)

The meter on resistance. The terminals aren't fitted yet, so use their pads. Reading GND, use a
GND test hole (TP6, TP8 or TP11).

| # | Between | Expected | Why |
|---|---|---|---|
| 2.1 | +5V (TP7) and GND | Not a short: rising past 100 Ω as the capacitors charge | |
| 2.2 | +3V3 (TP9) and GND | Not a short: rising past 100 Ω | |
| 2.3 | C1's + lead and GND | Rising, past 100 kΩ | The DC bus |
| 2.4 | J1's N pad and GND | **About 0 Ω** (the lead resistance) | R29 |
| 2.5 | J1's N pad and J2's N pad | **About 0 Ω** | The shunt (1 mΩ) |
| 2.6 | J1's L pad and J1's N pad | **About 1.95 MΩ** (20 MΩ range) | The divider (5 × 390 kΩ + 470 Ω) |
| 2.7 | J1's L pad and the F1 clip pads | ∞ until F1 is fitted | |
| 2.8 | Any mains pad and each mounting hole's surround | ∞ | The holes are unplated |

Anything that reads as a short: find it before going on.

## 3. Hand-fitting the mains parts

The parts are in `pcb/out/petro/hand-fit.csv`, bought from authorised distributors:
- J1 and J2 (Degson DG636, wire entry at their own ends);
- K1 (the relay);
- R1 (10 Ω 2 W fusible);
- RV1 (the MOV);
- XF1 and XF2 (F1's clips);
- XF3 (F2's holder).

**These joints carry 10 A, and solid pours on both layers make them heavy heatsinks.** A cold or
part-filled joint is about 1 W in the fillet at 10 A: that is how these units cook (Fable, at
Gate 1).

1. Preheat the board if you can (to about 100 °C from underneath).
2. Use the 90–100 W iron with plenty of flux. Hold the tip until solder **wicks through the barrel
   and wets the top-side pad** as well.
3. Fit K1, J1 and J2, then the clips and the holder, then R1 and RV1. Keep R1's body about 2 mm
   off the board: it runs warm.
4. **Check every mains joint from both sides:**
   - a concave fillet on the solder side;
   - solder visible round the lead on the component side (at least 75 % of the barrel filled);
   - nothing dull or grainy.

   Reflow anything doubtful.
5. **Clean all the flux** with isopropyl alcohol and the brush, top and bottom:
   - the mains area;
   - **the supply's middle** (U4, D8, L1, L2, C1, C2, R2), where gaps are only 1.0 mm. Fable's
     condition for accepting 1.0 mm was clean flux.

   Let it dry fully.
6. Fit F1 (15 A, 6.3×32 mm ceramic) in its clips. **Leave F2 out** until Gate 3.
7. Photograph both sides (`b<k>-fitted-top.jpg`, `-bottom.jpg`).

**Dead checks after fitting:**

| # | Between | Expected |
|---|---|---|
| 3.1 | J1 L and J1 N | Still about 1.95 MΩ |
| 3.2 | J1 L and J2 L | ∞ (the relay is open) |
| 3.3 | J2 L and J2 N | ∞ |
| 3.4 | J1 L and C1's + lead | ∞ (F2 out) |
| 3.5 | Each terminal screw, tightened onto a scrap of wire, and the board | Firm; the terminal doesn't move on its joints |

## 4. The USB cable

The house cable, before it goes near the board (`CLAUDE.md`: JST SH 5-pin, 1 VBUS, 2 D−, 3 D+,
4 CC, 5 GND). Plug its USB-C end into a charger, and on the JST end measure:

| # | Between | Expected |
|---|---|---|
| 4.1 | Pin 1 and pin 5 | **≈ 5 V**, pin 1 positive (most chargers give it only once the board's 5.1 kΩ Rd is on CC; if 0 V, check with the cable on the board at step 5.1) |
| 4.2 | Any other pin and pin 5 | ≈ 0 V |

Then, with the cable unplugged, check continuity from the USB-C plug to each JST pin, to be sure
it isn't a 4-pin Qwiic-style cable.

## 5. Powered on USB

The laptop on battery or mains is fine here, **because no mains reaches the board**.

| # | Do | Expected |
|---|---|---|
| 5.1 | Plug in USB. Measure +5V (TP7) and +3V3 (TP9) to GND | +5V **4.5–4.9 V** (USB through D6's Schottky); +3V3 **3.25–3.35 V**. Nothing warm (fingertip on U2, U5, U3) |
| 5.2 | Flash the firmware (`idf.py -p <port> flash monitor`) | Flashes, boots, the console prompt appears |
| 5.3 | `info` | The version, the MAC, the reset reason; `prov` state |
| 5.4 | `led 255 0 0`, then `0 255 0`, `0 0 255`, `0 0 0` | Red, green, blue, off |
| 5.5 | `button`, press SW1 three times | Three presses and releases logged, no bounce doubles |
| 5.6 | `relay on`; measure COIL (TP10) to GND; then `relay off` | A click. COIL ≈ 0 V when on; ≈ +5V when off |
| 5.7 | `relay on`, and measure **J1 L to J2 L** with the meter on continuity | ≈ 0 Ω (through F1 and the closed contact). `relay off`: ∞ |
| 5.8 | `relay cycle 20 200 200` | 20 clicks; the C6 doesn't reset (no brown-out from the coil) |
| 5.9 | `bl` | Every frame's checksum good. **Voltage and currents near zero** (no mains); the chip's temperature near room temperature |
| 5.10 | `edges` | ZX and OC: 0 a second (no mains) |
| 5.11 | `ntc` | Within ± 3 °C of the room's temperature |
| 5.12 | `wifi scan`, with the board where it'll live | The house APs listed; the strongest at least −70 dBm in the same room |
| 5.13 | `j3` (with an LED and 1 kΩ from OUT to GND, if handy) | OUT toggles at 1 Hz; IN reads 0 (100 kΩ pull-down); I²C scan finds nothing (or the sensor fitted) |
| 5.14 | The current USB draws (a USB meter, if you have one), relay on, Wi-Fi scanning | Under 400 mA |

OTA is checked once PETRO-3 has it, through Fleet with USB still the only supply. Record it here
too.

**Gate 2 passes** when every check above matches on that board.

## Results

Copy the table for each board.

### B1

Date: · Firmware version: · Tester: Martin

| Check | Reading | Pass? | Notes |
|---|---|---|---|
| 1.1–1.8 inspection | | | |
| 2.1 +5V–GND | | | |
| 2.2 +3V3–GND | | | |
| 2.3 C1+–GND | | | |
| 2.4 N–GND | | | |
| 2.5 N_IN–N_OUT | | | |
| 2.6 L–N | | | |
| 2.8 mains–holes | | | |
| 3 joints both sides, flux cleaned | | | |
| 3.1–3.5 | | | |
| 4 cable | | | |
| 5.1 +5V / +3V3 | | | |
| 5.2–5.3 flash, info | | | |
| 5.4 LED | | | |
| 5.5 button | | | |
| 5.6 relay, COIL | | | |
| 5.7 contact continuity | | | |
| 5.8 cycling | | | |
| 5.9 BL0939 | | | |
| 5.10 edges | | | |
| 5.11 NTC (room °C) | | | |
| 5.12 RSSI | | | |
| 5.13 J3 | | | |
| 5.14 USB current | | | |
| OTA (PETRO-3) | | | |
