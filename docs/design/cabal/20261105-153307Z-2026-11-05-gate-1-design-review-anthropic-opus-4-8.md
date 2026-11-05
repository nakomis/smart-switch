# Cabal consultation — anthropic:opus-4-8

- Tokens: 2954 in / 5498 out
- Cost: $0.152220 USD
- Latency: 103741 ms

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

Blunt verdict up front: the board itself is unusually well thought through for a home build. The thing that will actually hurt you isn't on the PCB — it's the live-to-neutral reversal fault mode combined with a fully live, non-isolated board carrying I/O terminals and a USB connector. That's the gate-1 blocker. Details below in order.

## 1. Non-isolated with GND = neutral — acceptable here?

For a sealed, cable-in/cable-out box where nothing conductive exits and USB is only touched unplugged, a non-isolated topology is defensible *in principle*. People do this (Sonoff, Shelly, etc.). But you are underestimating two things and one of them is serious:

**L/N reversal is not a corner case in the UK — it's common.** UK plugs are polarised, but:
- Extension leads, reels, and non-standard sockets get miswired regularly.
- Some EU-plug-to-UK-adapter situations and certain multi-way strips don't guarantee polarity.
- An RCD does *nothing* about polarity.

When L and N swap:
- F1 and the MOV end up in the neutral leg. Your line conductor (now at 230 V) is unfused through the board until the plug's BS1362 fuse.
- GND (your "neutral" star point) sits at ~230 V relative to true earth. Everything — ESP32, J3 I/O terminals, USB shield, BL0939 — is at 230 V to earth instead of near-0 V.

Your mitigation ("closed case, USB unplugged") covers the *electrocution* risk reasonably. What it does **not** cover: anyone who opens the case for the "add sensors inside" use-case, or touches J3, while plugged in, *believing* GND is near earth potential. Your silk says "BOARD IS LIVE" but human nature + "GND = NEUTRAL" labelling invites the assumption that GND is the safe-ish node. In reversal it isn't.

**Neutral loss / open-neutral:** if the outgoing neutral opens while a load is connected, your whole GND plane and L_F can float up toward line through the load. The BL0939, shunt, and divider return all move. Not a shock risk in a sealed box, but it can destroy the metering front end and the LNK306 return reference.

**Would I block on this?** Not outright — but I'd block until you add an **active L/N-polarity / lost-neutral detect** that refuses to close the relay (and ideally flags a fault) when the board's "neutral" is hot relative to line phase, OR you make a conscious written decision that the case is **never opened while plugged in** and treat J3 as permanently sealed. The current design pretends J3 is a convenient internal header; physically it's a 230 V live terminal block someone will probe. That contradiction is the real hazard.

## 2. Fuse coordination

Mostly sound, with one caveat.

- **F1 15 A vs plug 13 A:** F1 will essentially never clear on overload — the 13 A BS1362 is faster and lower-rated for sustained overcurrent. F1 is really a short-circuit/fault interrupter (its 50 kA rating is the point), and for that it's fine because the plug fuse has nowhere near the breaking capacity you'd want at the board for a hard L-N short with low loop impedance. Fine, but understand F1 is **not** your 10 A protection — firmware is, and firmware is not a safety device. If the relay welds, nothing on the board limits to 10 A; you're relying on the 13 A plug fuse. Your 3.5 mm pours and 16 A relay survive that. OK.
- **F2 T500 mA vs inrush into 2×4.7 µF = 9.4 µF through R1 10 Ω:** charge inrush is limited by R1; peak ≈ 230√2/10 ≈ 32 A instantaneous, decaying with τ ≈ 10 Ω × 9.4 µF ≈ 94 µs. I²t of that transient is tiny (well under 0.42 A²s). A **slow-blow** T500 mA is correct and won't nuisance-trip. Good. R1 as the inrush limiter + fusible flameproof backup is the right idea.
- One thing: confirm R1's 2 W rating survives steady-state. Half-wave rectified into that load — average current is small, so dissipation is low. Fine. But R1 sees the full inrush pulse energy; FKN2WS handles pulses well, OK.

No real mis-coordination. The honest statement is: **the plug fuse is your primary overcurrent protection**, F1 is backup/fault-breaking, firmware is convenience. Label your mental model that way.

## 3. MOV after F1, surge through the shunt

Two problems:

- **Surge current through the WSK2512 1 mΩ shunt:** the TMOV20 can pass hundreds to thousands of amps for microseconds. A 2512 shunt is not spec'd for kA surge pulses; you may see the sense voltage momentarily huge and, worse, you risk degrading the Kelvin element or the metering input (BL0939) via the 1k/33nF filter clamp. Route the MOV's return to a **neutral node that does not pass through the shunt** (i.e., N_IN side / true neutral star, not through the sense element). You separated power and sense elsewhere — do it here too.
- **MOV as the *only* surge element:** a single L-N MOV after the fuse is acceptable for a sealed unit, but a thermally-protected MOV that end-of-lifes open leaves you unprotected silently. Fine for personal use; just know it's a wear part. Also consider that with L/N reversed the MOV is L_F(neutral now)-to-N_OUT(line now) — still across the mains, so it still clamps. OK there.

Move the MOV return off the shunt. That's a real fix.

## 4. Spacings

- **2.5 mm L-N and mains-to-GND:** IEC 60664-1 PD2 / material group III for 230 V working gives clearances/creepage in the ~1.5–2.5 mm range depending on which table and whether you count rated impulse. 2.5 mm functional is adequate **for normal operation**. But you asked the right question: **is 2.5 mm L-to-GND enough when GND can float to line in reversal/open-neutral?** In reversal, L-to-GND working voltage is unchanged (still one mains potential to another), so 2.5 mm still holds. In open-neutral, transients could exceed working voltage briefly, but 2.5 mm with soldermask + sealed enclosure (PD2) is fine. No basic-insulation requirement applies because there is **no isolation barrier anywhere** — everything is live, so you only need functional spacing. Consistent. Accept.
- **1.0 mm for LNK306 SW/BP/FB/FBH group:** justified as functional insulation inside the converter. A short there trips the LNK current limit. Agreed — but FB/FBH reference the output; make sure 1.0 mm is honoured to the *input-side* mains pour too, not just within the group. The LNK306 BP/SW node swings the full rectified rail; 1 mm to adjacent mains nets is tight but within functional spec. OK.
- **1.2–2.0 mm divider steps:** each step only sees a fraction of 253 V, so per-step is fine. But verify **total creepage from L_IN to the 470 Ω / BL0939 input** across the whole chain — a flashover across a contaminated gap bridging two non-adjacent resistors is the failure. Keep the chain physically spread so no single contamination path shorts out multiple steps. Clean, conformal-coat the divider region.

Spacings pass. Conformal coat the metering/divider area; that's cheap insurance against pollution degradation and I'd make it a condition.

## 5. Copper / thermal / through-hole joints

- **3.5 mm/layer × 2 layers for 10 A:** IPC-2221 external-trace charts give roughly 3.5 mm at ~8–9 A for 10–20 °C rise, so two layers for 16 A design is reasonable *if* the vias actually carry current between layers. 1.2/0.6 mm vias at your stitching density are fine for current; make sure the stitch count near the relay and terminals is generous (a dozen+), not just along the middle of the pour. Current crowds at the pin interfaces.
- **Real thermal concern is the joints, not the copper:** the HF115F relay COM/NO pins and the DG636 terminal pins on 1 oz with HASL, hand-soldered — these are the hot spots at 10 A. 1 oz pads sink heat poorly; the relay's own contact resistance is the main heat source. Ensure large thermal-relief-free (solid) connections to those pins — do **not** use thermal-relief spokes on the 10 A pins, or they'll run hot. Hand-soldering through-hole into a solid 2-layer pour is hard to heat; cold joints here are a fire risk. Preheat the board.
- **Fuse clips at 15 A:** the 01220088Z clips on 1 oz solid pour — same deal, solid connection, good wetting. The ceramic 6.3×32 fuse runs warm at sustained high current; give it airflow/clearance from the 3D-printed wall.
- **FR-ABS/FR-PC-ABS wall near the fuse and R1:** V-0 filament's real-world flammability depends on print density and infill. A V-0 *filament* does not guarantee a V-0 *printed part* — layer adhesion and infill voids change behaviour. Keep hot components (fuse, MOV, R1, relay) off the wall by several mm and don't rely on the printed enclosure as a fire enclosure the way a molded V-0 part would be. This is a genuine weakness of 3D-printed mains enclosures.

## 6. LNK306 high-side buck topology

- Topology is from the datasheet (high-side buck, neutral-return). With the neutral-leg diode omitted, the converter return is neutral and the output rail sits referenced to neutral. That's consistent with your GND = neutral scheme. It will regulate.
- **Minimum load:** you have a 3.3k pre-load plus the diode-OR'd 5 V buck and loads downstream. LNK306 buck needs minimum load to maintain the feedback sampling; the 3.3k pre-load and FB sampling network per Fig 5 handle this. Confirm the pre-load is sized for the *lightest* condition (ESP32 in deep sleep, relay open). If the only load is sleep current, verify regulation doesn't droop/overshoot. Add margin to the pre-load if in doubt — it costs you standby power, which you don't care about on a smart switch.
- **Half-wave rectifier + single-ended buck:** 100 Hz ripple on a smallish bulk cap (9.4 µF) feeding the LNK — check hold-up at 253 V and at low line (216 V). ESP32 Wi-Fi TX draws 350 mA pulses *after* the TPS563201, but reflected to the 12 V rail these are current spikes. Make sure the 12 V bulk (680 µH out + whatever output cap) and the TPS input cap buffer the TX bursts so the LNK doesn't brown out. This is the most likely *functional* failure: Wi-Fi TX brownout resetting the ESP32. Not a safety issue, but it'll drive you mad.
- **EMI:** half-wave + buck on mains with a 1 mH pi filter — radiated/conducted EMI will be poor by commercial standards, but this is a personal device not going through EMC. Just don't be surprised if it interferes with your own radio/DAB.

No safety problem with the topology. Watch brownout and min-load.

## 7. BL0939 hookup

- **Shunt in neutral:** fine, standard low-side current sense.
- **Voltage divider from L_IN *before* F1:** means the metering sees line even when F1 is blown. Minor — it just means your voltage reading is "mains present" not "load-side present," which may confuse fault diagnosis but isn't unsafe. Arguably you'd prefer sensing after the fuse to know the switched leg is live.
- **5×390k over 470 Ω:** 61 mV at 253 V vs 70 mV max — only ~13% headroom. A surge or over-voltage (open-neutral swell) will clip and could over-stress the input. Add a clamp (you have filters; consider a small TVS or Schottky clamp to the BL0939 VP input rail, carefully, without wrecking accuracy). Also 470 Ω burden means the divider dissipates little but any tolerance stack in the 390k resistors shifts calibration — use 1% and calibrate in firmware.
- **Surge coupling:** as in Q3, keep the MOV surge out of this node.
- **L/N reversal again:** with L and N swapped, your "voltage from L_IN" now samples neutral-side and your shunt is in the line. Metering still works (it's differential-ish) but sign/phase of power will flip. Firmware over-current trip via the shunt still works regardless of polarity — good, that's the one protection that's polarity-independent.

## 8. Bench checks before first mains power-up

Make these mandatory (gate 3):

1. **Dielectric/continuity first, dead:** ring out L_IN→L_OUT through relay, N path through shunt, confirm no L-N short, confirm no mains net to any mounting hole or board edge within 3 mm.
2. **Dim-bulb / current-limited bring-up:** power the mains section through a series incandescent lamp (or variac + current limit) first. If the lamp glows steady, you have a short (likely a cap in backwards or a solder bridge). Do **not** go straight to a 13 A socket.
3. **Verify polarity of the socket/extension you test on** with a socket tester, every time, and know it only proves *that* socket.
4. **Confirm USB is physically disconnected and no scope ground is attached** before any mains-on test. One earthed scope probe clip on this board = dead short through your earth and a destroyed board, possibly a bang. Use a differential probe or isolated scope, as you noted — but *verify* it, don't assume.
5. **Thermal soak at 10 A resistive** for 30+ min, closed case, measure relay pin, fuse, terminal, R1 temps (IR through a gap or thermocouples with isolation). This is where the 1 oz joints and printed enclosure reveal themselves.
6. **Weld/stuck-relay test:** force the firmware trip and confirm it opens; then confirm behaviour if the relay *doesn't* open (you have only the 13 A plug fuse — accept it).
7. **Confirm the LNK/ESP survives Wi-Fi TX at low line** (Q6).

## 9. Top 3 changes I'd insist on before ordering

1. **Resolve the live-I/O contradiction (Q1).** Either (a) add polarity/lost-neutral detect that inhibits the relay and flags fault, and treat J3/USB/debug as *never accessed while plugged in* with a hard rule, or (b) remove J3 as a "convenient internal expansion" concept — if it stays, it's a permanently sealed 230 V terminal, documented as such, not a sensor header you'll casually revisit. The current design invites someone to probe a live node they think is safe.
2. **Move the MOV return off the current shunt** to the true neutral star (Q3), so surge current doesn't pass through the WSK2512 or couple into the BL0939.
3. **Fix the thermal/joint reliability on the 10 A through-hole parts:** solid (no thermal-relief) connections on relay COM/NO, terminals, and fuse clips; add stitching vias at those pins; and keep the fuse/MOV/R1/relay physically clear of the printed enclosure wall with margin, since a 3D-printed part is **not** a guaranteed fire enclosure even in V-0 filament.

Plus the conditions I'd attach but not block on: conformal-coat the divider/metering region; add input clamping headroom on the BL0939 VP; verify pre-load for min-load regulation; verify Wi-Fi-TX brownout immunity.

Net: good engineering, one conceptual hazard (a live node dressed up as a friendly header/ground), and a couple of routing fixes. Fix #1 and I'd let you order.
