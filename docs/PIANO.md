# Corrente — piano d'azione

> Documento vivo. Ultimo aggiornamento: 6 ottobre 2026.
> Chi lavora al progetto (anche una nuova sessione di Claude) legge questo file **prima** di fare qualsiasi cosa.

## 1. In una frase

**Corrente** è un'integrazione gratuita e open source per Home Assistant che porta **prezzi e tariffe
dell'elettricità di Italia e Svizzera** dentro la casa. Mostra quanto costa l'energia adesso, quando
conviene accendere gli elettrodomestici e quanto si è risparmiato.

## 2. Perché questo prodotto (in breve)

Viene dall'ascolto di mercato del 5–6 ottobre 2026: circa 47.000 post Reddit, il forum ufficiale,
il mercato italiano e svizzero e i venditori a pagamento.

- **Pannelli e dashboard generiche sono un campo saturo.** Da giugno 2026 escono decine di progetti
  quasi identici, molti fatti con l'AI. Lì non avremmo un vantaggio difendibile.
- **Svizzera:** le tariffe dinamiche (EKZ, CKW, BKW, Groupe E) hanno 4–5 integrazioni minuscole
  (0–3 stelle), ognuna per un solo fornitore. Per il **Ticino (AIL, AEM, SES) non esiste niente**.
- **Italia:** per il prezzo PUN esiste un'integrazione buona (pun_sensor, circa 150 stelle). Per il
  contatore **Chain2 / Open Meter** non c'è nessun progetto, e manca una guida italiana completa.
- **Il valore è concreto:** fa risparmiare soldi. Dal 2026 in Svizzera l'energia immessa in rete è
  pagata al prezzo di mercato trimestrale, sceso fino a circa 3 cent/kWh, mentre comprarla costa
  circa 27,7 cent/kWh. Consumare in casa al momento giusto vale molto.
- **Il nostro vantaggio:** lingua italiana, sede in Ticino, conoscenza di tariffe e bollette locali.

**Il compromesso, accettato:** il mercato è più piccolo (centinaia di utenti paganti, non migliaia),
ma possiamo diventare il riferimento nella nicchia.

## 3. Decisioni prese (6 ottobre 2026)

| # | Decisione | Scelta |
|---|---|---|
| 1 | Faccia pubblica | Repo sull'account personale **MichaelPito** (niente organizzazione). Il marchio è il nome del progetto, Corrente. Nessun dato personale oltre al nome utente GitHub. |
| 2 | Nome | **Corrente** (scelto da Claude, approvato dall'owner). Repo `ha-corrente`, dominio integrazione `corrente`. |
| 3 | Lingua | Codice e documentazione principale in **inglese**; interfaccia tradotta in IT/DE/FR/EN; guide anche in italiano. |
| 4 | Trasparenza AI | Si dichiara apertamente che il progetto è sviluppato con Claude. |
| 5 | Altri progetti | Snello, Beasts Off Duty e Jenny **restano attivi** (decisione dell'owner). |
| 6 | Donazioni | Link **Buy Me a Coffee** (`buymeacoffee.com/michaelpito`) su tutto il materiale gratuito, dal primo rilascio. |
| 7 | Suggerimenti | **Modulo per richiedere modifiche e suggerimenti** incluso nel prodotto (vedi §6). |

## 4. Il prodotto

### 4.1 Componenti
1. **Integrazione** (Python, custom component `corrente`, installabile da HACS)
   - Configurazione guidata dall'interfaccia, senza YAML: paese → fornitore/zona → tipo di contratto.
   - Sensori:
     - prezzo attuale;
     - fascia attuale (IT: F1/F2/F3; CH: alta/bassa tariffa o prezzo dinamico);
     - prossima finestra economica;
     - costo di oggi e del mese;
     - risparmio stimato.
   - Eventi e attributi pensati per le automazioni ("adesso conviene").
2. **Card per la dashboard** (Lovelace, JavaScript)
   - Prezzo adesso, linea delle prossime 24 ore, "momento migliore per accendere".
   - Discreta, leggibile anche da chi in casa non è appassionato.
3. **Blueprint di automazione**
   - Avvia lavatrice, lavastoviglie o boiler nella finestra più economica.
   - Usa l'eccedenza del fotovoltaico.
   - Avvisa quando il prezzo sale.
4. **Guide** (EN + IT, poi DE): installazione, scelta del contratto, contatore Chain2 / Open Meter,
   lettura del contatore svizzero.

### 4.2 Fonti di dati (tutte da verificare nella settimana 1)

| Paese | Fonte | Cosa | Stato |
|---|---|---|---|
| IT | GME (Gestore Mercati Energetici) | PUN Index / prezzi zonali orari e al quarto d'ora | Da verificare: termini d'uso, formato, stabilità |
| IT | Calendario | Fasce F1/F2/F3 con festività nazionali | Regole note: F1 lun–ven 8–19; F2 lun–ven 7–8 e 19–23, sab 7–23; F3 il resto, domeniche e festivi |
| IT | Contratto utente | Prezzo fisso, PUN + spread, prezzo per fascia | Inserito dall'utente nella configurazione |
| CH | ElCom (dati aperti) | Tariffe di tutti i gestori, per comune (Ticino incluso) | Da verificare: API/LINDAS, aggiornamento annuale |
| CH | EKZ, CKW, BKW / SmartGridready, Groupe E | Tariffe dinamiche (anche al quarto d'ora) | Da verificare: API pubbliche, chiavi, termini |
| CH | AIL, AEM, SES (Ticino) | Tariffe locali | Probabilmente solo da ElCom o pubblicate: da verificare |

Regola: **nessuna fonte non ufficiale o con termini che vietano il riuso.** Se una fonte manca,
la tariffa si può inserire a mano.

### 4.3 Cosa resta fuori (per ora)
- Lettura diretta dei contatori via hardware: per ora solo guide. Si valuta più avanti.
- Gas, acqua, altri paesi.
- Qualsiasi servizio cloud nostro: tutto gira in locale, in casa dell'utente.

## 5. Modello economico

1. **Gratis e open source:** integrazione, card, blueprint base, guide. Licenza MIT.
2. **Donazioni dal primo giorno:** link **Buy Me a Coffee** in README, pagine della documentazione,
   pulsante "Sponsor" di GitHub e un piccolo link discreto (disattivabile) nelle opzioni della card.
3. **Più avanti, solo se il progetto prende piede (da febbraio 2027):** abbonamento sostenitori
   **"Corrente Pro"** a 4–5 €/mese:
   - ottimizzazione automatica dei carichi;
   - report mensile dei risparmi;
   - temi della card;
   - assistenza prioritaria scritta.
4. **Link affiliati**, dichiarati, per l'hardware consigliato nelle guide (contatori, gateway, Shelly).

## 6. Modulo per richiedere modifiche e suggerimenti

Obiettivo: chiunque deve poter chiedere una modifica in meno di un minuto, anche senza essere
esperto. Le richieste diventano la roadmap pubblica.

1. **Moduli guidati su GitHub** (Issue Forms), già pronti in `.github/ISSUE_TEMPLATE/`:
   - 🐞 *Segnala un problema*: versione, paese, fornitore, cosa succede e cosa ti aspettavi;
   - 💡 *Suggerisci una modifica o un'idea*: cosa vorresti, perché, quanto è importante per te;
   - 🏷️ *Aggiungi il mio fornitore o la mia tariffa*: paese, gestore, comune, link alla tariffa.
2. **Link "Suggerisci una modifica" dentro il prodotto:** nelle opzioni dell'integrazione e nella card.
   Apre il modulo giusto già compilato con versione e paese.
3. **Modulo senza account GitHub** (dal lancio): un modulo web semplice (per esempio Tally) per chi non
   ha GitHub. Ogni risposta viene riportata da Claude come richiesta su GitHub, senza dati personali.
4. **Gestione:** ogni settimana una sessione automatica di Claude legge le richieste nuove, le
   etichetta (bug / idea / fornitore / domanda), risponde e aggiorna la roadmap. L'owner viene
   chiamato solo per decisioni di prodotto.
5. **Roadmap pubblica:** una sezione in `docs/ROADMAP.md`. Le idee più richieste salgono in cima.

## 7. Calendario

| Periodo | Cosa | Chi |
|---|---|---|
| **6–12 ott** | Repo creata; struttura del progetto; controlli automatici (hassfest, validazione HACS); verifica di tutte le fonti dati (§4.2). | Owner: 2 minuti per creare la repo. Claude: tutto il resto. |
| **13–26 ott** | Integrazione v0.1: Italia (PUN + fasce + contratto) e Svizzera (tariffe ElCom per tutti i gestori, Ticino incluso). Test automatici. | Claude |
| **27 ott – 2 nov** | Card v0.1, traduzioni IT/DE/FR/EN, guida di installazione, screenshot e GIF automatici. | Claude |
| **3–9 nov** | Test sulla casa dell'owner (circa 30 min, Home Assistant in macchina virtuale) e correzioni. Modulo senza account. | Owner: circa 30 min. Claude: correzioni. |
| **~17–20 nov** | **Lancio pubblico** v0.1: release su GitHub, richiesta di inserimento nello store HACS, post pronti da copiare (forum HA, r/homeassistant, Telegram inDomus, forum.fibra.click). | Owner: copia e incolla dei post (circa 10 min). Claude: tutto il resto. |
| **Dic – gen** | Una versione ogni 2 settimane. v0.2: tariffe dinamiche svizzere. v0.3: costo per apparecchio + guida Chain2 / Open Meter. v0.4: blueprint fotovoltaico e spostamento carichi. | Claude |
| **Feb 2027** | Se i numeri lo giustificano (§8): Corrente Pro e account pagamenti (Lemon Squeezy). | Owner: circa 45 min di account. Claude: il resto. |
| **Fine mar 2027** | **Punto di decisione**: raddoppiare, correggere o chiudere. | Insieme |

### Stato di avanzamento
- **6 ottobre 2026** (in anticipo sul calendario):
  - ✅ Italia: fasce F1/F2/F3 e contratti a prezzo fisso.
  - ✅ Svizzera v0.1 completa: comune → gestore via ElCom → file tariffe del gestore, fasce, voci nazionali, IVA, ricerca a cascata del file, link manuale, sensori, cambio d'anno automatico. Provata dal vivo su Lugano, Mendrisio, Massagno e Zurigo.
  - 68 test.
  - **Prossimi pezzi, in ordine:**
    1. card per la dashboard (prezzo ora, prossime 24 ore, momento migliore);
    2. sensore "prossima finestra economica" per Italia e Svizzera;
    3. guida di installazione e README completi con screenshot;
    4. PUN Index GME (dopo conferma dell'owner sulle regole d'uso, vedi FONTI-DATI);
    5. modifica delle tariffe svizzere dalle opzioni;
    6. tariffe dinamiche svizzere (v0.2).

- **7 ottobre 2026** (prima sessione automatica):
  - ✅ momento migliore per avviare (2 ore) e andamento del prezzo nelle prossime 36 ore;
  - ✅ card per la dashboard, caricata da sola dall'integrazione, provata in Chromium (screenshot in `docs/images`);
  - ✅ README completo e guida in italiano;
  - ✅ cambio di tariffa svizzera dalle opzioni;
  - ✅ costo di oggi e del mese dal contatore dell'utente;
  - ✅ durata dell'apparecchio scelta dall'utente; blueprint "avvia l'apparecchio al momento migliore";
  - ✅ **correzione**: voci nazionali svizzere verificate per gestore con ElCom (prima EKZ era gonfiato del 13% circa);
  - ✅ kit di lancio (`docs/LANCIO.md`);
  - 90 test.
  - ✅ **PUN** (decisione dell'owner nel pomeriggio: download GME come pun_sensor): contratti "PUN o zona + spread", prezzi al quarto d'ora di oggi e domani, un download al giorno; 102 test.
  - **Prossimi pezzi:**
    1. tariffe dinamiche svizzere (v0.2), con la stessa verifica delle voci nazionali;
    2. icona e logo per l'elenco ufficiale (repo `home-assistant/brands`);
    3. modulo per le richieste senza account GitHub;
    4. versione v0.1.0 e note di rilascio.

- **8 ottobre 2026** (sessione automatica; git sbloccato dall'owner a metà mattina):
  - ✅ **tariffe dinamiche svizzere** (in anticipo: erano previste per dicembre) dalle API dei gestori, formati 2026 e 2027; provate dal vivo con EKZ (media del giorno a 0,1 Rp dal totale ElCom) e Groupe E;
  - ✅ **correzione**: voci nazionali per Groupe E con rete dinamica o a due fasce (prima +2,3 Rp di troppo);
  - ✅ **correzione**: il file BKW (date con l'ora, comuni "#N/A") faceva fallire la lettura di tutte le tariffe BKW;
  - ✅ link "Suggerisci una modifica" nelle opzioni e nella card, con la fonte dei dati in fondo alla card (per il GME è un obbligo); screenshot aggiornati;
  - ✅ icona e logo dentro l'integrazione (cartella `brand/`): da Home Assistant 2026.3 non serve più la richiesta al repo `home-assistant/brands`, quindi una azione in meno per l'owner;
  - 130 test.
  - ✅ modulo per chi non ha GitHub: creato dall'owner con lo script, collegato a README, guida e scelta delle richieste; le risposte si leggono ogni giorno (`docs/MODULO.md`);
  - ✅ **v0.1.0 pubblicata** (release su GitHub con note e `corrente.zip`, avviata da Claude con il pulsante "Run workflow" su richiesta dell'owner: «sì, avviala tu»): versione unica nel codice (test che la confronta con il manifest e il changelog), note di rilascio, release automatica dal tag con lo zip; test anche su Home Assistant 2025.10 (il minimo dichiarato), ora anche su GitHub;
  - 132 test.
  - ✅ **test a casa preparato** (`docs/TEST-A-CASA.md`: VirtualBox, copia di Corrente con Samba, domande, blueprint facoltativo) e **prova generale** di Claude su un Home Assistant vero con interfaccia web e dati reali (Lugano, AIL dinamica, Italia bioraria, PUN). Corretti:
    - la tariffa "dinamica" di AIL rimanda a una pagina web: ora il messaggio dice proprio questo, invece di "riprova più tardi";
    - il prezzo fisso che AIL scrive sulla tariffa dinamica non si somma più a quello dell'API;
    - nomi più corti: "Corrente Lugano" invece della ragione sociale del gestore (`sensor.corrente_lugano_prezzo_attuale`);
  - 134 test.
  - **Prossimi pezzi:**
    1. versione v0.1.1 con queste correzioni, prima del test a casa (in attesa dell'ok dell'owner, chiesto l'8 ottobre);
    2. CKW: tipo `integrated` e file delle tariffe (oggi risponde 403).

- **9 ottobre 2026** (sessione automatica):
  - nessuna richiesta nuova (GitHub e modulo);
  - CKW: il 403 è la verifica anti-bot di Cloudflare; non la aggiriamo (`FONTI-DATI.md`), CKW resta fuori finché non lascia libero il file;
  - ✅ **blueprint "avviso sul prezzo"** (sotto o sopra una soglia, qualsiasi azione), provato in Home Assistant nei test;
  - ✅ **guida "i tuoi consumi in Home Assistant"** (`docs/meter.md`, riassunto nella guida italiana): pinza, Chain 2 / Open Meter, interfaccia cliente svizzera; solo fatti verificati su fonti ufficiali (affermazioni su CKW e Areti tolte perché non verificabili);
  - ✅ card: la riga della fonte ElCom nella lingua di chi guarda (quella del GME resta com'è, la chiedono le sue condizioni);
  - 137 test.
  - ✅ **pagina di stato** per l'owner: <https://claude.ai/artifact/9nKRSNAPchwgitzGPuEMp8> (aggiornata alla fine di ogni sessione);
  - **Prossimi pezzi:**
    1. ✅ v0.1.1 pubblicata il 9 ottobre (ok dell'owner: «sì, pubblica la 0.1.1»);
    2. ✅ blueprint "usa il surplus del fotovoltaico" (12 ottobre, su richiesta dell'owner: «ok, vai avanti con il blueprint del fotovoltaico»);
    3. costo per apparecchio (v0.3).

- **12 ottobre 2026**:
  - ✅ **blueprint "usa il surplus del fotovoltaico"**: acceso quando i pannelli mandano in rete almeno la potenza dell'apparecchio, spento quando la casa torna a comprare; attesa contro le nuvole; sensore in W o kW, con entrambi i segni; facoltativo anche nelle ore a prezzo basso, senza spegnersi per mancanza di sole. Provato in Home Assistant nei test (nuvola passeggera, kW positivi, ore economiche);
  - ✅ **costo per apparecchio** (su richiesta dell'owner: «ok, vai avanti con il costo per apparecchio»): nelle opzioni si scelgono i sensori di energia degli apparecchi con un contatore proprio (prese intelligenti); per ognuno "Costo di oggi — nome" e "Costo del mese — nome", nome preso dalla presa; togliendo l'apparecchio dall'elenco i sensori spariscono. EN/IT/DE/FR;
  - 142 test, anche su Home Assistant 2025.10.
  - **Prossimi pezzi:**
    1. ✅ testi e lista di controllo del lancio aggiornati (`LANCIO.md`): versione 0.2.0, data 17 novembre, post EN/IT con tariffe dinamiche, tre blueprint, costo per apparecchio e modulo;
    2. ✅ v0.2.0 pubblicata il 12 ottobre (ok dell'owner: «sì, pubblica la 0.2.0»);
    3. ✅ screenshot della card in inglese per i post (13 ottobre: `card-ekz-dynamic-en.png`, `card-lugano-en.png`, fatti con la card attuale);
    4. test a casa dell'owner a inizio novembre (`TEST-A-CASA.md`), correzioni come v0.2.x.

- **13 ottobre 2026** (sessione automatica):
  - nessuna richiesta nuova (GitHub e modulo);
  - ✅ screenshot della card in inglese per i post del lancio;
  - ✅ **Home Assistant 2026.10.1** (uscito questo mese, richiede Python 3.14): tutti i test passano, e una prova vera con interfaccia web e dati reali (Lugano, Italia bioraria, PUN) funziona; da oggi GitHub prova ogni modifica su 2026.10 oltre che su 2025.10;
  - ✅ **correzione importante**, trovata nella prova vera: con due o più configurazioni di Corrente (per esempio Svizzera e Italia), dopo un riavvio ne partiva solo una e le altre davano "Impostazione non riuscita". C'era dalla 0.1.0; nessun test lo copriva perché i test aggiungevano una configurazione alla volta. Corretto e coperto da un test nuovo;
  - 143 test, su Home Assistant 2025.10, 2026.2 e 2026.10.
  - **Prossimi pezzi:**
    1. ✅ v0.2.1 pubblicata il 13 ottobre (ok dell'owner: «sì, pubblica la 0.2.1»);
    2. test a casa dell'owner a inizio novembre (`TEST-A-CASA.md`).

- **13 ottobre 2026, pomeriggio** (owner: «ok, vai avanti»):
  - prova di tutte le configurazioni su Home Assistant 2026.10 vero, questa volta con un gestore nuovo: **ewz (Zurigo città e villaggi dei Grigioni)**. Trovati e corretti quattro errori:
    1. Zurigo città: prezzo di circa **3,3 Rp/kWh troppo alto** (+11%): ewz include già le voci nazionali e Corrente le aggiungeva; il controllo con ElCom ora funziona anche con sole tariffe di rete giorno/notte;
    2. la domenica intera (finestra a sé nel file ewz) si sommava alla tariffa notturna;
    3. la tariffa notturna partiva un minuto prima (ewz scrive "06:00–21:59");
    4. i **suggerimenti nella configurazione**: a Zurigo venivano proposti rete e tributi di un villaggio dei Grigioni, a EKZ una rete per aziende (e non la rete dinamica con l'energia dinamica). Ora la proposta usa i dati del file (dinamica, clientela, comune o cantone, tariffa standard) e i tributi del proprio comune;
  - controllato che AIL, AIM, AMB e Groupe E restano come prima (stessi suggerimenti, stessi prezzi);
  - ✅ **prova con i gestori delle città più grandi** (ewz, EKZ, SIG, SiL, ewb, San Gallo, Winterthur, OIKEN, Viteos, Groupe E), confrontando il prezzo con il totale ElCom: ora tutti entro circa ±1,5 Rp. Corretti: San Gallo (rete contata due volte), Losanna (5 tributi su 6 mancanti), suggerimenti controllati con i dati ElCom; i tributi possono essere più d'uno. Limite noto: Losanna tariffa DUO (vedi `FONTI-DATI.md`);
  - ✅ **EKZ**: la tariffa standard per le case ("Erneuerbar", prezzo d'inverno e d'estate) non si poteva scegliere ("mancano le finestre orarie"), dalla 0.1.0: un controllo pensato per un file AMB difettoso la scartava. Corretto;
  - 167 test, su Home Assistant 2025.10, 2026.2 e 2026.10.
  - **Prossimi pezzi:**
    1. versione v0.2.2 con queste correzioni: **serve l'ok dell'owner** (non tocca il test a casa in Ticino, ma Zurigo è il comune più grande);
    2. stessa prova con altri gestori (BKW, Romande Energie, Groupe E per comune, CKW e IWB appena il file è leggibile);
    3. GIF della configurazione per README e post.

- **14 ottobre 2026** (sessione automatica):
  - nessuna richiesta nuova (GitHub e modulo);
  - ✅ **prova estesa**: 31 gestori e comuni in 22 cantoni confrontati voce per voce con ElCom (energia, rete, tributi). Tributi ora entro 0,3 Rp in tutti i 32 casi, rete entro circa 0,5 Rp. Corretti: Thun (voci nazionali due volte), BKW (tributi non trovati), Svitto ed ebs/Mendrisio AIM (voci nazionali mancanti, ~3 Rp), Winterthur (due fasce sommate), Yverdon (tributo in CHF invece che Rp), Obwaldo (tributi cantonali), Losanna DUO (risolto). Dettagli in `FONTI-DATI.md`;
  - 179 test, su Home Assistant 2025.10, 2026.2 e 2026.10.
  - **Prossimi pezzi:**
    1. versione v0.2.2 con tutte le correzioni svizzere del 13 e 14 ottobre: **serve l'ok dell'owner** (chiesto il 13 ottobre);
    2. GIF della configurazione per README e post;
    3. gestori senza file leggibile: ricontrollare a dicembre (file 2027).

- **15 ottobre 2026** (sessione automatica):
  - nessuna richiesta nuova (GitHub e modulo);
  - ✅ **GIF della configurazione** (`docs/images/setup.gif`, 26 s, in inglese): Home Assistant 2026.10 vero, dati reali, Zurigo dall'aggiunta dell'integrazione alla card; nel README e nel kit di lancio;
  - ✅ la configurazione propone già la tariffa d'energia standard del gestore, se il file la indica (ewz.natur); prima la prima in ordine alfabetico;
  - trovato registrando: dopo la prima configurazione la card compare solo **ricaricando la pagina** (il browser carica le card all'apertura). Scritto nel README, nella guida italiana e nella guida del test a casa;
  - 186 test.
  - **Prossimi pezzi:**
    1. ✅ v0.2.2 pubblicata il 15 ottobre (ok dell'owner: «Si», in risposta alla richiesta di pubblicarla);
    2. gestori senza file leggibile: ricontrollare a dicembre (file 2027);
    3. Home Assistant 2026.11 beta (fine ottobre): prova come per la 2026.10.

- **16 ottobre 2026** (sessione automatica):
  - nessuna richiesta nuova (GitHub e modulo);
  - ✅ **Italia verificata**: i prezzi PUN e zonali letti da Corrente (al quarto d'ora) coincidono esattamente con i prezzi orari pubblicati dal GME (96 ore × 3 zone, differenza 0); il cambio d'ora del 25 ottobre è già coperto da test;
  - ✅ **revisione del codice della 0.2.2**: 10 problemi trovati, tutti corretti con un test (9 casi falliscono sul codice di prima). Nessuno visto con i gestori provati finora; il confronto con ElCom resta 32 casi su 32;
  - 200 test, su Home Assistant 2025.10, 2026.2 e 2026.10.
  - **Prossimi pezzi:**
    1. versione v0.2.3 con queste correzioni: serve l'ok dell'owner (non urgente: si può unire alle correzioni del test a casa);
    2. Home Assistant 2026.11 beta (fine ottobre): prova come per la 2026.10;
    3. gestori senza file leggibile: ricontrollare a dicembre (file 2027).

- **19 ottobre 2026** (sessione automatica):
  - nessuna richiesta nuova (GitHub e modulo);
  - ✅ **Home Assistant 2026.10.2** (uscito il 17 ottobre): tutti i test passano; da oggi GitHub prova ogni modifica su questa versione;
  - ✅ **cambio d'ora svizzero** (25 ottobre e 28 marzo): le fasce giorno/notte restano all'ora giusta e durano le ore vere (Zurigo: notte del sabato fino a lunedì 06:00 = 33 ore). Funzionava già; ora è coperto da due test;
  - 16 ottobre: guida del test a casa adattata al laptop dell'owner (sua scelta: test sul laptop);
  - 202 test, su Home Assistant 2025.10 e 2026.10.
  - **Prossimi pezzi:**
    1. versione v0.2.3: serve l'ok dell'owner (non urgente: si può unire alle correzioni del test a casa);
    2. Home Assistant 2026.11 beta (fine ottobre): prova come per la 2026.10;
    3. gestori senza file leggibile: ricontrollare a dicembre (file 2027).

## 8. Numeri di controllo

Le installazioni si misurano con le statistiche pubbliche di Home Assistant (analytics.home-assistant.io,
solo utenti che le condividono, quindi sono una stima per difetto) e con le stelle e i download su GitHub.

| Quando | Obiettivo | Se non ci arriviamo |
|---|---|---|
| 8 settimane dopo il lancio (metà gennaio) | Almeno 50 stelle **e** almeno 100 installazioni rilevate | Sotto le 25 stelle: si rivede il prodotto o si chiude |
| Fine febbraio | Almeno 150 stelle **o** almeno 400 installazioni | Niente Corrente Pro, si rivaluta |
| 2 mesi dopo Corrente Pro | Almeno il 3% degli utenti attivi paga | Sotto l'1%: si rivede l'offerta |
| Sempre | Le donazioni sono un segnale, non un obiettivo | — |

## 9. Ruoli

### Cosa fa Claude (tutto il resto)
- Codice, test, rilasci, compatibilità con ogni nuova versione di Home Assistant (beta testata prima
  dell'uscita).
- Documentazione, guide, traduzioni, screenshot e GIF.
- Richieste su GitHub: lettura, etichette, risposte (firmate come generate da Claude Code).
- Richiesta di inserimento nello store HACS.
- Testi pronti per ogni post nelle community.
- Questo piano e il registro delle decisioni (`docs/DECISIONI.md`), sempre aggiornati nella repo.

### Quando serve l'owner (elenco completo)

| Quando | Cosa | Tempo |
|---|---|---|
| Ora | Creare la repo `ha-corrente` sul proprio account GitHub e dare accesso all'app Claude | 2 min |
| Inizio novembre | Test a casa (Home Assistant in macchina virtuale) | 30 min |
| Lancio + ogni rilascio importante | Copiare e incollare i post preparati nelle community | 2 min a post, 3–5 post in tutto |
| Febbraio 2027 (se si va avanti) | Account pagamenti per Corrente Pro | 30–60 min |
| Una volta l'anno | Dichiarare i redditi in Svizzera | — |
| Quando Claude chiede | Decisioni di prodotto non ovvie | — |

## 10. Come lavora Claude (continuità)

- **La repo è la memoria.** Ogni sessione parte leggendo `CLAUDE.md`, questo piano e `docs/DECISIONI.md`.
  Niente resta solo nella chat.
- **Sessioni automatiche programmate** (con l'ok dell'owner):
  - **ogni lunedì:** controllo delle richieste nuove, risposte, aggiornamento della roadmap;
  - **una settimana prima di ogni versione mensile di Home Assistant:** test sulla beta;
  - all'owner arriva un messaggio **solo** se serve una sua decisione.
- **Ogni modifica** passa da un ramo dedicato, controlli automatici verdi, poi `main`. I rilasci pubblici
  hanno numero di versione e note.

## 11. Rischi e risposte

| Rischio | Risposta |
|---|---|
| Diffidenza della community verso i progetti fatti con l'AI | Trasparenza dichiarata, test automatici seri, risposte rapide alle richieste. |
| Fonti dati che cambiano o chiudono | Più fonti dove possibile, inserimento manuale come riserva, controlli automatici giornalieri sui formati. |
| Nicchia troppo piccola | Numeri di controllo e punto di decisione a fine marzo; poi si possono aggiungere altri paesi (Germania, Austria) con la stessa architettura. |
| Home Assistant migliora la sua parte energia | Puntiamo su ciò che il progetto ufficiale non fa: tariffe locali italiane e svizzere, fasce, contratti. |
| Concorrenza di pun_sensor in Italia | Non lo copiamo: Corrente può anche usarlo come fonte e aggiunge fasce, contratti, costi e Svizzera. Se ha senso, si collabora. |
