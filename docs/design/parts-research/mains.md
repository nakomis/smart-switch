# Petro: mains-side parts selection (2 Nov 2026)

Method: datasheets read from PDFs where I could obtain them (Hongfa HF115F, Omron G5RL, Littelfuse 372, Mean Well IRM-05/IRM-01, Belling BL0942 V1.06); LCSC stock and prices read from LCSC's product-detail API and the JLCPCB parts API on 2 Nov 2026 (USD, quantity-1 price; stock is a snapshot and moves daily). Anything I could not confirm from a primary document is marked **unverified**. UK distributor stock/prices were not retrievable (RS and Farnell return 403 to automated fetches), so UK part numbers come from search listings only.

## Parts table

| Ref / role | MPN | Manufacturer | LCSC # | LCSC stock & unit price (qty 1) | UK distributor & part no. | Key rating verified | Notes |
|---|---|---|---|---|---|---|---|
| K1 relay (recommended) | HF115F-I/005-1HS3A | Hongfa | C2976795 | 25; $2.80 (10+ $2.33) | Not found for the -I variant (unverified). Farnell/RS list other HF115F codes | 16 A 250 VAC at 85 C (VDE, AgSnO2, 1HS3A); coil 5 V / 62 ohm / 400 mW (80.6 mA); 5 kV coil-contact, 10 mm creepage, "VDE 0700/0631 reinforced insulation"; 120 A / 20 ms inrush rating (-I) | Preferred: AgSnO2 and the inrush rating. Low LCSC stock; PCBWay can buy elsewhere |
| K1 relay (equivalent) | HF115F/005-1HS3A | Hongfa | C2976778 | **0**; $2.80 | unverified | As above, without the -I inrush rating | Same footprint. Out of stock at LCSC today, so use if restocked |
| K1 relay (fallback) | G5RL-1A-E-HR 5VDC | Omron | not stocked (LCSC has the -TV8: C1562978, stock 1, $7.65) | n/a | Farnell 2213809 (jp/nz/au listings; UK page not fetched), RS 6839239P / 0419277P | 16 A 250 VAC cos phi 1 at 85 C (VDE); coil 80 mA / 62.5 ohm / ~400 mW; 6 kVAC 1 min; 10 kV impulse; clearance 8 mm, creepage 8 mm; coil-contact "Reinforced" (VDE licence 40007172) | Exactly 8 mm, no margin. Near-identical footprint to the HF115F |
| F1 main fuse | 0215010.MXP | Littelfuse | C142733 | 11,143; $0.19 | Farnell 2840075 | 5x20 ceramic, T10A (time-lag), 250 V, breaking capacity 1.5 kA @ 250 V (LCSC attribute; datasheet not fetched), melting I2t 333.6 A2s (LCSC) | Time-lag recommended (see section 2) |
| F1 holder | 65600001009 (656 series) | Littelfuse | C187510 | 55; $0.78 | Farnell 1597013; RS 787-4300 (7874300) | 10 A / 250 V (IEC 60127-6, UL 512, VDE/SEV/SEMKO); dielectric > 3 kV; 12 kV impulse; UL 94 V-0; contact resistance 5 mohm; -40 to +85 C | Open (uncovered) holder; add cover 659/660 if the case allows |
| F1 fast alternative | 0216010.MXP | Littelfuse | C142735 | 6,471; $0.17 | unverified | 5x20 ceramic F10A, 250 V, 1.5 kA | Not recommended, see section 2 |
| RV1 MOV (recommended) | TMOV14RP275E | Littelfuse | C1528070 | **3**; $1.69 | Farnell 1817007 (FR listing) | 275 Vrms / 350 Vdc / 430 V varistor / 110 J / 6 kA / 710 V clamp (LCSC and Digi-Key listings); thermally protected; -55 to +85 C | LCSC stock very low; P=7.5 mm |
| RV1 MOV (alt, in stock) | TMOV20RP275E | Littelfuse | C187710 | 440; $2.08 | unverified | 275 Vrms / 430 V / 190 J / 10 kA / 710 V | 20 mm disc, larger footprint |
| RV1 MOV (non-thermal) | 14D431K | Ruilon | C233160 | 2,409; $0.14 | n/a (use Littelfuse V14E275P / Epcos S14K275 for UK sourcing) | 275 Vac / 350 Vdc / 387-473 V / 4.5 kA / 77.4 J (LCSC) | Cheap fallback; no thermal disconnect |
| F2 PSU fuse (recommended) | 0215.500MXP | Littelfuse | C142839 | 2,052; $0.27 | unverified (Farnell stocks the 0215 family) | 5x20 ceramic T500mA, 250 V, 1.5 kA breaking, melting I2t 0.42 A2s (LCSC) | Needs a second 656 holder (C187510). See section 4 |
| F2 alt (TR5) | 37205000001 (bulk) / 37205000411 | Littelfuse (Wickmann) | C142835 (stock 1,338, $0.26) / C178791 (stock 0) | see left | RS 1740502 (500 mA 250 V ac, listing) | Datasheet: T500mA, 250 V, **breaking capacity 35 A / 250 VAC**, I2t 1.3 A2s, drop 180 mV, cold resistance 125 mohm (table row 0500) | Low breaking capacity, see section 4 |
| PS1 main PSU | IRM-05-5 | Mean Well | not checked | n/a | n/a (Farnell/RS stock Mean Well) | 5 V / 1 A / 5 W; 85-305 Vac; cold-start inrush 40 A @ 230 V; 4.2 kVac I/P-O/P | CLAUDE.md names IRM-03-5/02-5; this brief says IRM-05-5. Confirm |
| PS2 metering PSU | IRM-01-5 | Mean Well | not checked | n/a | n/a | inrush 10 A @ 230 V; 18 mA typ @ 230 V; 4.2 kVac I/P-O/P | |
| R_SH shunt (recommended) | WSK25121L000FEA | Vishay | C4248455 | 3,998; $1.00 | Farnell 1107426 | 1 mohm +/-1 %, 1 W, TCR +/-250 ppm/C, **4-terminal** (E1/E2 sense, I1/I2 current), 2512 | True Kelvin part |
| R_SH shunt (low TCR, 2-terminal) | RLP25FEGR001 | TA-I | C459678 | 27,168; $0.09 | n/a | 1 mohm +/-1 %, 3 W, TCR +/-50 ppm/C (LCSC) | 2-terminal: make the Kelvin tap on the pad inner edges |
| R_SH alt | MA251220FR001MZ | Ever Ohms | C252657 | 2,238; $0.14 | n/a | 1 mohm +/-1 %, 2 W, +/-50 ppm/C (LCSC) | 2-terminal |
| J1..J4 terminals | DG636-7.62-02P-14-02A(H) (x2) | Degson | C2827897 | 933; $0.56 | Phoenix MKDS 5/2-7,62 (1868076), RS 871-7646 (8717646) | 32 A / 630 V, 10-26 AWG, M3 screw, 7.62 mm pitch (LCSC attributes; Phoenix equivalent 32 A / 630 V III/2 per RS listing) | One 2-way for L (in/out), one for N (in/out). Height 21.5 mm. Variant -00A is C581337 (37 in stock) |
| J alt (cheap) | KF128-7.5-2P | Cixi Kefa | C474954 | 1,780; $0.22 | n/a | "24 A / 450 V", 12-22 AWG, M2.5 (LCSC listing only, **unverified**) | Not recommended for mains |
| Q1 driver | AO3400A | AOS | C20917 | 418,675; $0.09 | n/a | Vds 30 V, Id 5.7 A, RDS(on) 48 mohm @ Vgs 2.5 V, Vth 1.45 V (LCSC) | Already in the heatlink catalogue |
| D1 flyback | 1N4148W | Semtech | C81598 | 2.26 M; $0.013 | n/a | 75 V, 150 mA continuous, 1 A surge | Fine; SS14 gives more margin |
| R_V1-5 divider top | RC1206FR-07390KL | Yageo | C137298 | 36,400; $0.009 | n/a | 390 kohm 1 %, 1206, 250 mW, **200 V** limiting voltage, 100 ppm/C | Five in series. Uniroyal 1206W4F3903T5E is C17933 (stock 714) |
| R_V6 divider bottom | 1206W4F5100T5E | Uniroyal | C17991 | 423,900; $0.004 | n/a | 510 ohm 1 % 1206 | |
| U_M metering IC | BL0942 (SSOP-10) | Belling | C2837510 | **0**; $0.47 | n/a | n/a | Out of stock at LCSC; separate sourcing issue |

---

## 1. Relay

**Recommendation: Hongfa HF115F-I/005-1HS3A (C2976795). Fallback: Omron G5RL-1A-E-HR 5VDC.**

Datasheet figures (Hongfa HF115F datasheet, 2018 Rev 1.00, p.1 "Features" and "Characteristics"; ordering info p.3; PCB layout p.4):
- Coil: 5 V nominal, 62 ohm +/-10 %, "Coil power approx. 400 mW" so 80.6 mA. Pick-up max 3.50 V, drop-out min 0.5 V, max 7.5 V.
- Contacts: "12 A/16 A 250 VAC (res. load)". Ordering code says version **3 = "5.0 mm 1 pole 16 A"**; contact material A = AgSnO2, nil = AgCdO.
- Insulation: "5 kV dielectric strength (between coil and contacts)", "Creepage distance: 10 mm", "Meeting VDE 0700, 0631 reinforce insulation". Characteristics table: coil-contacts 5000 VAC 1 min; surge (coil-contacts) 10 kV 1.2/50 us. A separate clearance figure is not given, only creepage.
- **VDE ratings table matters**: the plain `HF115F/005-1HS3` (AgCdO, LCSC C81373) is VDE-rated **10 A 250 VAC at 70 C** only. The `.1H(S)3A` AgSnO2 version is rated **16 A 250 VAC at 85 C**. So take the **A** suffix (or -I/...3A); do not buy C81373 for a 10 A continuous design. (C81373 is also cadmium oxide.)
- The `-I` series (datasheet C2976795, text partly garbled in the PDF but legible after decoding): same 5 kV / 10 mm / "reinforce insulation" claims, 16 A 250 VAC at 85 C, plus an inrush rating of 120 A for 20 ms. Good for lamp/capacitive loads.
- Footprint (p.4, "5 mm 1 pole 16 A", bottom view): 1.3 mm holes; dimensions 7.56, 2.6, 5.04 and **20.16 mm**. I read the 20.16 mm as the spacing between the coil-pin column and the contact-pin column, so the surface path coil pad to contact pad is about 20 mm, far more than 8 mm: **no slot is required between coil and contact pins** on the footprint itself. The 5.04 mm pitch is between contact pins of the same relay, i.e. across the open contact (functional insulation, 1 kV open-contact withstand); consider a slot there if you want more than ~3.5 mm edge-to-edge. The pin-by-pin mapping is not readable from the text extraction, so check the EasyEDA/LCSC footprint against the drawing before routing (**unverified**).
- Contact gap on LCSC listing: >= 0.75 mm.

Omron G5RL-1A-E-HR (datasheet en-g5rl.pdf): coil 5 VDC, rated current 80 mA, 62.5 ohm, ~400 mW; 70 % max operate, 10 % min release, max voltage 130 %; dielectric coil-contacts 6,000 VAC 1 min; impulse 10 kV; "Clearance: 8 mm, Creepage: 8 mm"; VDE (EN 61810-1, licence 40007172) table: Creepage/clearance 8 mm min, pollution degree 3, OVC III, "coil-contact circuit: Reinforced", rated insulation voltage 250 V; 16 A 250 VAC cos phi = 1 at 85 C (15,000 operations) and 240 VAC 100 A (0-P) / 10 A steady. Dimensions: 29 x 12.7 x 15.7, pin spacing 7.5 / **20** / 5 mm, six 1.3 mm holes. So the Omron is a near drop-in (Hongfa 7.56/20.16/5.04 versus 7.5/20/5): design the footprint with 1.4 mm drills so both fit (**check tolerances**; difference is up to 0.16 mm on the long span).

Why Hongfa first: 10 mm creepage versus Omron's exact 8 mm; cheaper ($2.80 against $7.65 for the TV8); both have reinforced coil-contact insulation in the VDE tables. Stock is the weakness: C2976778 is 0 and C2976795 is 25.

## 2. 10 A fuse and holder

**Recommendation: Littelfuse 0215010.MXP (T10A, 5x20 ceramic, 1.5 kA) in a Littelfuse 656 PCB holder 65600001009.**

- Time-lag (T) is right for a 10 A resistive load on a 13 A plug: the plug's BS 1362 fuse (13 A, or 3 A/5 A in some cord sets) protects the cable; this board fuse protects the board and relay. A T rating avoids nuisance blows on cold-filament lamp inrush and on the PSU/MOV transients, and a ceramic body with 1.5 kA breaking capacity (HBC) is right for a 230 V UK supply (prospective short-circuit current can reach well over a kA). Fast-acting adds nothing here since the relay and 2 oz tracks can survive a few seconds of overload; let the 13 A plug fuse and RCD do the first-line job. The LCSC listing gives melting I2t 333.6 A2s (T10A).
- Holder: Littelfuse 656 series (RS listing and Littelfuse datasheet mirror at pdf.jiepei.com): "10 A / 250 V", IEC 60127-6, UL 512, CSA; dielectric > 3 kV, impulse > 12 kV between live parts, contact resistance 5 mohm, UL 94 V-0, solder pins 0.4 x 1.1 mm, pitch variants 22.5 mm (A=22.5, LCSC lists P=22.5 mm) and 25 mm; operating -40 to +85 C "de-rating should be considered"; power acceptance 4 W (no cover).
- **Derating warning (important)**: a 10 A fuse running at 10 A continuous inside a closed case is outside normal practice (general fuse practice is to run at about 75 % of the nominal rating at 25 C; I have not extracted the 215-series rerating curve, so the exact figure is **unverified**). The holder is also only rated 10 A. At the 10 A gate-4 load test, expect warm fuse and holder and possibly slow nuisance fatigue. Options: (a) accept and measure at gate 4; (b) state the true continuous rating as about 8 A; (c) move to a 6.3 x 32 mm T12.5A/T15A with a 15 A holder if a real 10 A is needed (not researched). Raise with Martin.
- Soldered PCB fuses (SMD) top out at 125 V for the 10 A parts found on LCSC (Littelfuse 0154010.DR: 125 V), so they are not suitable.

## 3. MOV

**Recommendation: 275 V AC class, 430 V varistor voltage (the "431" / "275" series), thermally protected: Littelfuse TMOV14RP275E (C1528070).**

- UK mains is 230 V +10 % / -6 % (253 V max). 275 Vrms continuous gives about 8.7 % headroom above 253 V, and 430 V (387-473 V at 1 mA) is the standard pairing (14D431K / V14E275P / S14K275). 10D471K/300 V parts also work but clamp higher (775 V) and are only 2.5 kA; the 14 mm 275 V disc gives 6 kA and 110 J.
- TMOV14RP275E (LCSC / Digi-Key listings): max AC 275 V, DC 350 V, varistor 430 V (387/473 V tolerance), clamping 710 V, 6 kA, 110 J, 450 pF, -55 to +85 C. Littelfuse's text: the integrated thermal element opens if the device overheats on abnormal overvoltage or limited current. It is placed after the 10 A fuse (as you have it), which also supplies the fault-current limiting a MOV needs. I could not retrieve the primary datasheet text about series-fuse requirements: **unverified**.
- LCSC stock for the TMOV14 is only 3. The 20 mm TMOV20RP275E (C187710, 440 in stock) is the in-stock thermal alternative (190 J / 10 kA, bigger footprint). Non-thermal fallback 14D431K (C233160).
- Note that the clamp voltage (710 V) is below the 8 mm creepage design's impulse expectation for OVC II (2.5 kV) but the downstream relay (10 kV impulse) and PSU modules (1 kV L-N surge withstand) are fine.

## 4. T500mA PSU-branch fuse

**Recommendation: Littelfuse 0215.500MXP (5x20 ceramic T500mA, 1.5 kA breaking, C142839) in a second 656 holder. Fallback: TR5 37205000001/0411/0431.**

- The Littelfuse 372 TR5 datasheet (static.chipdip.ru DOC003869221): 372 series, time-lag, 250 V, IEC 60127-3; row 0500: 500 mA, 250 V, drop 180 mV, cold resistance 125 (as printed), melting I2t 1.3 A2s; breaking capacity **35 A @ 250 VAC** for currents up to 3.15 A (UL approved 50 A). A 35 A breaking capacity is a concern: if the branch (or an IRM module) fails short, the prospective current at a UK socket is far higher, and this fuse may fail to clear safely. The 0215 5x20 ceramic is rated 1.5 kA (LCSC attribute; datasheet not fetched).
- The 40 A cold-start inrush of the IRM-05-5 (and 10 A for the IRM-01-5) against I2t of 0.42 A2s for the 0215.500 is the tension: inrush duration is not given by Mean Well, so I cannot compute the I2t; if the bench shows nuisance blows, step to T630mA (not researched), not fast-acting. The TR5 has I2t 1.3 A2s (better for inrush) but only 35 A breaking.
- Whichever is fitted, it must sit before both PSU modules and after (or in parallel with) the main fuse tap point. It needs 250 V AC; both candidates are 250 V AC rated.
- SMD alternatives for 250 V AC: Bel UMTS 250 (C3167089, 250 mA only, stock 0) and AEM/JDT 2410 types (C91409 etc.) have unclear certification; not recommended.

## 5. Inrush NTC: what Mean Well recommends

Read IRM-05 (spec 2025-08-08) and IRM-01 (spec) directly: **neither datasheet recommends an external fuse value, an NTC, or EMI components.** IRM-05: "EMI Class B without additional components"; "Class II design (no FG pin), incorporating the built-in EMI filtering"; INRUSH CURRENT (Typ.) "COLD START 20 A / 115 Vac, 40 A / 230 Vac"; leakage < 0.25 mA / 277 Vac; input 85-305 Vac, 0.08 A @ 230 Vac; surge immunity "Level 3, 1 kV L-N"; withstand 4.2 kVac I/P-O/P; EMC note refers to Mean Well's EMI-testing-of-component-power-supplies statement. IRM-01: inrush 5 A / 115 Vac, 10 A / 230 Vac; 18 mA typ at 230 Vac; same 4.2 kVac, leakage < 0.25 mA, Class B, 1 kV surge L-N. The grep for "fuse", "NTC" and "recommend" returned nothing in either file.

Conclusion: no NTC is needed by the vendor. 40 A + 10 A = about 50 A cold-start peak on the common branch; against the main 10 A T fuse (I2t 333 A2s) this is negligible, and it only matters for the T500mA fuse (section 4). If you find the T500mA blowing at power-up, an NTC (e.g. 10 ohm, >= 1 A) in the PSU branch is the standard remedy, at roughly 0.1-0.5 W loss; keep it after the fuse on the branch only. Not selected, as nothing here requires it yet.

## 6. Shunt

**Recommendation: Vishay WSK25121L000FEA (C4248455), 1 mohm, 4-terminal, 2512.**
- WSK2512 family: 4-terminal design (E1/E2 sense, I1/I2 current), 1 W, +/-1 %, TCR +/-250 ppm/C for 1-2.9 mohm (family datasheet via search; the part-level PDF could not be downloaded, so TCR and 1 W for this exact code are from Farnell/LCSC listings). At 10 A the dissipation is only 0.1 W; at 16 A 0.26 W.
- The TCR is the weak point (250 ppm/C is about 1 % over a 40 K rise). For lower TCR use the TA-I RLP25FEGR001 (C459678, 3 W, +/-50 ppm/C) or the Ever Ohms MA251220FR001MZ (C252657), both 2-terminal: put the sense traces on the inner pad edges. Isabellenhuette BVS-A-R001 (3920, +/-50 ppm/C, C2688857) is out of stock. Manganin proper is not needed; these are metal alloy strips.
- BL0942 datasheet V1.06: "Current RMS range (10 mA ~ 30 A) @ 1 mOhm", IP/IN input max +/-42 mV peak (30 mV RMS); error 0.2 % for 30 A-100 mA, 0.4 % to 50 mA, 0.6 % to 10 mA, all "@ 1 mOhm sampling resistor"; current RMS register = 305978 x I(mV) / Vref with Vref = 1.218 V. ESPHome bl0942 defaults: current_reference 251065.68, which equals 305978/1.218 = 251,213 per mV, i.e. 1 mohm exactly (0.06 % off). At 16 A the drop is 16 mV RMS (23 mV peak) < 30 mV RMS limit. Good margin to the relay's 16 A limit.

## 7. Terminals

**Recommendation: Degson DG636-7.62-02P (C2827897 or C581337), two off 2-way blocks (L in/out, N in/out). Phoenix Contact MKDS 5/2-7,62 (1868076) is the branded equivalent for RS.**
- LCSC attributes: 7.62 mm pitch, 32 A, 630 V, 10-26 AWG, M3 screws, 21.5 mm above board, 105 C. Phoenix MKDS 5/2-7.62 per RS listing: nominal current 32 A, rated voltage (III/2) 630 V, 4 mm2. 1.0-1.5 mm2 flex sits comfortably inside the 10-26 AWG (down to 0.13 mm2, up to 6 mm2) range. Wire entry is from the side with the clamp screw on top: standard for this style.
- **Difference between the -00A and -02A suffixes is not documented** on the LCSC page; check the datasheet (links: ccf46534a5d8f09b26d580ef5634ab2c.pdf and b305b8db0026c1730f6da807af2bc08e.pdf under datasheet.lcsc.com/datasheet/pdf/) before ordering. 4-way DG636 not found on JLCPCB's search. Pitch of 7.62 between L-in and L-out poles of a 2-way is fine as both are line side (functional); keep L and N on different blocks so the L↔N distance is the board layout's choice.
- 21.5 mm height may clash with the junction box lid. Check against the box.
- Cixi Kefa KF128-7.5-2P (C474954, "24 A / 450 V", 14 mm) is cheaper and lower, but the figures are LCSC-listing only. I would not trust it on mains.

## 8. Relay driver

AO3400A + 1N4148W suits the coil. Coil current 80 mA (Hongfa 80.6 mA; Omron 80 mA, +10 % tolerance gives about 88 mA). AO3400A (LCSC): Id 5.7 A, RDS(on) 48 mohm at Vgs 2.5 V, Vth 1.45 V, so fully on at 3.3 V from the ESP32. Dissipation about 0.4 mW. Use 100 ohm gate series and 100 kohm gate pull-down as in the heatlink catalogue (R100, R100K). 1N4148W: 75 V, 150 mA continuous, 1 A surge; flyback current is the coil current decaying, below 100 mA, so OK; SS14 (1 A) adds margin but slows release a little more than a signal diode. Both datasheets require a surge diode on the coil (Omron note 2: "Be sure to use a diode"). Coil voltage tolerance: IRM-05-5 is 5 V +/-2.5 % (5.75-6.75 V OVP), within the 7.5 V (Hongfa) and 130 % (Omron) maxima; pick-up 3.5 V is well under the lowest sagged rail.

Both relays are 80 mA, i.e. 0.4 W from the 5 W (1 A) IRM-05-5.

## 9. BL0942 voltage divider

BL0942 datasheet V1.06 pin table: VP "maximum input range of +/-100 mV p-p (70 mV RMS)"; electrical table: VP differential input (peak) 100 mV; input impedance 370 kohm; absolute maximum -4 to +4 V on IP/IN/VP. **The datasheet text I extracted (V1.06) contains no recommended resistor values**; the numbers come from the Belling/Tuya reference design: **five 390 kohm in series over 510 ohm** (390 K x 5 : 0.51 K), per the Tuya support note. I cross-checked it independently: the datasheet gives V_RMS register = 73989 x V(mV) / 1.218, and ESPHome's default voltage_reference of 15883.34 per mains volt implies a divider ratio of 1:3824; (1,950,000 + 510) / 510 = 3825. They match to 0.03 %.

- At 230 V: 60.1 mV RMS at VP. At 253 V (UK maximum): 66.1 mV RMS, peak 93.5 mV against the 100 mV peak limit, so **only about 6.5 % headroom**; the result clips above ~265 V RMS (70 mV RMS). Consider 6 x 390 k only if the ratio is re-calibrated (ESPHome `voltage_reference` then changes); I would keep the reference ratio and accept it, since the design range is 230 V.
- Resistors: Yageo RC1206FR-07390KL (C137298), 250 mW, **200 V limiting element voltage**, +/-1 %, 100 ppm/C. Five in series give 358 V peak / 5 = 72 V each (surge 710 V clamp / 5 = 142 V), and 33 mW total at 253 V. Place the string in a line (not meandering) with 1206 pads 3.2 mm long; keep the chain's creepage to the 3.3 V domain per your 8 mm rule (the BL0942 is on the mains side in option A, so the chain only has to be functional-L/N spaced). Bottom resistor 510 ohm 1206 (C17991), or 0603 (C23193, stock 4.45 M) if the 100 mW is acceptable (0.04 mW actual).
- Optionally add a small RC (about 100 ohm / 100 nF) on VP/IP as in typical reference designs; **unverified** from the datasheet.
- The 370 kohm VP input impedance in parallel with 510 ohm changes the ratio by only 0.14 %, absorbed by calibration.

## Risks / open questions

1. **Fuse continuous derating**: T10A 5x20 at 10 A continuous, with a 10 A holder, in a sealed ABS box, will run hot. Decide at gate 4 or change format (6.3x32, 15 A holder). Nothing here has been thermally verified.
2. **Stock**: HF115F-1HS3A is 0 at LCSC (C2976778), -I/...3A has 25; TMOV14RP275E has 3; BL0942 SSOP-10 is 0 (C2837510); Omron G5RL-1A-E-HR is not on LCSC at all. PCBWay can buy these elsewhere, but lead times and counterfeit risk rise. Verify before ordering.
3. **Relay variant trap**: C81373 (`HF115F/005-1HS3`, AgCdO) is VDE 10 A at 70 C, not 16 A at 85 C. Only the A-suffix is 16 A at 85 C.
4. **Footprint**: confirm pin mapping of the 6-pin HF115F against the drawing; confirm the combined Hongfa/Omron footprint with 1.4 mm drills.
5. **Open-contact spacing** (5.04 mm c/c) and L↔N spacing near the relay pins need a DRC check; consider a slot between contact pins.
6. **T500mA fuse trade-off**: 35 A breaking capacity (TR5) versus 40 A inrush against low I2t (0215.500). Measure the actual IRM-05-5 inrush on a bench with the scope before finalising.
7. **BL0942 voltage headroom** is only 6.5 % at 253 V; clipping above ~265 V RMS. Acceptable for UK mains, but note it.
8. **Datasheet gaps**: I could not obtain the Littelfuse 215 and TMOV datasheets (Littelfuse and RS block automated fetches), the per-part Vishay WSK2512 PDF, or the Degson DG636 datasheet; the claims from those are from LCSC/distributor listings and are marked as such. LCSC datasheet PDFs are behind bot protection; Martin can download them in a browser.
9. **UK distributor part numbers** were only available from search snippets (Farnell 2840075, 1597013, 1817007, 1107426, 2213809; RS 7874300, 1740502, 8717646, 6839239P). Prices and stock not checked.
10. **PSU model**: CLAUDE.md names IRM-03-5/IRM-02-5 but this brief says IRM-05-5/IRM-01-5. The datasheet values above are for the latter pair.
11. **Cadmium**: avoid the plain HF115F "-1HS3" (AgCdO) for a home build you may later open or dispose of; the A-suffix is AgSnO2.
12. **Terminal -00A vs -02A** difference unknown; 21.5 mm height versus the box.
13. **MOV after fuse**: a failing MOV that does not trip its thermal link would open the 10 A T fuse slowly; the TMOV's thermal element is the reason to prefer it over the plain disc. Series-fuse requirement from the TMOV datasheet is unverified.
14. **Safety**: Martin does the mains work and gates, per CLAUDE.md. Nothing in this file is ordered.
