# Fonti dei dati

> Verificate il 6 ottobre 2026. Ogni fonte nuova o cambiata va registrata qui prima di usarla nel codice.

## Italia

### Fasce F1 / F2 / F3 — ✅ implementate (`core/italy.py`)
- Fonte: ARERA, TIV (Allegato A alla delibera 362/2023/R/eel, **Tabella 6**), https://www.arera.it/fileadmin/allegati/docs/23/362-23tiv.pdf; definizione originale nella delibera 181/06.
- F1: lun–ven 8–19. F2: lun–ven 7–8 e 19–23, sab 7–23. F3: lun–sab 0–7 e 23–24, domeniche e festivi.
- **Festivi F3 (elenco chiuso):** 1/1, 6/1, Lunedì dell'Angelo, 25/4, 1/5, 2/6, 15/8, 1/11, 8/12, 25/12, 26/12.
- **Il 4 ottobre (San Francesco, di nuovo festa nazionale dal 2026) NON è nell'elenco ARERA.** Non usare `holidays.IT()` della libreria python-holidays, che lo include: per le bollette conta la tabella ARERA. Nel 2026 il 4/10 è domenica; la differenza conta dal lunedì 4/10/2027. Da ricontrollare se ARERA aggiorna la tabella.

### Prezzi all'ingrosso (PUN Index GME e prezzi zonali) — ✅ implementati (`core/gme.py`, decisione dell'owner del 7 ottobre)
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
- **Implementazione (7 ottobre 2026):**
  - stesse intestazioni del modulo di download del sito, ma User-Agent onesto "Corrente/0.1 (+link alla repo)": il server accetta;
  - prezzi al quarto d'ora, con fallback orario;
  - giorni di 92 e 100 quarti d'ora verificati sui file reali del 29 marzo 2026 e del 26 ottobre 2025;
  - un download a mezzogiorno circa per oggi e domani, con minuto casuale per installazione dopo le 13:30; nuovo tentativo ogni 30 minuti solo finché domani manca.
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
| AIM (Mendrisio) | ✅ funziona, completo | Rete HT lun–ven 8–20; NT 20–8, sabato e domenica | Il file "2027" contiene anche il 2026: filtrare per data di inizio |
| SES (Locarno) | ❌ solo pagina web | AMBRA+: NT 22–6 tutti i giorni (solo con apparecchi comandati) | Serve l'inserimento manuale |
| AEM (Massagno) | ❌ link 2027 rotto (404) | — | Serve l'inserimento manuale |
| Stabio, Ascona, Airolo, Bedretto, Faido, Moesano | ✅ pubblicano il JSON | — | — |

### Tariffe dinamiche — ✅ implementato l'8 ottobre 2026
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
- **Come le legge Corrente (8 ottobre 2026):**
  - una tariffa del file con `tariffForm: "dynamic"` è proposta solo se `prices.dynamic.url` è un indirizzo `https` (AEW scrive `www.aew.ch/dynamic`, una pagina web: esclusa);
  - si chiama quell'URL aggiungendo `tariff_type` (il tipo della tariffa: `electricity` o `grid`), `start_timestamp` e `end_timestamp`; i parametri già presenti nel link (EKZ: `tariff_name=…`) restano;
  - due formati: 2026 = lista `[{"unit": "CHF_kWh", "value": …}]`, 2027 = oggetto con `energy: {"unit": "CHF/kWh", …}`; si legge solo la parte al kWh. La quota mensile (EKZ `CHF_m` 3.–) viene dal file statico; prezzi **senza IVA**;
  - EKZ restituisce anche l'intervallo dopo la fine richiesta, con la sola quota mensile: ignorato;
  - nella configurazione Corrente prova l'API una volta prima di salvare;
  - aggiornamento: oggi subito; domani da mezzogiorno più un minuto fisso per installazione, al massimo ogni 30 minuti finché non arriva (CKW lo pubblica verso le 11:20, Groupe E verso le 14:50, EKZ verso le 17:50).
- **Prova dal vivo dell'8 ottobre 2026:**
  - EKZ Dietikon, energia dinamica + rete 400D: media del giorno **24,23 Rp/kWh senza IVA** contro il totale ElCom H4 di **24,14 Rp**;
  - Groupe E Bulle, energia BASIC/STAR + rete Vario: rete Vario in media 9,4 Rp contro 11,7 Rp della tariffa unica;
  - CKW: l'API funziona (192 quarti d'ora, oggi e domani), ma il file statico delle tariffe risponde **403** al download automatico, quindi la tariffa non si può ancora scegliere. Inoltre CKW pubblica solo il tipo `integrated` (energia + rete + voci), che il modello di Corrente non gestisce ancora;
  - BKW: "Sonne Scheint" è dinamica solo dal 2027 e l'URL indicato oggi non accetta parametri: da riprovare a gennaio.
- **Voci nazionali con una rete dinamica o a due fasce:** il confronto con ElCom non può usare la tariffa scelta (non è a prezzo unico). Prima si usavano tutte le tariffe a prezzo unico del gestore, e per Groupe E una tariffa per aziende ("BT DUO") portava ad aggiungere di nuovo il supplemento di 2,3 Rp. Ora l'ordine è: la tariffa scelta se a prezzo unico, le tariffe standard, quelle della **stessa clientela** (stesso `customerType`, altrimenti stessa quota mensile), poi tutte. Groupe E: voci **incluse**.
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

### Stranezze dei file reali — da gestire nel lettore (v0.1)
Estratti reali in `tests/fixtures/ch/`.

0. **Una voce rotta non deve far perdere il file intero** (BKW, 8 ottobre 2026): date scritte come `2027-01-01T00:00:00` e comuni con numero `#N/A`. Il lettore prende solo la data e salta le voci illeggibili.

1. **Più voci sempre valide (00:00–00:00) si sommano.** In AIL "tìacqua" l'energia è 0,0975 più un supplemento verde di 0,006 CHF/kWh. Quando le voci sono fasce orarie distinte, ne vale una sola alla volta.
2. **AMB "Dinamica"** ha tre voci tutte 00:00–00:00 (codifica sbagliata delle fasce giornaliere). Sommarle sarebbe sbagliato: per Corrente è una tariffa **non supportata** finché AMB non pubblica le fasce.
3. **AIM è completo** (correzione del 6 ottobre: la prima analisi aveva letto solo 3 voci su 4). Rete HT lun–ven 8–20; NT 0–8 e 20–24 tutti i giorni, più sab–dom 8–20. Per sicurezza il lettore gestisce comunque eventuali buchi negli orari: usa il prezzo più basso e lo segnala.
4. **"23:59" vuol dire fine giornata** (lo dice la specifica); "00:00–00:00" vuol dire tutto il giorno.
5. **Raggruppare le tariffe di un prodotto non è uniforme:**
   - AIL usa prefisso più suffisso (`…-electricity`, `…-grid7`, `…-metering`, `…-regional_fees`);
   - AMB usa lo stesso nome per energia e rete ("Casa");
   - AIM usa "Tariffa PC Piccoli clienti - Energia / - Rete".
   → Nella configurazione l'utente sceglie **la tariffa dell'energia** e Corrente **propone** la tariffa di rete più simile, che l'utente conferma.
6. **Anni misti nello stesso file** (AIM): filtrare sempre per `startDate` / `endDate`.
7. **Prezzi senza IVA:** aggiungere l'IVA svizzera (8,1%). Secondo la specifica i supplementi nazionali (rete, art. 35 LEne, riserva) sono **già inclusi** nella tariffa di rete: non vanno aggiunti di nuovo. Da verificare sui totali ElCom: AIL 2027, energia 10,35 + rete 9,628 + tributi 2,22 + supplemento 2,3 = 25,911 secondo ElCom.
8. Le quote fisse (`base`, CHF/mese) e la tassa di misura vanno nei costi mensili, non nel prezzo al kWh.

### Prova dal vivo sul 2026 (6 ottobre 2026)
Per il 2026 ElCom ha spesso registrato **pagine web** invece dei file, perché l'obbligo del JSON è entrato in vigore con le tariffe 2027. Corrente prova in ordine:
1. il link dell'anno;
2. il link dell'anno successivo;
3. lo stesso link con l'anno sostituito.

Ogni file viene accettato solo se contiene tariffe valide oggi.

| Comune | Gestore | Risultato |
|---|---|---|
| Lugano | AIL | ✅ `…/prd/tariffs_2026` (anno sostituito) |
| Mendrisio | AIM | ✅ il file registrato per il 2027 contiene anche il 2026 |
| Massagno | AEM | ✅ `Tariffe_AEM_2026.json` (anno sostituito; il file 2027 è ancora 404) |
| Zurigo | ewz | ✅ file leggibile da macchina |
| Bellinzona | AMB | ❌ nessun file 2026: link manuale (dal 2027 c'è il file) |
| Locarno | SES | ❌ nessun file: link manuale |

### Voci nazionali: incluse o no? Dipende dal gestore (verificato il 7 ottobre 2026)
Confronto tra i file dei gestori e i totali ElCom (profilo H4, 4500 kWh/anno; ElCom mette il supplemento di rete di 2,3 Rp a parte e le altre voci nella "rete"):

| Gestore | Tariffa di rete nel file | Voci nazionali |
|---|---|---|
| AIL Lugano 2027 | 6,8 Rp + 8,55 CHF/mese = 9,08 | **escluse**: ElCom 9,628 = 9,08 + 0,55 (riserva, Swissgrid, costi solidali) |
| ewb Berna 2027 | 12,9 | **escluse** (stessa differenza di 0,55) |
| EKZ 2026, "400F" (case) | 10,53 | **incluse**: 7,95 lavoro + 0,27 Swissgrid + 2,3 supplemento (listino EKZ) |
| EKZ 2026, "400LS" (aziende) | 8,23 | uguale a ElCom senza supplemento |

Quindi Corrente **non** aggiunge più sempre le stesse voci. Per ogni gestore e anno confronta con ElCom tre ipotesi (nessuna inclusa / solo il supplemento da aggiungere / tutte incluse) e sceglie quella che torna. Usa in ordine: la tariffa di rete scelta dall'utente, la tariffa marcata standard dal gestore, tutte le tariffe a prezzo unico. Se ElCom non risponde aggiunge tutte le voci e lo segnala nell'attributo `federal_charges_checked_with_elcom`.

**Limite noto:** per EKZ "400F" riserva elettrica e costi solidali (circa 0,46 Rp nel 2026) potrebbero non essere né nel file né aggiunti da Corrente: errore massimo stimato intorno all'1,5%. Prima della correzione il prezzo EKZ era gonfiato di circa il 13% (voci contate due volte).

