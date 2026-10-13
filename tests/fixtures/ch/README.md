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
