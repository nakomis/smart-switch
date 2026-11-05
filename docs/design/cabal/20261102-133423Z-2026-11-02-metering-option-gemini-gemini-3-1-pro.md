# Cabal consultation — gemini:gemini-3.1-pro

- Tokens: 809 in / 4053 out
- Cost: $0.050254 USD
- Latency: 38260 ms

## Prompt

```
Design review question for a home-built (personal use only, never sold) 230 V AC / 10 A continuous Wi-Fi smart switch, an in-line cord unit (cable in, cable out). ESP32-S3 on the low-voltage side, powered by an isolated Mean Well IRM-03-5 module (reinforced isolation) so everything after it is SELV, with a house USB connector for flashing that must be safe to touch while mains-connected. A 16 A relay with reinforced coil-contact insulation bridges SELV/mains. Metering chip: BL0942 (UART, single-phase). 2-layer PCB, 2 oz copper, 8 mm creepage mains↔SELV.

The BL0942's ground sits at whatever its sense inputs reference. Two options:

Option A (what commercial plugs do): a 1 mΩ manganin 2512 shunt in the live, plus a resistor divider for voltage. The BL0942 lives on the mains side, powered by its own tiny supply there (a capacitive dropper ~1 mA, or a second small isolated module, or a winding?). Its UART TX/RX crosses the 8 mm gap through two reinforced-isolation optocouplers or a reinforced digital isolator (wide-body, e.g. ISO6721-style), with the isolator's mains-side supply coming from the mains-side rail.

Option B: a current transformer (e.g. ZMCT103C) and a voltage transformer (e.g. ZMPT101B) feed the BL0942 on the SELV side. No isolators, no mains-side supply, but bulkier, adds phase error that calibration must remove, and is less accurate at low loads.

Questions, answer in order:
1. Which option would you choose for this build, and why? Be concrete.
2. For Option A: what is the best way to power the BL0942 and the isolator's mains side (capacitive dropper, a second IRM module, an IRM with a non-isolated tap, something else)? Any trap with a dropper here (inrush, surge, MOV placement, the dropper's X2 cap)?
3. For Option A: optocouplers or a digital isolator for the 4800-baud UART, and what isolation rating/creepage must the part itself have to count as reinforced at 230 V for a personal device (IEC 62368 / 60664 terms)?
4. For Option B: is the ZMPT101B actually rated as a safety isolation barrier, or is it a cheap module whose insulation you should not trust? Same for the ZMCT103C.
5. Anything about the shunt (manganin 1 mΩ at 10 A = 0.1 W; Kelvin connection; thermal EMF; which side of the relay; placement relative to the fuse) that commonly goes wrong?
6. Any failure mode of either option that would compromise the SELV side's safety (i.e., make the USB connector live) that I should design out?
7. One thing you think I have not considered at all.
```


**System prompt:**

```
Be blunt. If any part of the question or design is wrong, hand-wavy, or based on a misunderstanding, say so directly. Prefer "this won't work because X" over polite hedging. Don't pad with caveats unless the caveat *is* the answer. If a question is malformed, point that out instead of answering it as asked. If the questions are numbered, answer them in order using the same numbering so the replies can be diffed across models.
```

## Response

1. **Option A.** It is objectively better for an inline cord unit. Option B requires bulky transformers that will not fit well in a cable-in/cable-out form factor, introduces phase errors that require complex software calibration, and relies on uncertified Chinese transformers (ZMPT/ZMCT) for your life safety. Option A uses verifiable, certified solid-state isolation and is the industry standard for a reason.

2. **A half-wave capacitive dropper.** Do not use a second IRM module; it wastes space and money. 
*The traps:* 
First, you *must* use a half-wave rectifier, not a full-wave bridge. A full-wave bridge destroys the common ground reference between the BL0942 and the mains line, making the shunt voltage impossible to read. 
Second, capacitive droppers cannot supply the 5-10mA needed to drive optocoupler LEDs without requiring a physically massive X2 capacitor. 
Third, inrush current. If you omit a surge-limiting wirewound or fusible resistor in series with the X2 cap, mains transients will treat the capacitor as a dead short and blow the Zener diode or LDO instantly. Place the MOV directly across L and N *before* the dropper's series resistor so it clamps before the transient hits the dropper.

3. **A digital isolator.** Optocouplers require too much LED forward current (often 5mA+ each), which breaks the power budget of a reasonably sized capacitive dropper. A digital isolator (like the TI ISO6721) draws <2mA. 
To count as reinforced at 230 V under IEC 62368-1, the isolator must be in a wide-body package (e.g., SOIC-8 wide) guaranteeing $\ge$ 8 mm creepage and clearance. The datasheet must explicitly state it is certified for "Reinforced Isolation" with a working voltage of $\ge$ 250 Vrms and a transient overvoltage rating of $\ge$ 5 kVrms. 

4. **Do not trust them.** The ZMPT101B and ZMCT103C are cheap, uncertified components. While they claim high dielectric withstand voltages, they lack UL/VDE/TUV certification for reinforced safety isolation under IEC standards. Using them as the sole barrier between 230 V mains and a touch-safe USB port is a severe safety hazard. 

5. **Placement relative to the relay.** You must place the shunt and the BL0942's power tap *before* the relay (on the incoming mains side). If you place them after the relay, the BL0942 loses its line reference and power when the relay opens, rendering it dead and unable to measure line voltage or detect zero-crossings. 
*Routing:* You must use strict Kelvin connections. Route thin force/sense traces from the *inside* edges of the shunt pads directly to the BL0942. If you route the main 10 A trace through the sense pads, the copper trace resistance will dwarf your 1 mΩ shunt and ruin your calibration. 
*Placement relative to fuse:* The shunt must be downstream of the main fuse so a catastrophic failure of the shunt clears the fuse.

6. **Carbon tracking from a mains-side blowout.** If the capacitive dropper's X2 cap, Zener, or the MOV fails violently (which happens during severe surges), the resulting plasma arc and carbon soot can bridge your 8 mm creepage gap, making the USB port live. You must design this out by cutting an isolation slot (a physical hole in the PCB) along the 8 mm boundary between the mains and SELV sides, and physically locating the high-energy mains components (fuse, MOV, dropper) as far from the isolation boundary as possible.

7. **Your power budget is maxed out.** The Mean Well IRM-03-5 provides exactly 600 mA. An ESP32-S3 can draw 500 mA peaks during Wi-Fi transmission. A standard 5 V / 16 A relay coil draws ~80 to 100 mA. 500 + 90 = 590 mA. You have zero margin. When the relay is closed and the ESP32 transmits, the 5 V rail will sag, causing brownouts and continuous reboot loops. You must upgrade to the IRM-05-5 or use a latching relay to remove the continuous coil current.
