# Petro: design decisions

This records the design decisions behind Petro, and why each was made (PETRO-1, PETRO-2).
`CLAUDE.md` holds the short form; this file has the reasoning and the parts.

**Petro is for Martin's own home and will never be sold or given away.** Nothing here has been
safety tested or certified.

The board is **revision B: non-isolated** (§3.1). Two earlier designs are kept as tags:

| Tag | What it is |
|---|---|
| `5v-240v-separation-v1` | Rev A: isolated, a Mean Well IRM-05-5, the BL0939 behind a reinforced ISOW7743, the ESP32-S3, 2 oz copper. Quoted at £240.67 for 5 |
| `rev-b-isolated-io` | Rev B with J3 behind three reinforced isolators (an island of SELV I/O). About £75 more for 5 than rev B as it stands |

## 1. Requirements

- 10 A continuous at 230 V AC (UK), resistive. Derate inductive and capacitive loads.
- An in-line cord unit: cable in, cable out, in Martin's own printed case (PETRO-6) in a UL94 V-0
  flame-retardant filament, with glands and cord grips. The case is opaque and must not leak LED
  light through cracks or joins.
- Energy metering: V, A, W and kWh (BL0939).
- One tactile button cycling on → off → auto; a status LED.
- MQTT through AWS IoT Core (Fleet), OTA updates with rollback, and Alexa.
- **The whole board is at mains potential.** Nothing conductive leaves the closed case; the button
  cap and the light pipe are plastic. USB and the debug pads are used only with mains unplugged.
- About £150 for five assembled boards (Martin's budget, 4 Nov 2026).

## 2. Block diagram

```
 L in ─┬─ F1 15 A ─┬─ MOV (to N in, ahead of the shunt)
       │           ├─ K1 relay contact ── L out
       │           └─ F2 T500 mA ─ R1 10 Ω fusible ─ D7 ─ π filter ─ LNK306 buck ─ 12 V
       │                                                                              │
       │                                                         TPS563201 ─ 5 V ─ diode-OR ─ USB VBUS
       │                                                                              │
       └─ divider 5 × 390 kΩ ─ VP ─┐                                     AP2112K ─ 3V3
                                   BL0939 ── UART, ZX, OC ── ESP32-C6 ─┬─ button, LED, NTC
                                   │ (IP/IN)                            ├─ relay driver (5 V coil)
 N in ─┬─ RS1 1 mΩ Kelvin ─────────┴──── N out                          └─ USB (J4), debug pads, J3 I/O
        │   E1 = KGND: a Kelvin return to the BL0939's IN- filters, carrying no current
        └─ R29 0 Ω = GND: the star point, the one place GND meets neutral
 Earth: not on the PCB (Wago 221 in the case).
```

## 3. Decisions

### 3.1 Non-isolated: rev B (decided 4 Nov 2026)

Rev A was finished, routed and DRC-clean: isolated throughout, with an 8 mm reinforced barrier,
the IRM-05-5 for the SELV side, and the BL0939's island powered and read across a TI ISOW7743. It
was quoted at **£240.67 for 5** (2 oz, Standard assembly, ex VAT and shipping), against a budget of
about £150. So Martin chose a non-isolated board:

- **The supply comes straight off the mains** (§3.3), and GND is neutral. Everything on the board
  is at mains potential, so every connector, test hole and pad is live whenever it is plugged in.
- **That moves the safety to the case and to how it's used.** The case is closed before mains is
  ever connected (Gate 3), nothing conductive passes through it, and the mounting holes are
  unplated so the screws aren't live. USB, the debug pads and a scope are only ever used with
  mains unplugged (or through an isolation transformer or a differential probe): USB with mains
  connected would tie the laptop's ground to neutral, or to live in a socket wired backwards. The
  silk says so on both sides ("DANGER 230 V AC / BOARD IS LIVE / GND = NEUTRAL / J3 I/O IS LIVE
  TOO / UNPLUG BEFORE USB").
- **An RCD-protected socket**, always. A fuse reacts only to hundreds of milliamps or more; an RCD
  is what protects someone touching a live part.
- **What it bought:** no ISOW7743 or IRM-05-5, no barrier or slot, and room for the supply on a
  120 × 80 mm board (4 mm rounded corners). With the changes in §3.6, five boards come to roughly £95–100 (ex VAT and
  shipping; an estimate until the basket gives a quote).

### 3.2 Metering: a shunt and a divider (Option A)

Decided on 2 Nov 2026, after asking seven models through `cabal` (6 votes to 1; the answers are in
`docs/design/cabal/`): a 1 mΩ manganin Kelvin shunt and a resistor divider (Option A), not a
current transformer and a voltage transformer (Option B). The ZMPT101B and ZMCT103C have no safety
certification, and B is bulkier, adds phase error and is weaker at low loads. In rev A the BL0939
sat on the live side behind a reinforced isolator; rev B needs none:

- **The shunt is in the neutral** (N_IN → RS1 → N_OUT), and both of its sense pads are true
  Kelvin connections: E2 is SENSE (to the IP inputs' 1 kΩ filters) and E1 is **KGND** (to the IN
  inputs' filters), a net of its own that carries no current. GND joins N_IN through **R29, a 0 Ω
  link** beside the metering corner: the **star point**, the one place GND meets neutral, so no load
  current flows in GND. (Until the gate 1 review GND *was* E1; then the supply's return current,
  the rectifier's charging pulses, flowed through the sense line and would have read as tens of
  watts of phantom power at the voltage peaks.)
- **Voltage: 5 × 390 kΩ (1206) from L_IN over 470 Ω**, about 4150:1: 61 mV rms at 253 V against
  the BL0939's 70 mV maximum (13 % headroom). 50 V across each 390 kΩ, whose 1206 pads are 1.75 mm
  apart. The divider hangs from L_IN, before F1, so the BL0939 still sees the mains with F1 blown.
- **Both current channels read the shunt** (Belling's 1 kΩ / 33 nF filters): channel A meters,
  channel B drives I_leak, the fast over-current output, an interrupt for the firmware trip.
- **UART, zero cross and over-current go straight to the ESP32**, with the BL0939's TX pulled up.
- **The Kelvin sense lines** leave from the shunt's sense pads through vias beside them and run
  as a tight pair on the bottom layer to the metering corner, routed by hand (`kelvin_route`). 10 mm
  of 5 mm-wide track is about 0.17 mΩ, so sense taps on the current path would be off by 17 %.
- **Order in the live:** F1 first, then the MOV and the relay. The MOV sits after F1, so F1 clears
  a shorted MOV, and it returns to **N_IN**, ahead of the shunt (moved at gate 1, all four reviewers
  agreeing): a surge goes back to the supply without passing through the shunt or into the BL0939's
  inputs. The shunt sits in the neutral strip east of the MOV for that.

### 3.3 Power: the LNK306 buck (decided 4 Nov 2026)

- **F2 (T500 mA, 5×20 ceramic) → R1 (10 Ω 2 W fusible, flameproof) → D7 (half-wave) → a π filter
  (2 × 4.7 µF 400 V and 1 mH) → Power Integrations' LNK306 high-side buck**, from its datasheet's
  Figure 5 with the neutral-leg diode left out so the return is neutral: 12.4 V out (13 kΩ / 2 kΩ
  feedback), a 680 µH output inductor (≥ 0.5 mH for MDCM; 1 A saturation, above the LNK306's
  0.65 A limit), a US1M freewheel diode and a 3.3 kΩ pre-load.
- **TI's TPS563201 makes 5 V** (datasheet 8.2), then the existing 5 V rail: a diode-OR with USB
  (SS34 × 2), a 1.1 A polyfuse and an SMAJ5.0A TVS, and the AP2112K for 3.3 V.
- **The supply's high-voltage nets are routed by hand** (`supply_tracks`), at the spacing matrix's
  distances. The smoothed bus (VBULK1, VBULK) sits at the rectified peak, 354 V DC above neutral, so
  it keeps **3.55 mm** from GND and **4.35 mm** from the live (the rms of that plus the live's AC,
  433 V; IEC 60664-1 Table F.4). The switching node and what rides on it (SW, BP, FB, FBH) keep
  **1.0 mm** from the supply's own input, its bus and GND only: functional insulation inside the
  converter, where a short trips its current limit or kills the LNK306, which F2 and R1 contain
  (IPC-2221 B4 gives 0.8 mm). To the live, the load and the divider it keeps the full 4.35 mm.
  (Both corrected at gate 1: the bus had been treated as 250 V, and the 1.0 mm had applied to
  every group.)
- **Buy safety-critical parts only from authorised distributors**: the fuses and holders, the
  relay, the MOV, the fusible resistor and the mains terminals. Never marketplace traders, because
  of counterfeits. That is why they are hand-fit (§3.6).

### 3.4 Mains polarity

UK BS 1363 plugs are polarised, so a single-pole relay and fuse in the live are enough. A miswired
socket or extension could still swap live and neutral: then F1 sits in the neutral (the plug's
fuse still protects the cord), the relay switches the neutral so the load stays live when "off",
and GND, J3 and everything on the board sit at 230 V to earth. A lost neutral upstream floats the
whole board to live through the load. The board is treated as live whenever it is plugged in
either way, and the output is labelled and treated as **live whenever the unit is plugged in**,
even with the relay open.

The board can't detect either: with GND at neutral it only sees the live-to-neutral difference.
Detecting reversal needs an earth reference on the PCB (a high-value resistor chain to earth, as
a socket tester does), which would undo "earth never touches the PCB". Considered at gate 1 and
**not fitted** (5 Nov 2026): the defences are a socket tester before every first use of a socket
or extension (Gate 3), the closed case, nothing conductive leaving it, and USB only with mains
unplugged. An RCD protects against a fault to earth, not against reversal.

### 3.5 J3: I/O for parts inside the case (decided 5 Nov 2026)

J3 is a 10-way 3.5 mm terminal for sensors and outputs added **inside** the case: 3.3 V, GND, SPI
(SCLK, MOSI, MISO, CS on GPIO18–21), I²C on the C6's LP_I2C pins (GPIO6/7, 4k7 pull-ups), IN on an
LP GPIO (GPIO3, 100 kΩ pull-down, so the low-power core can wake on it) and OUT (GPIO23). It is
wired straight to the ESP32 and is **at mains potential**: whatever is wired to it must sit
entirely inside the closed case, and a sensor that has to see out (a PIR, a light sensor) looks
through an insulating window. The 3.3 V rail is the AP2112K's: rated 600 mA, but heat limits it
first (5 V to 3.3 V in a SOT-23-5 at about 250 °C/W, so 1.7 V × the current). Keep J3's load to
**about 50 mA**: with the C6's average draw that is about 0.26 W, where 150 mA would be 0.4 W, a
100 °C rise (raised at gate 1). A sensor that needs more brings its own regulator from J3's 3.3 V.

An isolated J3 (an ISOW7743 for its 3.3 V, an ISO7741 for SPI and an ISO1640 for I²C, behind an
8 mm barrier) was built and routed, then dropped the same day for about £75 on five boards; it is
tag `rev-b-isolated-io`.

### 3.6 Assembly and cost (decided 4–5 Nov 2026)

- **JLCPCB Economic assembly.** Standard assembly charges a fee for every unique part and a higher
  setup fee. Economic can't place the S3-MINI (its LGA needs X-ray), hence the
  **ESP32-C6-WROOM-1-N8**, and the WS2812B-2020 became the **SK6812-EC20**. The C6 is single-core
  RISC-V at 160 MHz with Wi-Fi 6, and the same OTA and NVS model as the S3.
- **1 oz copper**, which saved about £27 on five. The mains pours are 3.5 mm wide or more on each
  layer (IPC-2221 for 8 A a layer, 16 A for the pair).
- **Basic parts where they fit**, and the mains parts **hand-fit**: J1, J2, F1's clips, F2's
  holder, K1, RV1 and R1 are left off the fab's BOM and CPL (`pcb/out/petro/hand-fit.csv`),
  bought from authorised distributors and soldered by Martin.

### 3.7 Light sealing

The case is opaque. The light pipe runs through an opaque boss whose flange sits around the LED on
the board, and it may be glued down with opaque glue or enamel paint. The board keeps a **2 mm
clear ring around the LED**: no parts in it, and nothing proud of the soldermask. The board
generator enforces this as a keep-out and exports the LED's position for the case.

## 4. Parts

From the generated netlist (`docs/petro-netlist.md`, which lists every part); stock and prices are
JLCPCB/LCSC's on 4–5 Nov 2026. The rev A research, with the datasheet figures and their sources,
is in `docs/design/parts-research/`.

### Mains (hand-fit)

| Ref | Part | Maker | LCSC | Key rating | Notes |
|---|---|---|---|---|---|
| K1 | HF115F-I/005-1HS3A | Hongfa | C2976795 | 16 A 250 VAC; 5 V coil, 80 mA | **Not** the plain HF115F/005-1HS3 (C81373), VDE-rated only 10 A at 70 °C |
| F1 | 0505015.MXP (15 A, 6.3×32 mm ceramic, sand-filled) | Littelfuse | C3165450 | **50 kA** breaking at 500 VAC | §5.1 |
| XF1, XF2 | 01220088Z (F1's clips, 122 series) | Littelfuse | C206903 | 30 A | Clip centres 26.59 mm apart |
| F2 | 0215.500MXP (T500mA 5×20 ceramic) | Littelfuse | C142839 | 1.5 kA breaking | Feeds the supply. Not a TR5 (35 A breaking only) |
| XF3 | 65600001009 (F2's holder, 656 series) | Littelfuse | C187510 | 10 A, 250 V, UL94 V-0 | |
| RV1 | TMOV20RP275E | Littelfuse | C187710 | 275 VAC, thermally protected | L_F to N_IN (ahead of the shunt) |
| R1 | FKN2WSJT-52-10R (10 Ω 2 W fusible) | Yageo | C1394194 | Flameproof | Inrush limit and fault fuse |
| J1, J2 | DG636-7.62-02P | Degson | C2827897 | 32 A, 630 V | Wire entry at their own ends |

### Mains (assembled)

| Ref | Part | LCSC | Notes |
|---|---|---|---|
| RS1 | WSK25121L000FEA (1 mΩ, 4-terminal 2512) | C4248455 | 0.1 W at 10 A |
| R12–R16, R17 | 5 × 390 kΩ 1206, 470 Ω 0402 | C17933, C25117 | The divider |
| R29 | 0 Ω 1206 | C17888 | The GND–neutral bond: the star point |
| U4 | LNK306DN | C34318 | |
| D7, D9 | M7 (1 kV) | C95872 | Rectifier; feedback sampling |
| D8 | US1M (75 ns) | C412437 | Freewheel |
| C1, C2 | 4.7 µF 400 V | C112482 | π filter |
| L1, L2 | 1 mH 350 mA; 680 µH 1 A | C168102, C48934988 | |

### Low voltage (also at mains potential)

| Ref | Part | LCSC | Notes |
|---|---|---|---|
| U1 | ESP32-C6-WROOM-1-N8 | C5366877 | Economic-capable |
| U2 | AP2112K-3.3TRG1 | C51118 | 600 mA |
| U3 | BL0939 (SOP-16) | C2836697 | §5.2 |
| U5 | TPS563201 | C116592 | 12 V → 5 V |
| D5, D6 | SS34 | C8678 | Diode-OR of the supply and USB VBUS |
| F3, D4 | 1.1 A polyfuse, SMAJ5.0A | C126818, C2925443 | On the supply's 5 V |
| J4 | House USB connector (SM05B-SRSS-G-TB) | C265419 | With F4 (500 mA polyfuse), D2 (SMF5.0A) and U6 (SRV05-4) on D± |
| J3 | DB125-3.5-10P-GN-S | C5184956 | §3.5 |
| SW1 | TS-1002 6×6 tactile, 7 mm | C455095 | On the GPIO9 boot strap |
| D1 | SK6812-EC20 | C2909058 | WS2812 protocol; the GPIO8 strap pulled up |
| Q1, D3 | AO3400A, 1N4148W | C20917, C81598 | Relay driver and flyback |
| TH1 | 10 kΩ 0603 NTC | C2892547 | Beside the relay; under-reads the terminal temperature, so calibrate at Gate 4 |

### Enclosure

**Martin's own printed case** (decided 4 Nov 2026, PETRO-6), designed around the board. It must be
printed in a **UL94 V-0 flame-retardant filament** (FR-ABS, FR-PC/ABS or FR-PETG; never plain PLA
or PETG), checked against what the CR6-SE can print. The board sets the case: 120 × 80 mm with 4 mm rounded corners, M3
holes near the corners (unplated), the C6's antenna overhanging the bottom edge (the case leaves it
clear space), and the heights and openings in `pcb/out/petro/case-interface.json`. With the board
live, the case is the safety barrier: no opening a finger or a wire can reach a part through, and
the button cap and light pipe insulating. Glands: HellermannTyton NGM16-BLK (5–10 mm), V-2 only;
no V-0 black nylon gland was found.

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
- **As built (Martin's decision, 5 Nov 2026): F1 and F2 are bridged** with solid copper links
  (≥ 1.5 mm², clamped), not fuses. Short circuits fall to the plug's 13 A BS 1362 (a breaking
  capacity of its own; Fable at Gate 1 judged F1 to add little on top of it), and a fault in the
  supply to R1, the fusible resistor, alone. The board is unchanged, so the fuses can go back in
  at any time (`docs/testing/README.md` rule 9).

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

- R1 and the bulk capacitors' inrush against F2's melting I²t (0.42 A²s): check it on the bench at
  first power-up (Gate 3). If F2 nuisance-blows, move to T1A.
- The LNK306's output and the 5 V converter under the full load (Wi-Fi transmit and the relay coil
  together): check at Gate 3 before the load test.
- The glands are V-2 only. Accept that (they're not current-carrying), or find V-0 glands.
- **Nothing bleeds the DC bus** (C1, C2): the 3.3 kΩ pre-load is on the 12 V output, so once the
  LNK306 stops switching after unplugging, what's left on the bus stays. The gate procedures
  measure it before touching, and discharge it with a tool (`docs/testing/README.md` rule 6).
  For a rev C: a bleeder across the bus (for example 2 × 1 MΩ 1206 in series, about 60 mW at
  354 V; τ ≈ 19 s).
