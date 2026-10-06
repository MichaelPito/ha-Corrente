# Fonti dei dati

> Verificate il 6 ottobre 2026. Ogni fonte nuova o cambiata va registrata qui prima di usarla nel codice.

## Italia

### Fasce F1 / F2 / F3 — ✅ implementate (`core/italy.py`)
- Fonte: ARERA, TIV (Allegato A alla delibera 362/2023/R/eel, **Tabella 6**), https://www.arera.it/fileadmin/allegati/docs/23/362-23tiv.pdf; definizione originale nella delibera 181/06.
- F1: lun–ven 8–19. F2: lun–ven 7–8 e 19–23, sab 7–23. F3: lun–sab 0–7 e 23–24, domeniche e festivi.
- **Festivi F3 (elenco chiuso):** 1/1, 6/1, Lunedì dell'Angelo, 25/4, 1/5, 2/6, 15/8, 1/11, 8/12, 25/12, 26/12.
- **Il 4 ottobre (San Francesco, di nuovo festa nazionale dal 2026) NON è nell'elenco ARERA.** Non usare `holidays.IT()` della libreria python-holidays, che lo include: per le bollette conta la tabella ARERA. Nel 2026 il 4/10 è domenica; la differenza conta dal lunedì 4/10/2027. Da ricontrollare se ARERA aggiorna la tabella.

### Prezzi all'ingrosso (PUN Index GME e prezzi zonali) — ⏳ da implementare
- Dal 1/1/2025 il riferimento è il **PUN Index GME**: media dei prezzi zonali ponderata per i volumi. Nei file XML è ancora nel tag `<PUN>`.
- Dal 1/10/2025 il mercato del giorno prima (MGP) ha **risoluzione al quarto d'ora**. I file orari sono ancora pubblicati.
- **Fonte A, download dal sito GME** (usata anche da pun_sensor, licenza MIT):
  - `https://gme.mercatoelettrico.org/DesktopModules/GmeDownload/API/ExcelDownload/downloadzipfile?...&Mercato=MGP&Settore=Prezzi`
  - Restituisce uno ZIP con un XML orario e uno al quarto d'ora; prezzi in €/MWh con la virgola decimale.
  - Richiede le intestazioni del modulo di download del sito.
  - **Non è un'API documentata**: può cambiare senza preavviso.
  - I prezzi di domani sono disponibili dal primo pomeriggio.
- **Fonte B, API ufficiale GME** (`api.mercatoelettrico.org`): gratuita, ma la registrazione richiede PDF firmati digitalmente inviati via PEC. Troppo pesante per un utente domestico; al massimo un'opzione futura per chi la vuole.
- **Fonte C, ENTSO-E Transparency Platform:** API ufficiale con token personale gratuito. Ha i prezzi zonali italiani ma **non il PUN Index**.
- **Termini GME (sito e API):**
  - solo uso **personale, informativo, non commerciale**;
  - **citazione obbligatoria** "Fonte: Gestore dei Mercati Energetici S.p.A.";
  - vietato condividere credenziali.
- **Regole per Corrente:**
  - ogni installazione scarica da sola i dati per la propria casa;
  - nessun server o cache condivisi;
  - 1–2 richieste al giorno con minuto casuale per installazione;
  - citazione della fonte nell'interfaccia;
  - **le funzioni a pagamento (Corrente Pro) non devono dipendere dalla rivendita di dati GME.**

### Forma dei contratti — riferimento per la configurazione
- **Prezzo dell'energia:**
  - fisso monorario, biorario (F1/F23) o triorario: ✅ implementato;
  - indicizzato, PUN + spread, a volte con fattore perdite: ⏳.
- **Altre voci, oltre l'energia:**
  - quota fissa di commercializzazione;
  - trasporto e gestione contatore: quota fissa, quota per potenza, quota per energia;
  - oneri di sistema ASOS/ARIM;
  - accisa;
  - IVA: 10% per le case, 22% negli altri casi.
- Fonte: guida ARERA alla bolletta, https://www.arera.it/fileadmin/bolletta/allegati/guidaele.pdf

## Svizzera

### La chiave: ogni gestore deve pubblicare le sue tariffe in JSON
- L'**art. 7b cpv. 1 OAEl (StromVV)** obbliga ogni gestore di rete a pubblicare le tariffe in **JSON nel formato VSE** e a comunicare il link a ElCom.
- ElCom lo espone nei dati aperti (campo `urltr`), quindi **un solo lettore copre quasi tutti i gestori, fasce alta/bassa tariffa incluse**.
- Copertura del link: 446 gestori su 551 nel 2026, 489 su 535 nel 2027.
- Specifica del formato: https://tariffconverter.strom.ch/ch-electricity-tariffs-openapi.yml ("Tariff Retrieval API" 1.0.1). Prezzi in CHF senza IVA; finestre con mesi, giorni della settimana e orari da/a.

### ElCom / LINDAS — ✅ verificato, ⏳ da implementare (v0.1)
- SPARQL: `https://lindas.admin.ch/query` (anche `cached.lindas.admin.ch`), POST, senza autenticazione.
- Cubo: `https://energy.ld.admin.ch/elcom/electricityprice`; dimensioni per comune (numero UST), anno, profilo (H1–H8), gestore, prodotto.
- Componenti in Rp./kWh: energia, rete, tributi, supplemento rete (2,3), misurazione, totale; più il link `urltr`. **Il 2027 è già pubblicato.**
- **Niente fasce orarie** nel cubo: solo medie annue per profilo. Le fasce si leggono dal JSON del gestore.
- Licenza: Open-Use, uso commerciale permesso, citazione non obbligatoria (la mettiamo comunque).
- Esempi H4, totale in Rp./kWh:
  - AMB Bellinzona: 24,226 nel 2026 e 25,203 nel 2027;
  - AIL Lugano: 25,133 nel 2026 e 25,911 nel 2027;
  - AIM Mendrisio: 28,432 nel 2027.

### Gestori ticinesi
| Gestore | JSON tariffe | Alta / bassa tariffa | Note |
|---|---|---|---|
| AIL (Lugano) | ✅ funziona (95 tariffe 2026–2027) | "giorno-notte": HT 6–22, NT 22–6 tutti i giorni | Tariffa dinamica a 4 fasce, pubblicata entro le 18 per il giorno dopo, **solo come tabella HTML** |
| AMB (Bellinzona) | ✅ `amb.ch/media/2hcct0s4/tariffe-2027.json` | "Casa" 2027 senza fasce | Il file inizia con un BOM: leggere con `utf-8-sig`. "Dinamica" con fasce diverse ogni giorno (app/email), nessuna API, codificata male nel JSON |
| AIM (Mendrisio) | ✅ funziona | Rete HT lun–ven 8–20; NT 20–8, sabato e domenica | Il file "2027" contiene anche il 2026: filtrare per data di inizio |
| SES (Locarno) | ❌ solo pagina web | AMBRA+: NT 22–6 tutti i giorni (solo con apparecchi comandati) | Serve l'inserimento manuale |
| AEM (Massagno) | ❌ link 2027 rotto (404) | — | Serve l'inserimento manuale |
| Stabio, Ascona, Airolo, Bedretto, Faido, Moesano | ✅ pubblicano il JSON | — | — |

### Tariffe dinamiche — ✅ verificato, ⏳ v0.2
- Standard comune **SmartGridready / VSE "Dynamic Tariff"** (OpenAPI, licenza BSD-3): https://github.com/SmartGridready/SGrSpecifications/tree/master/DynamicTariff
  - V1 per il 2026, V2 per il 2027.
  - `GET /tariffs?tariff_type=&tariff_name=&start_timestamp=&end_timestamp=`, pubblico.
  - Fasce da 15 minuti.
- Endpoint provati, tutti senza autenticazione:
  - **EKZ:** `https://api.tariffs.ekz.ch/v1/tariffs?tariff_name=electricity_dynamic`
  - **CKW:** `https://e-ckw-public-data.de-c1.eu1.cloudhub.io/api/v1/netzinformationen/energie/dynamische-preise?tariff_name=home_dynamic&tariff_type=integrated`
  - **Groupe E:** `https://api.tariffs.groupe-e.ch/v2/tariffs` (la v1 è dismessa)
  - **BKW**, rimunerazione per l'immissione: `https://api.bkw.ch/api/dyntariffs/v1/Tariffs/energyreturn`
- Scoperta automatica: il JSON statico del gestore indica l'URL dinamico in `prices.dynamic.url`.
- **AIL e AMB:** tariffe dinamiche senza API. Leggerle dall'HTML è fragile e di dubbia legittimità: **fuori programma**. Chiederemo loro di pubblicare un'API SGR.

### Rimunerazione per l'immissione
- VESE pvtarif (`opendata.vese.ch`) richiede una **chiave di licenza** con termini sconosciuti: **non usarla senza permesso di VESE**.
- Per BKW è disponibile tramite SGR.

### Concorrenza diretta
- **prusuino/ha_swiss_electricity_price** (MIT, 1 stella, luglio 2026) fa già ElCom + JSON VSE + fasce. Studiarlo, non copiarlo.
- **Le nostre differenze:**
  - Italia e Svizzera in un'unica integrazione;
  - lingua italiana e attenzione al Ticino;
  - finestra più economica, costi e blueprint;
  - card per la dashboard.
