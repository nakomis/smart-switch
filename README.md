# Petro: a 10 A mains Wi-Fi smart switch

<!-- logo: docs/logo.png once chosen from docs/logo-candidates/ -->

## Support

If you find this useful, please consider buying me a coffee:

[![Donate with PayPal](https://www.paypalobjects.com/en_GB/i/btn/btn_donate_SM.gif)](https://www.paypal.com/donate?hosted_button_id=Q3BESC73EWVNN&custom=smart-switch)

## Table of Contents

<!-- toc -->

- [What it is](#what-it-is)
- [⚠️ Safety](#%E2%9A%A0%EF%B8%8F-safety)
- [Architecture Diagram](#architecture-diagram)
- [Repository Layout](#repository-layout)
- [Status](#status)
- [Architecture Diagrams](#architecture-diagrams)
- [Licence](#licence)
- [Support](#support)

<!-- tocstop -->

## What it is

Petro is a home-built Wi-Fi smart switch: an in-line cord unit (cable in, cable out) that switches a
resistive load of up to **10 A at 230 V AC**. It has:

- energy metering (voltage, current, power and energy totals), from a BL0942;
- one tactile button that cycles **on → off → auto**;
- a multi-colour status LED for the mode, boot, Wi-Fi, pairing and faults;
- control over MQTT through AWS IoT Core, using Martin's Fleet device service, with OTA
  updates and rollback;
- Alexa Smart Home control;
- back-up over-current and over-temperature trips in firmware.

It runs on an ESP32-S3-MINI-1, powered from the mains through an isolated Mean Well module, so
everything on the low-voltage side is SELV.

Petro is named after a Clone Wars youngling: microcontrollers in this house are Younglings.

## ⚠️ Safety

**This is a mains device, built for its author's own home. It is not a product, it will never be
sold or given away, and it has not been safety tested or UKCA marked.** The designs are published
for interest. If you build one, you do so at your own risk: mains electricity can kill, and a badly
built 10 A switch can start a fire.

## Architecture Diagram

The board's block diagram and the system diagram are still to come
(`docs/architecture/smart-switch.drawio`).

## Repository Layout

| Path | What's there |
|---|---|
| `pcb/` | The board, generated as code: a Python generator for KiCad 10, with DRC rules for mains creepage and 10 A tracks, and outputs for PCBWay and JLCPCB |
| `firmware/` | ESP-IDF 5.5 firmware for the ESP32-S3: portable C with host tests, plus the IDF project |
| `case/` | The enclosure: a UL94 V-0 junction box with glands, plus any printed internal parts |
| `docs/` | Design notes, the test procedures for the safety gates, the logo |
| `.github/workflows/` | CI |

## Status

Early days: the repo is scaffolded and the work is planned in Plane (project `PETRO`). The board
and firmware haven't been started yet.

## Architecture Diagrams

`docs/architecture/smart-switch.drawio` will be the source for the diagram above. The SVG is
auto-regenerated on commit by the pre-commit hook in `.githooks/pre-commit`.

To activate the hook after cloning:

```bash
git config core.hooksPath .githooks
```

## Licence

[CC0 1.0 Universal](LICENSE).

## Support

If you find this useful, please consider buying me a coffee:

[![Donate with PayPal](https://www.paypalobjects.com/en_GB/i/btn/btn_donate_SM.gif)](https://www.paypal.com/donate?hosted_button_id=Q3BESC73EWVNN&custom=smart-switch)
