# Roadmap

Ideas and requests from users are collected through the [request forms](../../../issues/new/choose). The most requested items move up.

## v0.1 — first public release (planned mid-November 2026)
- [x] Italy: F1 / F2 / F3 bands with national holidays, fixed-price contracts (single, two bands, three bands)
- [x] Italy: PUN Index GME / zonal prices (quarter hours, today and tomorrow) and PUN + spread contracts with optional grid losses
- [x] Switzerland (core): reader for the VSE tariff files operators must publish, high/low windows, cantonal and municipal surcharges, federal charges, VAT — verified against ElCom totals
- [x] Switzerland (core): find the grid operator(s) of a municipality through ElCom open data, with curated fixes for operators that registered a web page instead of the file
- [x] Switzerland: UI setup (municipality → operator → tariff → grid and fees), manual link for operators without a readable file (SES, AEM), sensors (price, high/low period, next change, next price, fixed charges), refresh twice a day, automatic switch to the new year's file
- [x] Sensors: current price, current band, next band change, next band, next price
- [x] Sensors: best time to start (cheapest 2 hours in the next 24), price schedule for the next 36 hours (attribute, used by the card)
- [x] Sensors: cost today / this month from the user's energy meter, each kWh priced when used (options → energy meter); survives restarts; resets at local midnight
- [x] Choose the appliance duration for the best time to start (options → appliance duration, 0.5–8 h)
- [x] UI-only setup (config flow), translations EN / IT / DE / FR
- [x] Dashboard card: price now, next 24 h (cheap/dear colours), best time to start; loaded automatically by the integration, EN/IT/DE/FR, light and dark themes
- [x] Switzerland: change tariffs from the options
- [x] Icon and logo shipped with the integration (`brand/`, shown by Home Assistant 2026.3 and later)
- [x] "Suggest a change" link inside the integration (setup and options) and the card, with the data source shown on the card

- [x] README with screenshots, installation, sensors, card and an automation example; Italian guide

## Next (December 2026 – January 2027)
- [x] Swiss dynamic tariffs from the operator's API (VSE / SmartGridready standard, 2026 and 2027 formats): EKZ and Groupe E verified live
- [ ] Swiss dynamic tariffs: CKW (its tariff file cannot be downloaded yet), BKW (from 2027), operators without an API (AIL, AMB, AEW)
- [ ] Cost per appliance
- [x] Guide: reading your consumption — clamp, Chain 2 / Open Meter (Italy), smart-meter customer interface (Switzerland): [docs/meter.md](meter.md)
- [x] Blueprint: start an appliance at the best time ("ready" helper + switch, optional notification)
- [x] Blueprint: price alert (below or above a threshold, any action)
- [x] Blueprint: use solar surplus (W or kW, either sign, optional cheap-price hours)

## Ideas from users
_(empty — be the first: [suggest something](../../../issues/new/choose))_
