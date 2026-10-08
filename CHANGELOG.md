# Changelog

All notable changes to Corrente. Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased] — v0.1.0, planned for mid-November 2026

First public release.

### Italy 🇮🇹
- Time bands F1 / F2 / F3 following ARERA, with national holidays (ARERA's closed list) and Easter Monday.
- Fixed-price contracts: single price, two bands (F1 / F23), three bands.
- PUN-indexed contracts: PUN Index GME or a zonal price, plus your spread and optional grid losses, with quarter-hour prices for today and tomorrow. Source: GME (personal, non-commercial use).

### Switzerland 🇨🇭
- Find your grid operator from your municipality through ElCom's open data, and read the tariff file every operator must publish (Art. 7b StromVV).
- High/low windows, cantonal and municipal fees, federal charges (checked per operator against ElCom's totals) and VAT.
- Dynamic tariffs with quarter-hour prices from the operator's own API (VSE / SmartGridready standard): EKZ and Groupe E verified.
- Manual link for operators without a readable file; automatic switch to the new year's file.

### Everywhere
- Sensors: price now, band or period, next change, next price, best time to start an appliance (duration of your choice), fixed charges (Switzerland), wholesale price (PUN).
- Cost today and this month from your energy meter, each kWh priced when used.
- Dashboard card (price now, next 24 hours, best time to start, data source), loaded automatically.
- Blueprint: start an appliance at the best time.
- Setup from the UI only, in English, Italian, German and French. "Suggest a change" links in the setup, the options and the card.
- Icon and logo shipped with the integration (Home Assistant 2026.3 and later).
