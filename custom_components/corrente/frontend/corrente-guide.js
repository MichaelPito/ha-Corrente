// Corrente's guide: a sidebar panel. Content and status come from the integration
// (websocket "corrente/guide", built from guide.json); see docs/ONBOARDING.md.
// Pick a topic, or follow the full guide step by step; /corrente-guide?topic=<id>
// and /corrente-guide?tour=1 open it at the right place.

const TOUR_KEY = "corrente-guide-tour";
const SHOW_ALL_KEY = "corrente-guide-all";

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// The small markdown the guide uses: **bold**, *italic*, `code`, [links](url), "- " lists.
function markdown(text) {
  const inline = (line) =>
    escapeHtml(line)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, "<code>$1</code>")
      .replace(/\[(.+?)\]\((.+?)\)/g, (_, label, url) =>
        url.startsWith("/")
          ? `<a href="${url}" data-internal="1">${label}</a>`
          : `<a href="${url}" target="_blank" rel="noopener">${label}</a>`
      );
  const out = [];
  let list = false;
  for (const line of String(text).split("\n")) {
    if (line.startsWith("- ")) {
      if (!list) out.push("<ul>");
      list = true;
      out.push(`<li>${inline(line.slice(2))}</li>`);
      continue;
    }
    if (list) out.push("</ul>");
    list = false;
    if (line.trim()) out.push(`<p>${inline(line)}</p>`);
  }
  if (list) out.push("</ul>");
  return out.join("");
}

function storageGet(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (_) {
    return null;
  }
}

function storageSet(key, value) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch (_) {
    /* private mode: the guide works, it just does not remember */
  }
}

class CorrenteGuidePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._error = null;
    this._view = "home";
    this._topic = null;
    this._step = 0;
    this._showAll = storageGet(SHOW_ALL_KEY) === "1";
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._load();
    else if (this._narrowButton) this._narrowButton.hass = hass;
  }

  set narrow(narrow) {
    this._narrow = narrow;
    if (this._data) this._render();
  }

  async _load() {
    try {
      this._data = await this._hass.callWS({ type: "corrente/guide" });
    } catch (err) {
      this._error = err && err.message ? err.message : String(err);
    }
    const params = new URLSearchParams(window.location.search);
    if (params.get("tour")) this._startTour(params.get("tour") === "restart");
    else if (params.get("topic") === "whats_new") this._view = "news";
    else if (params.get("topic") && this._find(params.get("topic"))) this._open(params.get("topic"));
    this._render();
  }

  // --- content helpers ---

  get _lang() {
    const lang = ((this._hass && this._hass.language) || "en").split("-")[0];
    return ["en", "it", "de", "fr"].includes(lang) ? lang : "en";
  }

  _t(texts) {
    if (texts === undefined || texts === null) return "";
    if (typeof texts === "string") return texts;
    return texts[this._lang] !== undefined ? texts[this._lang] : texts.en;
  }

  _ui(key) {
    return this._t(this._data.content.ui[key]);
  }

  _find(id) {
    return this._data.content.topics.find((t) => t.id === id);
  }

  _status(topic) {
    return topic.status ? this._data.status[topic.status] || "" : "";
  }

  // Topics for this home: its countries (all if none set up yet, or "show both").
  _relevant(topic) {
    const countries = this._data.countries;
    if (this._showAll || !countries.length || !topic.countries.length) return true;
    return topic.countries.some((c) => countries.includes(c));
  }

  _tourTopics() {
    return this._data.content.tour
      .map((id) => this._find(id))
      .filter((t) => t && this._relevant(t) && this._status(t) !== "na");
  }

  // --- navigation ---

  _open(id) {
    this._view = "topic";
    this._topic = id;
    this._step = 0;
  }

  _startTour(restart) {
    const saved = restart ? null : storageGet(TOUR_KEY);
    const ids = this._tourTopics().map((t) => t.id);
    let [topic, step] = saved ? saved.split(":") : [ids[0], "0"];
    if (!ids.includes(topic)) [topic, step] = [ids[0], "0"];
    this._view = "tour";
    this._topic = topic;
    this._step = Number(step) || 0;
  }

  _saveTour() {
    storageSet(TOUR_KEY, this._view === "tour" ? `${this._topic}:${this._step}` : null);
  }

  _move(delta) {
    const topics = this._view === "tour" ? this._tourTopics() : [this._find(this._topic)];
    let index = topics.findIndex((t) => t.id === this._topic);
    let step = this._step + delta;
    if (step >= topics[index].steps.length) {
      index += 1;
      step = 0;
    } else if (step < 0) {
      index -= 1;
      step = index >= 0 ? topics[index].steps.length - 1 : 0;
    }
    if (index < 0) return;
    if (index >= topics.length) {
      this._view = this._view === "tour" ? "finished" : "home";
      storageSet(TOUR_KEY, null);
    } else {
      this._topic = topics[index].id;
      this._step = step;
      if (this._view === "tour") this._saveTour();
    }
    this._render();
  }

  _skipTopic() {
    const topic = this._find(this._topic);
    this._step = topic.steps.length - 1;
    this._move(1);
  }

  _home() {
    this._view = "home";
    this._topic = null;
    this._render();
    window.history.replaceState(null, "", window.location.pathname);
  }

  _navigate(path) {
    if (path.startsWith("/")) {
      window.history.pushState(null, "", path);
      window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
    } else {
      window.open(path, "_blank", "noopener");
    }
  }

  // --- rendering ---

  _badge(topic) {
    const status = this._status(topic);
    if (status === "done") return `<span class="badge done">✓ ${this._ui("done")}</span>`;
    if (status === "todo") return `<span class="badge todo">${this._ui("todo")}</span>`;
    return "";
  }

  _topicCard(topic) {
    return `<button class="topic" data-topic="${topic.id}">
      <ha-icon icon="${topic.icon}"></ha-icon>
      <span class="text"><span class="name">${escapeHtml(this._t(topic.title))}</span>
      <span class="summary">${escapeHtml(this._t(topic.summary))}</span></span>
      ${this._badge(topic)}</button>`;
  }

  _homeHtml() {
    const topics = this._data.content.topics.filter((t) => this._relevant(t) && this._status(t) !== "na");
    const forYou = this._tourTopics().filter((t) => this._status(t) === "todo");
    const resume = storageGet(TOUR_KEY);
    const news = this._data.content.whats_new[0];
    const countries = this._data.countries;
    const toggle = countries.length === 1
      ? `<label class="toggle"><input type="checkbox" id="all" ${this._showAll ? "checked" : ""}>
         ${escapeHtml(this._ui("show_all"))}</label>`
      : "";
    return `
      <div class="hero">
        <button class="primary" id="tour">${escapeHtml(this._ui(resume ? "resume_tour" : "full_tour"))}</button>
        ${resume ? `<button class="link" id="restart">${escapeHtml(this._ui("full_tour"))}</button>` : ""}
      </div>
      <h2>${escapeHtml(this._ui("for_you"))}</h2>
      ${forYou.length ? `<div class="grid">${forYou.map((t) => this._topicCard(t)).join("")}</div>`
        : `<p class="muted">${escapeHtml(this._ui("all_set"))}</p>`}
      <h2>${escapeHtml(this._ui("whats_new"))} <span class="muted">· ${escapeHtml(this._ui("version"))} ${escapeHtml(news.version)}</span></h2>
      <div class="news">${markdown(this._t(news.items).map((i) => `- ${i}`).join("\n"))}
        <button class="link" id="news">${escapeHtml(this._ui("whats_new"))} →</button></div>
      <h2>${escapeHtml(this._ui("topics"))}</h2>${toggle}
      <div class="grid">${topics.map((t) => this._topicCard(t)).join("")}</div>`;
  }

  _newsHtml() {
    return `<button class="link" id="home">← ${escapeHtml(this._ui("home"))}</button>
      <h1>${escapeHtml(this._ui("whats_new"))}</h1>
      ${this._data.content.whats_new.map((n) => `<section class="news">
        <h2>${escapeHtml(this._ui("version"))} ${escapeHtml(n.version)} <span class="muted">· ${escapeHtml(n.date)}</span></h2>
        ${markdown(this._t(n.items).map((i) => `- ${i}`).join("\n"))}</section>`).join("")}`;
  }

  _stepHtml() {
    const topic = this._find(this._topic);
    const step = topic.steps[this._step];
    const tour = this._view === "tour";
    const topics = tour ? this._tourTopics() : [topic];
    const all = topics.flatMap((t) => t.steps.map((_, i) => `${t.id}:${i}`));
    const position = all.indexOf(`${topic.id}:${this._step}`) + 1;
    // Settings pages are for administrators: other users do not get a button that fails.
    const admin = !this._hass.user || this._hass.user.is_admin;
    const action = step.action && (admin || !step.action.path.startsWith("/config"))
      ? `<button class="primary" id="action" data-path="${escapeHtml(step.action.path)}">${escapeHtml(this._t(step.action.label))}</button>`
      : "";
    const first = position === 1;
    const last = position === all.length;
    return `
      <div class="crumbs"><button class="link" id="home">← ${escapeHtml(this._ui("home"))}</button>
        ${tour ? `<span class="muted">${escapeHtml(this._ui("step_of").replace("{n}", position).replace("{total}", all.length))}</span>` : ""}</div>
      ${tour ? `<div class="bar"><div style="width:${(100 * position) / all.length}%"></div></div>` : ""}
      <div class="topichead"><ha-icon icon="${topic.icon}"></ha-icon>
        <h1>${escapeHtml(this._t(topic.title))}</h1>${this._badge(topic)}</div>
      <ol class="steps">${topic.steps.map((s, i) => `<li class="${i === this._step ? "current" : ""}"
        data-step="${i}">${escapeHtml(this._t(s.title))}</li>`).join("")}</ol>
      <section class="step"><h2>${escapeHtml(this._t(step.title))}</h2>
        ${markdown(this._t(step.body))}${action}</section>
      <div class="nav">
        <button id="back" ${first ? "disabled" : ""}>${escapeHtml(this._ui("back"))}</button>
        ${tour ? `<button class="link" id="skip">${escapeHtml(this._ui("skip_topic"))}</button>` : ""}
        <button class="primary" id="next">${escapeHtml(this._ui(last ? "finish" : "next"))}</button>
      </div>
      ${tour ? `<button class="link exit" id="exit">${escapeHtml(this._ui("exit"))}</button>` : ""}`;
  }

  _finishedHtml() {
    return `<div class="finished"><ha-icon icon="mdi:check-circle"></ha-icon>
      <p>${escapeHtml(this._ui("finished"))}</p>
      <button class="primary" id="home">${escapeHtml(this._ui("home"))}</button></div>`;
  }

  _render() {
    if (!this._data && !this._error) return;
    let body;
    if (this._error) body = `<p class="muted">${escapeHtml(this._error)}</p>`;
    else if (this._view === "topic" || this._view === "tour") body = this._stepHtml();
    else if (this._view === "news") body = this._newsHtml();
    else if (this._view === "finished") body = this._finishedHtml();
    else body = this._homeHtml();
    const title = this._data ? escapeHtml(this._ui("title")) : "Corrente";
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; background: var(--primary-background-color); min-height: 100vh;
          color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, inherit); }
        .toolbar { display: flex; align-items: center; height: 56px; padding: 0 12px; gap: 8px;
          background: var(--app-header-background-color, var(--primary-color));
          color: var(--app-header-text-color, white); font-size: 20px; }
        main { max-width: 860px; margin: 0 auto; padding: 16px; box-sizing: border-box; }
        h1 { font-size: 1.5rem; margin: 0; }
        h2 { font-size: 1.1rem; margin: 24px 0 8px; }
        p { line-height: 1.5; margin: 8px 0; }
        ul { padding-left: 20px; line-height: 1.5; }
        code { background: var(--secondary-background-color); padding: 1px 4px; border-radius: 4px; }
        a { color: var(--primary-color); }
        .muted { color: var(--secondary-text-color); font-weight: normal; }
        button { font: inherit; cursor: pointer; border-radius: 8px; padding: 8px 14px;
          border: 1px solid var(--divider-color); background: var(--card-background-color);
          color: var(--primary-text-color); }
        button[disabled] { opacity: 0.4; cursor: default; }
        button.primary { background: var(--primary-color); color: var(--text-primary-color, white); border-color: transparent; }
        button.link { border: none; background: none; color: var(--primary-color); padding: 4px 0; }
        .hero { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin: 8px 0 4px; }
        .hero .primary { font-size: 1.05rem; padding: 12px 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
        .topic { display: flex; align-items: flex-start; gap: 12px; text-align: left; padding: 12px;
          background: var(--card-background-color); border-radius: 12px; }
        .topic ha-icon { color: var(--primary-color); flex: none; }
        .topic .text { display: flex; flex-direction: column; gap: 2px; flex: 1; }
        .topic .name { font-weight: 500; }
        .topic .summary { color: var(--secondary-text-color); font-size: 0.9rem; }
        .badge { font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
        .badge.done { background: var(--success-color, #43a047); color: white; }
        .badge.todo { background: var(--warning-color, #ffa600); color: black; }
        .news { background: var(--card-background-color); border-radius: 12px; padding: 8px 16px; margin-bottom: 8px; }
        .toggle { display: block; margin: 0 0 8px; color: var(--secondary-text-color); }
        .crumbs { display: flex; justify-content: space-between; align-items: center; }
        .bar { height: 4px; background: var(--divider-color); border-radius: 2px; margin: 8px 0 16px; }
        .bar div { height: 4px; background: var(--primary-color); border-radius: 2px; }
        .topichead { display: flex; align-items: center; gap: 10px; margin: 12px 0; flex-wrap: wrap; }
        .topichead ha-icon { color: var(--primary-color); }
        .steps { display: flex; flex-wrap: wrap; gap: 6px; padding: 0; list-style: none; margin: 0 0 8px; counter-reset: s; }
        .steps li { counter-increment: s; font-size: 0.85rem; padding: 4px 10px; border-radius: 12px; cursor: pointer;
          background: var(--secondary-background-color); color: var(--secondary-text-color); }
        .steps li::before { content: counter(s) ". "; }
        .steps li.current { background: var(--primary-color); color: var(--text-primary-color, white); }
        .step { background: var(--card-background-color); border-radius: 12px; padding: 4px 16px 16px; }
        .step .primary { margin-top: 8px; }
        .nav { display: flex; justify-content: space-between; gap: 8px; margin-top: 16px; }
        .exit { margin-top: 12px; }
        .finished { text-align: center; padding: 40px 0; }
        .finished ha-icon { --mdc-icon-size: 64px; color: var(--success-color, #43a047); }
      </style>
      <div class="toolbar">${this._narrow ? '<ha-menu-button id="menu"></ha-menu-button>' : ""}<span>${title}</span></div>
      <main>${body}</main>`;
    this._wire();
  }

  _wire() {
    const root = this.shadowRoot;
    const on = (id, handler) => {
      const el = root.getElementById(id);
      if (el) el.addEventListener("click", handler);
    };
    this._narrowButton = root.getElementById("menu");
    if (this._narrowButton) {
      this._narrowButton.hass = this._hass;
      this._narrowButton.narrow = true;
    }
    on("tour", () => { this._startTour(false); this._saveTour(); this._render(); });
    on("restart", () => { this._startTour(true); this._saveTour(); this._render(); });
    on("home", () => this._home());
    on("news", () => { this._view = "news"; this._render(); });
    on("next", () => this._move(1));
    on("back", () => this._move(-1));
    on("skip", () => this._skipTopic());
    on("exit", () => { storageSet(TOUR_KEY, null); this._home(); });
    on("action", (ev) => this._navigate(ev.currentTarget.dataset.path));
    const all = root.getElementById("all");
    if (all) all.addEventListener("change", () => {
      this._showAll = all.checked;
      storageSet(SHOW_ALL_KEY, all.checked ? "1" : null);
      this._render();
    });
    root.querySelectorAll("[data-topic]").forEach((el) =>
      el.addEventListener("click", () => { this._open(el.dataset.topic); this._render(); }));
    root.querySelectorAll("[data-step]").forEach((el) =>
      el.addEventListener("click", () => { this._step = Number(el.dataset.step); this._saveTour(); this._render(); }));
    root.querySelectorAll("a[data-internal]").forEach((el) =>
      el.addEventListener("click", (ev) => { ev.preventDefault(); this._navigate(el.getAttribute("href")); }));
  }
}

if (!customElements.get("corrente-guide-panel")) {
  customElements.define("corrente-guide-panel", CorrenteGuidePanel);
}
