# Petro: design decisions

This records the design decisions behind Petro, and why each was made (PETRO-1). `CLAUDE.md` holds
the short form; this file has the reasoning and the parts.

**Petro is for Martin's own home and will never be sold or given away.** Nothing here has been
safety tested or certified.

## 1. Requirements

- 10 A continuous at 230 V AC (UK), resistive. Derate inductive and capacitive loads.
- An in-line cord unit: cable in, cable out, in Martin's own printed case (PETRO-6) in a UL94 V-0
  flame-retardant filament, with glands and cord grips. The case is opaque and must not leak LED
  light through cracks or joins.
- Energy metering: V, A, W and kWh (BL0939).
- One tactile button cycling on → off → auto; a WS2812B status LED.
- MQTT through AWS IoT Core (Fleet), OTA updates with rollback, and Alexa.
- Everything on the low-voltage side is SELV, so USB and the debug pads are safe to touch while
  mains is connected.

## 2. Block diagram

```
 L in ─┬─ F1 15 A ─┬─ MOV ─┐ (L–N)
       │           │       │
       │           ├─ F2 T500 mA ── PSU1 IRM-05-5 ═══╪══ 5 V SELV ─┬─ diode-OR ─ AP2112K 3V3 ─ ESP32-S3
       │           │                   (reinforced)    ║              │   (USB VBUS)              │  │
       │           │                                   ║              │                           │  ├ button, LED,
       │           │                                   ║              └─ relay coil (AO3400A) ───┘  │ NTC, USB, debug
       │           │                                   ║                                            │
       │           └─ R_shunt 1 mΩ (Kelvin) ── K1 relay contact ── L out                         │
       │                  │                                                                       │
       │              BL0939 ═ 3V3 + UART, ZX, OC ═ U4 ISOW7743 (reinforced, isolated DC-DC) ════┘
       │                  │ (V divider L–N)                 powered from the SELV 5 V
 N in ─┴──────────────────┴─────────────────────────────────────────────── N out
                                                     ═ / ║ : the 8 mm reinforced barrier
 Earth: not on the PCB (Wago 221 in the case).
```

Three things cross the barrier, and each must be rated as reinforced insulation in its own right:
**PSU1** (Mean Well, certified), **the relay** (coil to contact) and **the isolator with power**
(the ISOW7743 carries both the signals and the island's supply).

## 3. Decisions

### 3.1 Metering: Option A, a shunt with a reinforced isolator

Decided on 2 Nov 2026, after asking seven models through `cabal` (6 votes to 1; the answers are in
`docs/design/cabal/`).

- **A 1 mΩ manganin shunt in the live, and a resistor divider for voltage.** The BL0939 sits on
  the mains side, its ground on the shunt/live node.
- **Not Option B (a current transformer and a voltage transformer).** The ZMPT101B and ZMCT103C
  have no safety certification, so in Option B they would be the only thing between mains and the
  USB connector. Every model that answered agreed they can't be trusted for that, including the one
  that voted for B. B is also bulkier, adds phase error, and is weaker at low loads.
- **The UART crosses through a wide-body digital isolator certified as reinforced insulation**
  (VDE 0884-11 / IEC 60747-17), not optocouplers. Optocouplers wear out, and their LED current
  (2–5 mA per channel) strains a small supply. The narrow-body ISO6721 is rated only as basic
  insulation, so it doesn't qualify.
- **Four channels, not two** (decided 4 Nov 2026, PETRO-2). Three go from mains to SELV: the
  BL0939's TX, its zero-cross output (for zero-cross switching) and its channel-B fast over-current
  output I_leak (pin 10; an interrupt for the trip). One goes SELV to mains: the BL0939's RX.
- **The isolator also powers the island: TI ISOW7743** (decided 4 Nov 2026, PETRO-2; TI
  SLLSFK1C). It replaced the ISO7741 and PSU2 (an IRM-01-5 with its output tied to live), because
  the 120 mm board could not hold PSU2 beside F1, the relay and PSU1 with the cables at opposite
  ends. Its reinforced isolated converter (5 kV rms, 1000 V rms working, >8 mm creepage) takes the
  SELV 5 V and makes the island's 3.3 V (up to 140 mA; the island draws about 10–20 mA). Power
  flows from side 1 to side 2, so side 1 is SELV, hence the 7743 (1 forward, 3 reverse channels).
  TI's two ferrite beads (BLM15EX331SN1D) and decoupling are fitted for low emissions. EN/FLT is
  read on GPIO47. Prefer the non-F ISOW7743DFMR (outputs high on lost input, so a dead island
  reads as over-current); the F variant (LCSC C5216380) is acceptable. Never a B (basic) part. A
  bonus: the BL0939 is powered on USB alone, so Gate 2 can test its UART without mains.
- **Order in the live:** fuse → MOV → shunt → relay → load. The fuse comes first, because the
  shunt isn't a fuse and won't fail safely. The shunt goes before the relay, so the BL0939 keeps its
  reference to live when the relay is open.
- **The shunt is wired Kelvin-style:** the sense traces leave from the inside edges of its pads, as
  a tight pair, laid out symmetrically for temperature. 10 mm of 5 mm-wide 2 oz track is about
  0.17 mΩ, so sense taps on the current path would be off by 17 %.

### 3.2 Power: one Mean Well module

- **PSU1, the IRM-05-5 (5 V, 1 A), for the SELV side.** The IRM-03-5's 600 mA was tight: the peak
  load is about 450 mA (Wi-Fi transmit about 340 mA, relay coil about 80 mA, LED). RS 135-8923.
- **The metering island is powered by the ISOW7743 (§3.1), not from the mains.** PSU2 (an
  IRM-01-5) was dropped on 4 Nov 2026 for space. A capacitive dropper was rejected earlier (cabal,
  5 votes to 2): inrush, MOV placement, X2-capacitor ageing and its return current through the
  shunt.
- **A non-isolated supply for the SELV side is never acceptable.**
- **Protection on PSU1's output:** a polyfuse and a TVS, so that a failed module can't drive
  raw faults into the SELV rail.
- **Buy safety-critical parts only from authorised distributors.** That means the PSUs, isolator,
  relay, fuses and MOV: never marketplace traders, because of counterfeits.

### 3.3 Mains polarity

UK BS 1363 plugs are polarised, so a single-pole relay and fuse in the live are enough. A
miswired socket or extension could still swap live and neutral, so the output is labelled and
treated as **live whenever the unit is plugged in**, even with the relay open. The Gate 3 procedure
says so.

### 3.4 Light sealing

The case is opaque. The light pipe runs through an opaque boss whose flange sits around the LED on
the board, and it may be glued down with opaque glue or enamel paint. The board keeps a **2 mm
clear ring around the WS2812B**: no parts in it, and nothing proud of the soldermask. The board
generator enforces this as a keep-out and exports the LED's position for the case.

## 4. Parts

Stock and prices are from JLCPCB/LCSC on 2 Nov 2026 (the price is for one unit). The full
research, with the datasheet figures and their sources, is in `docs/design/parts-research/`.
Figures marked *unverified* there have not been checked against a primary datasheet.

### Mains side

| Ref | Part | Maker | LCSC | Stock | Key rating | Notes |
|---|---|---|---|---|---|---|
| K1 | HF115F-I/005-1HS3A | Hongfa | C2976795 | 25 | 16 A 250 VAC; 5 V coil, 80 mA; coil–contact 5 kV, 10 mm creepage, reinforced (VDE) | Coil and contact pins about 20 mm apart, so no slot needed. **Not** the plain HF115F/005-1HS3 (C81373), which is VDE-rated only 10 A at 70 °C. Fallback: Omron G5RL-1A-E-HR (not on LCSC) |
| F1 | 0505015.MXP (15 A, 6.3×32 mm ceramic, sand-filled, high breaking capacity) | Littelfuse | C3165450 | 65 | **50 kA** breaking at 500 VAC | Decided in §5.1. Fallback: 0215015.MXP (5×20, 15 A, only 500 A breaking, C720202) in 01000056Z clips (15 A, C151074) |
| F1 clips | 01220088Z (×2, 122 series PCB clips for ¼" fuses, beryllium copper, tin-plated, with ears) | Littelfuse | C206903 | 4,484 | 30 A; 505 series listed as compatible | Corrected 4 Nov 2026 (PETRO-2): the Keystone 3557-2 first listed here is an automotive blade-fuse holder and cannot hold this fuse. Clip centres 26.59 mm apart (outer holes 34.21 mm, Littelfuse's "A" for 1¼"). No barrier: the closed case covers that |
| F2 | 0215.500MXP (T500mA 5×20 ceramic) | Littelfuse | C142839 | 2,052 | 1.5 kA breaking | Feeds PSU1. Not a TR5 (35 A breaking only) |
| F2 holder | 65600001009 (656 series) | Littelfuse | C187510 | 55 (+199 of the `.J` variant) | 10 A, 250 V, UL94 V-0 | Open holder |
| RV1 | TMOV20RP275E | Littelfuse | C187710 | 440 | 275 VAC, thermally protected | TMOV14RP275E (C1528070) is the smaller option, but only 3 are in stock |
| R_SH | WSK25121L000FEA (1 mΩ, 4-terminal, 2512) | Vishay | C4248455 | 4,000 | Kelvin terminals | 0.1 W at 10 A |
| J1, J2 | DG636-7.62-02P | Degson | C2827897 | 933 | 32 A, 630 V, 7.62 mm pitch | L in/N in and L out/N out; wire entry to the side |
| PSU1 | IRM-05-5 | Mean Well | (RS 135-8923) | RS: in stock | 5 V 1 A, reinforced | 45.7 × 25.4 × 21.5 mm; inrush 40 A at 230 V |
| U_M | BL0939 (SOP-16) | Belling | C2836697 | 2,684 | 2 current channels, 1 voltage, ZX, UART 4800 | SSOP-20 C2841044: 6,789 in stock |
| R_V | 5 × 390 kΩ (1206, C17933) over 470 Ω (0402, C25117) | UNI-ROYAL | | | ≈ 4150:1 | 61 mV rms at 253 V against the BL0939's 70 mV maximum (13 % headroom; 510 Ω gave 6 %). 50 V across each 390 kΩ, whose 1206 pads are 1.75 mm apart (1.2 mm needed) |
| Q1, D1 | AO3400A, 1N4148W | | | | | Relay driver and flyback, as on the heatlink |

### Across the barrier

| Ref | Part | Maker | LCSC | Stock | Key rating | Notes |
|---|---|---|---|---|---|---|
| U4 | ISOW7743DFMR (preferred) or ISOW7743FDFMR | TI | C5216380 (F) | 48 (F) | Reinforced, 5 kV rms, isolated DC-DC 0.55 W; 1 forward + 3 reverse channels; SOIC-20 wide body, >8 mm creepage | Replaces the ISO7741 and PSU2 (§3.1). Never a B (basic) part. With TI's beads (BLM15EX331SN1D, C596498) |

### SELV side

| Ref | Part | LCSC | Notes |
|---|---|---|---|
| U1 | ESP32-S3-MINI-1-N8 | C2913206 | As on the heatlink; its LGA needs X-ray at assembly |
| U2 | AP2112K-3.3TRG1 | C51118 | The ESP32-S3 peaks at 355 mA on Wi-Fi transmit, against the LDO's 600 mA |
| D_OR | SS34 ×2 | C8678 | Diode-OR of USB VBUS and PSU1; over 0.5 V of margin above the LDO's dropout |
| F3, D_TVS | 1206L110THYR polyfuse, SMAJ5.0A TVS | C126818, C2925443 | On PSU1's output |
| J3 | House USB connector (JST SH 5-pin) | (as tinycrypt) | ESD on D±, polyfuse and TVS on VBUS, as on the heatlink |
| SW1 | TS-1002 6×6 tactile, 7 mm tall | C455095 | Other heights are available for the cap stack-up |
| LED1 | WS2812B-2020-V6 | C52917434 | 672k in stock. The 2 mm clear ring means its decoupling capacitor goes on the bottom side or outside the ring |
| RT1 | 10 kΩ 0603 NTC (B 3987 K) | C2892547 | SELV side, beside the relay coil pins; under-reads the terminal temperature, so calibrate at Gate 4 |

### Enclosure

**Martin's own printed case** (decided 4 Nov 2026, PETRO-2), designed around the board in PETRO-6.
It must be printed in a **UL94 V-0 flame-retardant filament** (FR-ABS, FR-PC/ABS or FR-PETG; never
plain PLA or PETG), checked against what the CR6-SE can print. The board sets the case: about
120 × 70 mm, M3 holes near the corners, the ESP32's antenna overhanging the SELV long edge (the case
leaves it clear space), and the heights in `pcb/out/case-interface.json`. Glands: HellermannTyton
NGM16-BLK (5–10 mm), V-2 only; no V-0 black nylon gland was found. The bought Hammond 1591XXDBK
(V-0 ABS, 75 mm inside) researched in PETRO-1 is the fallback; its fixed width was what pinched
the board.

## 5. Open questions

### 5.1 The main fuse and the current rating: decided 2 Nov 2026

**Petro stays at 10 A continuous.** A T10A fuse in a 10 A holder at 10 A continuous would run at
100 % of both ratings, against normal practice of about 75 %. So:

- **The copper, terminals and relay are sized for 16 A.** The relay is already 16 A and the
  terminals 32 A, and the `Mains16A` net class's minimum width is set for 16 A.
- **F1 is a 15 A high-breaking-capacity fuse** (0505015.MXP, 6.3×32 mm, 50 kA) in 30 A clips
  (Littelfuse 01220088Z). A replacement must be a 6.3×32 mm ceramic fast-acting (F) fuse of 15 or
  16 A (not above the 16 A the copper is sized for), rated at least 250 V AC, with a breaking
  capacity of **at least 1.5 kA at 250 V AC or above** stated on its datasheet, from an authorised
  distributor. Never a glass fuse, and not Littelfuse's 314 series: its 10 kA is at 125 V only,
  750 A at 250 V AC. The RS PRO F16A HBC (RS 209-9298) is an acceptable spare, but its datasheet
  gives no figure (HBC conventionally means 1.5 kA). It
  protects against short circuits. 15 A, not 16 A: 16 A comes in neither the high-breaking range
  nor 15 A clips, and 10 A is 67 % of 15 A. A 5×20 15 A fuse breaks only about 500 A, which is low
  for a UK socket's prospective fault current, hence the 6.3×32.
- **Overload:** the plug's 13 A BS 1362 fuse protects the cord, and the firmware trip at about
  10.5 A is the backstop for the unit's rating (PETRO-5).

### 5.2 Metering chip: the BL0939, decided 2 Nov 2026

The BL0942 has 0 stock at LCSC and JLCPCB in every package. **We use the BL0939** (C2836697 SOP-16,
2,684 in stock; or C2841044 SSOP-20, 6,789): the same Belling family, a UART at 4800 baud, voltage
and current zero-cross outputs (so zero-cross switching stays possible), and ESPHome's `bl0939`
component as a reference. It has two current channels: one measures the shunt, and the other is
spare (tie it off, or use it later). Its datasheet is in Chinese only, so the register map comes
from that and ESPHome.

The alternatives considered:

| Chip | Stock | UART | Zero-cross out | ESPHome | Why not |
|---|---|---|---|---|---|
| HLW8032 | 30,003 | TX only | No | Yes | No zero-cross output |
| HLW8110 | 13,521 | Yes | Yes (*unverified*) | No | The driver would be written from scratch |
| BL0942 from elsewhere | — | Yes | Yes | Yes | Not stocked where the board is assembled |

### 5.3 Other open questions

- The PSUs' inrush (40 A and 10 A) against F2's melting I²t (0.42 A²s): check it on the bench at
  power-up. If F2 nuisance-blows, move to T1A.
- The voltage divider's headroom: about 6.5 % at 253 V with the BL0942's reference divider.
  Re-check it for the chosen chip.
- The glands are V-2 only. Accept that (they're not current-carrying), or find V-0 glands.
