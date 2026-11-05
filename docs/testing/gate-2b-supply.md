# Gate 2b: the supply from a bench DC supply

This proves the LNK306 → 12 V → 5 V chain **without mains**. A current-limited bench supply at no
more than **60 V DC** (extra-low voltage, touch-safe) feeds the smoothed DC bus directly. On mains
that bus sits at about 325 V, so here the supply runs gently, at light load. Full-load behaviour
waits for Gate 3.

**Never above 60 V DC.** Above that the board stops being touch-safe, and this stops being a bench
test.

**Needs:**
- Gate 2 passed on this board;
- the bench DC supply with a current limit;
- two insulated clip leads;
- the meter;
- the USB cable, for step 5.

## Why it works, and what we don't know

- The bus is VBULK1, C1's + lead. With **F2 out**, nothing upstream is connected:
  - D7 (the rectifier) is reverse-biased by the bench supply, so nothing reaches L_RF or the live
    side;
  - F2's empty holder isolates R1.

  So the bench supply sees only the π filter (C1, L1, C2) and the LNK306's drain.
- The LNK306 charges its BYPASS pin from its drain, so it needs no bias supply. Its datasheet sizes
  designs for at least 70 V DC at full load, but publishes no minimum for starting at light load.
  **Finding where it starts and regulates is the result of this gate.** If the bench supply can't
  reach that, the result is "doesn't start at ≤ <max> V", which is safe and still worth recording.
- The LNK306's output (+12 V) and TPS563201's (VPSU, 5.07 V) are both measured to GND.

## Setup

1. F2 out (check the holder is empty); nothing on J1 or J2; USB unplugged.
2. Set the bench supply to **0 V and 50 mA**, output off. Expect the LNK306 to need tens of volts
   to start; it may not start at all by 60 V.
3. The negative lead to **C1's − lead** on the underside (GND); the positive lead to **C1's +
   lead** (VBULK1). Check them against the silk and the stripe twice: reversed, it drives C1 and
   C2 backwards.
4. The meter's black lead to a GND test hole (TP6); the red lead where each step says.

## Steps

Record the input current and each rail at every step.

| # | Bench supply | Measure | Expected |
|---|---|---|---|
| 1 | Output on at 0 V, then 5, 10, 15, 20 V | Input current | A brief charging spike, then a few mA or less (C1 and C2 charging, the LNK306's start-up current) |
| 2 | Then up in 2 V steps to the supply's maximum (≤ 60 V) | +12V across C4 (the 220 µF), and VPSU_F at D5's anode (VPSU after F3) | Somewhere in this range **+12V rises to about 12.4 V** (12.0–12.9 V) and VPSU to about 5.07 V. Note the voltage where each first appears and where they stop moving |
| 3 | Hold there | +5V (TP7), +3V3 (TP9); the LED | +5V 4.6–4.9 V (through D5); +3V3 3.25–3.35 V; the C6 boots (the LED shows the firmware's boot colour) |
| 4 | Hold, with the current limit raised to 100 mA if the input is near the limit | Input current at idle | Note it, and input power = V × I |
| 5 | Plug in USB too (laptop on battery preferably), and open the console | `info`; +5V | The board stays up, nothing resets. +5V follows whichever of USB and VPSU is higher, less a Schottky drop. Neither source back-feeds the other: VBUS stays at the laptop's 5 V and VPSU at 5.07 V |
| 6 | USB unplugged, so the supply carries everything. **Current limit to 150 mA** (still under 9 W at 60 V). Press the button once to go from off to on | Input current, +12V, +5V with the relay on | The click; note whether +12V holds, sags, or the LNK306 hiccups (restarts) at the current limit |
| 7 | With the board provisioned, it joins Wi-Fi by itself; leave it 5 minutes, relay on | +12V, +5V; then `petro_uptime_seconds` and `petro_resets_total` in Fleet/VictoriaMetrics, or `info` over USB with `idf.py monitor --no-reset` | Note any brown-outs. **Steps 6 and 7 are observations, not pass criteria**: the supply's margin under load is proved on mains, at Gate 3 step 6 |
| 7a | Press the button until the mode is **off** (README rule 8) | `petro_relay_on` 0 | |
| 8 | Turn the bench supply down slowly | The voltage where +12V drops out | Note it |
| 9 | Output off, leads off. Measure C1 (D7's cathode to TP6) at **2, 5 and 15 minutes** | C1's voltage | **Nothing bleeds the bus**: once the LNK306 stops switching, the rest stays. This resting voltage, scaled up, is why README rule 6 has a discharge tool. Then discharge it with the tool |

**Stop** at once (output off) if:
- the current goes to the limit and stays there with the voltage collapsing (a short);
- anything gets warm to the touch at these voltages, especially U4, D8, L2 and C4;
- +12V goes above 13.5 V or +5V above 5.3 V.

**Gate 2b passes** if:
- the supply starts and regulates within the bench supply's range, and steps 3–5 hold;
- or, if it doesn't start by 60 V, nothing gets warm and nothing draws more than its start-up
  current. That result is recorded, and the supply's own test is deferred to Gate 3's dim-bulb
  step.

## Results

### B1

Date: · Bench supply max: · Firmware version:

| Step | Reading | Notes |
|---|---|---|
| 1 current at 20 V | | |
| 2 +12V first appears at (V) | | |
| 2 +12V regulates (12.4 V) from (V) | | |
| 2 VPSU (5.07 V) from (V) | | |
| 3 +5V / +3V3, boots? | | |
| 4 idle input current and power at (V) | | |
| 5 USB + supply: resets? VBUS / VPSU | | |
| 6 relay on: input current, +12V, +5V | | |
| 7 Wi-Fi + relay: resets? | | |
| 8 drop-out voltage | | |
| 9 C1 at 2 / 5 / 15 min | | |
| Pass? | | |
