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
- **Guida dentro Home Assistant (onboarding) aggiornata a ogni rilascio** (owner, 28 ottobre 2026): ogni versione aggiunge le sue novità in `custom_components/corrente/guide.json` e aggiorna gli argomenti che tocca; una funzione nuova (sensore, passo, opzione, blueprint) va in un argomento. `tests/test_guide.py` blocca il rilascio se manca qualcosa. Dettagli in `docs/ONBOARDING.md`.
- Lingue: codice, commenti e documentazione principale in **inglese**; piano e decisioni interne in **italiano**; interfaccia tradotta in EN/IT/DE/FR.
- Trasparenza: il progetto dichiara di essere sviluppato con l'AI; le risposte pubbliche portano la firma di Claude Code.
- Fonti dati: solo ufficiali o con termini che consentono il riuso. Mai scraping di siti che lo vietano.
- Verifica sempre le API di Home Assistant sulla documentazione ufficiale per gli sviluppatori e sulla versione minima supportata dichiarata in `hacs.json`.
- 🖱️ **Tutto ciò che può fare Claude in Chrome lo fa Claude in Chrome: l'owner riceve un PROMPT, non una lista di clic (2026-11-08, vale per TUTTI i progetti).**
  👤 Testuale: *«Per qualsiasi cosa che claude in browser puo fare dammi sempre un prompt per farglielo fare cosi non faccio io e tu completi meglio tutte le info. Mettilo nel tuo modo di lavorare.»* e *«L'indicazione di utilizzare claude in browser è valida per tutti i progetti»*.
  - Quando un passo richiede il browser dell'owner (un pannello web, una console, un sito dove è già collegato), si scrive un **prompt pronto** in un file del repo, glielo si manda, e gli si chiede di incollarlo in Claude in Chrome e di **incollare qui il resoconto**.
  - Forma del prompt: chi parla e per conto di chi; **regole in testa** (segreti mai mostrati né rigenerati · niente cancellazioni · niente costi o pagamenti · niente invii/pubblicazioni non chiesti · non toccare ciò che non è nel prompt); **passi numerati con il controllo prima della modifica** e cosa fare se il controllo fallisce («fermati e dimmelo»); **resoconto finale** con campi precisi.
  - Restano all'owner solo password, codici, consensi, pagamenti e i gesti che il browser non sa fare (app sul telefono, dispositivi fisici): per quelli una lista breve.
  - ⛔ Nessun valore segreto nel prompt, e Claude in Chrome non deve copiarne in chat.
