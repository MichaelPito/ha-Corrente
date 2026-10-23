# Changelog

All notable changes to Corrente. Versions follow [Semantic Versioning](https://semver.org/).

## [0.3.1] — 2026-10-23

### Fixed
- Switzerland: the monthly fixed charges are right when an operator's file gives the yearly grid fee as a monthly one (Spreitenbach writes 66 CHF "a month", Quarten 144 CHF; ElCom lists the same figures as fees a year). When the file's monthly fee equals ElCom's yearly one, Corrente takes it as yearly. Before, the fixed-charges sensor and the cost of the month were twelve times too high for these operators.
- Home Assistant 2026.11: checked against the changes announced for developers; nothing to change.

## [0.3.0] — 2026-10-23

### Added
- Italy: the other costs on your bill, optional — transport, system charges and excise per kWh, and the fixed charges per month (in the contract step and in the options). The price, the best time and the cost sensors then include the per-kWh costs, and the fixed charges get a sensor of their own. Enter them like the energy prices (with or without VAT, the same way). Without them nothing changes: the price is the energy part, as before.

## [0.2.8] — 2026-10-23

### Fixed
- Switzerland, setup: the municipality is found however it is typed: without accents ("Zurich", "Neuchatel", "Delemont"), with "ue" for "ü" ("Muenchenstein"), without the dot or in full ("St Gallen", "Sankt Gallen", "St-Imier"), and the larger towns by their name in Italian, French, German or English ("Zurigo", "Ginevra", "Geneva", "Basilea", "Bâle"...). Before, "Zurich" found nothing.

## [0.2.7] — 2026-10-23

### Added
- Diagnostics (Settings → Devices & services → Corrente → ⋮ → Download diagnostics): the tariffs read, their time windows, the federal charges and fees checked with ElCom, the price now and for the next 24 hours. Attach the file to a request on GitHub; it holds your municipality, operator and tariffs, no passwords.

## [0.2.6] — 2026-10-21

Switzerland: cantonal and municipal fees now match ElCom's household figure within 0.3 Rp/kWh for 340 of 343 operators checked (250 before).

### Fixed
- Fees that hold the federal charges, which Corrente adds on its own, are no longer counted twice: Lachen, SIE (Chavannes-près-Renens), Goldach put the grid surcharge (2.3 Rp/kWh) in their fees, Fällanden all the federal charges (2.85 Rp/kWh).
- The fee suggestion counts monthly fees, as ElCom does: Blumenstein's fee for businesses (25 CHF a month) is no longer suggested to households.

## [0.2.5] — 2026-10-20

Switzerland: more operators can be used, and fees missing from operators' files are taken from ElCom.

### Added
- Cantonal and municipal fees that ElCom counts for a household but the operator's file leaves out are added to the price (attribute "other_fees_from_elcom"). 83 of 343 operators checked publish no fee in their file although ElCom lists some (about 1 Rp/kWh, up to 4); IWB's file has 0.65 of Basel's 7.79 Rp/kWh.
- Tariff files that could not be read: a web page registered with ElCom instead of the file (the .json files it links to are read: about 30 operators), two files in one (IWB, Basel), a zipped file, a file in UTF-16. A busy server is asked a second time.

## [0.2.4] — 2026-10-20

Switzerland: checked against ElCom for every operator with a readable tariff file (313 of 535 operators for 2027, 278 of 550 for 2026), not only 32.

### Fixed
- The federal charges are checked with ElCom's grid price per kWh, without monthly fees: some files give a yearly fee as monthly (Spreitenbach: 66 CHF), which made Corrente leave out or double the federal charges. In this check, about 30 operators per year had a price off by 2.3–2.85 Rp/kWh. The grid price per kWh now matches ElCom within 0.6 Rp. for 95% of operators in 2027 and 90% in 2026 (85% and 81% before).
- Tariffs that were refused and can now be priced: a single rate written as a high/low tariff with the same price twice (Gsteig, Egerkingen, Glarus and others), a part of a day inside a whole day (Dietlikon's Saturday 07:00–13:00), two windows with the same price at the same time (Diessenhofen), winter and summer prices plus small charges for the whole year (Herzogenbuchsee).
- Tariffs that still cannot be priced (two prices at the same time, as in Merenschwand's file) are no longer offered in the setup, instead of failing afterwards.
- The suggested grid tariff is never one far from ElCom's household figure when a closer one exists (Gränichen suggested its building-site tariff).

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
