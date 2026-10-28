# Guida dentro Home Assistant (onboarding)

Richiesta dell'owner, 28 ottobre 2026: «Fondamentale disegnare anche un processo di onboarding
contestuale che devi aggiornare con ogni rollout così è sempre tutto disponibile. L'onboarding deve
essere navigabile (i.e. posso scegliere su cosa voglio che il sistema mi guidi) e deve essere
possibile lanciarlo anche per intero, per esempio per nuovi utenti».

## Dove sta

Nella barra laterale di Home Assistant compare **Corrente** (icona a fulmine), registrata
dall'integrazione stessa: nessuna installazione a parte, sempre disponibile, in EN/IT/DE/FR (la lingua
dell'utente in Home Assistant). Chi non la vuole può nasconderla dalla barra laterale come ogni voce.

## Cosa fa

1. **Navigabile:** la pagina iniziale elenca gli argomenti (configurare l'Italia, il PUN, la Svizzera,
   le tariffe dinamiche, il prezzo, il momento migliore, i costi, il costo per apparecchio, i costi
   fissi, la card, i blueprint, cambiare contratto, il prezzo che non torna, chiedere aiuto). Si apre
   quello che serve.
2. **Per intero:** il pulsante «Guida completa» percorre tutti gli argomenti in ordine, un passo alla
   volta, con avanti/indietro, «salta l'argomento» ed «esci». Pensato per i nuovi utenti.
3. **Contestuale:**
   - guarda come è configurato Corrente (paese, contratto, contatore, apparecchi, tariffe dinamiche,
     altri costi) e segna ogni argomento come *fatto*, *da fare* o *non serve*; in alto propone «Per
     te» i prossimi passi utili;
   - mostra solo gli argomenti del paese configurato (con «mostra tutto» per gli altri);
   - si apre al punto giusto da fuori: link `/corrente-guide?topic=<argomento>` e
     `/corrente-guide?tour=1`, usati dalla configurazione, dalle opzioni, dalla card e dagli avvisi;
   - dopo l'installazione un avviso propone la guida completa; dopo ogni aggiornamento un avviso apre
     le **novità** della versione.
4. **Passi con azioni:** ogni passo può avere un pulsante che porta nel punto di Home Assistant dove
   si fa la cosa (aggiungere l'integrazione, le opzioni di Corrente, i blueprint, la dashboard).

## Come resta aggiornata a ogni rilascio (regola)

- Tutto il contenuto sta in un solo file: `custom_components/corrente/guide.json` (argomenti, passi,
  ordine del giro completo, novità per versione, in 4 lingue).
- **Un test blocca il rilascio** se:
  - manca la voce «novità» della versione in `manifest.json`, in una delle 4 lingue;
  - un testo manca in una lingua;
  - una funzione non è coperta da nessun argomento: ogni sensore, ogni passo della configurazione e
    delle opzioni, ogni blueprint, la card e la diagnostica devono comparire nel campo `covers` di
    almeno un argomento. Aggiungere una funzione senza aggiornare la guida fa fallire i controlli.
- Regola di lavoro (CLAUDE.md e sessione quotidiana): a ogni rilascio si aggiornano le novità e gli
  argomenti toccati.

## Parti tecniche

- `guide.json`: contenuto. `guide.py`: lettura del contenuto, stato per argomento calcolato dalle
  configurazioni, comando websocket `corrente/guide`, pannello nella barra laterale, avvisi di
  benvenuto e di novità (ultima versione vista salvata in `.storage/corrente.guide`).
- `frontend/corrente-guide.js`: il pannello (web component senza dipendenze, come la card); ricorda
  in locale dove si è arrivati nel giro completo.
