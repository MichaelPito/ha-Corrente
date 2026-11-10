Extracts of the tariff files that Swiss grid operators publish under Art. 7b StromVV
(VSE "Tariff Retrieval API" format), downloaded on 2026-10-06 and trimmed to the household
tariffs used in tests. `amb-2027.json` keeps the UTF-8 BOM found in the original file.

- `ail-2027.json` — AIL, Lugano
- `aim-2026-2027.json` — AIM, Mendrisio (one file with both years)
- `amb-2027.json` — AMB, Bellinzona

Added on 2026-10-08 for dynamic tariffs (files trimmed to the 2026 tariffs used in tests;
API answers saved as downloaded):

- `ekz-2026.json` — EKZ, Zurich canton (`tarife_ekz.json`)
- `groupe-e-2026.json` — Groupe E, Fribourg canton (grid tariffs and two energy tariffs)
- `ekz-electricity-dynamic-20261008.json`, `ekz-grid-400d-20261008.json` — EKZ's dynamic
  tariff API, 8 October 2026 (2026 format)
- `groupe-e-grid-20261008.json` — Groupe E's API, grid part, 8 October 2026
- `ckw-integrated-20261008-09.json` — CKW's API, 8–9 October 2026 (timestamps without seconds)
- `lindas-dietikon-2026.json` — ElCom (LINDAS) answer for Dietikon, 2026

Added on 2026-10-13 for the setup suggestions:

- `ewz-2026.json` — ewz, city of Zürich and villages in Graubünden (`tarif-ewz-maschinenlesbar.json`,
  trimmed to two energy tariffs and the grid tariffs and fees of both areas)
- `sgsw-2026.json` — St. Galler Stadtwerke (grid tariffs with the single-rate price inside the
  day/night tariff, reactive-energy prices as grid tariffs)
- `sil-2026.json` — Services Industriels de Lausanne, household tariffs (each fee a tariff of its own)
- `sig-2026.json` — SIG, Geneva, household tariffs ("réserve d'électricité" as a separate grid tariff)

Added on 2026-10-14, from the comparison with ElCom (`docs/FONTI-DATI.md`), trimmed:

- `bkw-2026.json` — BKW: fees numbered BKW's own way ("15040 Ittigen"), all with the same name
- `energie-thun-2026.json` — Energie Thun: federal charges written as cantonal fees
- `yverdon-2026.json` — Yverdon-les-Bains: the 2 Rp. municipal fee written as 2 CHF/kWh
- `ewo-2026.json` — EWO, Obwalden: fees for the whole canton ("6 Obwalden")
- `ebs-2026.json` — ebs, Schwyz: no flat household grid tariff, a flat one for building sites
- `winterthur-2026.json` — Stadtwerk Winterthur, fees only: a tier for consumption above 100'000 kWh

Added on 2026-10-19, from the comparison with ElCom for 2027, trimmed:

- `romande-energie-2027-double.json` — Romande Energie, "Double" tariffs: one grid price written
  as 10.62 CHF/kWh (it is 10.62 Rp.)
- `ebs-2027.json` — ebs, Schwyz: a seasonal day/night household grid tariff; the only flat
  grid tariff is for building sites (90 CHF a month)
- `oiken-2027.json` — OIKEN, Sion: the municipal fee has a monthly part (0.84 CHF) besides the
  per-kWh one (trimmed to "Tarif Simple" and two municipalities)

Added on 2026-10-20, from the comparison with ElCom of every operator for 2027, trimmed:

- `spreitenbach-2027.json` — Gemeinde Spreitenbach: the yearly grid fee (66 CHF) written as monthly
- `graenichen-2027.json` — TB Gränichen: with a flat energy tariff, the only flat grid tariff is
  for building sites

Added on 2026-11-10:

- `groupe-e-2027.json` — Groupe E, Fribourg (`tarifs.json`), trimmed to the 2027 single-price
  and day/night household tariffs: its day/night grid is flagged as the standard one.
