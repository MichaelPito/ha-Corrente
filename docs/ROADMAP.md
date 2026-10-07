# Roadmap

Ideas and requests from users are collected through the [request forms](../../../issues/new/choose). The most requested items move up.

## v0.1 — first public release (planned mid-November 2026)
- [x] Italy: F1 / F2 / F3 bands with national holidays, fixed-price contracts (single, two bands, three bands)
- [ ] Italy: PUN / zonal prices and PUN + spread contracts
- [x] Switzerland (core): reader for the VSE tariff files operators must publish, high/low windows, cantonal and municipal surcharges, federal charges, VAT — verified against ElCom totals
- [x] Switzerland (core): find the grid operator(s) of a municipality through ElCom open data, with curated fixes for operators that registered a web page instead of the file
- [x] Switzerland: UI setup (municipality → operator → tariff → grid and fees), manual link for operators without a readable file (SES, AEM), sensors (price, high/low period, next change, next price, fixed charges), refresh twice a day, automatic switch to the new year's file
- [x] Sensors: current price, current band, next band change, next band, next price
- [x] Sensors: best time to start (cheapest 2 hours in the next 24), price schedule for the next 36 hours (attribute, used by the card)
- [ ] Sensors: cost today / this month; choose the appliance duration (today fixed at 2 hours)
- [x] UI-only setup (config flow), translations EN / IT / DE / FR
- [x] Dashboard card: price now, next 24 h (cheap/dear colours), best time to start; loaded automatically by the integration, EN/IT/DE/FR, light and dark themes
- [ ] Switzerland: change tariffs from the options (today: remove and add again)
- [ ] "Suggest a change" link inside the integration and the card

- [x] README with screenshots, installation, sensors, card and an automation example; Italian guide

## Next (December 2026 – January 2027)
- [ ] Swiss dynamic tariffs (EKZ, CKW, BKW / SmartGridready, Groupe E)
- [ ] Cost per appliance
- [ ] Guide: Chain2 / Open Meter (Italy) and Swiss smart-meter readout
- [ ] Blueprints: run appliances in the cheapest window, use solar surplus, price alerts

## Ideas from users
_(empty — be the first: [suggest something](../../../issues/new/choose))_
