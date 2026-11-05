# Cabal consultation — anthropic:fable-5

- Tokens: 1108 in / 7678 out
- Cost: $0.394980 USD
- Latency: 123064 ms

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

**1. Option A.** Three concrete reasons:

- **The safety barrier in Option A is made of certified components** (a VDE-certified digital isolator, your already-certified IRM-03). In Option B the barrier *is* the ZMPT101B/ZMCT103C insulation, and those are uncertified commodity parts (see Q4). Option B *feels* safer ("no mains-side electronics") but actually rests the entire SELV claim on parts with no safety file. That's backwards for a device whose spec is "USB safe to touch."
- The BL0942 is designed around a shunt; its low-end accuracy and phase behavior with a 1 mΩ shunt beat a ZMCT103C + burden resistor, and the ZMPT101B is mediocre for RMS voltage (it's a 2 mA:2 mA current-type VT fed through a series resistor; gain and phase drift with temperature).
- Size. Two transformers won't fit nicely in an in-line cord barrel; a 2512 shunt and a wide-body SOIC will.

**2. Powering the mains side.** First, kill one of your listed options: **the IRM-03 has no non-isolated tap** — it's a sealed isolated module, there's nothing to tap. That idea is a misunderstanding.

Real choices:

- **Capacitive dropper (what I'd do, and what commercial plugs do).** Budget ~5 mA: BL0942 (~2–3 mA) + digital isolator side-1 (~1–2 mA). That rules out optos (LED drive alone blows the budget — see Q3). Traps, all real:
  - **Reference polarity:** BL0942 ground must sit at the shunt potential (live). The dropper therefore runs neutral → live, with its output referenced to the live/shunt node. Get this wrong and the sense inputs are out of range.
  - **Dropper current through the shunt:** tap the dropper so its return current does not flow through the shunt, or you meter your own supply.
  - **Inrush:** plugging in at the voltage peak dumps the cap's charge instantly — mandatory flameproof series resistor (few hundred Ω) and a bleed resistor across the X2 cap.
  - **MOV placement:** fuse → MOV → dropper. If the MOV sits downstream of the dropper (or is absent), line surges go through the X2 cap and kill the zener/regulator.
  - **X2 cap aging:** self-healing under humidity + transients erodes capacitance over years; the dropper browns out and metering silently dies while the relay (SELV-driven) keeps working. Oversize the cap ~30–50 % and use a decent brand, not a no-name X2.
- **Second tiny isolated module (IRM-01/02-5) with its output tied to the live reference** is the "I don't want dropper headaches" answer. Its isolation isn't doing safety work there — it's just a floating supply. Bulkier, ~€5, and bombproof. Legitimate choice if the enclosure fits it.

**3. Digital isolator, not optos.** At 4800 baud optos are plenty fast, but two opto channels need 2–5 mA LED drive each from your ~1 mA-class dropper — doesn't close. A dual-channel digital isolator does both directions in one package at ~1 mA.

Rating: careful — **ISO6721 in its standard narrow SOIC-8 (~4 mm creepage) is basic insulation only. It does not count.** You need a part certified to **VDE 0884-11 / IEC 60747-17 as *reinforced***, with:

- V_IORM ≥ ~354 V_peak (continuous working voltage for 230 V mains),
- impulse withstand per IEC 60664-1: 230 V, OVC II → 2.5 kV basic, **4 kV reinforced** (most reinforced parts spec 6 kV+ anyway),
- package creepage matching your board: wide-body SOIC-16, ≥8 mm. Examples: ISO7721DW, Si8621 BD-IS, ADuM1281 in the reinforced-grade wide package. Check the actual cert table, not the headline "5 kV_rms" number — withstand voltage alone does not make a part reinforced.

Also route a **slot** under the isolator; 8 mm over unbroken FR-4 with flux residue is not 8 mm.

**4. No, and no.** The ZMPT101B and ZMCT103C are uncertified Chinese measurement transformers. The datasheets claim a hipot figure (~3–4 kV test), but there is no IEC 62368/60664 safety certification, no declared comparative tracking index, no production insulation testing you can verify, and — the worse problem — the common breakout **modules** route primary and secondary with <3 mm spacing on cheap single-layer boards. Treat their insulation as functional, maybe basic, never reinforced. If you used Option B, your SELV claim would rest entirely on them, which contradicts your own spec. This is the decisive argument for Option A.

**5. Shunt gotchas, in rough order of how often they're botched:**

- **Kelvin or nothing.** Your full-scale signal is 10 mV. On 2 oz copper, ~10 mm of 5 mm-wide trace is ~0.17 mΩ — a 17 % error if sense taps share the current path. Use a true 4-terminal footprint with sense traces leaving from the inside edges of the pads, routed as a tight differential pair.
- **Solder joint drift:** 2512 pad joints add resistance that drifts; the Kelvin footprint also fixes this, but only if the sense taps are inboard of the fillets.
- **Thermal EMF:** manganin-copper is ~1 µV/K — small, but keep the layout thermally symmetric so both junctions sit at the same temperature; don't park the shunt next to the relay coil or the dropper resistor.
- **Order in the line: fuse → MOV tap → shunt → relay → load.** Fuse first (the shunt is not your fusible element; a bolted fault through 1 mΩ is thousands of amps and it will not open gracefully). MOV tapped *upstream* of the shunt so surge current doesn't cross it and slam the BL0942 inputs — and add RC filters on the sense lines regardless.
- **Shunt upstream of the relay**, so the chip's ground reference stays solidly tied to live when the relay is open. (You'll meter the relay coil's… nothing — coil is SELV-side — and the dropper only if you tapped it wrong, per Q2.)
- Power is fine: 0.1 W at 10 A, 0.26 W at 16 A — a 2512 manganin part handles it. Check the pulse/surge rating for the MOV-letthrough case anyway.

**6. Failure modes that make the USB live:**

- **The relay.** You said "16 A relay with reinforced coil–contact insulation" — verify that's real. Most cheap 16 A relays are 1.5–2.5 kV functional/basic coil-to-contact with ~3–4 mm internal creepage. You need something explicitly spec'd reinforced (e.g., Hongfa HF115F or Omron G5RL variants with 5 kV / 10 mm coil-contact). Also check the **footprint**: coil and contact pins on many 16 A relays are <8 mm apart on the PCB even when the internals are fine — slot the board between them.
- **Isolator failure:** mitigated by buying a genuinely reinforced-certified part (Q3), slot under it, no pours narrowing the gap.
- **Creepage erosion:** flux residue, dust, condensation in a sealed warm/cold-cycling cord barrel. Clean the board properly; slots under relay and isolator; consider conformal coat on the mains side.
- **Option B's version of this** — transformer insulation failure — puts mains directly on the SELV ground. Another reason it's rejected.
- **Mechanical:** cord strain relief failure letting a live conductor wander inside the enclosure can bypass every PCB barrier. Anchor both cords properly and keep the USB connector physically distanced from mains wiring, not just the PCB gap.

**7. Not considered: your plug is (almost certainly) non-polarized.** If this is a Schuko/Europlug region, the cord can be inserted either way, so "live" and "neutral" are not fixed. Consequences: your fuse and single-pole relay may end up in the *neutral*, meaning **relay-off does not make the load terminal dead**, and a fault downstream isn't cleared from the live side. Safety-wise your design survives (everything mains-side is treated as hazardous regardless), but you must *design and label* assuming the output is live whenever the plug is in — and if you ever service the thing with the relay off, that assumption matters. Double-pole relays or fusing both lines is the thorough fix; at minimum, internalize that "switched off" ≠ "isolated." Runner-up you also didn't mention: whether a 2-layer 2 oz board can actually carry 10 A continuous through the relay/shunt region without unacceptable heating — you'll want ~5–6 mm tracks or exposed-copper solder-filled paths, and heat here directly degrades your shunt accuracy and relay life.
