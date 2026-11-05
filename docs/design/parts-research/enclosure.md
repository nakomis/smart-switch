# Petro enclosure options (230 V / 10 A in-line cord switch, personal use, UK)

Research date 2 Nov 2026. Method: manufacturer drawings and datasheets were downloaded and read (Hammond drawings via Rapid Electronics' PDF mirror, Mean Well spec PDFs, Lapp and HellermannTyton datasheets). Where a figure could not be confirmed it says "unverified". Prices are Rapid Electronics' listed 1+ unit prices, taken from the page's own data (net, with VAT rate 20% shown separately), so treat as ex-VAT. Rapid is a UK stockist but is not on your suggested list. RS, Farnell, Mouser and DigiKey UK returned 403 or timed out to my tooling, so the same Hammond parts should be cross-checked there (Farnell stocks 1591XXDBK as 1244194, unverified).

## Corrections to the brief

- **IRM-05-5 is not 33.7 x 22.2 x 15 mm.** Mean Well's IRM-05 spec gives **45.7 x 25.4 x 21.5 mm**, case 222A, and says "94V-0 flame retardant plastic case" (https://www.meanwell.com/Upload/PDF/IRM-05/IRM-05-SPEC.PDF).
- **IRM-01-5 is 33.7 x 22.2 x 15 mm** (https://www.meanwell.com/Upload/PDF/IRM-01/IRM-01-SPEC.PDF). The 33.7 x 22.2 x 15 figure was the IRM-01's. Allow 21.5 mm height for the IRM-05 in the 25 mm budget.
- Wago 221 dimensions: not checked (unverified).

## Hammond 1591 naming trap (important)

In the 1591 range the **"S" before the colour code means general-purpose ABS, UL94-HB, which is not acceptable**. Hammond's own 1591E drawing lists: 1591EBK = FR ABS, UL94-V0; 1591ESBK = GP ABS, UL94-HB. The 1591XXD drawing says "Enclosure molded from FRABS UL 94-V0 Plastic" for 1591XXDBK/DGY. RS lists some 1591 items with "ABS" and no rating, so buy only the non-"S" codes (XXDBK, EBK) and read the rating on the datasheet.

## Ruled out

| Candidate | Why |
|---|---|
| Hammond 1591xxSBK/DSBK/ESBK/ESGY (GP ABS) | UL94-HB (Hammond 1591E drawing) |
| Hammond 1551 series | UL94-HB per distributor/Hammond 1551H datasheet; also tiny |
| Hammond 1552 hand-held (FR ABS, V-0) | Gland end panel only takes 2-6 mm cable; too small. Not suitable |
| Fibox ABS / TA series | UL 94 HB per Fibox datasheets |
| Spelsberg TK PC / TK PS / TG | Spelsberg's technical annex gives glass-fibre PC and transparent PC at UL94 V-2, TK PS (polystyrene) at HB. Below V-0 |
| Hammond RZ polycarbonate (RS 2657229) | UL94-V2 per RS listing |
| Gewiss / Wiska / Schneider Mureva / Takachi / OKW | No verifiable UL94 V-0 small box found in the time available. Unverified, not ruled in or out |
| Purpose-made in-line cord boxes | Nothing found with a verifiable rating (a Daiertek ABS "hot-dog" cord cover has no UL94 rating). Not recommended |

## Option A (recommended): Hammond 1591XXDBK

- **Part:** Hammond 1591XXDBK (black, RAL 7011). The grey is 1591XXDGY.
- **Supplier / price:** Rapid Electronics order code 30-1839, £6.59 (1+), £6.03 (10+), £5.52 (50+); 45 in stock on 2 Nov 2026. https://www.rapidonline.com/hammond-1591xxdbk-frabs-enclosure-152-x-82-x-50mm-black-30-1839
- **External:** 152.4 x 82.4 x 47.75 mm (box), IP54 per Rapid (no gasket).
- **Internal:** narrowest inside width 75.25 mm, inside height 46.5 mm, inside length about 148 mm (152.43 less two 2.0 mm walls: derived, not printed). Average wall 2.0 mm.
- **Material and rating:** FR ABS, **UL94-V0**. Source: Hammond drawing (https://static.rapidonline.com/pdf/30-1839.pdf), note reads "Enclosure molded from FRABS UL 94-V0 Plastic"; Rapid page also says UL94-V0.
- **Colour:** black, opaque. Joint between lid and box is un-gasketed, so mask the light-pipe area and consider a black internal baffle or tape on the lid join (light leak at the join is plausible, unverified).
- **Fixings / bosses:** four M3 brass inserts in the box corners (M3 x 0.5, 2.5 dia x 5 deep) and matching standoffs in the lid. Pattern **114.75 x 54.25 mm** (lid holes dia 3.5, box pilot dia 2.0 to 2.5; for #4 self-tapping screws, Hammond 1593ATS50). Lid screws M3 x 10 into brass inserts. Hammond's own "max size PCB, fits in box or lid" outline is 145 x 75 mm with corner notches. No DIN rail.
- **Lid:** flat, about 2 mm, easy to drill for a button and light pipe.
- **Glands:** none supplied. Drill the short end walls (box is 47.75 deep, 75 wide inside), centre about 22 mm up. M16 hole 16.2 mm or M20 hole 20.2 mm both fit.

## Option B: Hammond 1554J2GY (gasketed, long polycarbonate)

- **Part:** Hammond 1554J2GY, light grey RAL 7035.
- **Supplier / price:** Rapid 30-4595, £18.26 (1+), £15.12 (10+), £12.53 (50+); 12 in stock. https://www.rapidonline.com/hammond-1554j2gy-watertight-pc-enclosure-160-x-90-x-60mm-grey-30-4595
- **External:** 160 x 90 x 60 mm. IP66 / NEMA 4X (Hammond).
- **Internal (from drawing):** box inside 147.0 x 79.25 mm; inside height 46.37 mm. Panel (separately ordered 1554JPL) 147.3 x 77.5 mm.
- **Material and rating:** polycarbonate. Hammond drawing note: "Polycarbonate version is UL 508 approved, Matl UL94 - V0 / 5VA @ 3mm". Rapid's page says the same. Hammond's clear-lid datasheet describes the family as "UL94 5V" (5VA is the more demanding class). So grey/PC rating is V-0 or better at 3 mm thickness. Wall thickness actually moulded may be less than 3 mm (unverified).
- **Colour:** light grey, PC. Light grey PC may glow around a bright LED (unverified); the gasketed lid is good against light leak at the joint.
- **Fixings / bosses:** four M3 brass inserts / standoffs; moulded DIN tabs; vertical PCB card guides for 1.5 mm boards; lid on 4 captive M4 stainless screws. Panel pattern **121.5 x 58.0 mm** per drawing (Hammond's inner-panel holes dia 2.79, for #6 self-tapping). Verify exact boss positions against Hammond's STEP file before routing.
- **Glands:** none supplied; drill end walls (90 mm wide, box about 54 deep). Drilling for glands removes the IP66 only if the gland seal is not good; fit glands with sealing washers.
- **Downside:** about three times the price of A; lid thickness unverified.

## Option C: Hammond 1554F2GY (compact, for a short board)

- Rapid 30-4592, £17.64 (1+); 64 in stock. 120 x 90 x 60 mm. Inside 100 x 77 mm by 46.4 mm high (Hammond drawing https://static.rapidonline.com/pdf/30-4592.pdf). Same material, rating wording ("UL94 - V0 / 5VA @ 3mm"), colour and gasket as B.
- Boss pattern: panel holes about 91.7 x 68.0 mm per drawing (unverified exactly which holes are bosses).
- **Too short** for a 100 mm board plus two glands in-line (100 mm inside length). Only workable with a board of about 70 mm or less. Listed for completeness.

## Option D: Hammond 1591EBK (roomy fallback)

- Rapid 30-6147, £12.10 (1+), £10.02 (10+); 265 in stock. https://rapidonline.com/catalogue/product/30-6147
- External 190 x 110 x 56.7 mm (Hammond drawing https://static.rapidonline.com/pdf/30-6147.pdf); narrowest inside 102.74 mm wide x 182.74 mm long, max inside height 56.6 mm; IP54.
- FR ABS, **UL94-V0** per Hammond drawing part table (1591EBK; black). Not the 1591ESBK, which is HB.
- Bosses: M3 brass inserts at the lid corners (M3 x 0.5, 5.75 deep), lid pattern 88.1 mm x 96.0 mm; box PCB standoff positions not clearly dimensioned (unverified).
- Biggest of the four; easy to fit everything, including the Wago, but it is not a slim in-line body.

## Glands (for A, B, C, D)

Requirement: V-2 or better, clamp range covering 7-9 mm. No V-0 black nylon gland was found; the RS PRO V-0 range is red only (per RS listing). So V-2 is the best verified.

| Size | Part | Clamp | Supplier / price | Rating source |
|---|---|---|---|---|
| M16 x 1.5 | HellermannTyton **NGM16-BLK** (dome head, includes locknut and washer) | 5-10 mm | Rapid 04-0795, listed £2.01 (title says pack of 10; price looks low, check before ordering); 701 in stock | HT NGM family datasheet (https://www.farnell.com/datasheets/1965084.pdf): "Body & Nut: PA 66, UL 94 V2, IP68". Dimensions and clamp from https://static.rapidonline.com/pdf/04-0796.pdf |
| M20 short | HellermannTyton **NGM20S-BLK** | 6-12 mm | Rapid 04-0796, £7.89 per pack of 10; 224 in stock | As above. Thread length under hex 8.7 mm, so less intrusion into the box than the M16 (15 mm) |

Notes:
- 7-9 mm cable sits mid-range for NGM16-BLK (5-10) and low-mid for NGM20S (6-12). Measure your actual flex; H05VV-F 3 x 1.5 is about 9 mm, near the top of M16's range.
- Lapp SKINTOP ST-M (53111010 M16 4.5-10 mm; 53111020 M20 7-13 mm) is a fine alternative but the Lapp sheet states no UL94 class. Unverified, so not used.
- Gland strain relief is the only cord retention. The pull-test compliance of a home-made switch (BS EN 61058 style) is your own responsibility; I did not assess it.

## Recommendation: Option A, Hammond 1591XXDBK + 2 x NGM16-BLK

Cheapest by far, explicit V-0 on the Hammond drawing, black, flat lid, long and narrow for an in-line body, and the same Hammond family has a V-0 spec printed in the datasheet. Weakest points: IP54 only, ungasketed joint (light leak, check with the LED), and the Hammond boss pitch (114.75 mm) is bigger than your 70-100 mm board range.

### PCB outline implied

- Hard limit (Hammond): 145 x 75 mm, with 4.5 mm radius corner notches on the 114.75 x 54.25 holes.
- Using Hammond's four bosses: board about **120 x 60-62 mm**, 4 x M3 (dia 3.2-3.5) holes on a **114.75 x 54.25 mm** rectangle, centred on the board. Inside length is about 148 mm, so the board occupies 120 and leaves roughly 14 mm each end. The glands (about 13 mm of M16 thread and nut inside) then sit above the board ends, so keep those zones free of tall parts, or use the shorter NGM20S (8.7 mm).
- Without the bosses: 100 x 60 mm, fixed by your own M3 standoffs; the 75 mm inside width and 46.5 mm height give room for the IRM-05-5 (21.5 mm tall) and a relay up to about 25 mm tall on 5 mm standoffs. Be sure to keep mains clearances and creepage on the PCB, and treat the Wago 221 as sitting off-board (space for it is a layout check, since its size is unverified).

## Sources

- Hammond drawing 1591XXD: https://static.rapidonline.com/pdf/30-1839.pdf
- Hammond drawing 1591E: https://static.rapidonline.com/pdf/30-6147.pdf
- Hammond drawing 1554F: https://static.rapidonline.com/pdf/30-4592.pdf
- Hammond drawing 1554J: https://static.rapidonline.com/pdf/30-4595.pdf
- Hammond 1554 clear-lid sheet (UL94 5V wording): https://static.datasheets.com/doc/10170195-hammond-1554u2gycl-ds.pdf
- Mean Well IRM-05 and IRM-01 specs (URLs above)
- HellermannTyton NGM info: https://static.rapidonline.com/pdf/04-0796.pdf ; flammability: https://www.farnell.com/datasheets/1965084.pdf
- Lapp SKINTOP ST-M: https://docs.rs-online.com/dec3/0900766b81372fc3.pdf
