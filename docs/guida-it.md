# Corrente — guida in italiano

Corrente porta in Home Assistant il **vero prezzo della tua elettricità** e ti dice **quando conviene accendere** lavastoviglie, lavatrice e boiler. Funziona in Italia e in Svizzera.

## Installazione

1. Aggiungi il link di Corrente `https://github.com/MichaelPito/ha-corrente`:
   - **Marketplace** (Home Assistant 2026.11 e successive): **Impostazioni → Marketplace → Aggiungi dal collegamento**, incolla il link, **Aggiungi**. La prima volta il Marketplace chiede di collegare un account GitHub (legge solo informazioni pubbliche).
   - **HACS** (versioni precedenti): nel menu **⋮**, **Custom repositories**, incolla il link, tipo **Integration**.

   Dopo il lancio Corrente sarà direttamente nel catalogo, senza questo passo.
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
5. **Facoltativo, per avere il prezzo della bolletta e non solo dell'energia:** nella stessa pagina ci sono due campi.
   - **Altri costi per kWh:** somma le voci al kWh della bolletta oltre all'energia, cioè trasporto e gestione del contatore (quota energia), oneri di sistema e accise. Corrente le aggiunge al prezzo e ai costi di oggi e del mese.
   - **Costi fissi al mese:** quote fisse e quota potenza. Compaiono in un sensore a parte.

   Inseriscili come i prezzi dell'energia: con o senza IVA, allo stesso modo. Questi valori cambiano ogni tanto (ARERA li aggiorna ogni trimestre): li modifichi quando vuoi dalle **opzioni** di Corrente.

Le fasce seguono le regole ARERA:
- **F1:** lun–ven 8–19;
- **F2:** lun–ven 7–8 e 19–23, sabato 7–23;
- **F3:** notte, domenica e festivi.

### In Svizzera
1. Scegli **Svizzera** e scrivi il nome del tuo **comune**.
2. Corrente trova il tuo **gestore di rete** nei dati aperti di ElCom e legge il suo file delle tariffe.
3. Scegli la tua **tariffa dell'energia**, per esempio "Casa & PMI giorno-notte". Corrente propone la tariffa di rete e i tributi che vanno con quella scelta: confrontali con la bolletta e conferma.
4. **Tariffe dinamiche** (prezzo diverso ogni quarto d'ora): se il gestore le pubblica con l'API standard, compaiono nell'elenco e Corrente scarica da sola i prezzi di oggi e, appena escono, quelli di domani. Oggi funziona con EKZ (*Energie Dynamisch*, *Netz 400D*), Groupe E (*Vario*) e Primeo (*NetzDynamisch*, Basilea Campagna e Soletta). AIL e AMB per ora pubblicano i prezzi dinamici solo sul loro sito: non sono ancora supportati.
5. Se il gestore non ha pubblicato un file leggibile (succede per esempio con SES e, nel 2026, con AMB), puoi incollare il link al file, oppure [segnalarcelo](https://github.com/MichaelPito/ha-corrente/issues/new/choose) e lo aggiungiamo noi.

Il prezzo svizzero include IVA, supplemento di rete, riserva elettrica, servizi di sistema Swissgrid e tributi cantonali e comunali. Le quote fisse mensili sono in un sensore a parte.

Corrente controlla le voci nazionali e i tributi con i dati ElCom del tuo comune: se nel file del gestore mancano dei tributi, li prende da ElCom (attributo "other_fees_from_elcom" del sensore del prezzo). I **costi fissi al mese** comprendono anche la misurazione (il contatore), che quasi tutti i gestori mettono in una tariffa a parte: Corrente la prende da ElCom, circa 6 CHF al mese (attributo "metering_from_elcom"). Prima del lancio l'abbiamo confrontato con ElCom per tutti i gestori svizzeri con un file leggibile (circa 340).

## La guida dentro Home Assistant

Dopo la configurazione, nella barra laterale compare **Corrente**: una guida che spiega cosa puoi fare e come, segna cosa hai già configurato e propone cosa manca. Scegli un argomento o segui la **guida completa** passo dopo passo; dopo ogni aggiornamento mostra le **novità**. I pulsanti ti portano nel punto giusto di Home Assistant.

![La guida di Corrente in Home Assistant](images/guide-it.png)

## Quanto ho speso oggi?

Nelle **opzioni** di Corrente scegli **Contatore** e indica il sensore che conta i tuoi consumi in kWh (contatore intelligente, Shelly, consumo dalla rete della dashboard energia). Compaiono due sensori, **Costo di oggi** e **Costo del mese**: ogni kWh è pagato al prezzo del momento in cui l'hai consumato. In Italia il costo comprende la parte energia e, se li hai inseriti, gli altri costi per kWh della bolletta; i costi fissi al mese restano a parte.

**Non hai ancora un sensore dei consumi?** Le strade, dalla più semplice:
- **una pinza o un contatore nel quadro elettrico** (per esempio Shelly EM / Pro 3EM), installati da un elettricista: funzionano ovunque;
- **Italia, contatore Open Meter 2G ("Chain 2")**: serve un "Dispositivo Utente" certificato, che registra sul tuo contatore l'azienda che te lo vende; prima di comprarlo chiedi se funziona con Home Assistant in locale, senza abbonamento. Elenco delle aziende nelle [FAQ di E-Distribuzione](https://www.e-distribuzione.it/open-meter/chain-2/faq---esercizio-chain-2.html);
- **Svizzera, contatore intelligente**: chiedi al gestore di attivare l'interfaccia cliente (di solito DSMR P1) e collega un lettore P1 (per esempio gPlug o whatwatt Go) o l'integrazione [DSMR](https://www.home-assistant.io/integrations/dsmr/).

Tutti i dettagli (in inglese): [docs/meter.md](meter.md).

**Quanto costa la lavatrice?** Se un apparecchio ha un contatore suo (per esempio una presa intelligente che misura i kWh), nelle opzioni di Corrente scegli **Costo per apparecchio** e indica i suoi sensori di energia. Per ognuno compaiono **Costo di oggi — nome** e **Costo del mese — nome**, con ogni kWh pagato al prezzo del momento. Il nome è quello della presa (per esempio "Lavastoviglie"). Per toglierli, togli l'apparecchio dall'elenco.

## Avviare la lavastoviglie al momento giusto

Importa il blueprint **"Corrente — start an appliance at the cheapest time"** (pulsante nel README). Crea un aiutante "pronta" (interruttore). Quando carichi la lavastoviglie lo accendi, e Corrente la fa partire da sola nel momento più economico, poi spegne l'aiutante.

## Avviso sul prezzo

Importa il blueprint **"Corrente — price alert"** (pulsante qui sotto): scegli il sensore del prezzo, "sotto" o "sopra", la soglia (per esempio 0,20) e cosa fare, per esempio **Notifiche → Invia una notifica** al telefono. Scatta una volta ogni volta che il prezzo passa la soglia; nel testo puoi usare `{{ price }}` e `{{ unit }}`.

[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FMichaelPito%2Fha-corrente%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fcorrente%2Fprice_alert.yaml)

## Usare il surplus del fotovoltaico

Importa il blueprint **"Corrente — use solar surplus"** (pulsante qui sotto). Scegli il sensore della potenza scambiata con la rete (W o kW; di solito è **negativo** quando mandi in rete), l'interruttore dell'apparecchio (boiler, pompa di calore, presa dell'auto) e quanta potenza consuma. Si accende quando i pannelli mandano in rete almeno quella potenza e si spegne quando la casa torna a comprare corrente; ogni cambio aspetta qualche minuto, così una nuvola non lo accende e spegne di continuo. Facoltativo: scegli il sensore del prezzo di Corrente e una soglia, e l'apparecchio parte anche nelle ore economiche (per esempio la notte), senza spegnersi per mancanza di sole.

[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FMichaelPito%2Fha-corrente%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fcorrente%2Fsolar_surplus.yaml)

## La dashboard energia

Nella dashboard energia di Home Assistant, nel consumo dalla rete, scegli di usare **un'entità con il prezzo attuale** e indica **Prezzo attuale** di Corrente: Home Assistant conta il costo di ogni kWh al prezzo di quel momento.

## La card

Dopo aver configurato Corrente la prima volta, **ricarica la pagina** del browser una volta, così trova la card.

Nella dashboard: **Aggiungi scheda** → cerca **Corrente**: l'editor trova da solo il sensore giusto. In YAML:

```yaml
type: custom:corrente-card
entity: sensor.corrente_prezzo_attuale
```

Il nome del sensore dipende dalla lingua e dal comune (per esempio `sensor.corrente_lugano_prezzo_attuale`).

La card mostra il prezzo adesso, le prossime 24 ore a colori (verde più economico, rosso più caro) e il momento migliore per avviare un apparecchio di 2 ore. In basso trovi la fonte dei dati e i link **Guida** e **Suggerisci una modifica**; per nasconderli aggiungi `guide: false` o `feedback: false`.

## Il prezzo non torna con la bolletta?

- **Svizzera:** il prezzo al kWh è energia + rete + tributi cantonali e comunali + voci federali, **IVA compresa** (8,1%). Le quote mensili (quota di rete, contatore, quote dei tributi) non sono nel prezzo: sono nel sensore **Costi fissi al mese**, e i sensori dei costi contano solo i kWh. Controlla che il prodotto di energia e la tariffa di rete siano quelli della bolletta (opzioni → Contratto o tariffa): i prodotti "verdi" o locali costano più di quello standard. Gli attributi del sensore del prezzo mostrano le tariffe usate e i tributi presi da ElCom.
- **Italia:** con i soli prezzi dell'energia, il prezzo è la parte energia della bolletta. Aggiungi **Altri costi per kWh** (trasporto, oneri di sistema, accise) e **Costi fissi al mese** dalla bolletta per avere il prezzo intero (opzioni → Contratto o tariffa). Inserisci tutti i prezzi allo stesso modo, con o senza IVA. Nei contratti indicizzati al PUN i prezzi del GME sono senza IVA, quindi lo è anche il prezzo, a meno che tu non metta l'IVA nello spread e negli altri costi.
- Ancora diverso? Scarica la diagnostica (Impostazioni → Dispositivi e servizi → Corrente → ⋮ → Scarica diagnostica) e allegala a una [richiesta](https://github.com/MichaelPito/ha-corrente/issues/new/choose) o descrivila nel modulo: mostra ogni tariffa e cifra usata da Corrente e non contiene password.

## Hai un'idea o un problema?

[Apri una richiesta](https://github.com/MichaelPito/ha-corrente/issues/new/choose): basta un minuto, e puoi scrivere in italiano. Non hai un account GitHub? Usa il **[modulo](https://docs.google.com/forms/d/e/1FAIpQLSce_vFvHpz3Qav3o05DvoJhpIuM2zXWmvpgBHWRS1gJsEF6yQ/viewform)**: non serve nessun account, e pubblichiamo la richiesta su GitHub senza dati personali.

Un prezzo non ti torna? **Impostazioni → Dispositivi e servizi → Corrente → ⋮ → Scarica diagnostica** e allega il file alla richiesta: mostra quali tariffe ha letto Corrente e come ha calcolato il prezzo (comune, gestore e tariffe; nessuna password). Corrente è gratuito; se ti fa risparmiare, [offrici un caffè ☕](https://buymeacoffee.com/michaelpito).
