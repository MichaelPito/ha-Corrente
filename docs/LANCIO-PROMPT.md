# Prompt per Claude in Chrome — giorno del lancio

> Regola del progetto (owner, 8 novembre 2026, in `CLAUDE.md`): quello che può fare Claude in Chrome lo fa Claude in Chrome. L'owner apre questo file su GitHub, copia **un prompt alla volta** in Claude in Chrome (nel suo browser, dove è già collegato a GitHub e ai forum) e incolla il **resoconto** nella chat con Claude Code.
>
> Ordine nel giorno del lancio (`docs/LANCIO.md`): **A** e **B** prima; poi Claude Code toglie `ignore` dal controllo HACS, aspetta i controlli verdi e pubblica la versione; poi **C**; poi **D**, un post alla volta.
>
> Restano all'owner solo: la conferma finale per rendere pubblica la repo (GitHub può chiedere password o codice), il **sì** prima di ogni pubblicazione, e allegare un'immagine se Claude in Chrome non riesce a farlo.

---

## A — Descrizione e topic della repo

```text
Lavori per conto di Domenico (owner della repo GitHub MichaelPito/ha-corrente), su richiesta di Claude Code, che sviluppa il progetto. Sei già collegato a GitHub come MichaelPito.

REGOLE (valgono per tutto il compito):
- Non mostrare, copiare o rigenerare segreti, token o codici.
- Non cancellare nulla. Non cambiare impostazioni che non sono in questo prompt.
- Nessun costo o pagamento. Non pubblicare, non inviare e non invitare nessuno.
- Se un controllo non torna, FERMATI e dimmelo, senza correggere da solo.

PASSI:
1. Apri https://github.com/MichaelPito/ha-corrente. Controllo: la pagina è della repo «ha-corrente» (GitHub può scriverlo «ha-Corrente») di MichaelPito. Se non lo è, fermati.
2. Nella colonna a destra, accanto ad «About», premi l'ingranaggio.
3. In «Description» scrivi esattamente:
   Your real electricity price in Home Assistant and the best time to switch things on — Italy (F1/F2/F3) and Switzerland (your grid operator found via ElCom's open data, Ticino included).
4. In «Topics» aggiungi, uno per uno: home-assistant, hacs, hacs-integration, energy, electricity-prices, switzerland, italy, ticino. Lascia i topic che ci sono già.
5. Lascia vuoto «Website» e non toccare le caselle sotto. Premi «Save changes».
6. Controllo: ricarica la pagina e verifica che descrizione e topic compaiano nella colonna «About».

RESOCONTO FINALE (scrivilo così):
- Descrizione salvata: sì/no (testo che vedi)
- Topic visibili: (elenco)
- Problemi: (nessuno, oppure cosa è successo e dove ti sei fermato)
```

## B — Rendere pubblica la repo

```text
Lavori per conto di Domenico (owner della repo GitHub MichaelPito/ha-corrente), su richiesta di Claude Code. Sei già collegato a GitHub come MichaelPito. Oggi è il giorno del lancio e Domenico ha deciso di rendere pubblica la repo.

REGOLE:
- Non mostrare, copiare o rigenerare segreti, token o codici. Password e codici di verifica li inserisce solo Domenico.
- Non cancellare nulla, non archiviare, non trasferire, non rinominare la repo.
- Cambia SOLO la visibilità. Nessun'altra impostazione.
- Se un controllo non torna, FERMATI e dimmelo.

PASSI:
1. Apri https://github.com/MichaelPito/ha-corrente/settings. Controllo: è la pagina delle impostazioni di ha-corrente (o ha-Corrente) di MichaelPito, e in alto vicino al nome c'è l'etichetta «Private». Se c'è già «Public», fermati e scrivi che è già pubblica.
2. In fondo alla pagina, nella «Danger Zone», premi «Change visibility» → «Change to public».
3. Leggi le finestre di conferma. Se chiedono di scrivere il nome della repo, scrivilo come lo indica GitHub. Se GitHub chiede password, codice o una conferma sul telefono, FERMATI e chiedi a Domenico di farlo lui; poi continua.
4. Conferma il cambio solo all'ultima finestra, quella che dice che la repo diventerà pubblica.
5. Controllo: apri https://github.com/MichaelPito/ha-corrente e verifica che accanto al nome ci sia «Public».

RESOCONTO FINALE:
- Visibilità adesso: Public/Private
- Cosa ha fatto Domenico a mano (password, codice, nessuno)
- Problemi: (nessuno, oppure dove ti sei fermato e perché)
```

## C — Richiesta di inserimento nel catalogo (Marketplace e HACS)

> Da usare solo **dopo** che Claude Code ha scritto in chat che il controllo HACS senza `ignore` è verde e che la nuova versione è pubblicata.

```text
Lavori per conto di Domenico (MichaelPito su GitHub), su richiesta di Claude Code. Devi aprire una richiesta (pull request) nella repo hacs/default per aggiungere l'integrazione Corrente al catalogo della community (lo stesso catalogo usato dal Marketplace di Home Assistant 2026.11 e da HACS).

REGOLE:
- Non mostrare, copiare o rigenerare segreti o codici.
- Cambia SOLO il file «integration» di hacs/default, aggiungendo UNA riga. Non toccare altre righe né altri file.
- Non chiudere, commentare o approvare richieste di altri.
- Prima di premere il pulsante finale che apre la richiesta, mostrami titolo, testo e la riga aggiunta, e ASPETTA il mio «sì».
- Se un controllo non torna, FERMATI e dimmelo.

PASSI:
1. Raccogli tre link dalla repo https://github.com/MichaelPito/ha-corrente:
   a. l'ultima release: https://github.com/MichaelPito/ha-corrente/releases/latest (annota l'indirizzo completo, con il numero di versione);
   b. l'ultima esecuzione RIUSCITA del controllo «Validate» sul ramo main, in https://github.com/MichaelPito/ha-corrente/actions/workflows/validate.yml: aprila e annota l'indirizzo. Dentro ci sono due lavori, HACS e hassfest: verifica che siano entrambi verdi. Controllo: apri il file https://github.com/MichaelPito/ha-corrente/blob/main/.github/workflows/validate.yml e verifica che NON contenga la parola «ignore». Se la contiene, fermati: Claude Code deve ancora toglierla.
2. Apri https://github.com/hacs/default e leggi le istruzioni per chi aggiunge una repo (README e, se c'è, la guida «contributing»). Se dicono di fare qualcosa di diverso da quello che segue, fermati e riassumimelo.
3. Apri il file «integration» nella repo hacs/default e premi la matita per modificarlo (GitHub crea da solo una copia nel profilo di MichaelPito).
4. Aggiungi la riga
   MichaelPito/ha-corrente
   nel punto giusto dell'ordine alfabetico (come fanno le righe vicine; maiuscole e minuscole come le altre). Controllo: la riga non c'era già; il resto del file non cambia.
5. Proponi la modifica («Propose changes») e arriva alla pagina per aprire la pull request. Il titolo: «Adds new integration [MichaelPito/ha-corrente]» (o la forma che chiedono le istruzioni del punto 2).
6. Nel testo compare un modello con caselle e campi: compilalo seguendo il modello, spuntando una casella solo se è vera, e mettendo i link del punto 1 dove li chiede (release, controllo HACS, controllo hassfest). Non cancellare parti del modello.
7. Mostrami titolo, testo e la riga aggiunta. Aspetta il mio «sì». Poi apri la pull request.
8. Controllo: la pull request è aperta in hacs/default, modifica un solo file con una sola riga aggiunta, e i controlli automatici partono (annota se diventano verdi o rossi; se rossi, copia il messaggio d'errore).

RESOCONTO FINALE:
- Indirizzo della pull request
- Riga aggiunta e posizione (tra quali righe)
- Link usati: release, controllo HACS, controllo hassfest
- Stato dei controlli automatici della pull request (e messaggi d'errore, se ci sono)
- Problemi
```

## D — I post nelle community (uno alla volta)

> Ogni post si pubblica solo dopo il **sì** di Domenico sull'anteprima. I testi sono in `docs/LANCIO.md`; Claude in Chrome li legge da lì, così sono sempre quelli aggiornati.

```text
Lavori per conto di Domenico, su richiesta di Claude Code. Devi preparare e, dopo il suo «sì», pubblicare UN post per presentare Corrente, un'integrazione gratuita per Home Assistant. Il post di oggi è: [SCRIVI QUI: Post 1 forum Home Assistant / Post 2 Reddit / Post 3 forum.fibra.click / Post 3 Telegram inDomus].

REGOLE:
- Usa SOLO l'account di Domenico già collegato. Non creare account, non accettare nuovi termini senza chiederlo.
- Non mostrare né copiare password o codici.
- Prima di pubblicare mostrami l'anteprima e ASPETTA il mio «sì». Pubblica una volta sola.
- Non commentare, votare, scrivere messaggi privati o modificare altri post.
- Se il sito chiede qualcosa che non è in questo prompt (verifica, regole del gruppo, moderazione), FERMATI e dimmelo.

PASSI:
1. Apri https://github.com/MichaelPito/ha-corrente/blob/main/docs/LANCIO.md e trova la sezione del post di oggi («Post 1», «Post 2» o «Post 3»). Copia titolo (se c'è) e testo ESATTAMENTE come sono, senza il segno «>» all'inizio delle righe. Controllo: il testo contiene il link https://github.com/MichaelPito/ha-corrente.
2. Apri il posto giusto:
   - Post 1: https://community.home-assistant.io → categoria «Share your Projects!» → nuovo argomento;
   - Post 2: https://www.reddit.com/r/homeassistant → crea post; flair «Personal Setup» o «Share» (quello che esiste);
   - Post 3 forum: https://forum.fibra.click → la sezione più adatta alla domotica / Home Assistant (se non sei sicuro, chiedimelo);
   - Post 3 Telegram: https://web.telegram.org → gruppo inDomus (se Domenico non ne fa parte, fermati).
   Leggi le regole del posto (regole del forum, del subreddit o del gruppo): se vietano post come questo o chiedono un formato diverso, fermati e riassumimele.
3. Incolla titolo e testo. Allega l'immagine indicata in LANCIO.md, punto 7 della lista di controllo: scaricala da https://github.com/MichaelPito/ha-corrente/tree/main/docs/images (in inglese: card-ekz-dynamic-en.png o la GIF setup.gif; in italiano: prova-dashboard-it.png). Se non riesci ad allegarla, fermati e chiedi a Domenico di allegarla lui.
4. Mostrami l'anteprima (titolo, testo, immagine, categoria o flair). Aspetta il mio «sì». Poi pubblica.
5. Controllo: apri il post pubblicato e verifica che testo, link e immagine si vedano.

RESOCONTO FINALE:
- Dove: (sito, categoria o flair)
- Indirizzo del post pubblicato
- Immagine allegata: quale (o «allegata da Domenico»)
- Problemi o richieste del sito (moderazione, regole)
```
