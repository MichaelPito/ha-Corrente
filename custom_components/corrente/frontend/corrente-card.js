/*
 * Corrente card — price now, the next hours and the best time to start.
 * Plain web component, no build step. Reads the attributes of Corrente's
 * price sensor: "schedule" and "best_start" / "best_end" / "best_average_price".
 * https://github.com/MichaelPito/ha-corrente
 */

const STRINGS = {
  en: { now: "Now", best: "Best time to start", for: "for", hours: "h", avg: "avg",
        next: "Next hours", cheap: "cheaper", dear: "dearer", unavailable: "Corrente: sensor not found", waiting: "Price not available yet",
        startNow: "now", tomorrow: "tomorrow", suggest: "Suggest a change", guide: "Guide", elcom: "Tariffs: grid operator files via ElCom open data" },
  it: { now: "Adesso", best: "Momento migliore per avviare", for: "per", hours: "h", avg: "media",
        next: "Prossime ore", cheap: "più economico", dear: "più caro", unavailable: "Corrente: sensore non trovato", waiting: "Prezzo non ancora disponibile",
        startNow: "adesso", tomorrow: "domani", suggest: "Suggerisci una modifica", guide: "Guida", elcom: "Tariffe: file dei gestori di rete tramite i dati aperti ElCom" },
  de: { now: "Jetzt", best: "Beste Startzeit", for: "für", hours: "Std.", avg: "Ø",
        next: "Nächste Stunden", cheap: "günstiger", dear: "teurer", unavailable: "Corrente: Sensor nicht gefunden", waiting: "Preis noch nicht verfügbar",
        startNow: "jetzt", tomorrow: "morgen", suggest: "Änderung vorschlagen", guide: "Anleitung", elcom: "Tarife: Dateien der Netzbetreiber über die offenen Daten der ElCom" },
  fr: { now: "Maintenant", best: "Meilleur moment pour démarrer", for: "pendant", hours: "h", avg: "moy.",
        next: "Prochaines heures", cheap: "moins cher", dear: "plus cher", unavailable: "Corrente : capteur introuvable", waiting: "Prix pas encore disponible",
        startNow: "maintenant", tomorrow: "demain", suggest: "Suggérer une modification", guide: "Guide", elcom: "Tarifs : fichiers des gestionnaires de réseau via les données ouvertes de l'ElCom" },
};

const HOURS_SHOWN = 24;
const SUGGEST_URL = "https://github.com/MichaelPito/ha-corrente/issues/new/choose";
const GUIDE_PATH = "/corrente-guide?topic=card";  // the guide's panel, see corrente-guide.js

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function strings(hass) {
  const lang = (hass && hass.language ? hass.language : "en").slice(0, 2);
  return STRINGS[lang] || STRINGS.en;
}

function formatPrice(value, unit) {
  const currency = (unit || "").split("/")[0];
  const cents = value * 100;
  const label = currency === "CHF" ? "Rp." : "ct";
  return `${cents.toFixed(1)} ${label}/kWh`;
}

function formatTime(date, hass) {
  return date.toLocaleTimeString(hass && hass.language ? hass.language : undefined, {
    hour: "2-digit", minute: "2-digit",
  });
}

class CorrenteCard extends HTMLElement {
  static getStubConfig(hass) {
    const price = Object.keys(hass.states).find(
      (id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes.schedule)
    );
    return price ? { entity: price } : { entity: "" };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Set 'entity' to Corrente's price sensor");
    }
    this._config = config;
    this._drawn = null;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  // Home Assistant passes hass on every state change in the house: redraw only when
  // Corrente's sensor or the language changes, or once a minute for the "now" mark.
  set hass(hass) {
    this._hass = hass;
    const state = this._config ? hass.states[this._config.entity] : undefined;
    const minute = Math.floor(Date.now() / 60000);
    const key = this._drawn;
    if (key && key.state === state && key.language === hass.language && key.minute === minute) return;
    this._drawn = { state, language: hass.language, minute };
    this._render();
  }

  getCardSize() {
    return 4;
  }

  _render() {
    if (!this._config || !this.shadowRoot) return;
    const hass = this._hass;
    const t = strings(hass);
    const state = hass.states[this._config.entity];
    if (!state) {
      this.shadowRoot.innerHTML = `<ha-card><div class="msg" style="padding: 16px">${t.unavailable}: ${this._config.entity}</div></ha-card>`;
      return;
    }
    const unit = state.attributes.unit_of_measurement || "EUR/kWh";
    const price = Number(state.state);
    if (state.state === "" || !Number.isFinite(price)) {  // unavailable or unknown
      this.shadowRoot.innerHTML = `<ha-card><div class="msg" style="padding: 16px">Corrente: ${t.waiting}</div></ha-card>`;
      return;
    }
    const now = new Date();
    const horizon = new Date(now.getTime() + HOURS_SHOWN * 3600 * 1000);
    const segments = (state.attributes.schedule || [])
      .map((s) => ({ start: new Date(s.start), end: new Date(s.end), price: Number(s.price) }))
      .filter((s) => s.end > now && s.start < horizon)
      .map((s) => ({ ...s, start: s.start < now ? now : s.start, end: s.end > horizon ? horizon : s.end }));

    const prices = segments.map((s) => s.price).concat([price]);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const span = max - min || 1;

    const a = state.attributes;
    let bestHtml = "";
    let bestStart, bestEnd;
    if (a.best_start) {
      bestStart = new Date(a.best_start);
      bestEnd = a.best_end ? new Date(a.best_end) : undefined;
      const startsNow = bestStart <= new Date(now.getTime() + 60 * 1000);
      const sameDay = bestStart.toDateString() === now.toDateString();
      const when = startsNow ? t.startNow : `${sameDay ? "" : t.tomorrow + " "}${formatTime(bestStart, hass)}`;
      const avg = a.best_average_price !== undefined
        ? ` · ${t.avg} ${formatPrice(Number(a.best_average_price), unit)}` : "";
      bestHtml = `<div class="best"><span class="label">${t.best}</span>
        <span class="value">${when}</span>
        <span class="detail">${t.for} ${a.best_duration_hours} ${t.hours}${avg}</span></div>`;
    }

    const width = 300;
    const height = 70;
    const total = horizon - now;
    const bars = segments.map((s) => {
      const x = ((s.start - now) / total) * width;
      const w = Math.max(((s.end - s.start) / total) * width - 1, 1);
      const level = (s.price - min) / span; // 0 cheap .. 1 dear
      const h = 18 + level * (height - 26);
      return `<rect x="${x.toFixed(1)}" y="${(height - h).toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}"
        rx="2" class="${level < 0.34 ? "cheap" : level > 0.66 ? "dear" : "mid"}"><title>${formatTime(s.start, hass)}–${formatTime(s.end, hass)} · ${formatPrice(s.price, unit)}</title></rect>`;
    }).join("");
    let bestBand = "";
    if (bestStart && bestEnd) {
      const x1 = Math.max(0, ((bestStart - now) / total) * width);
      const x2 = Math.min(width, ((bestEnd - now) / total) * width);
      if (x2 > x1) bestBand = `<rect x="${x1.toFixed(1)}" y="0" width="${(x2 - x1).toFixed(1)}" height="${height}" class="bestband"/>`;
    }
    // Axis: "now", then every full hour divisible by 6 (00, 06, 12, 18), local time.
    const tickTimes = [];
    const first = new Date(now);
    first.setMinutes(0, 0, 0);
    for (let d = new Date(first.getTime() + 3600 * 1000); d < horizon; d = new Date(d.getTime() + 3600 * 1000)) {
      if (d.getHours() % 6 === 0 && (d - now) / total > 0.15) tickTimes.push(d);
    }
    const ticks = [`<text x="0" y="${height + 13}" text-anchor="start">${t.now}</text>`].concat(
      tickTimes.map((d) => {
        const x = ((d - now) / total) * width;
        const anchor = x > width - 20 ? "end" : "middle";
        return `<line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${height}" y2="${height + 3}" class="tick"/>` +
          `<text x="${x.toFixed(1)}" y="${height + 13}" text-anchor="${anchor}">${formatTime(d, hass)}</text>`;
      })
    ).join("");

    const level = (price - min) / span;
    const chip = level < 0.34 ? t.cheap : level > 0.66 ? t.dear : "";
    const title = this._config.title !== undefined ? this._config.title : "Corrente";
    // The data source (e.g. "Fonte: GME", required by its terms) and a link for
    // requests; "feedback: false" in the card's YAML hides the link.
    // Home Assistant does not translate attributions: the ElCom one is shown in the
    // viewer's language; GME's stays as GME's terms require ("Fonte: GME").
    const attribution = a.attribution && a.attribution.includes("ElCom") ? t.elcom : a.attribution;
    const source = attribution ? `<span>${escapeHtml(attribution)}</span>` : "<span></span>";
    const suggest = this._config.feedback === false ? "" :
      `<a href="${SUGGEST_URL}" target="_blank" rel="noopener">${t.suggest}</a>`;
    // "guide: false" hides the link to Corrente's guide.
    const guide = this._config.guide === false ? "" : `<a href="${GUIDE_PATH}" class="guide">${t.guide}</a>`;
    const links = guide || suggest ? `<span class="links">${[guide, suggest].filter(Boolean).join(" · ")}</span>` : "";
    const footHtml = a.attribution || links ? `<div class="foot">${source}${links}</div>` : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host { --cheap: var(--success-color, #2e7d32); --mid: var(--warning-color, #f9a825); --dear: var(--error-color, #c62828); }
        ha-card { padding: 16px; }
        .head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
        .title { font-size: 1rem; color: var(--secondary-text-color); }
        .price { font-size: 2rem; font-weight: 600; line-height: 1.1; color: var(--primary-text-color); }
        .chip { font-size: .8rem; padding: 2px 8px; border-radius: 10px; background: var(--secondary-background-color); color: var(--secondary-text-color); }
        .best { margin: 12px 0 8px; display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: baseline; }
        .best .label { color: var(--secondary-text-color); width: 100%; font-size: .85rem; }
        .best .value { font-size: 1.3rem; font-weight: 600; color: var(--cheap); }
        .best .detail { color: var(--secondary-text-color); font-size: .85rem; }
        .sub { font-size: .8rem; color: var(--secondary-text-color); margin-top: 8px; }
        svg { width: 100%; height: auto; overflow: visible; }
        svg text { font-size: 9px; fill: var(--secondary-text-color); }
        rect.cheap { fill: var(--cheap); } rect.mid { fill: var(--mid); } rect.dear { fill: var(--dear); }
        rect.bestband { fill: var(--cheap); opacity: .15; }
        line.tick { stroke: var(--secondary-text-color); stroke-width: .5; }
        .msg { color: var(--error-color, #c62828); }
        .foot { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 8px; margin-top: 8px; font-size: .7rem; color: var(--secondary-text-color); }
        .foot > span:first-child { flex: 1 1 180px; }
        /* the links stay together: on a narrow card they move to a line of their own */
        .foot .links { white-space: nowrap; margin-left: auto; }
        .foot a { color: inherit; }
      </style>
      <ha-card>
        <div class="head"><span class="title">${title}</span>${chip ? `<span class="chip">${chip}</span>` : ""}</div>
        <div class="price">${formatPrice(price, unit)}</div>
        ${bestHtml}
        <div class="sub">${t.next}</div>
        <svg viewBox="0 0 ${width} ${height + 16}" role="img" aria-label="${t.next}">${bestBand}${bars}${ticks}</svg>
        ${footHtml}
      </ha-card>`;
    // The guide opens inside Home Assistant, without reloading the page.
    const guideLink = this.shadowRoot.querySelector("a.guide");
    if (guideLink) guideLink.addEventListener("click", (ev) => {
      ev.preventDefault();
      window.history.pushState(null, "", GUIDE_PATH);
      window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
    });
  }
}

if (!customElements.get("corrente-card")) {
  customElements.define("corrente-card", CorrenteCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "corrente-card",
    name: "Corrente",
    description: "Electricity price now, the next hours and the best time to start.",
    documentationURL: "https://github.com/MichaelPito/ha-corrente",
  });
}
