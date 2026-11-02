# Cabal consultation — anthropic:opus-4-8

- Tokens: 1108 in / 3429 out
- Cost: $0.091265 USD
- Latency: 65296 ms

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

# Design Review

## 1. Which option

**Option A.** For an in-line cord unit at 230 V / 10 A you want the accuracy and the small footprint, and Option A is literally what every shipping smart plug does for good reasons. Your isolation strategy is already sound: the relay and the digital isolator are the two barriers, the BL0942 lives in the dirty domain where it belongs, and you never have to trust a $1 transformer module as a safety barrier.

Option B's hidden cost is not "bulkier + phase error." It's that you're putting two Chinese hobby-grade transformer modules in the safety-critical isolation path (see Q4), and the ZMPT101B in particular is terrible at mains-voltage metering accuracy because it's a current-sense transformer being abused as a voltage transformer through a burden resistor. At 10 A continuous the bulk isn't free either — ZMCT103C saturation and phase shift at the low end will annoy you.

So: Option A, shunt + divider on mains side, one reinforced digital isolator for UART.

## 2. Powering the BL0942 + isolator mains side

Don't use a capacitive dropper. Here's the trap list and why it loses:

- 1 mA from a dropper is *not enough*. BL0942 + the mains-side supply of a digital isolator (ISO6721 family draws a few mA on each side just for the channels) will blow past 1 mA. You'd need a bigger X2 cap, which means more inrush and more heat in the bleeder.
- Dropper output is unregulated and sags under load; the BL0942's analog front end wants a stable rail or your calibration drifts.
- Dropper + MOV + inrush interactions are a genuine pain and the X2 cap failure mode (open) just kills your meter silently, which is benign, but a dropper with a failed series resistor can dump mains transients into your "3.3 V."

**Best answer:** a *second* small isolated module (another IRM-03-5 or the tiny IRM-01-3.3) dedicated to the mains-side domain. "Isolated" here is relative — this module's output is referenced to the shunt/live node, i.e. it is *mains-referenced by design*, which is exactly what you want. The reinforced isolation of that second module isn't doing safety work (both its sides are in the dirty domain effectively), it's just a convenient buck/flyback that gives you a clean regulated rail sitting at mains potential. Two independent modules also keeps the two 5 V rails from needing any cross-reference.

Do **not** try to tap a non-isolated node off your main IRM-03-5 — that defeats the whole point of having a SELV side.

MOV placement: L-N across the input, *before* everything, downstream of the fuse. One MOV. Don't scatter them across the barrier.

## 3. Optocouplers vs digital isolator for UART

**Digital isolator, wide-body.** At 4800 baud speed is a non-issue, so the choice is about reliability and lifetime. Optocouplers degrade (CTR falls with age/temperature); a capacitive/magnetic digital isolator doesn't. The ISO6721/ISO7721-class wide-body SOIC is the right part.

For the part to *count* as reinforced at 230 V mains:

- You're in **overvoltage category II**, pollution degree 2, working voltage ~230 Vrms (~325 Vpk).
- Reinforced insulation requires roughly **8 mm creepage** at 250 V OVCII PD2 per 60664-1 — which is why you need the *wide-body* package. Standard narrow SOIC (~4 mm pin-to-pin) only gets you basic/supplementary.
- Look for the datasheet's VDE 0884-11 / IEC 60747-17 certification with a stated **V_IORM** (maximum repetitive working voltage) comfortably above 325 V and a **reinforced** rating, not basic. ISO6721 wide-body variants are certified to several kV surge and ~1.4 kV_IORM — plenty.
- The *component* rating is necessary but not sufficient: your PCB creepage under and around the part must also be 8 mm, and don't let the isolator's two grounds get closer than that anywhere on the board. A slot milled under the body helps if pin spacing is tight.

Note: UART is only two signals plus you need *nothing* else crossing — good. Keep the barrier clean.

## 4. ZMPT101B / ZMCT103C as safety barriers

**No. Do not trust either as a safety isolation barrier. Full stop.**

- **ZMPT101B**: it's a small signal transformer on a hobby breakout. No VDE/UL safety cert for reinforced or even basic mains isolation that you can rely on, no specified creepage/clearance, no partial-discharge testing, bobbin and wire insulation of unknown grade. People use it in 230 V projects and get away with it, but "gets away with it" is not a safety rating. Also as noted it's metrologically poor.
- **ZMCT103C**: same story. It's a current transformer that happens to provide galvanic separation, but there's no safety datasheet qualifying it as a reinforced barrier at 250 V working voltage. A CT's isolation can be decent physically, but you have no documentation and no PD data, so you can't claim it.

This is another reason Option A wins: in Option A your *certified* barriers (the relay's coil-contact insulation, the digital isolator, the isolated supply) are the ones doing safety work, and the metering chip never has to be a barrier at all.

## 5. Shunt gotchas

- **Kelvin / 4-wire is mandatory.** 1 mΩ is comparable to trace and solder-joint resistance. Sense traces must tap the pads *inside* the current path, routed as a tight differential pair straight to the BL0942, away from the power loop. If you let sense current share copper with load current, your calibration is garbage and drifts with temperature.
- **Thermal EMF**: manganin is chosen precisely for low thermal EMF and low tempco — good. But you can still introduce junction EMF if the two Kelvin taps sit at different temperatures (asymmetric copper, one near the relay). Keep the two sense taps thermally symmetric.
- **Power/heat**: 0.1 W at 10 A nominal is fine, but a 2512 at 10 A still warms, and if an inductive/motor load pulls inrush you'll see transient dissipation. More importantly the heat near the shunt skews nearby components; keep the BL0942 a bit away but sense traces short — tension there, lay it out carefully.
- **Which side of the relay**: put the shunt in **live, on the load side of the relay** only if you want to measure load current regardless — actually put it in the live conductor in series with the load; relay before or after doesn't change the measurement much, but conventionally shunt is in the switched live so it reads the controlled load. Divider taps live-to-neutral.
- **Relative to fuse**: fuse goes *first*, at the live inlet, protecting everything downstream including the shunt. Never put the shunt upstream of the fuse. The shunt is not a fusible link; don't rely on it to fail safe.

## 6. Failure modes that make USB live

The whole safety case is: **mains can only reach the SELV side if a reinforced barrier fails.** Design so no *single* fault bridges it:

- **Digital isolator failure**: a surge punch-through could short mains-side to SELV-side. Mitigation: pick the reinforced-rated part (Q3), keep the surge rating well above your OVCII transient, keep PCB creepage full 8 mm *including under the part*, and MOV at the input to clamp transients that would otherwise stress it.
- **The two SELV/mains barriers must not have a sneak path.** Check that *no* trace, no mounting screw, no ground-pour, no silk, no thermal relief crosses the 8 mm barrier anywhere. A single via placed carelessly in the gap ruins it. Consider a routed slot in the PCB along the barrier.
- **Relay**: coil-to-contact reinforced insulation is your other barrier. Verify the relay's datasheet actually states reinforced/kV coil-contact, and that its own pin creepage on your board meets 8 mm. A relay with only basic insulation here is a hidden single-fault-to-live.
- **USB connector itself**: when flashing, the laptop's ground ties your SELV ground to earth. That's *fine* and actually good (SELV referenced to PE), but it means any barrier breakdown energizes the laptop. So the barrier integrity is the only thing between mains and the person holding the USB cable — treat it as life-safety, not convenience.
- **Y-cap across the barrier**: if you add one for EMC, it *must* be a safety-rated **Y1** cap, because it deliberately bridges SELV↔mains. A wrong cap here is a direct shock path on failure.

## 7. The thing you haven't considered

**Mechanical/thermal enclosure and strain relief for an in-line cord unit carrying 10 A continuous.** You've designed the electronics to spec but an in-line cord switch is a thermal and mechanical product:

- 10 A continuous through connectors, the relay, the shunt, and the PCB traces means **real steady-state heat** in a sealed plastic box. 2 oz copper helps but your trace width for 10 A continuous inside an enclosure (poor convection, derate hard) needs checking — and the relay + IRM modules + shunt all dumping heat into a small box with no airflow can cook the electrolytic caps and shift your meter calibration. Do a thermal budget.
- **Strain relief on both cord entries** must be real (not just a cable gland squeezing insulation). An in-line unit gets yanked. If the live conductor pulls loose internally and touches the SELV side or the case, your whole isolation story is moot.
- **Enclosure flammability and the fact it's a cord-mounted mass.** The box hangs on the cable. Pick a V-0 enclosure, secure the PCB, and make sure nothing mains-referenced can touch a wall of the box that a person touches.

Electrically you've thought it through well. The part that bites home builders on in-line cord units is the boring mechanical/thermal stuff.
