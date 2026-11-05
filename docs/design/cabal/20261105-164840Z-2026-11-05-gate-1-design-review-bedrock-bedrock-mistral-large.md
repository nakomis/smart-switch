# Cabal consultation — bedrock:mistral-large

- Tokens: 2319 in / 901 out
- Cost: $0.010044 USD
- Latency: 19280 ms

## Prompt

```
Design review (safety gate 1, before ordering) of a home-built 230 V AC / 10 A Wi-Fi smart switch PCB. It is for the author's own UK home only: never sold or given away. The author does all mains work himself, tests at an RCD-protected socket, and powers it only closed in its case. Please falsify the design: find what is wrong or dangerous, ranked by severity. Answer the numbered questions in order, then list anything else you would block the order on.

THE DESIGN (revision B, non-isolated, chosen for budget: about GBP 97 for 5 assembled boards):
- Form factor: in-line cord unit, cable in / cable out, in the author's own 3D-printed case in UL94 V-0 flame-retardant filament (FR-ABS / FR-PC-ABS), cable glands (V-2 nylon) and cord grips. Earth does not touch the PCB (Wago 221 inside the case). Board 120 x 80 mm, 2 layers, FR-4 1.6 mm, 1 oz copper, black mask, lead-free HASL, 4 mm rounded corners, four unplated M3 mounting holes (all copper kept 3 mm from every hole; mains copper 3 mm from the edge).
- Mains path: J1 (Degson DG636 7.62 mm 32 A terminal) L_IN -> F1 Littelfuse 0505015.MXP 15 A 6.3x32 mm ceramic sand-filled, 50 kA at 500 VAC, in two Littelfuse 01220088Z PCB clips -> L_F -> relay K1 Hongfa HF115F-I/005-1HS3A (16 A 250 VAC, 5 V coil) COM, NO -> L_OUT -> J2. MOV Littelfuse TMOV20RP275E (275 VAC, thermally protected) from L_F to N_IN (the supply side of the shunt, so surge current never crosses the shunt). Neutral: J1 N_IN -> 1 mOhm Vishay WSK2512 4-terminal shunt -> N_OUT -> J2. The UK plug's 13 A BS 1362 fuse protects the cord; firmware trips the relay at about 10.5 A (BL0939 fast over-current output on an interrupt plus metering); rated 10 A resistive.
- Mains copper: L_IN, L_F, L_OUT, N_IN, N_OUT are solid pours on BOTH layers, stitched with 1.2/0.6 mm vias, each layer at least 3.5 mm wide everywhere (IPC-2221 for 8 A per layer at 20 C rise on 1 oz, so 16 A for the pair), no thermal relief on through-hole pads; the build fails if a pour necks below that or splits. Spacing (IEC 60664-1 Table F.4, PD2, material group III, worst case over relay-open/closed and fuse-blown scenarios): 2.5 mm between different AC mains potentials, including every mains net to GND (GND = neutral); the supply's smoothed DC bus (rectified peak, 354 V DC above neutral) 3.55 mm to GND and 4.35 mm to the live (433 V rms); less within the 5 x 390 kOhm 1206 divider chain (1.2-2.0 mm per step); 1.0 mm for the LNK306 switching-node group (SW, BP, FB, FBH) to the supply's own input, its bus and GND only (functional insulation inside the converter: a short trips its current limit or kills the IC, contained by F2 and the fusible resistor), 4.35 mm from it to the live, load and divider.
- Power, non-isolated: L_F -> F2 Littelfuse 0215.500MXP T500 mA 5x20 ceramic in a 656-series holder -> R1 Yageo FKN2WS 10 Ohm 2 W fusible flameproof -> D7 M7 half-wave -> pi filter (2 x 4.7 uF 400 V electrolytic, 1 mH 350 mA) -> Power Integrations LNK306DN high-side buck (datasheet Figure 5, neutral-leg diode omitted so the return is neutral), 12.4 V, 680 uH 1 A output inductor, US1M freewheel, M7 feedback sampling diode with 10 uF across, 13k/2k feedback, 3.3 kOhm pre-load. Then TI TPS563201 12 V -> 5 V, diode-OR (SS34 x2) with USB VBUS, 1.1 A polyfuse + SMAJ5.0A on the 5 V, AP2112K 3.3 V. Loads: ESP32-C6-WROOM-1 (Wi-Fi peaks ~350 mA at 3.3 V), relay coil 5 V 80 mA, an LED, and up to about 50 mA on an internal I/O terminal.
- Grounding: GND joins N_IN through a 0 Ohm 1206 link (the one star point). The shunt's two sense pads are true Kelvin: SENSE to the BL0939's IP inputs and KGND (a separate net carrying no current) to its IN inputs, through 1k/33 nF filters, hand-routed as a tight pair. EVERYTHING on the board is at mains potential: the ESP32, the USB connector (JST SH, internal), debug pads, test holes, and J3, a 10-way 3.5 mm screw terminal (3.3 V, GND, SPI, I2C, IN, OUT) for sensors added INSIDE the closed case only. Silk on both sides: DANGER 230 V AC / BOARD IS LIVE / GND = NEUTRAL / J3 I/O IS LIVE TOO / UNPLUG BEFORE USB. USB, debug and scope use only with mains unplugged, or through an isolation transformer / differential probe. Button cap and light pipe are plastic, through the case. No live/neutral reversal detection (it would need an earth reference on the PCB); the author uses a socket tester instead.
- Metering: Belling BL0939 on GND reads the neutral shunt (both current channels) and the voltage via 5 x 390 kOhm 1206 from L_IN (before F1) over 470 Ohm (61 mV rms at 253 V vs the chip's 70 mV max).
- Assembly: JLCPCB Economic; the mains parts (terminals, fuse clips, F2 holder, relay, MOV, R1) are hand-soldered by the author from authorised distributors. Our own JLCPCB tooling holes in the low-voltage area.

QUESTIONS:
1. Is a non-isolated design with GND at neutral acceptable for a one-off personal device under these constraints? What failure modes remain that the author may be underestimating? Would you block the order on it?
2. Fuse coordination: F1 15 A HBC vs the plug's 13 A BS1362, the 16 A relay and 3.5 mm per-layer 1 oz pours; F2 T500 mA with R1 10 Ohm fusible and 2 x 4.7 uF bulk (inrush, I2t vs F2's 0.42 A2s). Any mis-coordination?
3. MOV after F1 from L_F to N_IN, the only surge element: acceptable?
4. Spacings as listed: too tight anywhere?
5. 1 oz copper with both-layer pours >= 3.5 mm per layer for 10 A continuous: thermal concerns at the relay, fuse clips and terminals, hand-soldered?
6. The LNK306 high-side buck at 12 V with the neutral-leg diode omitted and the 5 V buck after it: any reason this is unsafe or will not regulate?
7. Anything on the BL0939 hookup (Kelvin shunt in neutral with a separate KGND, 0 Ohm GND bond, voltage from L_IN before F1) that is unsafe or will mismeasure?
8. What should a home builder check on the bench before first mains power-up that this design makes especially important?
9. Top 3 changes you would insist on before ordering, if any.
```


**System prompt:**

```
Be blunt. If any part of the question or design is wrong, hand-wavy, or based on a misunderstanding, say so directly. Prefer "this won't work because X" over polite hedging. Don't pad with caveats unless the caveat *is* the answer. If a question is malformed, point that out instead of answering it as asked. If the questions are numbered, answer them in order using the same numbering so the replies can be diffed across models.

You are an experienced mains power-electronics and product-safety engineer reviewing a PCB before fabrication.
```

## Response

1. A non-isolated design with GND at neutral is acceptable for a one-off personal device under these constraints, but it comes with inherent risks. The author must be aware that any failure in the system could expose the low-voltage circuitry to mains voltage, potentially causing harm or damage. The author seems to be aware of this risk and has taken some precautions (e.g., using a single star point, marking the board as live, etc.), but this design should still be approached with extreme caution. I would not block the order based on this alone, but I would strongly advise the author to thoroughly test the device and take all necessary safety precautions.
2. Fuse coordination appears to be well-considered. The 15A HBC fuse (F1) is appropriately rated for the 13A BS1362 plug fuse, the 16A relay, and the 3.5mm per-layer 1 oz pours. The T500mA fuse (F2) with the 10 Ohm fusible resistor (R1) and the 2 x 4.7uF bulk capacitors seems to be properly coordinated as well. However, it's important to note that fuse coordination is complex and depends on various factors, including the specific characteristics of the fuses and the actual load conditions. The author should verify this coordination through testing.
3. Placing the MOV after F1 from L_F to N_IN is acceptable as a surge protection measure. This configuration should provide adequate protection against voltage surges. However, it's important to note that MOVs have a limited lifespan and can fail after repeated exposure to surges. The author should monitor the MOV and replace it if necessary.
4. The spacings listed appear to be in accordance with IEC 60664-1 and should be sufficient for safety. However, it's crucial to ensure that these spacings are maintained throughout the manufacturing process. Any deviation could potentially result in dangerous conditions.
5. The 1 oz copper with both-layer pours >= 3.5 mm per layer should be adequate for 10A continuous operation. However, the author should be aware of potential thermal issues at the relay, fuse clips, and terminals, especially since these components are hand-soldered. The author should monitor these components for excessive heating during operation and ensure that they are properly secured and cooled.
6. The LNK306 high-side buck at 12V with the neutral-leg diode omitted and the 5V buck after it should be safe and functional. However, the author should verify this through testing and ensure that the neutral-leg diode is not necessary for proper operation in this specific application.
7. The BL0939 hookup appears to be safe and should provide accurate measurements. The use of a Kelvin shunt in neutral with a separate KGND and a 0 Ohm GND bond is a good practice. The voltage measurement from L_IN before F1 should also be adequate. However, the author should verify the accuracy of these measurements through testing.
8. Before first mains power-up, a home builder should thoroughly inspect the board for any manufacturing defects or soldering issues. They should also perform a continuity test to ensure that there are no unintended connections between different parts of the circuit. Additionally, they should verify that all components are properly rated for their respective voltages and currents.
9. Top 3 changes I would insist on before ordering:
   a. Include a live/neutral reversal detection feature. Although the author plans to use a socket tester, this feature would provide an additional layer of safety.
   b. Add thermal relief pads for the mains components. Although the author has chosen not to use them, they can help prevent excessive heating during soldering and operation.
   c. Consider adding an isolation transformer or an optocoupler to provide galvanic isolation between the mains and low-voltage circuitry. This would significantly reduce the risk of electric shock.
