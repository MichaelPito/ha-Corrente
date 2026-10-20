# Changelog

All notable changes to Corrente. Versions follow [Semantic Versioning](https://semver.org/).

## [0.2.3] — 2026-10-20

From a code review of 0.2.2, and a check of the 2027 tariffs (in force from 1 January) against ElCom's 2027 figures.

### Added
- Settings → Repairs explains when an operator's file has no prices in force (usually at the start of a year, before the operator publishes the new file); the issue goes away by itself once the file is there. Before, the sensors only showed as unavailable.

### Fixed
- 2027, Romande Energie (Vaud): one of the "Double" grid prices is written in the file as 10.62 CHF/kWh instead of 10.62 Rp. Any price of 1 CHF/kWh or more is now read as Rp., as was already done for fees.
- 2027, Schwyz (ebs): the federal charges were left out (about 3.5 Rp/kWh) because the check compared ElCom's figure with a tariff for building sites; your own grid tariff now comes first.
- Fixed charges: the monthly part of a cantonal or municipal fee is counted (OIKEN, Sion: 0.84 CHF a month).
- Several fees with day/night prices are priced separately and added up (merged, they stopped the price with "overlapping time windows").
- A seasonal all-day price (summer only, for example) is no longer dropped when it lies between another season's day and night prices.
- Fees with the same name (EKZ): the one for your place is used, whatever the order in the operator's file.
- BKW fees are also found for municipalities that ElCom writes with the canton ("Kirchdorf (BE)").
- Fees that apply everywhere are suggested together with the local ones.
- "AG" in a company name and "NE7" (network level) no longer count as the canton of Aargau or Neuchâtel when suggesting the grid tariff.
- A local fee whose comment says it excludes a federal charge ("ohne Netzzuschlag") is no longer dropped.
- Clearing all fees in setup now keeps none (the suggestion used to come back).
- The fee suggestion is computed faster, and the options ask ElCom once instead of at every redisplay.

## [0.2.2] — 2026-10-15

Switzerland: checked against ewz's file (city of Zürich and villages in Graubünden) and EKZ's.

### Fixed
- EKZ (canton of Zürich): the standard household energy tariff "Erneuerbar", with a winter and a summer price, could not be chosen ("time windows missing"). Since 0.1.0.
- City of Zürich (ewz): prices were about 3 Rp/kWh too high. ewz's grid tariff already includes the federal charges, and Corrente added them again; the check with ElCom now also works for operators that only have day/night grid tariffs.
- Sundays were priced too high where a tariff gives Sunday as a whole day of its own (ewz): Sunday's price was added on top of the night price.
- The night price started one minute early with operators that write "06:00–21:59" (ewz).
- Setup suggests the right grid tariff and fees for where you live: ewz proposed a Graubünden village's to people in Zürich, EKZ a business grid tariff to households (and now the dynamic grid tariff with the dynamic energy tariff).
- St. Gallen: the grid price was doubled. St. Gallen's grid tariff holds both the day/night prices and the single-rate price, and they were added up.
- Lausanne: only one of the six cantonal and municipal fees was counted (about 4 Rp/kWh missing). Fees can now be several, and setup picks them.
- Thun: the federal charges were counted twice (Energie Thun lists them as cantonal fees).
- BKW (Bern, Jura, Solothurn...): municipal fees were not found (BKW numbers municipalities its own way); now found by name.
- Schwyz (ebs) and Mendrisio (AIM): federal charges missing (about 3 Rp/kWh).
- Winterthur: two fee tiers (up to and above 100,000 kWh) were added up. Yverdon: a 2 Rp. fee written as 2 CHF in the file. Obwalden: fees given for the whole canton were missed.

### Changed
- Setup pre-selects the operator's standard energy tariff (ewz.natur at ewz), when the operator flags one.
- Checked against ElCom for 31 operators and municipalities in 22 cantons: the fees now match ElCom's within 0.3 Rp. everywhere, the grid within about 0.5 Rp. (see docs/FONTI-DATI.md).
- Setup checks its suggestions against ElCom's figures for a household in your municipality: the grid tariff whose price is closest (St. Gallen suggested a reactive-energy price, Geneva its separate "réserve d'électricité"), and the fees that add up to ElCom's (one set per product, as at AIL, or all of them, as in Lausanne).

## [0.2.1] — 2026-10-13

### Fixed
- With two or more Corrente entries (for example a Swiss and an Italian contract), after a restart only one of them started and the others showed "Failed to set up". Since 0.1.0.

### Changed
- Tested on Home Assistant 2026.10 (and still on 2025.10, the oldest supported version).

## [0.2.0] — 2026-10-12

Two new features: use your solar surplus, and see what each appliance costs.

### Added
- Cost per appliance: pick the energy sensors of appliances with their own meter (smart plugs) and get *Cost today* and *Cost this month* for each, named after the appliance.
- Blueprint "use solar surplus": switch an appliance on when the panels export enough power and off when the home buys power again, with a delay against clouds; optionally also during cheap-price hours.

## [0.1.1] — 2026-10-09

Fixes from a full trial run on a real Home Assistant, a new blueprint and a guide.

### Added
- Guide: how to get your consumption into Home Assistant (clamp, Italian Open Meter / Chain 2, Swiss smart-meter interface), for the cost sensors.
- Blueprint "price alert": do something (a notification, a switch…) when the price goes below or above a threshold.

### Fixed
- Card: the Swiss data source line is shown in the viewer's language.
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

[0.2.3]: https://github.com/MichaelPito/ha-corrente/releases/tag/v0.2.3
[0.2.2]: https://github.com/MichaelPito/ha-corrente/releases/tag/v0.2.2
[0.2.1]: https://github.com/MichaelPito/ha-corrente/releases/tag/v0.2.1
[0.2.0]: https://github.com/MichaelPito/ha-corrente/releases/tag/v0.2.0
[0.1.1]: https://github.com/MichaelPito/ha-corrente/releases/tag/v0.1.1
[0.1.0]: https://github.com/MichaelPito/ha-corrente/releases/tag/v0.1.0
