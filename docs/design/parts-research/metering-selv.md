# Petro: metering and SELV-side parts (2 Nov 2026)

Prices are USD, LCSC list, quantity-1 or lowest break, read from LCSC's and JLCPCB's public product APIs on 2 Nov 2026. Stock moves daily: re-check at basket time. "Verified" means read in a datasheet I downloaded (file names in `dl/` beside this note). "Unverified" means I could not confirm it.

## Parts table

| Ref / role | MPN | Manufacturer | LCSC # | Stock & unit price | UK distributor | Key rating verified | Notes |
|---|---|---|---|---|---|---|---|
| U_MTR metering IC | BL0942 (SSOP-10) | Shanghai Belling | C2837510 | **0 in stock** (LCSC and JLCPCB), $0.47 @1, $0.39 @50, reel 3000 | None found (unverified) | VDD 3.0 to 3.6 V, Iop 3 mA typ; UART 4800 to 38400; IP/IN +/-42 mV pk, VP +/-100 mV pk | **Stock risk, see item 1.** TSSOP-14 twin C2909509 also 0. BL0939 (C2836697, SOP-16, 2684 in stock, $0.945) is the fallback |
| U_ISO reinforced isolator | ISO7721DWR | Texas Instruments | C524805 | 3386, $1.31 @1, $1.09 @10 | Mouser, Farnell/Newark, Digi-Key list it (aggregator snapshot, unverified live) | DW-16: CLR/CPG 8 mm, V_IORM 2121 Vpk, V_IOTM 8000 Vpk, V_IMP 8000 Vpk, 5000 Vrms UL; 1 fwd + 1 rev; default output high; VCC 2.25 to 5.5 V | **Do not use ISO7721B variants (basic only).** Active, no F suffix = default high |
| U_ISO fallback 1 | CA-IS3721HW | Chipanalog | C5337993 (also C428885, 44 in stock) | 1363, $1.11 @1, $0.88 @10 | None found | SOIC16-WB: CLR/CPG 8 mm, V_IORM 1414 Vpk, V_IOTM 7070 Vpk, V_IOSM 6250 Vpk; 1 fwd + 1 rev; H = default high; 2.5 to 5.5 V | Datasheet (rev B/C, 2019) lists VDE as "pending" and states no V_IMP: certification unverified. Pin-for-pin check against ISO7721 needed |
| U_ISO fallback 2 | ISO7721DWVR (DWV-8) | Texas Instruments | C2864013 | 24 only, $1.74 | as ISO7721DWR | CLR/CPG 8.5 mm, V_IORM 2121, V_IOTM 7071, V_IMP 8000 | Same silicon, 8-pin wide package; tiny stock, so a second-source footprint rather than a first choice |
| U_LDO_M mains-side 3.3 V | AP2112K-3.3TRG1 | Diodes Inc | C51118 | 2825, $0.18 @5, $0.13 @150 | Farnell, RS, Mouser (unverified live) | 600 mA min, dropout 250 mV typ / 400 mV max @600 mA, Iq 55 uA, VIN 2.5 to 6.0 V, abs max 6.5 V | Already in heatlink parts.py; confirmed fine |
| U_LDO_S SELV 3.3 V | AP2112K-3.3TRG1 | Diodes Inc | C51118 | as above | as above | as above | Adequate for the ESP32-S3-MINI-1, see item 9 |
| U_PSU_M mains-side PSU | IRM-01-5 | Mean Well | C5656515 | 50, $3.45 | **RS 135-9124 (214 in stock, GBP 5.38 ex VAT @1)**, Farnell 2815475, Digi-Key UK | 5 V, 200 mA, 1 W, 85 to 305 VAC | LCSC stock thin: buy from RS/Farnell. SMD variant IRM-01-5S C5772336 has 0 stock |
| U_PSU SELV PSU | IRM-05-5 | Mean Well | C48603696 | 3267, $4.94 | RS/Farnell (unverified live) | 5 V, 1 A, 5 W, 85 to 305 VAC | See Risks: CLAUDE.md names IRM-03-5 (C6969425, 0 stock) and IRM-02-5; your brief names IRM-05-5 |
| D_OR1, D_OR2 5 V diode-OR | SS34 | MDD | C8678 | 2.4 M, $0.035 | Any Schottky, e.g. onsemi/Vishay SS34 via Farnell | 40 V, 3 A, Vf 0.55 V @3 A (LCSC attributes) | Lower Vf and thermal margin than SS14 at the same cost. SS14 C2480 ($0.019) also fine |
| F_5V rail polyfuse | 1206L110THYR | Littelfuse | C126818 | 20560, $0.060 | Farnell, RS, Mouser | Hold 1.1 A, trip 2.2 A, 8 V max, 40 mOhm (LCSC attributes) | Hold chosen above 450 mA with hot-enclosure derating headroom |
| D_TVS_5V | SMAJ5.0A | MDD (or Littelfuse C83329) | C113952 (Littelfuse C83329, 5422 in stock, $0.115) | 475383, $0.041 | Littelfuse part at Farnell/RS | 5 V stand-off, Vc 9.2 V @43.5 A, 400 W 10/1000 us (LCSC attributes) | Place after the polyfuse |
| SW1 button, THT | TS-1002-07026 (7.0 mm) | XUNPU | C455095 | 20920, $0.049 | n/a (SELV, not safety-critical) | 6x6 mm THT, 7 mm tall, 2.6 N, 50 mA 12 V | Height codes below |
| SW1 alternates | TS-1002-04326 / -05526 / -08526 / -10026 | XUNPU | C455089 / C455092 / C455098 / C455101 | 19790 / 950 / 2530 / 2450 | n/a | 4.3 / 5.5 / 8.5 / 10 mm tall | All 6x6 THT, 2.6 N |
| SW1 SMD option | TS-1005A-AR07026 | XUNPU | C2856781 | 425, $0.107 | n/a | 7 mm tall, SMD | Listed as "Surface Mount, Right Angle": check footprint before use |
| D_LED status | WS2812B-2020-V6 | Worldsemi | C52917434 | 662940, $0.092 @5 | n/a | VDD 3.3 to 5.3 V (LCSC attributes), 800 kbit/s | Already in heatlink; run from 3V3 as heatlink does |
| NTC1 | KNTC0603/10KF3950 | KUU | C2892547 | 63400, $0.030 | n/a | 10 kOhm @25 C, B25/50 = 3987 K, 0603, 100 mW, -40 to +125 C | B-constant is 3987 K not 3950 K: use the maker's R-T table |
| R_NTC fixed | 0402WGF1002TCE 10 kOhm 1% | UNI-ROYAL | C25744 | LCSC 0 (JLCPCB basic stock 16.2 M) | n/a | 1%, 62.5 mW | Already in heatlink |
| C_LED decoupling | CL05B104KO5NNNC 100 nF | Samsung | C1525 | 20.2 M, $0.003 | n/a | 16 V X7R | Already in heatlink |
| USB connector | SM05B-SRSS-G-TB(LF)(SN) | JST | C265419 | 2920, $0.56 | Farnell, Mouser | House 5-pin SH | Reuse from heatlink |
| USB ESD | USBLC6-2SC6 | ST | C7519 | 40685, $0.18 | Farnell, Mouser, RS | | Reuse |
| USB polyfuse | 1206L050YR | Littelfuse | C163512 | 11320, $0.074 | Farnell, RS | 500 mA hold, 6 V | Reuse. 450 mA peak is close to the 500 mA hold, see Risks |
| USB TVS | SMF5.0A | Littelfuse | C151296 | 10855, $0.19 | Farnell, Mouser | 5 V, 9.2 V Vc | Reuse |
| MCU | ESP32-S3-MINI-1-N8 | Espressif | C2913206 | 1228, $4.79 | Mouser, Digi-Key, Farnell | VDD33 3.0 to 3.6 V, IVDD min 0.5 A | Reuse |
| BOOT button | TS-1187A-B-A-B | XKB | C318884 | 1.06 M, $0.021 | n/a | 5.1x5.1 SMD | Reuse |
| Pass-through | 1N4148W C81598, AO3400A C20917, 5k1 C25905, 4k7 C25900, 100k C25741, 100R C25076, 330R C25104, 1uF C52923, 10uF C19702 | various | as listed | all in stock (millions) | n/a | | Reuse from heatlink `parts.py` |

## 1. BL0942

- LCSC **C2837510**, SSOP-10-150mil, BL (Shanghai Belling), $0.4745 @5, $0.3902 @50, $0.3555 @150 (reel 3000). **Stock is 0 on both LCSC and JLCPCB** (JLCPCB shows a BL0942 SOP-8 C56267182 and TSSOP-14 C2909509, also 0). A web snapshot quoted 8,500 to 13,700 in stock; that is stale.
- Supply: VDD 3.0 to 3.6 V (3.3 V nominal), Iop 3 mA typical at 3.3 V; reset below 2.7 V (V1.05 datasheet, section 1.7.1 and features list, `bl0942b.pdf`, p.4 and p.11). Absolute max VDD 4 V.
- Pins, SSOP-10 (datasheet V1.05 p.7; V1.06 English p.6): 1 VDD, 2 IP, 3 IN, 4 VP, 5 GND, 6 CF1, 7 SEL, 8 SCLK_BPS, 9 RX/SDI, 10 TX/SDO.
- **ZX and CF.** The SSOP-10 has **no ZX pin and no CF2**; only **CF1** (pin 6). ZX and CF2 exist only on the TSSOP-14 (pins 9 and 8). However OT_FUNX (register 0x18) lets CF1 output ZX_V (b10) or ZX_I (b11), or CF energy pulses (b00, default) or over-current (b01) (V1.06 English p.~11). So zero-crossing is available on the SSOP-10 via CF1, but it would then cost you the CF pulse output. Either way these pins are on the mains island: to use one in the ESP32 it needs its own isolator channel. Over UART the zero-cross state is readable as STATUS bits I_ZX_LTH_F / V_ZX_LTH_F, which needs no extra pin. Zero-crossing output delay 570 us typical.
- **UART.** SEL: 0 = UART, 1 = SPI, internal 56.9 kOhm pull-down, so floating or tied to GND is UART; no strap needed, but tie it to GND explicitly for noise immunity. **SCLK_BPS** sets the baud rate at power-up (MODE[9:8] resets to 00): pin = 0 gives 4800 bps, pin = 1 gives 9600 bps; so **tie SCLK_BPS to GND for 4800**. Format 8N1, half-duplex, slave. **RX and TX both need external pull-ups** in UART mode (pins 9 and 10, datasheet pin table); use about 4.7 to 10 kOhm to the mains-side 3.3 V. Frame timeout: bytes more than 20 ms apart reset the interface; 32 consecutive zeros reset it.
- **Front end.** The datasheet I could obtain (V1.05 and V1.06 English) gives **no typical application circuit and no anti-alias RC values** (unverified). What it does give: current input max +/-42 mV pk (30 mV rms) at the default 16x gain, voltage input max +/-100 mV pk (70 mV rms), input impedance 370 kOhm, analogue bandwidth 3.5 kHz (-3 dB), 10 mA to 30 A range with a 1 mOhm shunt. Tuya's support note quotes the Belling reference schematic for sockets as a **390 kOhm x 5 : 0.51 kOhm** voltage divider with a 1 mOhm shunt (via search summary; the page itself would not load, treat as second-hand). An open-source Rust driver comments use R1 = 1 kOhm with R2 = 6 x 390 kOhm. Divider check: 1.95 MOhm : 510 Ohm gives 85 mV pk at 230 V rms and 93 mV pk at 253 V, inside the 100 mV limit (my calculation). **RC values are my proposal, not from a datasheet**: about 1 kOhm in series with each of IP and IN with ~33 nF across them (corner ~2.4 kHz), and a matching time constant on the voltage channel so the current-to-voltage phase error stays small; tune on the bench against a reference meter. The ESPHome BL0942 component (https://esphome.io/components/sensor/bl0942/) uses 4800 baud, 1 stop bit, and default references `current_reference` 251065.6814 and `voltage_reference` 15883.34116, which belong to a specific commercial board; Petro will need its own calibration (their formula: new_reference = reported x default / actual).
- Temperature: **the BL0942 has no on-chip temperature reading** (I searched the V1.06 English datasheet; only operating range -40 to +85 C appears). BL0940 reportedly does but is not stocked (C691894, 0), unverified.
- Fallback **BL0939** (C2836697 SOP-16, 2684 in stock, $0.945; C2841044 SSOP-20, 6789): dual current channel, UART, ESPHome has `bl0939` (4800 baud, 2 stop bits per its docs). Its datasheet and pinout were not retrievable here, so the footprint and front end are unverified. If BL0942 stays at zero, decide before the layout is committed.

## 2. Reinforced digital isolator

Recommended: **TI ISO7721DWR, C524805** (16-SOIC wide, 10.3 x 7.5 mm), $1.31 @1, 3386 in stock.
Verified in SLLSEP3G (May 2024), `iso7721.pdf`, section 6.6:
- CLR 8 mm and CPG 8 mm for DW; CTI > 600 V, material group I.
- DIN EN IEC 60747-17 (VDE 0884-17): V_IORM 2121 Vpk, V_IOTM 8000 Vpk (60 s qualification, 1.2x for 1 s production), V_IMP 8000 Vpk (IEC 62368-1), V_IOSM 12800 Vpk. All comfortably above 565 Vpk and 6 kV.
- The datasheet says the family includes devices with reinforced ratings, and **"ISO7721B is designed for applications that require basic insulation ratings only"** (V_IORM 1414, V_IMP 6000). So **ISO7721BDW(R) (C5216476, $4.06) must not be used** even though it is wide-body. The plain ISO7721DW is the reinforced one.
- Channels: ISO7721 has one forward and one reverse. DW pinout: INB pin 5 to OUTB pin 12 (side 1 to side 2); INA pin 13 to OUTA pin 4 (side 2 to side 1). VCC1 pin 3 / GND1 pins 1, 7; VCC2 pin 14 / GND2 pins 9, 16. Side 1 = SELV (ESP32), side 2 = mains island (BL0942). Then ESP32 TX goes to INB (pin 5), OUTB (pin 12) goes to BL0942 RX; BL0942 TX goes to INA (pin 13), OUTA (pin 4) goes to ESP32 RX.
- **Default output: high** for the part without the F suffix, "in the event of input power or signal loss"; this matches UART idle. (LCSC attribute "Default Output: High Level".) Do not buy the FDWR (C2865882; default low).
- Supply 2.25 to 5.5 V each side, so 3.3 V on both is fine. Typical supply current about 1 to 3 mA per side at 4800 baud.
- The package's 8 mm is the minimum: cut a slot or keep the board surface bare between pins 8/9 across the gap, and do not route anything under the body between sides.
- UK stock: Mouser, Farnell/Newark and Digi-Key listings exist (aggregator snapshots: Mouser ~3,700, Newark 2,000, Digi-Key conflicting). Check live before relying on it.

Fallbacks:
1. **Chipanalog CA-IS3721HW, C5337993** (1363 in stock, $1.11): same footprint class, 1 fwd + 1 rev, H suffix default high, CLR/CPG 8 mm, V_IORM 1414 Vpk, V_IOTM 7070 Vpk, V_IOSM 6250 Vpk (`ca.pdf`, section 7.6). But the datasheet's certification table says VDE (and others) "pending" (rev B, 2019) and it states no V_IMP, so **reinforced certification is unverified**; look for a current VDE certificate before using.
2. **NOVOSENSE NSi8121W1-DSWR** is a 5 kV, 1+1, default-high wide SOIC-16 (order table, `nsi812.pdf`) but is **not on LCSC/JLCPCB**, and its datasheet (Rev 1.9) gives VDE **basic** insulation at 849 Vpk, with reinforced only under the CQC column at 565 Vpk ("file pending"). Reject. The stocked sibling NSi8221W1-DSWR (C2987925, 968 in stock, ~$1.34) is a different datasheet which I could not read: unverified.
3. Silicon Labs Si8621ED/BD: not in LCSC stock (JLCPCB: 0), RS UK lists the BD, one RS page says the ED may be discontinued. Not pursued.
4. TI ISO6721: LCSC stocks only the 8-pin narrow D package (4 mm) so it is useless here; wide-body ISO6721 availability unverified. ADuM1281/1201: only narrow SOIC-8 on LCSC, so not 8 mm.

## 3. Mains-side 3.3 V LDO

AP2112K-3.3TRG1 (C51118) confirmed. Datasheet (Diodes, `ap2112.pdf`): 600 mA minimum output, dropout 250 mV typ / 400 mV max at 600 mA, Iq 55 uA typ (80 max), line range 2.5 to 6.0 V operating (6.5 V abs max), +/-1.5% accuracy, foldback short-circuit 50 mA, SOT-25 theta-JA 184 C/W. The mains island draws: BL0942 3 mA + ISO7721 side 2 about 3 mA + pull-ups, well under 15 mA, so the IRM-01-5's 200 mA is generous. It will output about 3.3 V from a 5 V input with the full 1.7 V headroom burning 25 mW: no thermal concern. Alternative in principle: a lower-Iq 3.3 V part, but nothing needed.

## 4. Diode-OR of USB VBUS and the 5 V module

Recommendation: **two Schottky diodes, SS34 (C8678)**, one from the PSU branch (after its polyfuse/TVS) and one from the USB branch (after the existing PTC), with outputs joined as the "5V" rail.
- Headroom: IRM 5 V minus roughly 0.4 V (Vf is 0.55 V at 3 A per LCSC; at 0.45 A it is lower, curve not checked) gives about 4.6 V. USB 4.75 V worst case minus PTC and diode drops gives about 4.2 V. AP2112K-3.3 needs 3.3 + 0.4 V = 3.7 V worst-case input at 600 mA (verified dropout), so the margin is more than 0.5 V in the worst case. The 5 V relay coil (HF46F/5-HS1, 40 mA) sees about 4.2 to 4.6 V; check the coil pull-in voltage in the Hongfa datasheet (unverified) before accepting it.
- Cost: pennies, SMA package. The diodes also stop the IRM back-feeding the host or USB charger, which a plain wire-OR would not.
- Ideal-diode ICs considered. **TPS2116DRLR (C3235557, $0.39)**: 1.6 to 5.5 V, 2.5 A, Rds(on) about 40 mOhm, Iq 1.32 uA, priority mode would prefer the PSU and fall back to USB (verified in `tps2116.pdf`). **LM66100DCKR (C2869734, $0.21)**: 1.5 to 5.5 V, 1.5 A, 95 mOhm. Both save ~0.4 V but add a control pin network, a 5.5 V input ceiling (the IRM output can ring above that during a TVS-clamped event), and failure modes the Schottky pair does not have. Not worth it at 450 mA.
- BAT54C: confirmed too small (200 mA class).
- B5819W (C64885, 1 A, 600 mV @1 A, SOD-123) would work for the SELV load but runs closer to its rating; SS34 is better.

## 5. Protection on the 5 V output

- **Polyfuse: Littelfuse 1206L110THYR, C126818**: hold 1.1 A, trip 2.2 A, 8 V max, 40 mOhm, 800 mW (LCSC attributes). Reason: 450 mA peak load, and the enclosure may sit at 60 C or more; polyfuse hold current derates substantially with temperature (the Littelfuse derating curve is not in my downloads, so the exact figure is unverified), so 0.75 A parts such as 1206L075THYR (C99563) or 1812L075PR (C142689, 13.2 V) risk nuisance trips. The IRM-05-5 has its own short-circuit protection; the polyfuse protects the board tracks and the diodes. Place it between the module and the diode.
- **TVS: SMAJ5.0A**, MDD C113952 ($0.041, 475k in stock) or genuine Littelfuse C83329 ($0.115): 5 V stand-off, 9.2 V clamp at 43.5 A, 400 W. Place it after the polyfuse and before the diode-OR. Caveat: 9.2 V is above the AP2112K's 6.5 V abs max, but only at high surge current; the stand-off is 5 V with 7 V minimum breakdown (LCSC attribute). The module output cannot source tens of amps, so this protects against a transient, not a module failure. The existing USB-side parts (500 mA 1206L050YR, SMF5.0A) stay on the USB branch.
- The IRM-01-5 on the mains island needs nothing extra beyond a 10 uF and 100 nF at the LDO: it is a closed 200 mA island.

## 6. Tactile button heights

The case lid presses the cap; pick the height from the lid-to-board stack. XUNPU **TS-1002** series, 6 x 6 mm THT, 2.6 N, 50 mA 12 V; the code is height in mm x 10 (4.3 and 5.5 mm confirmed from LCSC attributes, 7, 8.5 and 10 mm confirmed too):
- 4.3 mm C455089 (19790 in stock, $0.069)
- 5.5 mm C455092 (950)
- 6.5 mm C455094 (740, $0.055)
- **7.0 mm C455095 (20920, $0.049): suggested default, in stock**
- 8.5 mm C455098 (2530), 10 mm C455101 (2450), 12 mm C455105 (328)
SMD 6x6: TS-1005A-AR04526 to -AR07026 (C2856776 to C2856781, 4.5 to 7.0 mm; 340 to 480 in stock, $0.107). ALPS SKHHALA010 (C139755, 6x6x4.3, 1.6 N, 695 in stock) if a lighter feel is wanted. For a solid feel through a cap, THT is better; the pin holes sit on the SELV side so the 8 mm gap is not affected. For a button with a 1.5 mm stroke travel keep the cap clearance in mind; stroke is not in my LCSC attributes (unverified).

## 7. Status LED

WS2812B-2020-V6, C52917434, 662,940 in stock, $0.092 @5. LCSC lists supply 3.3 to 5.3 V, which is why heatlink runs it from 3V3 with DIN driven directly from a GPIO via 330 Ohm. Keep that. 2020 package is about 2.0 x 2.0 mm (LCSC: 2 mm square, 0.84 mm high); heatlink footprint 2.2 x 2.0.
- 2 mm clear ring means a keep-out of about 6.2 x 6.0 mm centred on the LED. Nothing taller than the mask inside it, so **no decoupling cap, no series resistor, no test points, no silk-screen heights** in the ring.
- The 100 nF (C1525) therefore goes either **outside the ring on the top side** (about 2 mm of VDD/GND stub each way, acceptable for a 3 mA to ~20 mA load at 800 kHz data, though not ideal) or, better, **on the bottom side directly under the LED**, with tented vias; this leaves the top flange area untouched. The 330 Ohm DIN resistor can sit outside the ring with a short trace into it.
- DOUT is unused. Leave it unconnected.
- Mask: the flange seats on solder mask; avoid vias in the ring unless tented and filled, and keep exposed copper out.

## 8. NTC thermistor

- Part: **KUU KNTC0603/10KF3950, C2892547**, 0603, 10 kOhm at 25 C, 1%, B25/50 3987 K (LCSC attributes), 63,400 in stock, $0.030. It is "B3950" by name; the quoted 3987 K means use the supplied R-T table, not the 3950 formula. Fixed divider resistor: 10 kOhm 1% 0402 (C25744, already in heatlink), to 3V3 with the NTC to GND (or vice versa) and a 100 nF filter at the ADC pin. Self-heating is negligible (about 0.5 mW at 25 C).
- Placement: it must stay on the SELV side, at least 8 mm from any mains copper (reinforced) or other mains-referenced part. It cannot touch the terminal or relay contact copper. Best placement: **on the SELV side of the relay body, on the board edge of the boundary near the relay coil pins** (the coil is SELV and the heat from the contacts flows through the relay body and its pins); also consider a dedicated spur of SELV copper pour (thermal pad) beside the relay and, if there is room, near the terminals within the 8 mm rule, with a thin slot to keep the creepage. The reading will lag and under-read the actual contact/terminal temperature; **calibrate in gate 4 with a thermocouple on the terminal at 10 A** and set the trip threshold from the measured relationship (target: trip well below ~70 C at the terminal).
- A second option I did not verify: heat-conductive potting or a silicone pad between the relay body and the NTC (plastic, not metal). Do not use a metal clip.
- The BL0942 has no temperature reading (see item 1), so this NTC is the only temperature input. The ESP32-S3's on-die sensor is only a case-ambient proxy.

## 9. SELV 3.3 V LDO

AP2112K-3.3 (C51118), 600 mA minimum. Espressif ESP32-S3-MINI-1 datasheet (`esp.pdf`): VDD33 3.0 to 3.6 V, **required supply current 0.5 A minimum** (table 6-2). Wi-Fi TX peaks (table 6-4): 802.11b 1 Mbps at 20.5 dBm **355 mA**; 802.11g 54 Mbps at 18 dBm 297 mA; 802.11n HT20 MCS7 286 mA; RX about 95 mA. Rated at 100% duty. Add the LED (about 5 to 20 mA at the brightness a light pipe needs), button and misc (under 10 mA) and the isolator side 1 (about 3 mA): the SELV 3.3 V rail peaks at about 400 mA. That is within the LDO's 600 mA minimum, and the LDO's guaranteed 600 mA also meets Espressif's 0.5 A supply requirement, so it is adequate (verdict: yes, with about 200 mA of headroom). Thermal: worst case (5 V to 3.3 V at 0.4 A) is 0.68 W, and with theta-JA 184 C/W for SOT-25 that is 125 C of rise if sustained at 100% TX, so give the part copper pour; real Wi-Fi duty is a few percent, average dissipation is more like 0.1 to 0.2 W. Use at least 10 uF at the output (C19702, 10 uF 0603 in stock) and 1 uF at the input. The 160 MHz clock in CLAUDE.md also lowers the draw.

## Risks / open questions

1. **BL0942 is out of stock at both LCSC and JLCPCB** for SSOP-10, TSSOP-14 and SOP-8. Check again before the layout is frozen; decide on BL0939 (in stock) or another source now. No UK authorised distributor found.
2. **No BL0942 reference front-end** in the datasheets I could download; RC values above are a proposal and Petro will need bench calibration (ESPHome reference constants are for someone else's board).
3. **SSOP-10 has no ZX pin**; a CF1 pin can be reconfigured for ZX_V or ZX_I, but not both with energy pulses. Use the STATUS register over UART instead if possible.
4. **ISO7721B (basic) trap**: always order ISO7721**DWR** (no B, no F). The CA-IS3721HW certification is unverified; the NSi8121W is basic under VDE.
5. **IRM naming conflict**: your brief says the BL0942 island is fed by IRM-01-5 and also mentions IRM-05-5 for the diode-OR; CLAUDE.md names IRM-03-5 or IRM-02-5. I treated IRM-05-5 as the SELV PSU. IRM-03-5 has 0 LCSC stock, IRM-01-5 has 50; buy modules from RS or Farnell. Confirm two modules are intended (a second module costs about GBP 5 and 25 x 45 mm of board).
6. **USB path load**: the heatlink USB polyfuse (500 mA hold) is close to the 450 mA peak; derating when warm could trip it on USB-only bench power. Consider the 750 mA 1206L075THYR on USB only if USB must carry the relay coil and Wi-Fi.
7. **Relay coil voltage** after the Schottky drop (about 4.2 to 4.6 V on a 5 V coil): check the HF46F coil pull-in figure in Hongfa's datasheet (not verified here).
8. **NTC under-reads** the terminal temperature, B constant is 3987 K not 3950 K, and its trip level needs empirical calibration.
9. **Stock figures** come from public LCSC and JLCPCB endpoints today; the 25744 10 kOhm resistor shows 0 at LCSC but 16 M at JLCPCB (basic part); check at order time.
10. LCSC `datasheet` files used: `/private/tmp/claude-501/-Users-nakomis-repos-nakomis-smart-switch/ba1ea166-061a-4a9e-a183-cf15f35875f1/scratchpad/parts/dl/` (`bl0942b.pdf`, `bl106.pdf`, `iso7721.pdf`, `ca.pdf`, `nsi812.pdf`, `tps2116.pdf`, `lm66100.pdf`, `ap2112.pdf`, `esp.pdf`).
