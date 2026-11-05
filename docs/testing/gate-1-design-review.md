# Gate 1: design review before ordering

**Result: passed, 5 Nov 2026.** Martin ordered five assembled boards from JLCPCB the same day
($148.20), from tag `rev-b-ordered` (`da3ad1a`). The work is in PR #3 (merged).

This page gathers the evidence. The reasoning for each decision is in `docs/DESIGN.md`; the
reviewers' answers are in `docs/design/cabal/20261105-*-gate-1-design-review-*`.

## What was checked

| Check | Result | Where |
|---|---|---|
| KiCad DRC, with the mains and 10 A rules | **0 violations, 0 unconnected** (KiCad 10.0.0, 5 Nov 2026 16:37) | `pcb/out/petro/drc.json` |
| Mains pours whole, ≥ 3.5 mm on each layer | Whole on both layers; the `Mains16A` class and the zones' minimum width fail the build otherwise | `pcb/board/checks.py` (`pour_problems`), tests |
| Spacing by working voltage (IEC 60664-1 Table F.4, PD2, material group III) | 2.5 mm between mains potentials and to GND; the DC bus 3.55 mm to GND and 4.35 mm to the live; the switching node 1.0 mm inside the converter only; 3 mm to the edge and holes | `pcb/board/rules.py`, `docs/DESIGN.md` §3.3 |
| Fuse coordination | F1 15 A HBC (50 kA) for short circuits; the plug's 13 A for the cord; the firmware trip at ~10.5 A for the rating; F2 T500 mA with R1 10 Ω fusible for the supply. Inrush I²t ≈ 0.05 A²s against F2's 0.42 A²s (Fable's estimate; checked at Gate 3) | `docs/DESIGN.md` §5.1, §5.3 |
| The relay's ratings | HF115F-I/005-1HS3A: 16 A 250 V AC (not the plain HF115F, VDE-rated only 10 A at 70 °C); 5 V coil, 80 mA | `docs/DESIGN.md` §4 |
| Code review of the generator (`superpowers:requesting-code-review`) | "With fixes": 1 critical and 4 important findings, all fixed; 6 minor (2 fixed, 4 accepted or already covered) | PR #3, below |
| `cabal`: seven models on the mains design | Answers from all seven, on the design before and after the fixes | `docs/design/cabal/` |
| Board-generator tests | 287 passing | `pcb/tests/` |

## What the review changed

**From the code review:**
- **Critical:** the switching node's 1.0 mm applied to every group, so DRC would have passed SW
  1 mm from the live. Now it applies only to the supply's own input, its bus and GND. A test
  shows SW 2 mm from L_F failing.
- The DC bus was treated as 250 V rms. It is now its own group at the rectified peak: 3.55 mm to
  GND, 4.35 mm to the live. R1, C1, D3 and Q1 moved to meet that.
- The PSU group no longer holds nets with hundreds of volts between them.
- A negative test for a necked pour, and SMD pads (the shunt's included) are now checked against
  the pours.
- `case-interface.json` flags J4 and the button and LED openings as at mains potential.

**From the cabal:**
- **The MOV returns to N_IN**, ahead of the shunt (all four first-round reviewers), so a surge
  misses the shunt and the BL0939's inputs.
- **J3's 3.3 V load is cut to about 50 mA**, for the AP2112K's heat (Fable, Opus).

**Found while re-laying out the shunt:** the shunt's sense pad *was* GND, so the supply's return
current flowed in a sense line, which would have read as tens of watts of phantom power. E1 is now
KGND, a current-free Kelvin return, and GND joins N_IN through R29 (0 Ω), the star point.

## Considered and declined (Martin's decisions)

| Suggestion | From | Decision |
|---|---|---|
| Isolate the board (or J3) | Fable, Llama 3, Nova Pro | Declined for cost (4 Nov): rev A at £240.67 for 5; isolated J3 about £75 more. Tags `5v-240v-separation-v1`, `rev-b-isolated-io`. Safety moves to the case and how it's used (README rules) |
| A polarity (reversal) guard | Several | Declined (5 Nov): it needs an earth reference on the PCB. A socket tester before every first use instead (§3.4) |
| 2 oz copper | Fable | Declined (5 Nov): 1 oz, pours ≥ 3.5 mm a layer. **The joints are the real risk, so Gate 2 makes the hand-soldering check strict** |
| The switching node to ~1.5 mm | Fable, Nova Pro | Kept at 1.0 mm (5 Nov): 1.6 mm left five spots at 1.15–1.46 mm and needed the supply re-laid out. Fable accepts 1.0 mm **if the flux is cleaned thoroughly**, which is in Gate 2 |
| F1 at 10 A | Fable | Kept at 15 A: a 10 A fuse at 10 A continuous runs at 100 % of its rating. F1 is there for breaking capacity; the trip covers the rating (§5.1) |
| The divider after F1 | Fable | Kept from L_IN, so the BL0939 still sees the mains with F1 blown; 5 × 390 kΩ limits any fault current |
| 450 V bulk capacitors | Fable | Kept at 400 V: the thermally protected MOV clamps first. Noted for a rev C |
| Thermal relief on the mains pads | Mistral | Declined: solid joins for current (Opus) |

## Carried into the later gates

- **Gate 2:** preheat and a large tip for the mains joints, fill checked from both sides;
  flux cleaned from the supply's 1.0 mm gaps; dead checks before any power.
- **Gate 3:** a dim-bulb first power-up (Opus); the socket tester; USB and scope never
  connected; F2's inrush over 10 plug-ins; the supply under sustained Wi-Fi with no brown-outs
  (Fable, Opus); creepage round the button and light pipe (Fable, for PETRO-6).
- **Gate 4:** the trip is tested before the load test; the relay's behaviour if it doesn't open
  (only the plug fuse is left, which is accepted).
