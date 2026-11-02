# Cabal consultation — bedrock:mistral-large

- Tokens: 893 in / 715 out
- Cost: $0.006076 USD
- Latency: 14822 ms

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

1. I would choose Option A for this build. The main reason is that Option A provides better accuracy at low loads compared to Option B. Additionally, Option A uses a manganin shunt for current sensing, which is known for its high stability and low thermal coefficient of resistance, resulting in more accurate current measurements. Lastly, Option A does not introduce phase error, which can be challenging to calibrate out.
2. For powering the BL0942 and the isolator's mains side in Option A, I would recommend using a second small isolated module, such as another Mean Well IRM-03-5. This approach is safer and more reliable than using a capacitive dropper, which may have issues with inrush current, surge, and MOV placement. An IRM with a non-isolated tap could be considered, but it might compromise safety and reinforce insulation.
3. For the 4800-baud UART in Option A, using a reinforced digital isolator would be a better choice than optocouplers. This is because digital isolators provide better noise immunity, higher data integrity, and lower power consumption. The isolation rating for the part itself should be at least 5000 Vrms (reinforced) to meet the safety requirements for 230 V AC applications, according to IEC 62368 and IEC 60664 standards. The creepage distance should be at least 8 mm for reinforced insulation.
4. The ZMPT101B and ZMCT103C modules are not explicitly rated as safety isolation barriers. Although they provide some level of insulation, it is not recommended to rely solely on their insulation for safety. Instead, use additional safety measures and components with certified reinforced insulation ratings to ensure user safety.
5. Regarding the shunt, a common issue is thermal EMF, which can introduce measurement errors. To minimize this, consider using a shunt with a low thermal coefficient or using a differential amplifier to cancel out the thermal EMF. Additionally, place the shunt on the line side of the relay to avoid measuring any inrush current caused by the relay coil. Lastly, ensure proper placement of the shunt relative to the fuse, as the fuse should be placed on the line side to protect the entire circuit.
6. A potential failure mode that could compromise the SELV side's safety in both options is a failure of the reinforced insulation between the mains and SELV sides. To mitigate this risk, ensure that all components with reinforced insulation (such as the IRM-03-5 module, optocouplers, or digital isolators) are rated for the appropriate voltage and have adequate creepage distances. Additionally, implement a protective earth connection and use a fuse on the mains side to protect against overcurrent situations.
7. One aspect you might not have considered is the potential for electromagnetic interference (EMI) in the design. To ensure EMI compliance and minimize the risk of interference with other devices, consider adding appropriate EMI filtering components, such as common-mode chokes and X/Y capacitors, to the design. Additionally, ensure proper PCB layout and grounding techniques to minimize EMI emissions.
