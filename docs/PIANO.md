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
