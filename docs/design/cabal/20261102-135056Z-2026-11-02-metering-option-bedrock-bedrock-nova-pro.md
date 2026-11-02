# Cabal consultation — bedrock:nova-pro

- Tokens: 823 in / 423 out
- Cost: $0.002012 USD
- Latency: 4428 ms

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

1. Choose Option B. Despite its bulkiness and potential phase error, it simplifies the design by avoiding mains-side electronics and complex isolation schemes. The BL0942 on the SELV side reduces risk and complexity. Calibration for phase error is a solvable problem.

2. For Option A, using a second small isolated module (like another IRM-03-5) is the best approach. Capacitive droppers are problematic due to inrush current, surge vulnerability, and the need for precise MOV placement to protect the dropper's X2 capacitor. A dedicated isolated supply avoids these issues.

3. For Option A, use a digital isolator rated for reinforced insulation. The ISO6721-style isolators are suitable, offering the necessary creepage and clearance for 230 V applications. Optocouplers are less reliable for digital signals at 4800 baud over reinforced isolation distances.

4. The ZMPT101B and ZMCT103C are not rated as safety isolation barriers. Their insulation should not be trusted for safety-critical applications. Use them for signal transformation only, not as a substitute for proper isolation.

5. The shunt's placement should be on the load side of the relay to ensure it's only in circuit when the relay is closed. Ensure proper Kelvin connection to minimize measurement error. Thermal EMF is negligible at these currents. Ensure the shunt can dissipate 0.1 W without overheating.

6. A failure in the isolation barrier (whether optocouplers, digital isolators, or transformers) could compromise SELV safety. Design with redundant isolation or fail-safe mechanisms (e.g., fuses on the SELV side) to prevent live conditions on the SELV side in case of isolation failure.

7. Consider the environmental conditions the device will operate in. Ensure the design accounts for temperature extremes, humidity, and potential physical damage. Use conformal coating on the PCB if necessary, and choose components rated for the expected operating conditions.
