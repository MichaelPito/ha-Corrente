# Kit di lancio (bozza — metà novembre 2026)

> Preparato da Claude. L'owner deve solo **copiare e incollare** i post nel giorno indicato. Tutto il resto lo fa Claude.
>
> **Versione da lanciare:** l'ultima 0.2.x (oggi la 0.2.6, 21 ottobre), con le correzioni del test a casa di inizio novembre.
> **Data:** martedì 17 novembre 2026 (finestra 17–20). Testi aggiornati il 22 ottobre: verifica con ElCom su tutti i gestori svizzeri (0.2.3–0.2.6).

## Lista di controllo per il giorno del lancio

| # | Cosa | Chi | Stato |
|---|---|---|---|
| 0 | Test a casa dell'owner con la sua tariffa (`docs/TEST-A-CASA.md`), inizio novembre | **Owner**, circa 45 min | ⏳ |
| 1 | Versione con note di rilascio (`CHANGELOG.md`, release da GitHub Actions) | Claude | ✅ v0.1.0 l'8 ottobre … v0.2.6 il 21; le correzioni del test a casa escono come v0.2.x |
| 2 | Repo da privata a **pubblica** (Settings → General → Danger zone → Change visibility) | **Owner**, 1 min | ⏳ |
| 3 | Descrizione della repo e topic (`home-assistant`, `hacs`, `hacs-integration`, `energy`, `electricity-prices`, `switzerland`, `italy`, `ticino`) — Settings → General / About | **Owner**, 1 min (testo qui sotto) | ⏳ |
| 4 | Il controllo HACS si riattiva da solo con la repo pubblica: verifica verde | Claude | ⏳ |
| 5 | Icona e logo: dentro l'integrazione (cartella `brand/`, letta da Home Assistant 2026.3 e successivi), nessuna richiesta esterna | Claude | ✅ 8 ottobre |
| 6 | Richiesta di inserimento nello store HACS (`hacs/default`): una riga `MichaelPito/ha-corrente` nel file `integration`, in ordine alfabetico; serve la repo pubblica con release, descrizione e topic | Claude prepara, **owner** approva | ⏳ |
| 7 | Post nelle community (testi qui sotto), con uno screenshot da `docs/images/` (o la GIF della configurazione `docs/images/setup.gif`, 26 s, per il forum e Reddit): `prova-dashboard-it.png` per i post in italiano, `card-ekz-dynamic-en.png` (tariffa dinamica EKZ, in inglese) per quelli in inglese; in alternativa `card-lugano-en.png` | **Owner**, copia e incolla, circa 10 min | ⏳ |
| 8 | Modulo per chi non ha GitHub: Google Form creato da uno script (`docs/MODULO.md`), nessun account nuovo | Claude prepara ✅, **owner** esegue lo script una volta (circa 3 min) | ✅ 8 ottobre |
| 9 | Il giorno del lancio: README, guida italiana e link del modulo ricontrollati sulla repo pubblica; nessuna richiesta aperta senza risposta | Claude | ⏳ |

**Descrizione della repo (punto 3):**
> Your real electricity price in Home Assistant and the best time to switch things on — Italy (F1/F2/F3) and Switzerland (your grid operator found via ElCom's open data, Ticino included).

## Post 1 — Forum ufficiale di Home Assistant (categoria "Share your Projects!", in inglese)

**Titolo:** Corrente — real electricity prices for Switzerland 🇨🇭 and Italy 🇮🇹, with the best time to start your appliances

**Testo:**

> Hi everyone! I'd like to share **Corrente**, a free and open-source integration that brings your *real* electricity price into Home Assistant.
>
> **Switzerland:** type your municipality, and Corrente finds your grid operator in ElCom's open data and reads the tariff file every operator must publish. High/low tariff windows, cantonal and municipal fees, federal charges and VAT are all included, and checked against ElCom's figures for your municipality. Before release I compared it with ElCom for every Swiss operator that publishes a readable tariff file (about 340 of 535): the grid price matches within 0.6 Rp/kWh for 95% of them, and fees missing from an operator's file are taken from ElCom. It works for most operators, Ticino included — and with **dynamic tariffs** (EKZ, Groupe E) it reads the quarter-hour prices from the operator's own API.
>
> **Italy:** F1/F2/F3 time bands following ARERA's rules (holidays included) and your contract (monoraria, bioraria, trioraria), or a **PUN-indexed** contract with the quarter-hour prices published by GME. Optionally add the other costs from your bill (transport, system charges, excise, fixed charges) to get the whole price, not only the energy part.
>
> What you get:
> - price now, next change, next price, and the fixed charges per month (in Switzerland grid fee and metering included);
> - **best time to start** an appliance (you choose how long it runs);
> - **cost today / this month** from your energy meter, each kWh priced when it was used — and **per appliance**, if it has its own meter (smart plug);
> - a dashboard card (screenshot);
> - three blueprints: start the dishwasher at the cheapest time, a **price alert** (below or above a threshold), and **use your solar surplus** (switch the boiler or the car charger on when the panels export enough power, off when the home buys from the grid again).
>
> Everything is set up from the UI, no YAML. Every Home Assistant downloads its own data from the official sources (ElCom, the operators, GME): no Corrente server, no account, no telemetry.
>
> **Transparency:** Corrente is developed with the help of AI (Claude) and tested against real tariff files. Feedback is very welcome: open an issue on GitHub (if a price looks wrong, attach the diagnostics file: it shows every tariff and figure Corrente used), or use the form if you don't have a GitHub account (e.g. "add my operator / tariff"): https://docs.google.com/forms/d/e/1FAIpQLSce_vFvHpz3Qav3o05DvoJhpIuM2zXWmvpgBHWRS1gJsEF6yQ/viewform
>
> GitHub: https://github.com/MichaelPito/ha-corrente

## Post 2 — r/homeassistant (in inglese, flair "Personal Setup" o "Share")

**Titolo:** I made a free integration that shows your real Swiss/Italian electricity price and when it's cheapest to run the dishwasher

**Testo:** (con lo screenshot della card)

> Corrente is a free, open-source Home Assistant integration (HACS) for Switzerland and Italy. Swiss users type their municipality and get their grid operator's real tariff (high/low windows, fees, federal charges, VAT; dynamic quarter-hour prices for EKZ and Groupe E), checked against ElCom's figures for about 340 operators. Italian users get the F1/F2/F3 bands or PUN-indexed prices from GME, plus the other costs from their bill if they want the whole price.
>
> It shows the price now and the next change, the best time to start an appliance, what you spent today and this month (also per appliance), and comes with blueprints for cheap-hour starts, price alerts and solar surplus.
>
> Upfront: it's developed with the help of AI (Claude), and tested against real tariff files. Feedback welcome!
>
> https://github.com/MichaelPito/ha-corrente

## Post 3 — Telegram inDomus e forum.fibra.click (in italiano)

> Ciao a tutti! Ho pubblicato **Corrente**, un'integrazione gratuita per Home Assistant che porta il vero prezzo della luce in casa.
>
> 🇮🇹 **Italia:** fasce F1/F2/F3 secondo ARERA (festivi inclusi) e il tuo contratto (monoraria, bioraria, trioraria), oppure un contratto **indicizzato al PUN** con i prezzi al quarto d'ora pubblicati dal GME. Se vuoi, aggiungi gli altri costi della bolletta (trasporto, oneri di sistema, accise, quote fisse) per avere il prezzo intero e non solo l'energia.
> 🇨🇭 **Svizzera / Ticino:** scrivi il tuo comune e Corrente trova il gestore (AIL, AIM, AEM…) e le sue tariffe ufficiali, con tasse e IVA. Prima del lancio l'ho confrontato con i dati ElCom di circa 340 gestori svizzeri: i prezzi tornano.
>
> Ti dice anche **quando conviene avviare** lavastoviglie o lavatrice, quanto hai **speso oggi e nel mese** (anche per singolo apparecchio, se ha una presa intelligente), e c'è una card per la dashboard.
> Ci sono tre blueprint pronti: avvio all'ora più economica, **avviso sul prezzo** e **uso del surplus del fotovoltaico** (accende boiler o auto quando i pannelli mandano corrente in rete).
> Si configura tutto dall'interfaccia, senza YAML, e i dati arrivano direttamente dalle fonti ufficiali: nessun server, nessun account. Guida in italiano: https://github.com/MichaelPito/ha-corrente/blob/main/docs/guida-it.md
>
> È sviluppato con l'aiuto dell'AI e ogni suggerimento è benvenuto! Chi non ha un account GitHub può scrivere qui: https://docs.google.com/forms/d/e/1FAIpQLSce_vFvHpz3Qav3o05DvoJhpIuM2zXWmvpgBHWRS1gJsEF6yQ/viewform

## Prima del lancio (controllo di Claude, settimana del 9 novembre)
- AEM Massagno: il link 2027 registrato presso ElCom risponde 404 (controllato il 23 ottobre; il file 2026 funziona). Se manca ancora, togliere "AEM" dagli esempi del post in italiano e del README, o lasciarlo se il file 2026 basta fino al 31 dicembre (Corrente avvisa con una segnalazione in Riparazioni quando il file dell'anno nuovo manca).

## Dopo il lancio
- Claude risponde alle richieste su GitHub e del modulo ogni giorno feriale (sessione automatica delle 8:52); le risposte pubbliche portano la firma di Claude Code.
- La prima settimana: le correzioni urgenti escono subito come versioni 0.3.x (Claude le pubblica da sé: autorizzazione dell'owner del 20 ottobre; l'ok serve solo per cancellare).
- Dopo 8 settimane: controllo dei numeri (PIANO §8).
