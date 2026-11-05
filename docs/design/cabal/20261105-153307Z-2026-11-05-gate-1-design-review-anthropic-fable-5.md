# Cabal consultation — anthropic:fable-5

- Tokens: 2954 in / 16000 out
- Cost: $0.829540 USD
- Latency: 265246 ms

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

# Verdict up front

The core concept (non-isolated, neutral-referenced, everything sealed in an insulated case, for yourself only) is defensible. Several implementation details are not. I would block the order on four things: the J3/USB expansion philosophy, the MOV/shunt/divider arrangement, F1's rating, and the 1 oz copper + hand-soldered high-current joints. Details below.

---

**1. Non-isolated, GND = neutral — acceptable? Block?**

Acceptable in principle for a one-off, *if* the live-reference discipline is absolute. Yours isn't, and that's the problem:

- **J3 is the design's biggest lie to itself.** A 10-way screw terminal carrying 3.3 V/SPI/I2C "for sensors added inside the case" means you *will* eventually run a sensor wire. Any sensor, probe, or cable attached to J3 is hazardous-live, forever, including when the relay is "off." A temperature probe touching the case wall, a wire pinched in the lid — these are the realistic kill paths, not the PCB itself. Either delete J3, or put a digital isolator + isolated DC/DC behind it so the connector is genuinely SELV. Silk-screen warnings do not count as insulation.
- **The USB diode-OR actively invites the fatal mistake.** You designed it so the board *works* from USB — which means one day you'll plug in a laptop to debug "just quickly" with the mains lead still in. GND = neutral is nominally near earth, so it'll work fine every time until the one socket/extension with reversed polarity, and then the laptop chassis is at 230 V. Procedural safety ("unplug first") fails statistically. Physically prevent it: USB only reachable when the mains cord is removed from the gland, or no USB power path at all (UART pads only).
- **L/N reversal:** yes, correctly identified — F1 and the relay end up in the neutral, the load stays live when "off," GND sits at 230 V. UK plugs are polarised but miswired sockets and cheap extension reels exist. You can't fix this in a non-isolated design; you can only ensure nothing conductive ever leaves the case (see J3).
- **RCD misconception:** the RCD protects against L→E faults. Every fault inside your all-insulated case is L→N and the RCD sees nothing. Also note a half-wave rectified supply injects pulsating DC; fine for Type A RCDs, can degrade an old Type AC. Don't count the RCD as a design layer at all.
- **Lost neutral / broken N in the cord:** whole board floats to ~230 V via the load. Same mitigation: nothing exits.

Block? Not on non-isolation itself. Block on J3-as-specified and the USB arrangement.

**2. Fuse coordination**

- **F1 = 15 A is mis-coordinated and essentially decorative.** It sits behind a 13 A BS 1362, so for overload it never operates; it only adds breaking capacity (which the BS 1362 already provides adequately for domestic PSCC — ~6 kA rated). Meanwhile it permits 15 A continuous through a 16 A relay and pours you sized for 16 A total — zero margin, and firmware OCP is not a protective device. Fit a **10 A** HBC here so F1 actually protects the relay, pours and your 10 A rating. This is a cheap, obvious fix.
- **F2/R1/inrush:** fine. Inrush I²t ≈ V²C/2R ≈ 325² × 9.4 µF / 20 ≈ **0.05 A²s**, ~12% of F2's 0.42 A²s melting I²t — no nuisance blow, acceptable pulse-aging margin for a time-lag part. R1 fusible flameproof as backup is correct practice. Check the 0215 series is the 250 VAC-rated variant (it is) and keep the holder.
- One coordination gap nobody fused: the **voltage divider taps L_IN *before* F1** — that string's only protection is the plug fuse. See Q7.

**3. MOV placement**

**Wrong node. Move it.** With the MOV from L_F to **N_OUT**, every surge the MOV diverts is driven through the 1 mΩ shunt. A modest 3 kA 8/20 µs event is ~0.15 J deposited adiabatically in a 2512 foil in 20 µs, plus multi-volt + L·di/dt spikes straight into the BL0939 sense pins through only 1 k/33 nF. Best case you drift the shunt and ruin metering; worst case you crack it open or kill the BL0939 inputs. Connect the MOV **L_F to N_IN** (supply side of the shunt) so surge current bypasses the measurement element entirely. TMOV as the sole surge element is fine for this product class, and the thermal disconnect is the right choice given F1 won't clear MOV end-of-life leakage. Secondary issue: during a clamp (~710 V) the 10 Ω feed can pump ~80 V extra into the bulk caps — use **450 V** electrolytics, not 400 V.

**4. Spacings**

- 2.5 mm functional creepage at 250 V, PD2, MG III, coated/enclosed: correct per the table, and adequate for L↔N and mains↔GND. The "neutral can float" fault doesn't change L–N working voltage, so no, you don't need more there — the hazard of floating neutral is touch-access (Q1), not tracking.
- **1.0 mm around the LNK306 switch node is below the table for a ~325 Vpk node** (functional creepage at that voltage is ~2.5–3.2 mm; clearance for 2.5 kV impulse is 1.5 mm). Your "short is safe" argument is legitimate 60335-style fault reasoning *only* for shorts the current limit + F2 + R1 actually make safe — SW-to-neutral yes; SW-to-BP/FB kills the IC, which F2/R1 then contain, so arguably still safe-fail. I'd accept it **only if** you clean flux thoroughly (hand-solder + HASL + 1.0 mm gaps is a tracking recipe) and preferably conformal-coat that area. If you have the room — and on 120×80 mm you do — just widen it to ≥1.6 mm and stop arguing.
- Divider steps at 1.2–2.0 mm: fine at 50 Vrms/step steady-state; a shared 2.5 kV impulse splits five ways, ~marginal but acceptable. The resistors are the weaker link than the gaps (Q7).
- **Verify the M3 screw heads.** "Copper 3 mm from every hole" — from hole *edge* clears a 5.6 mm pan head; from hole *center* does not. Check which your DRC rule actually measures; use nylon screws or washers regardless.
- Check creepage from live parts to the **button plunger and light-pipe penetrations** — those are the only paths to a finger. You want several mm through air around the plastic parts, and a button that can't be pushed through if the actuator breaks.

**5. Copper and joints**

- Ampacity math is right in isolation but optimistic: two stacked pours sharing the same air don't give 2× a single external trace — closer to ~1.5×. Still fine: at 10 A that's ~5 A/layer (<10 °C rise), and with F1 corrected to 10 A the worst case is bounded. At F1 = 15 A as drawn, you're at your 20 °C design edge with no margin — another reason to change F1.
- **The real risk is the hand-soldered through-hole joints, not the traces.** Solid pours on both layers tied to relay pins and 32 A fuse clips are enormous heatsinks; with a typical hobby iron you will make cold or partially-filled joints on the exact pins carrying 10 A, and a 10 mΩ bad joint at 10 A is 1 W in a solder fillet — that's how these units cook. Either go **2 oz copper with proper thermal spokes** on the TH pads, or keep solid pours and commit to a 90–100 W iron with preheat, and verify ≥75% barrel fill (inspect both sides, reflow any dull joint). 2 oz also buys back all the ampacity margin for pennies.
- Vias: 0.6 mm drills are ~1–2 A each comfortably; make sure the stitching count per neck reflects that, not just "some vias."

**6. LNK306 topology**

Figure-5 direct-feedback high-side buck with the return-leg diode omitted for direct neutral reference is the documented configuration; it regulates, the preload is correct, the sampling-diode/10 µF/divider FB is per datasheet (±10% tolerance — fine, the TPS563201 doesn't care). Omitting the second diode costs you some differential EMI and surge margin; acceptable for a personal device. Real issues:

- **Power budget is thin.** 5 V loads worst case ≈ 590 mA → ~275 mA at 12 V. LNK306 gives 360 mA only in MDCM (225 mA CCM). You're inside the envelope but with little headroom during sustained Wi-Fi TX; verify on the bench with a thermal camera and scope the 12 V rail under iperf traffic. If it droops, you need LNK3206/a bigger stage, not firmware hope.
- **The AP2112K is the part that actually won't survive.** 510 mA worst case through a SOT-23-5 LDO dropping 1.4–1.7 V is ~0.8 W — at ~230 °C/W it thermal-limits long before that. Even realistic averages (~0.45 W) put it in shutdown territory with your 150 mA I/O budget. Replace with a small 5→3.3 V sync buck, or cut the I/O budget to ~tens of mA and give the LDO serious copper. This is a brick-the-device bug, not a safety bug.
- EMI: half-wave + no X-cap + π filter only will not pass Class B conducted. For your own house, your call; expect some AM-band hash.

**7. BL0939 hookup**

- Shunt-in-neutral metering on a neutral-referenced chip is the standard BL0939 topology; 61 mV at 253 V is correctly inside the 70 mV range; both current channels paralleled on one shunt with one used for fast OCP is fine.
- **Move the voltage divider tap to after F1 (L_F).** As drawn it is an unfused, un-MOV'd (except through F1's impedance) 230 V path. 390 k limits current so it won't start a fire, but a surge-flashed or failed-short resistor leaves a deg
