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

⏳ In verifica: dati aperti ElCom, orari di alta e bassa tariffa dei gestori ticinesi, API delle tariffe dinamiche (EKZ, CKW, BKW / SmartGridready, Groupe E).
