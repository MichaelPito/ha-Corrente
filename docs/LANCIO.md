# Kit di lancio (bozza — metà novembre 2026)

> Preparato da Claude. L'owner deve solo **copiare e incollare** i post nel giorno indicato. Tutto il resto lo fa Claude.

## Lista di controllo per il giorno del lancio

| # | Cosa | Chi | Stato |
|---|---|---|---|
| 1 | Versione v0.1.0 con note di rilascio | Claude | ⏳ |
| 2 | Repo da privata a **pubblica** (Settings → General → Danger zone → Change visibility) | **Owner**, 1 min | ⏳ |
| 3 | Descrizione della repo e topic (`home-assistant`, `hacs`, `hacs-integration`, `energy`, `electricity-prices`, `switzerland`, `italy`, `ticino`) — Settings → General / About | **Owner**, 1 min (testo qui sotto) | ⏳ |
| 4 | Il controllo HACS si riattiva da solo con la repo pubblica: verifica verde | Claude | ⏳ |
| 5 | Icona e logo: dentro l'integrazione (cartella `brand/`, letta da Home Assistant 2026.3 e successivi), nessuna richiesta esterna | Claude | ✅ 8 ottobre |
| 6 | Richiesta di inserimento nello store HACS (`hacs/default`) | Claude prepara, **owner** approva | ⏳ |
| 7 | Post nelle community (testi qui sotto) | **Owner**, copia e incolla, circa 10 min | ⏳ |
| 8 | Modulo per chi non ha GitHub: Google Form creato da uno script (`docs/MODULO.md`), nessun account nuovo | Claude prepara ✅, **owner** esegue lo script una volta (circa 3 min) | ✅ 8 ottobre |

**Descrizione della repo (punto 3):**
> Your real electricity price in Home Assistant and the best time to switch things on — Italy (F1/F2/F3) and Switzerland (every grid operator via ElCom, Ticino included).

## Post 1 — Forum ufficiale di Home Assistant (categoria "Share your Projects!", in inglese)

**Titolo:** Corrente — real electricity prices for Switzerland 🇨🇭 and Italy 🇮🇹, with the best time to start your appliances

**Testo:**

> Hi everyone! I'd like to share **Corrente**, a free and open-source integration that brings your *real* electricity price into Home Assistant.
>
> **Switzerland:** type your municipality, and Corrente finds your grid operator in ElCom's open data and reads the tariff file every operator must publish. High/low tariff windows, cantonal and municipal fees, federal charges and VAT are all included, and checked against ElCom's totals. It works for most operators, Ticino included — and with **dynamic tariffs** (EKZ, Groupe E) it reads the quarter-hour prices from the operator's own API.
>
> **Italy:** F1/F2/F3 time bands following ARERA's rules (holidays included) and your contract (monoraria, bioraria, trioraria), or a **PUN-indexed** contract with the quarter-hour prices published by GME.
>
> What you get:
> - price now, next change, next price;
> - **best time to start** an appliance (you choose how long it runs);
> - **cost today / this month** from your energy meter, each kWh priced when it was used;
> - a dashboard card (screenshot) and a blueprint to start the dishwasher at the cheapest time.
>
> Everything is set up from the UI, no YAML, and computed locally.
>
> **Transparency:** Corrente is developed with the help of AI (Claude) and tested against real tariff files. Feedback is very welcome — there's a form for requests, including "add my operator / tariff".
>
> GitHub: https://github.com/MichaelPito/ha-corrente

## Post 2 — r/homeassistant (in inglese, flair "Personal Setup" o "Share")

**Titolo:** I made a free integration that shows your real Swiss/Italian electricity price and when it's cheapest to run the dishwasher

**Testo:** versione breve del post 1, più la GIF o lo screenshot della card. Dichiarare subito che è sviluppato con l'AI.

## Post 3 — Telegram inDomus e forum.fibra.click (in italiano)

> Ciao a tutti! Ho pubblicato **Corrente**, un'integrazione gratuita per Home Assistant che porta il vero prezzo della luce in casa.
>
> 🇮🇹 **Italia:** fasce F1/F2/F3 secondo ARERA (festivi inclusi) e il tuo contratto (monoraria, bioraria, trioraria), oppure un contratto **indicizzato al PUN** con i prezzi al quarto d'ora pubblicati dal GME.
> 🇨🇭 **Svizzera / Ticino:** scrivi il tuo comune e Corrente trova il gestore (AIL, AIM, AEM…) e le sue tariffe ufficiali.
>
> Ti dice anche **quando conviene avviare** lavastoviglie o lavatrice, quanto hai **speso oggi e nel mese**, e c'è una card per la dashboard.
> Si configura tutto dall'interfaccia, senza YAML. Guida in italiano: https://github.com/MichaelPito/ha-corrente/blob/main/docs/guida-it.md
>
> È sviluppato con l'aiuto dell'AI e ogni suggerimento è benvenuto!

## Dopo il lancio
- Claude risponde alle richieste su GitHub ogni giorno (sessione automatica delle 8:52).
- Dopo 8 settimane: controllo dei numeri (PIANO §8).
