# Cabal consultation — gemini:gemini-3.1-pro

- Tokens: 2133 in / 5842 out
- Cost: $0.074370 USD
- Latency: 56933 ms

## Prompt

```
Design review (safety gate 1, before ordering) of a home-built 230 V AC / 10 A Wi-Fi smart switch PCB. It is for the author's own UK home only: never sold or given away. The author does all mains work himself, tests at an RCD-protected socket, and powers it only closed in its case. Please falsify the design: find what is wrong or dangerous, ranked by severity. Answer the numbered questions in order, then list anything else you would block the order on.

THE DESIGN (revision B, non-isolated, chosen for budget: about GBP 97 for 5 assembled boards):
- Form factor: in-line cord unit, cable in / cable out, in the author's own 3D-printed case in UL94 V-0 flame-retardant filament (FR-ABS / FR-PC-ABS), cable glands (V-2 nylon) and cord grips. Earth does not touch the PCB (Wago 221 inside the case). Board 120 x 80 mm, 2 layers, FR-4 1.6 mm, 1 oz copper, black mask, lead-free HASL, 4 mm rounded corners, four unplated M3 mounting holes (copper kept 3 mm from every hole and the board edge for mains nets).
- Mains path: J1 (Degson DG636 7.62 mm 32 A terminal) L_IN -> F1 Littelfuse 0505015.MXP 15 A 6.3x32 mm ceramic sand-filled, 50 kA at 500 VAC, in two Littelfuse 01220088Z PCB clips -> L_F -> relay K1 Hongfa HF115F-I/005-1HS3A (16 A 250 VAC, 5 V coil) COM, NO -> L_OUT -> J2. MOV Littelfuse TMOV20RP275E (275 VAC, thermally protected) from L_F to N_OUT. Neutral: J1 N_IN -> 1 mOhm Vishay WSK2512 4-terminal shunt -> N_OUT -> J2. The UK plug's 13 A BS 1362 fuse protects the cord; firmware trips the relay at about 10.5 A (BL0939 fast over-current output on an interrupt plus metering); rated 10 A resistive.
- Mains copper: L_IN, L_F, L_OUT, N_IN, N_OUT are solid pours on BOTH layers, stitched with 1.2/0.6 mm vias, each layer at least 3.5 mm wide everywhere (IPC-2221 for 8 A per layer at 20 C rise on 1 oz, so 16 A for the pair); DRC fails if a pour necks below that. Spacing (functional, IEC 60664-1 Table F.4, pollution degree 2, material group III, by worst-case working voltage over relay-open/closed and fuse-blown scenarios): 2.5 mm between different mains potentials, including every mains net to GND (GND = neutral); less within the 5 x 390 kOhm 1206 divider chain (1.2-2.0 mm per step); 1.0 mm for the LNK306 switching node group (SW, BP, FB, FBH) to anything (justified as functional insulation inside the converter where a short only trips its current limit).
- Power, non-isolated: L_F -> F2 Littelfuse 0215.500MXP T500 mA 5x20 ceramic in a 656-series holder -> R1 Yageo FKN2WS 10 Ohm 2 W fusible flameproof -> D7 M7 half-wave -> pi filter (2 x 4.7 uF 400 V electrolytic, 1 mH 350 mA) -> Power Integrations LNK306DN high-side buck (datasheet Figure 5, neutral-leg diode omitted so the return is neutral), 12.4 V, 680 uH 1 A output inductor, US1M freewheel, M7 feedback sampling diode with 10 uF across, 13k/2k feedback, 3.3 kOhm pre-load. Then TI TPS563201 12 V -> 5 V, diode-OR (SS34 x2) with USB VBUS, 1.1 A polyfuse + SMAJ5.0A on the 5 V, AP2112K 3.3 V. Loads: ESP32-C6-WROOM-1 (Wi-Fi peaks ~350 mA at 3.3 V), relay coil 5 V 80 mA, an LED, and up to about 150 mA on an internal I/O terminal.
- GND is neutral, joined at the shunt's supply-side Kelvin sense pad only (one star point; no load current in GND). EVERYTHING on the board is at mains potential: the ESP32, the USB connector (JST SH, internal), debug pads, test holes, and J3, a 10-way 3.5 mm screw terminal (3.3 V, GND, SPI, I2C, IN, OUT) for sensors added INSIDE the closed case only. Silk on both sides: DANGER 230 V AC / BOARD IS LIVE / GND = NEUTRAL / J3 I/O IS LIVE TOO / UNPLUG BEFORE USB. USB, debug and scope use only with mains unplugged, or through an isolation transformer / differential probe. Button and light pipe are plastic, through the case.
- Metering: Belling BL0939 on GND reads the neutral shunt (both current channels, 1k/33 nF filters) and the voltage via 5 x 390 kOhm 1206 from L_IN (before F1) over 470 Ohm (61 mV rms at 253 V vs the chip's 70 mV max).
- Assembly: JLCPCB Economic; the mains parts (terminals, fuse clips, F2 holder, relay, MOV, R1) are hand-soldered by the author from authorised distributors. JLCPCB tooling holes placed by us in the low-voltage area.

QUESTIONS:
1. Is a non-isolated design with GND at neutral acceptable for a one-off personal device under these constraints (closed V-0 case, nothing conductive exits, RCD socket, USB only unplugged)? What failure modes remain that the author may be underestimating (e.g. live/neutral reversal in a miswired socket or extension: then F1 is in the neutral and GND sits at 230 V; or neutral loss)? Would you block the order on it?
2. Fuse coordination: F1 15 A HBC ceramic vs the plug's 13 A BS1362, the 16 A relay and 3.5 mm per-layer 1 oz pours; F2 T500 mA with R1 10 Ohm fusible and 2 x 4.7 uF bulk capacitors (inrush, I2t vs F2's 0.42 A2s). Any mis-coordination?
3. MOV after F1 from L_F to N_OUT (so the surge current passes through the 1 mOhm shunt): acceptable? Thermally protected TMOV - any issue with it being the only surge element on a non-isolated board?
4. Spacings: 2.5 mm functional between L and N potentials and mains-to-GND (GND = neutral) on a coated (soldermask) PCB inside an enclosure; 1.0 mm for the LNK306 switching-node group; the divider steps. Too tight anywhere? Is 2.5 mm L-to-GND enough given GND is at neutral but neutral can float in fault?
5. 1 oz copper with both-layer pours at >= 3.5 mm per layer for 10 A continuous (16 A design margin), stitched: thermal concern at the relay and fuse clips and terminals? Anything about through-hole joints of the hand-soldered 16 A relay and 30 A clips on 1 oz?
6. The LNK306 high-side buck at 12 V with the neutral-leg diode omitted and the 5 V buck after it: any reason this topology is unsafe or will not regulate (e.g. feedback referencing, minimum load, EMI on a home device)?
7. Anything on the BL0939 hookup (shunt in neutral, voltage from L_IN before F1) that is unsafe or will mismeasure?
8. Practical: anything a home builder should check on the bench before first mains power-up (gate 3) that this design makes especially important?
9. Top 3 changes you would insist on before ordering, if any.
```


**System prompt:**

```
Be blunt. If any part of the question or design is wrong, hand-wavy, or based on a misunderstanding, say so directly. Prefer "this won't work because X" over polite hedging. Don't pad with caveats unless the caveat *is* the answer. If a question is malformed, point that out instead of answering it as asked. If the questions are numbered, answer them in order using the same numbering so the replies can be diffed across models.

You are an experienced mains power-electronics and product-safety engineer reviewing a PCB before fabrication.
```

## Response

Here is the design review. I am evaluating this strictly as a one-off for your own use based on the constraints provided. 

**1. Is a non-isolated design with GND at neutral acceptable?**
Acceptable for a sealed box, but a death trap on the bench. This won't work safely if you ever deviate from your strict handling rules. 
The failure modes you are underestimating:
*   **Live/Neutral Reversal:** Common in UK extension leads or miswired wall sockets. If this happens, your "GND" plane sits at 230 V RMS relative to Earth. The F1 fuse is now in the neutral return. A short to Earth anywhere on the board or in the load will not blow F1, it will blow the plug fuse (if you're lucky) or start a fire.
*   **Neutral Loss Upstream:** If the neutral connection breaks at the plug or socket, the entire board and GND plane will float to 230 V through the load's impedance. 
I would not block the order for a personal, sealed, V-0 enclosed device, but you must treat this board as live 100% of the time, regardless of switch state.

**2. Fuse coordination**
*   **F1 vs BS1362:** A 15 A fast-acting ceramic fuse and a 13 A BS1362 (which is essentially slow-blow) will race during a dead short. F1 will likely blow first or they will blow together. This is fine; it protects the relay.
*   **F2 vs Inrush:** This won't work as an effective coordination strategy, but it's not dangerous. You have a T500 mA fuse *and* a 10 Ohm fusible resistor. The fusible resistor is redundant and will likely fatigue from inrush before the slow-blow fuse ever cares. Pick one: use a standard flameproof wirewound resistor with the fuse, or drop the fuse and use a rated UL1412 fusible resistor. 

**3. MOV after F1 to N_OUT**
This won't work because you have routed the MOV return through the 1 mOhm current shunt.
When a transient hits, the MOV clamps and dumps thousands of amps. A 2,000 A surge through a 1 mOhm shunt generates a 2 V spike across the shunt. The absolute maximum rating for the BL0939 current sense pins is typically ±0.5 V to ±2 V. A mains surge will instantly blow the front end out of your metering IC. 
*Fix:* The MOV must go from L_F to N_IN (the supply side of the shunt). 

**4. Spacings**
*   **2.5 mm functional:** This is the bare minimum creepage for 250 V working voltage under IEC 60664-1 (Pollution Degree 2). It is acceptable only because the board is coated and enclosed.
*   **1.0 mm at LNK306:** This won't work. The switching node (Drain to Source) sees the rectified mains peak (340 VDC) plus the inductive kickback (up to the 700 V internal MOSFET avalanche rating). 1.0 mm will arc over during a line transient before the MOV has time to clamp. You need at least 2.5 mm here as well. 

**5. 1 oz copper for 10 A continuous (16 A margin)**
This won't work for long-term reliability because of the fuse clips. 
While a 7 mm total width (3.5 mm top + 3.5 mm bottom) on 1 oz copper can theoretically carry 15 A with a 20-30 °C rise, the Littelfuse clips and the Hongfa relay pins are massive thermal sinks with mechanical contact resistance. At 10 A continuous, the fuse clips will generate localized heat. 1 oz copper is too thin to wick this heat away from the clip pads. The FR-4 under the fuse clips will scorch and eventually delaminate. 
*Fix:* You must use 2 oz copper, or abandon the clips and use a pigtail fuse soldered directly to the board.

**6. LNK306 topology**
The topology works. Omitting the neutral-leg diode to keep the return referenced to neutral is standard for non-isolated designs. The TPS563201 will regulate fine because it sees a stable 12 V DC relative to the neutral plane. 
However, EMI will be atrocious. A half-wave rectified offline switcher with a simple pi-filter will dump significant conducted emissions back into the mains. For a home device, this might just mean your AM radio buzzes, but be aware of it.

**7. BL0939 hookup**
Aside from the fatal MOV placement mentioned in Q3, the hookup is fine. Taking the voltage from L_IN (before F1) is actually smart because if F1 blows, the IC remains powered (via F2) and will report 230 V but 0 A, which is a perfect diagnostic signature for a blown main fuse. 81 mV peak on the voltage channel is within the BL0939's ±100 mV peak spec.

**8. Bench testing (Gate 3)**
The most critical check: **Do not plug a USB cable connected to a mains-earthed PC into this board while it is plugged into the wall.** 
Because GND is Neutral, and Neutral sits a few volts above Earth (or at 230 V if reversed!), plugging in a standard USB cable will vaporize the USB trace, blow your PC's motherboard, and trip your house RCD. You must use a USB isolator module or flash it completely unpowered.

**9. Top 3 changes I would insist on before ordering:**
1.  **Move the MOV return to N_IN.** Do not pass surge currents through the metering shunt.
2.  **Increase clearance around the LNK306.** 1.0 mm on a 700 V switching node is a hard failure waiting to happen. Increase to 2.5 mm minimum.
3.  **Upgrade to 2 oz copper or use a through-hole pigtail fuse.** 1 oz copper cannot adequately heat-sink 10 A continuous through mechanical PCB fuse clips.
