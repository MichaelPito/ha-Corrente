# Corrente — istruzioni per Claude

> Questa repo è **solo** il progetto Corrente (integrazione Home Assistant: prezzi e tariffe dell'elettricità per Italia e Svizzera).
> Niente qui riguarda Snello, Beasts Off Duty o Jenny: quelli vivono nelle loro repo.

## Prima di fare qualsiasi cosa
1. Leggi `docs/PIANO.md` (piano, calendario, ruoli, numeri di controllo).
2. Leggi `docs/DECISIONI.md` (cosa è già stato deciso, da chi e quando). Non ridiscutere decisioni già prese.
3. Guarda `docs/ROADMAP.md` e le richieste aperte su GitHub.

## Ruoli
- Claude fa tutto lo sviluppo, la documentazione, i rilasci e la gestione delle richieste su GitHub.
- L'owner va chiamato **solo** per: accessi/account (GitHub, Buy Me a Coffee, pagamenti), test sulla sua casa, pubblicazione dei post nelle community (testi preparati da Claude), decisioni di prodotto non ovvie. L'elenco completo è in `docs/PIANO.md` §9.

## Regole di lavoro
- **La repo è la memoria:** ogni decisione nuova va in `docs/DECISIONI.md` (data, chi, cosa, perché). Il lavoro non pushato si perde quando la sessione si chiude: commit + push a ogni passo.
- Si lavora su **rami dedicati**; in `main` si entra solo con i controlli automatici verdi.
- I rilasci pubblici hanno numero di versione (SemVer) e note di rilascio. **Le nuove versioni si pubblicano senza chiedere** (owner, 20 ottobre 2026); l'ok dell'owner serve **solo per cancellare** qualcosa (file, rami, versioni, dati).
- **Segreti mai committati**, nemmeno in file di prova.
- Lingue: codice, commenti e documentazione principale in **inglese**; piano e decisioni interne in **italiano**; interfaccia tradotta in EN/IT/DE/FR.
- Trasparenza: il progetto dichiara di essere sviluppato con l'AI; le risposte pubbliche portano la firma di Claude Code.
- Fonti dati: solo ufficiali o con termini che consentono il riuso. Mai scraping di siti che lo vietano.
- Verifica sempre le API di Home Assistant sulla documentazione ufficiale per gli sviluppatori e sulla versione minima supportata dichiarata in `hacs.json`.
