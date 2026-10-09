# Your consumption in Home Assistant

Corrente's **cost today / this month** sensors need one thing from you: a sensor that counts the kWh your home uses. This page explains the ways to get one in Italy and Switzerland, from the simplest to the most precise.

> Checked in October 2026. Devices and rules change: always confirm with your grid operator or the seller before buying anything.

## Any country: a clamp or a meter in the panel (simplest)
A current clamp (for example a Shelly EM / Pro 3EM) or a DIN-rail meter with Modbus, installed in your electrical panel, measures what your home uses and has a Home Assistant integration. It does not depend on your grid operator. **Have it installed by an electrician.**

Then: Corrente → **Configure → Energy meter** → choose its *energy* sensor (kWh, always increasing).

## Italy: the Open Meter 2G and "Chain 2"
Second-generation meters from E-Distribuzione (**Open Meter 2G**) send your consumption into the house over the power line, on a channel called **Chain 2** (CEI TS 13-82 / 13-83).
- You need a 2G meter on E-Distribuzione's low-voltage grid. Older meters (1G) can be replaced with a 2G one first.
- You need a **"Dispositivo Utente" (DU)** that passed E-Distribuzione's tests. You do not register it yourself: the company that sells it (the *Asset Provider*) registers it for your meter.
- E-Distribuzione lists the companies with a Chain 2 contract (on 1 April 2026: AEM Acotel, Bitron Electronics, CONNET, Helioty, MAC, Novaproject, Sidora, Sinapsi, Smartdhome, TERA, Urmet Telecomunicazioni) in its [Chain 2 FAQ](https://www.e-distribuzione.it/open-meter/chain-2/faq---esercizio-chain-2.html).
- Before buying, ask the seller: *does it work with Home Assistant, locally (for example Modbus TCP or MQTT), without a subscription?* Users report devices that need the maker's app or cloud to be set up ([discussion](https://community.home-assistant.io/t/italian-open-meter-2-0-and-chain-2-protocol/634033)).
- Other grid operators have their own Chain 2 pages (for example [Edyna](https://www.edyna.net/clienti/smart-meter/chain-2.html) in South Tyrol): check with yours.

If you are not on E-Distribuzione's grid, or you want something simple today, the clamp above works everywhere.

## Switzerland: the smart meter's customer interface
Swiss smart meters must have a **customer interface** that gives you your own data as it is measured. The most common is **DSMR P1** (an RJ12 socket on the meter; specification *P1 Companion Standard 5.0.2*); some meters use M-Bus instead.
1. **Ask your grid operator** to activate the customer interface: it is often off at delivery. Many operators explain it on their website (for example [ewl Luzern](https://www.ewl-luzern.ch/netzdienstleistungen/messwesen/smart-meter/aktivierung-schnittstelle-smart-meter), [EKS](https://www.eks.ch/smartmeter)).
2. **Plug in a reader**: a P1 dongle powered by the meter (for example gPlug or whatwatt Go) that sends the data to Home Assistant over Wi‑Fi, or a P1 cable to the official [DSMR integration](https://www.home-assistant.io/integrations/dsmr/). Overview of Swiss options: [smart-metering-interface.ch](https://www.smart-metering-interface.ch/en/kategorien/schnittstelle).
3. In Home Assistant use the sensor of **imported energy** (kWh). If the meter gives two counters, one for the high and one for the low tariff, add them up with a helper: **Settings → Devices & services → Helpers → Create helper → Template → Template sensor**, with
   - state: `{{ states('sensor.your_high_tariff_counter') | float(0) + states('sensor.your_low_tariff_counter') | float(0) }}`
   - unit **kWh**, device class **Energy**, state class **Total increasing**,

   and give Corrente that one.

## Then, in Corrente
**Settings → Devices & services → Corrente → Configure → Energy meter**: choose the kWh sensor. From then on, *Cost today* and *Cost this month* price each kWh at the moment it was used, at your real tariff.

Something unclear, or a device that works well for you? [Tell us](https://github.com/MichaelPito/ha-corrente/issues/new/choose) and we add it here.
