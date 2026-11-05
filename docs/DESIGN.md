# Petro: design decisions

This records the design decisions behind Petro, and why each was made (PETRO-1). `CLAUDE.md` holds
the short form; this file has the reasoning and the parts.

**Petro is for Martin's own home and will never be sold or given away.** Nothing here has been
safety tested or certified.

## 1. Requirements

- 10 A continuous at 230 V AC (UK), resistive. Derate inductive and capacitive loads.
- An in-line cord unit: cable in, cable out, in a bought UL94 V-0 enclosure with glands and cord
  grips. The case is opaque and must not leak LED light through cracks or joins.
- Energy metering: V, A, W and kWh (BL0939).
- One tactile button cycling on → off → auto; a WS2812B status LED.
- MQTT through AWS IoT Core (Fleet), OTA updates with rollback, and Alexa.
- Everything on the low-voltage side is SELV, so USB and the debug pads are safe to touch while
  mains is connected.

## 2. Block diagram

```
 L in ─┬─ F1 15 A ─┬─ MOV ─┐ (L–N)
       │           │       │
       │           ├─ F2 T500 mA ─┬─ PSU1 IRM-05-5 ══╪══ 5 V SELV ─┬─ diode-OR ─ AP2112K 3V3 ─ ESP32-S3
       │           │              │    (reinforced)   ║              │   (USB VBUS)              │  │
       │           │              └─ PSU2 IRM-01-5 ──┐║              │                           │  ├ button, LED,
       │           │                 (output tied to │║              └─ relay coil (AO3400A) ───┘  │ NTC, USB, debug
       │           │                  live: mains)   │║                                            │
       │           └─ R_shunt 1 mΩ (Kelvin) ── K1 relay contact ── L out                         │
       │                  │                                                                       │
       │              BL0939 ── LDO 3V3 ── PSU2           UART ═ U_iso (reinforced) ═════════════┘
       │                  │ (V divider L–N)
 N in ─┴──────────────────┴─────────────────────────────────────────────── N out
                                                     ═ / ║ : the 8 mm reinforced barrier
 Earth: not on the PCB (Wago 221 in the case).
```

Three things cross the barrier, and each must be rated as reinforced insulation in its own right:
**PSU1** (Mean Well, certified), **the relay** (coil to contact) and **the digital isolator**.
PSU2's isolation does no safety work: its output is deliberately tied to live.

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
- **Order in the live:** fuse → MOV → shunt → relay → load. The fuse comes first, because the
  shunt isn't a fuse and won't fail safely. The shunt goes before the relay, so the BL0939 keeps its
  reference to live when the relay is open.
- **The shunt is wired Kelvin-style:** the sense traces leave from the inside edges of its pads, as
  a tight pair, laid out symmetrically for temperature. 10 mm of 5 mm-wide 2 oz track is about
  0.17 mΩ, so sense taps on the current path would be off by 17 %.

### 3.2 Power: two Mean Well modules

- **PSU1, the IRM-05-5 (5 V, 1 A), for the SELV side.** The IRM-03-5's 600 mA was tight: the peak
  load is about 450 mA (Wi-Fi transmit about 340 mA, relay coil about 80 mA, LED). RS 135-8923.
- **PSU2, the IRM-01-5 (5 V, 200 mA), for the mains-side metering.** Its output is tied to live,
  and it feeds a 3.3 V LDO for the BL0939 and the isolator's mains side, which draw about 5–10 mA.
  RS 135-9124. It replaces the capacitive dropper the brief suggested, which cabal favoured 5 votes
  to 2 against. A dropper brings inrush, MOV placement, X2-capacitor ageing and its return current
  flowing through the shunt, and it would need sizing for about 5 mA, not 1 mA. The fallback, if the
  IRM-01 is out of stock, is a second IRM-05-5.
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
| F1 clips | 3557-2 (×2, 6.3 mm fuse clips) | Keystone | C352820 | 1,089 | 30 A, 500 V | Fit a cover or barrier if the case allows |
| F2 | 0215.500MXP (T500mA 5×20 ceramic) | Littelfuse | C142839 | 2,052 | 1.5 kA breaking | Feeds both PSUs. Not a TR5 (35 A breaking only) |
| F2 holder | 65600001009 (656 series) | Littelfuse | C187510 | 55 (+199 of the `.J` variant) | 10 A, 250 V, UL94 V-0 | Open holder |
| RV1 | TMOV20RP275E | Littelfuse | C187710 | 440 | 275 VAC, thermally protected | TMOV14RP275E (C1528070) is the smaller option, but only 3 are in stock |
| R_SH | WSK25121L000FEA (1 mΩ, 4-terminal, 2512) | Vishay | C4248455 | 4,000 | Kelvin terminals | 0.1 W at 10 A |
| J1, J2 | DG636-7.62-02P | Degson | C2827897 | 933 | 32 A, 630 V, 7.62 mm pitch | L in/N in and L out/N out; wire entry to the side |
| PSU1 | IRM-05-5 | Mean Well | (RS 135-8923) | RS: in stock | 5 V 1 A, reinforced | 45.7 × 25.4 × 21.5 mm; inrush 40 A at 230 V |
| PSU2 | IRM-01-5 | Mean Well | (RS 135-9124) | RS: in stock | 5 V 200 mA | 33.7 × 22.2 × 15 mm; output tied to live; inrush 10 A |
| U_M | BL0939 (SOP-16) | Belling | C2836697 | 2,684 | 2 current channels, 1 voltage, ZX, UART 4800 | SSOP-20 C2841044: 6,789 in stock |
| R_V | 5 × 390 kΩ (1206) over 510 Ω | | | | ≈ 3825:1 | The Belling/Tuya reference divider; re-check the headroom for the chosen chip |
| U_LDO_M | AP2112K-3.3TRG1 | Diodes | C51118 | 7,985 | 600 mA | The mains-side 3.3 V |
| Q1, D1 | AO3400A, 1N4148W | | | | | Relay driver and flyback, as on the heatlink |

### Across the barrier

| Ref | Part | Maker | LCSC | Stock | Key rating | Notes |
|---|---|---|---|---|---|---|
| U_ISO | ISO7721DWR | TI | C524805 | 3,386 | Reinforced (VDE 0884-17); V_IORM 2121 Vpk; V_IOTM 8 kV; 8 mm creepage and clearance; outputs default high | **Never the ISO7721B**: it's rated as basic insulation only |

### SELV side

| Ref | Part | LCSC | Notes |
|---|---|---|---|
| U1 | ESP32-S3-MINI-1-N8 | C2913206 | As on the heatlink; its LGA needs X-ray at assembly |
| U2 | AP2112K-3.3TRG1 | C51118 | The ESP32-S3 peaks at 355 mA on Wi-Fi transmit, against the LDO's 600 mA |
| D_OR | SS34 ×2 | C8678 | Diode-OR of USB VBUS and PSU1; over 0.5 V of margin above the LDO's dropout |
| F3, D_TVS | 1206L110THYR polyfuse, SMAJ5.0A TVS | C126818, C113952 | On PSU1's output |
| J3 | House USB connector (JST SH 5-pin) | (as tinycrypt) | ESD on D±, polyfuse and TVS on VBUS, as on the heatlink |
| SW1 | TS-1002 6×6 tactile, 7 mm tall | C455095 | Other heights are available for the cap stack-up |
| LED1 | WS2812B-2020-V6 | C52917434 | 672k in stock. The 2 mm clear ring means its decoupling capacitor goes on the bottom side or outside the ring |
| RT1 | 10 kΩ 0603 NTC (B 3987 K) | C2892547 | SELV side, beside the relay coil pins; under-reads the terminal temperature, so calibrate at Gate 4 |

### Enclosure

**Hammond 1591XXDBK**: black ABS, UL94 V-0 according to Hammond's drawing (not the "S" codes,
which are HB). About 148 × 75 × 46.5 mm inside, with four M3 bosses at 114.75 × 54.25 mm. Rapid
30-1839, £6.59. Glands: HellermannTyton NGM16-BLK (5–10 mm), which are V-2 only. No V-0 black nylon
gland was found. That leaves a **board of about 120 × 60 mm** on the box's bosses.

## 5. Open questions

### 5.1 The main fuse and the current rating: decided 2 Nov 2026

**Petro stays at 10 A continuous.** A T10A fuse in a 10 A holder at 10 A continuous would run at
100 % of both ratings, against normal practice of about 75 %. So:

- **The copper, terminals and relay are sized for 16 A.** The relay is already 16 A and the
  terminals 32 A, and the `Mains16A` net class's minimum width is set for 16 A.
- **F1 is a 15 A high-breaking-capacity fuse** (0505015.MXP, 6.3×32 mm, 50 kA) in 30 A clips. It
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
