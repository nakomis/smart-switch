# Cabal consultation — bedrock:nova-pro

- Tokens: 2136 in / 508 out
- Cost: $0.003334 USD
- Latency: 4407 ms

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

1. **Non-isolated design**: This is highly dangerous and unacceptable for a mains device, even for personal use. The entire board being at mains potential means any fault can expose live voltage to the user. This design must be isolated. Block the order.

2. **Fuse coordination**: The fuses and current ratings are mismatched and could lead to unsafe conditions. The 15 A fuse is higher than the 13 A plug fuse, which is problematic. The T500 mA fuse with a 10 Ohm fusible resistor and bulk capacitors could lead to miscoordination during inrush current. This needs re-evaluation.

3. **MOV placement**: Placing the MOV after F1 is acceptable, but relying on a single MOV for surge protection is insufficient. Additional protection, like a TVS diode, should be considered.

4. **Spacings**: The spacings are generally acceptable but borderline in some areas. The 1.0 mm spacing for the LNK306 switching-node group is too tight and should be increased to at least 1.5 mm.

5. **Thermal concerns**: The 1 oz copper with both-layer pours should handle 10 A continuous, but thermal management at the relay, fuse clips, and terminals needs careful consideration, especially with hand-soldering. Ensure adequate thermal relief and consider thicker copper or additional heat sinking.

6. **LNK306 high-side buck**: Omitting the neutral-leg diode in the LNK306 circuit is unsafe and could lead to unregulated output. This configuration must be revised to include proper regulation.

7. **BL0939 hookup**: The Kelvin shunt and separate KGND are correctly implemented, but the 0 Ohm GND bond and voltage measurement from L_IN before F1 are acceptable. However, ensure the voltage divider is correctly rated for mains voltage to avoid measurement errors.

8. **Bench checks**: Before first mains power-up, the home builder should verify insulation resistance, check for shorts, ensure correct fuse coordination, and confirm proper operation of all protection devices (fuses, MOV).

9. **Top 3 changes**:
   1. Implement isolation between the mains and low-voltage sections.
   2. Revise the fuse coordination to ensure proper protection.
   3. Correct the LNK306 circuit to include proper regulation and safety features.
