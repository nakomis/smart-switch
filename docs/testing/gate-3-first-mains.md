# Gate 3: first mains power-up

**Martin only. The unit is closed in its case before it is ever plugged in.** It runs from an
RCD-protected socket, and nothing is connected to the board but its own cords: no USB, no probe,
no scope. Everything is read from outside, over Wi-Fi (Fleet and VictoriaMetrics), or from the
plug-in power meter.

Read the rules in [README.md](README.md) first.

## Prerequisites

- [ ] Gates 2 and 2b passed on this board.
- [ ] The mode is **off** (README rule 8), so the relay stays open at power-up. Check with `info`
  over USB before the case is closed.
- [ ] The firmware (PETRO-3) is flashed over USB and **provisioned**: Wi-Fi, the Fleet
  certificate and the VictoriaMetrics credential, all in `prov`. Confirm `info` shows each key
  present, then **unplug USB**.
- [ ] Fleet shows the Thing, and VictoriaMetrics shows its `petro_*` series. This works from Gate
  2b's bench supply or from USB; the dashboards need to be working before mains is involved.
- [ ] F2 (T500 mA ceramic) is in its holder; F1 (15 A) is in its clips.
- [ ] **The case** (PETRO-6), printed in the V-0 filament:
  - the board is on nylon M3 screws;
  - the button cap is captive and the light pipe is seated;
  - the cords pass through the glands with their cord grips tight;
  - the earth is joined from the input cord to the output on a Wago 221, clear of the board, with
    the earth conductor left **longer** than L and N at each grip, so that it takes strain last;
  - the case is closed and screwed.
- [ ] **Look over the outside:**
  - no metal is exposed: screw heads are recessed or nylon, and no part of the board shows through
    any gap;
  - the button and the light pipe can't be pushed in to reach the board (Fable, at Gate 1).
- [ ] The input cord ends in a BS 1363 plug with a **13 A** fuse. The output ends in its socket or
  appliance lead (PETRO-6).
- [ ] At hand:
  - the socket tester and the plug-in RCD;
  - the plug-in power meter;
  - the dim-bulb tester;
  - a 60 W incandescent lamp on a lead;
  - the meter, the insulation tester and the discharge tool (README);
  - Fleet and VictoriaMetrics on a laptop that is **not** connected to the unit.

## 1. Dead checks, case closed (unplugged)

The meter on resistance, at the input plug's pins and the output's socket.

| # | Between | Expected | If not |
|---|---|---|---|
| 1.1 | Input plug L and N | Climbs to about **1.95 MΩ** (the meter charges C1 through D7 one way; the divider shows the other) | A short or a low reading: stop |
| 1.2 | Input L and E; input N and E | **∞** (above 20 MΩ) | **Stop: the earth touches something live** |
| 1.3 | Input E and output E | **< 0.5 Ω** | The earth's Wago or a crimp |
| 1.4 | Input L and output L | ∞ (the relay is open) | |
| 1.5 | Input N and output N | ≈ 0 Ω | |
| 1.6 | Output L and output N | ∞ (nothing on the output) | |
| 1.7 | Input L and N to each case screw and the gland nuts | ∞ | |

**1.8 Insulation at 500 V DC.** The case is the only barrier, and a meter at about 1 V can't find
a creepage path through a gap, the button or the light pipe.
1. Join the input plug's L and N pins together with a short lead. The MOV then sees nothing.
2. With the insulation tester at 500 V DC, measure from L+N to:
   - the earth pin: at least **2 MΩ**;
   - aluminium foil pressed over the button cap: at least **7 MΩ**;
   - the same over the light pipe, then along each seam of the case and over each gland, one at
     a time: at least **7 MΩ** each.
3. Remove the link.

Any reading below: stop, and find the path before going on.

**1.9 Distances at the openings** (PETRO-6's design, checked on the print): from the outside
surface of the button cap and the light pipe to the nearest live part (the switch's top plate,
the LED) is at least **6 mm** through the insulating parts (reinforced insulation, as there is
no earth to fall back on).

## 2. The socket

1. Plug the socket tester into the wall socket: it shows **correct** (no reversal, earth present).
2. Plug in the plug-in RCD and press its **test** button: it trips. Reset it.
3. The chain, in this order: wall socket → plug-in RCD → plug-in power meter → the unit.

## 3. First power-up through the dim bulb

The dim-bulb tester goes between the power meter and the unit, with a 60–100 W **incandescent**
lamp. With a short anywhere in the unit, the lamp lights fully and takes the voltage. A healthy
unit draws under 1–2 W, so the lamp stays dark.

| # | Do | Expected | Stop if |
|---|---|---|---|
| 3.1 | Nothing on the output. Plug the unit into the dim-bulb tester, then switch on at the wall | A brief glimmer at most (C1 and C2 charging), then dark. The LED shows the boot colours, then Wi-Fi joining, then connected | The lamp stays lit; the RCD trips; any smell, sound or smoke |
| 3.2 | Wait 5 minutes | Fleet: connected. VictoriaMetrics: `petro_voltage_volts` reads a few volts **below** the power meter's reading (the lamp drops a little; UK mains is often 240–245 V); `petro_zx_hz` ≈ 100; `petro_relay_on` 0 | The voltage reads 0 or wildly off |
| 3.3 | Press the button **once** (off → on) | The relay clicks; the lamp stays dark (nothing on the output) | The lamp lights |
| 3.4 | Press it **twice more** (on → auto → off), or set off from Fleet; check `petro_relay_on` is 0. Switch off at the wall, then unplug | | |

## 4. Direct, with a lamp load

The dim-bulb tester comes out: wall → RCD → power meter → the unit → the 60 W lamp on the output.

| # | Do | Expected | Stop if |
|---|---|---|---|
| 4.1 | Relay off. Switch on at the wall | The unit boots and connects; the lamp is off | The lamp lights with the relay off |
| 4.2 | Read the power meter | **Idle power** (relay off): note it. Expected under 1 W, though many plug-in meters can't resolve below 1 W | Over 2 W |
| 4.3 | `petro_voltage_volts` against the power meter's voltage | Within ± 10 % (uncalibrated; PETRO-4 calibrates). The UK range is 216–253 V | More than 20 % off |
| 4.4 | Relay on with the button | The lamp lights. The power meter shows about 60 W; `petro_power_watts` and `petro_current_amps` (≈ 0.26 A) within ± 10 %. Note the idle power with the relay on (the coil's 0.4 W is about 0.6 W at the wall) | |
| 4.5 | Relay off and on from Fleet | The lamp follows | |
| 4.5a | Relay on. Swap the lamp for the **socket tester** on Petro's output | Correct polarity and earth present at the output too | Anything else: stop |
| 4.6 | Five minutes on, then a hand on the case | Not noticeably warm anywhere | Warm anywhere |

## 5. Inrush: F2 against plugging in

F2's melting I²t is 0.42 A²s, and the inrush into C1 and C2 through R1 is estimated at about
0.05 A²s (`docs/DESIGN.md` §5.3).

1. Relay off. Switch the socket on and off **10 times**, about 10 seconds on and 10 seconds off.
2. Each time the unit must boot and connect. If F2 has blown, the unit stays dead: the LED is
   dark and there is no Fleet connection.

If F2 blows (and only then):
- unplug and open (README rule 6);
- confirm nothing else is damaged, **R1 included** (a fusible resistor can open on repeated
  surges: measure it, 10 Ω);
- fit **T1A** (`docs/DESIGN.md` §5.3);
- repeat this step;
- record it.

## 6. An hour under Wi-Fi load

The supply's margin under sustained Wi-Fi transmission with the relay's coil on (Fable and Opus,
at Gate 1).

1. Relay on, the lamp lit, and the firmware's **Wi-Fi transmit-stress mode** on through Fleet, for
   **1 hour**. One push every 10 s isn't sustained transmission.
2. VictoriaMetrics, for the hour:
   - `petro_resets_total` must not rise (in particular, no `reason="brownout"`);
   - `petro_uptime_seconds` climbs without a break;
   - `petro_board_temperature_celsius`: note the rise from room temperature;
   - `petro_wifi_rssi_dbm`: note it.
3. Stress mode off, mode **off** (README rule 8). Switch off at the wall and unplug.

## 7. Opening up

1. Follow README rule 6: wait 2 minutes, open without touching the board, and measure D7's
   cathode to TP6. Note the reading and the time since unplugging. Above 30 V: discharge with the
   tool and measure again.
2. Look and smell:
   - no discolouration;
   - nothing melted or bulged (C1, C2, C4, R1);
   - no flux residue that has darkened.
3. Photograph the board (`photos/gate-3/b<k>-after.jpg`).

**Gate 3 passes** when steps 1–7 match: no lamp in the dim-bulb test, idle power under 2 W,
readings within the ranges, F2 surviving 10 plug-ins (or T1A fitted and surviving), and an hour
without a reset.

## Results

### B1

Date: · Firmware version: · Room temperature:

| Check | Reading | Pass? | Notes |
|---|---|---|---|
| Prerequisites | | | |
| 1.1–1.7 dead checks | | | |
| 1.8 insulation at 500 V: earth / button / light pipe / seams / glands | | | |
| 1.9 distances at the openings | | | |
| 4.5a socket tester at the output | | | |
| 2 socket tester, RCD test | | | |
| 3.1 dim bulb dark, boots | | | |
| 3.2 V (dim bulb), ZX | | | |
| 3.3 relay, no load | | | |
| 4.2 idle power, relay off | | | |
| 4.3 V: Petro / meter | | | |
| 4.4 lamp: W and A, Petro / meter; idle power relay on | | | |
| 4.5 Fleet control | | | |
| 4.6 case warm? | | | |
| 5 10 plug-ins: F2 | | | |
| 6 1 h: resets, NTC rise, RSSI | | | |
| 7 C1 after 2 min; inspection | | | |
