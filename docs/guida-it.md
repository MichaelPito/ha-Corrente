# Corrente — guida in italiano

Corrente porta in Home Assistant il **vero prezzo della tua elettricità** e ti dice **quando conviene accendere** lavastoviglie, lavatrice e boiler. Funziona in Italia e in Svizzera.

## Installazione

1. In HACS: ⋮ → **Repository personalizzati** → aggiungi `https://github.com/MichaelPito/ha-corrente`, categoria **Integrazione**. Dopo il lancio Corrente sarà direttamente nello store di HACS.
2. Installa **Corrente** e riavvia Home Assistant.
3. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Corrente**.

## Configurazione

### In Italia
1. Scegli **Italia**.
2. Scegli il tipo di contratto:
   - **monoraria** (un prezzo solo);
   - **bioraria** (F1 e F23);
   - **trioraria** (F1, F2, F3).
3. Inserisci i prezzi dell'energia della bolletta in **€/kWh**, per esempio `0,1250`.
   - Li trovi nella sezione "spesa per la materia energia" o "quota energia".
4. Se il contratto è **indicizzato al PUN**, scegli "Indicizzato: PUN (o zona) + spread" e inserisci:
   - lo **spread** in €/kWh scritto in bolletta;
   - le **perdite di rete** in %, solo se il contratto le applica al PUN (spesso circa 10%);
   - il **prezzo di riferimento**: PUN Index GME, oppure la zona se il contratto la usa.

   Corrente scarica ogni giorno dal sito del GME i prezzi al quarto d'ora di oggi e di domani (fonte: GME) e calcola il tuo prezzo momento per momento.

Le fasce seguono le regole ARERA:
- **F1:** lun–ven 8–19;
- **F2:** lun–ven 7–8 e 19–23, sabato 7–23;
- **F3:** notte, domenica e festivi.

### In Svizzera
1. Scegli **Svizzera** e scrivi il nome del tuo **comune**.
2. Corrente trova il tuo **gestore di rete** nei dati aperti di ElCom e legge il suo file delle tariffe.
3. Scegli la tua **tariffa dell'energia**, per esempio "Casa & PMI giorno-notte". Corrente propone la tariffa di rete e i tributi che vanno con quella scelta: confrontali con la bolletta e conferma.
4. **Tariffe dinamiche** (prezzo diverso ogni quarto d'ora): se il gestore le pubblica con l'API standard, compaiono nell'elenco e Corrente scarica da sola i prezzi di oggi e, appena escono, quelli di domani. Oggi funziona con EKZ (*Energie Dynamisch*, *Netz 400D*) e Groupe E (*Vario*). AIL e AMB per ora pubblicano i prezzi dinamici solo sul loro sito: non sono ancora supportati.
5. Se il gestore non ha pubblicato un file leggibile (succede per esempio con SES e, nel 2026, con AMB), puoi incollare il link al file, oppure [segnalarcelo](https://github.com/MichaelPito/ha-corrente/issues/new/choose) e lo aggiungiamo noi.

Il prezzo svizzero include IVA, supplemento di rete, riserva elettrica, servizi di sistema Swissgrid e tributi cantonali e comunali. Le quote fisse mensili sono in un sensore a parte.

## Quanto ho speso oggi?

Nelle **opzioni** di Corrente scegli **Contatore** e indica il sensore che conta i tuoi consumi in kWh (contatore intelligente, Shelly, consumo dalla rete della dashboard energia). Compaiono due sensori, **Costo di oggi** e **Costo del mese**: ogni kWh è pagato al prezzo del momento in cui l'hai consumato. In Italia il costo comprende solo la parte energia del contratto che hai inserito.

## Avviare la lavastoviglie al momento giusto

Importa il blueprint **"Corrente — start an appliance at the cheapest time"** (pulsante nel README). Crea un aiutante "pronta" (interruttore). Quando carichi la lavastoviglie lo accendi, e Corrente la fa partire da sola nel momento più economico, poi spegne l'aiutante.

## La card

Nella dashboard: **Aggiungi scheda** → cerca **Corrente**. In YAML:

```yaml
type: custom:corrente-card
entity: sensor.corrente_price_now
```

La card mostra il prezzo adesso, le prossime 24 ore a colori (verde più economico, rosso più caro) e il momento migliore per avviare un apparecchio di 2 ore. In basso trovi la fonte dei dati e il link **Suggerisci una modifica**; per nasconderlo aggiungi `feedback: false`.

## Hai un'idea o un problema?

[Apri una richiesta](https://github.com/MichaelPito/ha-corrente/issues/new/choose): basta un minuto, e puoi scrivere in italiano. Non hai un account GitHub? Usa il **[modulo](https://docs.google.com/forms/d/e/1FAIpQLSce_vFvHpz3Qav3o05DvoJhpIuM2zXWmvpgBHWRS1gJsEF6yQ/viewform)**: non serve nessun account, e pubblichiamo la richiesta su GitHub senza dati personali. Corrente è gratuito; se ti fa risparmiare, [offrici un caffè ☕](https://buymeacoffee.com/michaelpito).
