# Changelog

All notable changes to Corrente. Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Blueprint "price alert": do something (a notification, a switch…) when the price goes below or above a threshold.

### Fixed
- Switzerland: a dynamic tariff whose link is a web page (AIL "dinamica") now says so, instead of "try again later".
- Switzerland: the indicative fixed price that a tariff file may give for a dynamic tariff is no longer added to the price from the operator's API.

### Changed
- Swiss entries are named after the municipality ("Corrente Lugano"), so entity ids are short: `sensor.corrente_lugano_price_now`. Existing entries keep their name.

## [0.1.0] — 2026-10-08

First release. The repository opens to the public with the launch, planned for mid-November 2026.

Works with Home Assistant 2025.10 and later (tested on 2025.10 and 2026.2).

### Italy 🇮🇹
- Time bands F1 / F2 / F3 following ARERA, with national holidays (ARERA's closed list) and Easter Monday.
- Fixed-price contracts: single price, two bands (F1 / F23), three bands.
- PUN-indexed contracts: PUN Index GME or a zonal price, plus your spread and optional grid losses, with quarter-hour prices for today and tomorrow. Source: GME (personal, non-commercial use).

### Switzerland 🇨🇭
- Find your grid operator from your municipality through ElCom's open data, and read the tariff file every operator must publish (Art. 7b StromVV).
- High/low windows, cantonal and municipal fees, federal charges (checked per operator against ElCom's totals) and VAT.
- Dynamic tariffs with quarter-hour prices from the operator's own API (VSE / SmartGridready standard): EKZ and Groupe E verified.
- Not yet: CKW's dynamic tariff, BKW's (from 2027) and operators that publish dynamic prices only on their website (AIL, AMB, AEW).
- Manual link for operators without a readable file; automatic switch to the new year's file.

### Everywhere
- Sensors: price now, band or period, next change, next price, best time to start an appliance (duration of your choice), fixed charges (Switzerland), wholesale price (PUN).
- Cost today and this month from your energy meter, each kWh priced when used.
- Dashboard card (price now, next 24 hours, best time to start, data source), loaded automatically.
- Blueprint: start an appliance at the best time.
- Setup from the UI only, in English, Italian, German and French. "Suggest a change" links in the setup, the options and the card, and a [form for people without a GitHub account](https://docs.google.com/forms/d/e/1FAIpQLSce_vFvHpz3Qav3o05DvoJhpIuM2zXWmvpgBHWRS1gJsEF6yQ/viewform).
- Icon and logo shipped with the integration (Home Assistant 2026.3 and later).

### Data and privacy
- Every Home Assistant downloads its own data: ElCom open data and operators' tariff files and APIs (Switzerland), GME's daily prices (Italy). No Corrente server, no account, no telemetry.
- GME data is for personal, non-commercial use; the source is shown on the sensors and the card.

[0.1.0]: https://github.com/MichaelPito/ha-corrente/releases/tag/v0.1.0
