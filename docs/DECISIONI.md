# Registro delle decisioni

Formato: data — chi — decisione — perché. Le decisioni più recenti in alto.

- **2026-10-08 — owner** — Claude usa git normalmente sulla repo `ha-corrente` (la verifica di sicurezza aveva bloccato i comandi git dopo un cambio di indirizzo della repo). Parole dell'owner: «ok, usa git normalmente sulla repo ha-corrente». L'indirizzo resta `MichaelPito/ha-corrente`.
- **2026-10-08 — Claude** — Tariffe dinamiche svizzere: solo dalle **API pubbliche indicate dal gestore** nel suo file (standard VSE / SmartGridready), chiamate da ogni installazione; niente lettura di pagine web (AIL, AMB, AEW restano fuori finché non pubblicano un'API). *Perché:* fonte ufficiale e stabile, coerente con la regola sulle fonti di `CLAUDE.md`.
- **2026-10-08 — Claude (correzione tecnica)** — Verifica delle voci nazionali: con una tariffa di rete dinamica o a due fasce si confronta con le tariffe a prezzo unico **della stessa clientela**, non con tutte. *Perché:* per Groupe E una tariffa per aziende faceva aggiungere di nuovo il supplemento di rete (2,3 Rp, circa +2,5 Rp IVA inclusa). Dettagli in `FONTI-DATI.md`.
- **2026-10-07 — owner** — Prezzo PUN italiano: si usa il **download dal sito GME come pun_sensor** (opzione 1). Parole dell'owner: «1, vai con il download GME come pun_sensor». Regole vincolanti:
  - ogni installazione scarica da sola i propri dati, 1–2 volte al giorno, con minuto casuale;
  - nessun server o cache condivisi;
  - "Fonte: GME" visibile nell'interfaccia;
  - **nessuna funzione a pagamento basata sui dati GME** (le condizioni GME vietano l'uso commerciale).

  *Rischio accettato:* GME può cambiare l'indirizzo senza preavviso.
- **2026-10-07 — Claude (correzione tecnica)** — Le voci nazionali svizzere non si aggiungono più sempre: per ogni gestore si verifica con ElCom se sono già nel file. *Perché:* EKZ le include già, quindi il prezzo risultava gonfiato di circa il 13%; AIL ed ewb invece le escludono. Dettagli e limite noto in `FONTI-DATI.md`.
- **2026-10-07 — Claude** — Ordine dei lavori: prima il momento migliore e l'andamento del prezzo, poi la card. *Perché:* la card ha bisogno di quei dati.
- **2026-10-06 — owner** — Attivata una **sessione di lavoro automatica ogni giorno feriale alle 8:52** (ora svizzera; routine `trig_014xRbz8QHHxwJXknrBfbGtS`, "Corrente — sessione di lavoro quotidiana"). Parole dell'owner: «Il mio obiettivo è che vai avanti il più possibile da solo, non mi interessa che consumi tutti i crediti». Claude scrive all'owner solo quando serve una sua decisione o azione.
- **2026-10-06 — owner** — Niente organizzazione GitHub: la repo sta sull'account personale **MichaelPito** (`MichaelPito/ha-corrente`). *Perché:* più semplice; il nome visibile non è un problema per l'owner. Se servirà, la repo si può trasferire in un'organizzazione più avanti (GitHub mantiene i reindirizzamenti). Sostituisce la decisione "marchio con organizzazione dedicata".
- **2026-10-06 — owner** — Account donazioni: `buymeacoffee.com/michaelpito`. La pagina è condivisa con altri progetti dell'owner, quindi deve restare generica (vedi suggerimenti in chat del 6 ottobre).
- **2026-10-06 — owner** — Si procede con il prodotto "energia Italia/Svizzera" invece del pannello per la famiglia. *Perché:* il pannello per la famiglia è saturo di progetti simili usciti da giugno 2026; nell'energia locale il campo è libero e c'è un vantaggio (lingua, Ticino, conoscenza delle tariffe).
- **2026-10-06 — owner** — Link **Buy Me a Coffee** su tutto il materiale gratuito, per aprire alle donazioni.
- **2026-10-06 — owner** — Nel prodotto ci deve essere un **modulo per richiedere modifiche e suggerimenti** (vedi `PIANO.md` §6).
- **2026-10-06 — Claude, approvato dall'owner** — Nome **Corrente**, repo `ha-corrente`, dominio integrazione `corrente`. *Perché:* parola italiana breve (elettricità / aggiornato), nessun progetto GitHub con questo nome.
- **2026-10-06 — owner** — Marchio con organizzazione GitHub dedicata; lingua principale inglese; trasparenza dichiarata sull'uso dell'AI.
- **2026-10-06 — owner** — Snello, Beasts Off Duty e Jenny **restano attivi**, finché non costano soldi.
