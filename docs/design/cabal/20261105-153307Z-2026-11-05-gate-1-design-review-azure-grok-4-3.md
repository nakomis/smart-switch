# Cabal consultation — azure:grok-4.3

- Tokens: 1920 in / 1029 out
- Cost: $0.025035 USD
- Latency: 19576 ms

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

1. No. A non-isolated design with GND tied to neutral is unacceptable even for a one-off personal unit. Reversal of L/N at the socket or extension cord immediately puts every net (ESP32, USB, J3, debug pads, all copper) at 230 V. A broken neutral upstream floats the entire board and everything connected to it to line potential. A failed relay contact or MOV short can likewise energise the “low-voltage” sections. Plastic case, RCD socket, and “unplug before USB” warnings do not remove these single-point faults. Block the order.

2. Marginal coordination on both fuses. The 13 A BS 1362 in the plug will usually clear before the 15 A F1, but the 16 A relay and the 3.5 mm 1 oz pours are the next weakest links; a sustained 14–15 A fault can weld the relay or melt the pours before either fuse acts. For F2, the 10 Ω + 9.4 µF combination produces ~30 A peak inrush on the first half-cycle; the T500 mA fuse’s I²t (≈0.42 A²s) is easily exceeded on repeated hot-plug events. Replace F2 with a slower fuse or add a proper NTC.

3. No. Placing the MOV after F1 forces surge current through the 1 mΩ shunt and the narrow N_OUT pour. A 3 kA differential surge drops 3 V across the shunt and deposits significant energy in a part never rated for that. A thermally protected MOV that fails short will then blow F1 and leave the board without surge protection; on a non-isolated board that is the only protection element, this is inadequate.

4. 2.5 mm functional clearance/creepage between L and N (and L/N to GND) is the minimum allowed by IEC 60664-1 for 250 V, pollution degree 2, but soldermask cannot be relied upon as insulation and the board is inside a DIY enclosure. Under neutral fault or reversal the 2.5 mm L-to-GND gap becomes L-to-live. The 1.0 mm LNK306 switching-node spacing is acceptable only as functional insulation inside the converter; any layout error or contamination bridges it directly to the rest of the live board. The divider chain steps are fine. Increase all mains-to-mains and mains-to-GND spacings to ≥3.5 mm and remove soldermask between them.

5. Thermal and mechanical concern at every high-current through-hole joint. 1 oz copper with 3.5 mm pours on both layers is marginal once vias, terminal pads, fuse clips and relay pins are included; the current crowds into the plated barrel and the pad fillet. Hand-soldered 16 A relay and 30 A clips on 1 oz copper routinely overheat at the joint long before the pour itself reaches 20 °C rise. Add copper pours on both sides with solid thermal reliefs or switch to 2 oz copper.

6. The LNK306 configuration is unsafe. With the neutral-leg diode omitted the return current flows in the neutral-referenced GND plane while the high-side buck switch node swings to ~325 V. Feedback divider referenced to the same neutral point is correct in theory, but any load transient or relay kick couples directly into the control loop and the non-isolated 12 V rail. Conducted EMI on the neutral wire is high; the topology violates the assumptions in the datasheet example. Use a properly isolated or flyback converter instead.

7. Voltage sense taken before F1 means the BL0939 continues to report line voltage after the fuse has cleared; that is misleading but not unsafe. Shunt in neutral is acceptable provided the star-point connection is exactly as drawn. Under L/N reversal the shunt sees line current while the voltage divider sees neutral; metering becomes meaningless and the over-current trip threshold shifts. No outright measurement error under normal wiring, but the fault behaviour is poor.

8. Before first mains power-up:  
- 500 V megger between L+N tied together and any accessible metal (case screws, USB shell if fitted, earth pin).  
- Visual and microscope inspection of every mains creepage path for solder mask voids or flux residue.  
- Low-ohm test of every via stitching the high-current pours (target <0.5 mΩ per via).  
- Variac ramp with differential probe on the LNK306 switch node and on the 12 V rail while monitoring neutral current.  
- Verify that the relay contacts remain open with coil unpowered at 253 V.

9. Top three mandatory changes before ordering:  
- Convert to an isolated AC-DC supply (or at minimum add a safety isolating transformer for the ESP32/USB section).  
- Increase all mains clearances to ≥3.5 mm and remove soldermask between L, N and GND.  
- Switch to 2 oz copper or add explicit high-current stitching and enlarged thermal pads at relay, fuse clips and terminals.
