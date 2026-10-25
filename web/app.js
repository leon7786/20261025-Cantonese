/* 粵語 TTS 實驗室 — front-end logic (no build step) */

const MAX_CHARS = 2000;

const SAMPLES = [
  { label: "日常問候", text: "你好，我係阿明，今日天氣好好，不如一齊去飲茶？" },
  { label: "數字時間", text: "呢個優惠做到二〇二六年十月三十一號，記得準時交表。" },
  { label: "繞口令", text: "四十四隻石獅子，死死實實食咗四十四隻死雞。" },
  { label: "新聞腔", text: "政府今日公布，下個月起會調整公共交通票價，市民普遍表示關注。" },
  { label: "中英夾雜", text: "我哋個 project 今日 deadline，你快啲 send 個 file 俾我。" },
  { label: "懶音測試", text: "你覺得呢個構想係咪真係可行？我諗諗先，轉頭覆你。" },
];

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};

const state = { engines: [], running: false, playing: false, stopPlay: false };

/* ---------------- text composer ---------------- */

const textarea = $("#text");
const count = $("#count");

function updateCount() {
  const n = textarea.value.length;
  count.textContent = n.toLocaleString();
  count.parentElement.classList.toggle("over", n > MAX_CHARS);
  const over = n > MAX_CHARS;
  $("#runAll").disabled = over || state.running;
  saveText();
}

let saveTimer;
function saveText() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try { localStorage.setItem("cantonese.text", textarea.value); } catch { /* ignore */ }
  }, 250);
}

function setText(value) {
  textarea.value = value;
  updateCount();
  textarea.focus();
}

function renderSamples() {
  const box = $("#samples");
  for (const s of SAMPLES) {
    const b = el("button", "chip", s.label);
    b.type = "button";
    b.title = s.text;
    b.addEventListener("click", () => setText(s.text));
    box.append(b);
  }
}

/* ---------------- card factory ---------------- */

function makeCard(engine) {
  const card = el("article", "card");
  card.dataset.id = engine.id;
  card.dataset.available = String(engine.available);
  card.dataset.category = engine.category || "baseline";
  if (!engine.available) card.classList.add("offline");
  if (engine.category === "paid") card.classList.add("paid");

  const head = el("header", "card-head");
  const titleWrap = el("div", "card-title");
  const h2 = el("h2", null, engine.name);
  const badgeText = engine.requires_key
    ? "需 API Key"
    : ({ local: "本地", online: "在線", remote: "需配置" }[engine.kind] || engine.kind);
  const badge = el("span", `badge ${engine.requires_key ? "paid" : engine.kind}`, badgeText);
  titleWrap.append(h2, badge);
  const link = el("a", null, "GitHub ↗");
  link.href = engine.homepage;
  link.target = "_blank";
  link.rel = "noreferrer";
  head.append(titleWrap, link);

  const desc = el("p", "desc", engine.description);

  const status = el("div", `status ${engine.available ? "ok" : "bad"}`);
  status.append(el("span", "dot"), el("span", null, engine.detail || (engine.available ? "可用" : "不可用")));

  const controls = el("div", "controls");

  // voice select
  const voiceField = el("label", "field");
  voiceField.append(el("span", null, "音色"));
  const select = el("select");
  (engine.voices || []).forEach((v, i) => {
    const opt = el("option", null, v.label + (v.note ? ` · ${v.note}` : ""));
    opt.value = v.id;
    if (i === 0) opt.selected = true;
    select.append(opt);
  });
  voiceField.append(select);
  controls.append(voiceField);

  // rate slider
  let rateInput = null;
  let rateOut = null;
  if (engine.supports_rate) {
    const field = el("div", "field");
    field.append(el("span", null, "語速"));
    const row = el("div", "range-row");
    rateInput = el("input");
    rateInput.type = "range";
    rateInput.min = "-30";
    rateInput.max = "30";
    rateInput.step = "5";
    rateInput.value = "0";
    rateOut = el("output", null, "0%");
    rateInput.addEventListener("input", () => { rateOut.textContent = `${rateInput.value}%`; });
    row.append(rateInput, rateOut);
    field.append(row);
    controls.append(field);
  }

  const foot = el("div", "card-foot");
  const btn = el("button", "btn primary", engine.id === "browser" ? "朗讀" : "合成");
  btn.type = "button";
  btn.dataset.idle = btn.textContent;
  btn.disabled = !engine.available;
  const meta = el("span", "meta");
  foot.append(btn, meta);

  const audio = el("audio");
  audio.controls = true;
  audio.preload = "none";
  audio.hidden = true;

  const error = el("div", "error");
  error.hidden = true;

  card.append(head, desc, status, controls, foot, audio, error);
  if (!engine.available) {
    select.disabled = true;
    if (rateInput) rateInput.disabled = true;
  }
  card._refs = { btn, meta, audio, error, select, rateInput, status };

  btn.addEventListener("click", () => handleSynth(card, engine));

  return card;
}

/* ---------------- synthesis ---------------- */

async function handleSynth(card, engine, { fromAll = false } = {}) {
  if (state.running && !fromAll) return;
  const { btn, meta, audio, error } = card._refs;
  const text = textarea.value.trim();
  if (!text) { showError(card, "請先輸入文字"); return; }
  if (text.length > MAX_CHARS) { showError(card, `文字超過 ${MAX_CHARS} 字`); return; }

  clearError(card);

  if (engine.id === "browser") {
    speakInBrowser(card, engine, text);
    return;
  }

  setBusy(card, btn, true);
  meta.textContent = "合成中…";
  try {
    const payload = {
      engine: engine.id,
      text,
      voice: card._refs.select.value,
      rate: card._refs.rateInput ? Number(card._refs.rateInput.value) : 0,
    };
    const resp = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);

    audio.hidden = false;
    audio.src = data.url;
    meta.innerHTML = "";
    meta.append(
      document.createTextNode(`${(data.bytes / 1024).toFixed(0)} KB · ${data.ms} ms `),
    );
    if (data.cached) meta.append(el("span", "cached", "· 快取"));

    audio.play().catch(() => { /* autoplay may be blocked; user can press play */ });
  } catch (err) {
    showError(card, err.message || String(err));
    meta.textContent = "";
  } finally {
    setBusy(card, btn, false);
  }
}

function setBusy(card, btn, busy) {
  card.classList.toggle("busy", busy);
  btn.disabled = busy || card.dataset.available !== "true";
  btn.replaceChildren();
  if (busy) {
    btn.append(el("span", "spinner"), document.createTextNode(" 合成中"));
  } else {
    btn.textContent = btn.dataset.idle || "合成";
  }
}

function showError(card, message) {
  const box = card._refs.error;
  box.hidden = false;
  box.textContent = message;
}

function clearError(card) {
  const box = card._refs.error;
  box.hidden = true;
  box.textContent = "";
}

/* ---------------- browser speech ---------------- */

function browserVoices() {
  if (!("speechSynthesis" in window)) return [];
  return speechSynthesis
    .getVoices()
    .filter((v) => /^(zh[-_]HK|yue)/i.test(v.lang) || /cantonese|粵|粤/i.test(v.name));
}

function speakInBrowser(card, engine, text) {
  const synth = window.speechSynthesis;
  if (!synth) { showError(card, "此瀏覽器不支援 Web Speech API"); return; }
  synth.cancel();

  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "zh-HK";
  const chosen = browserVoices().find((v) => v.name === card._refs.select.value);
  if (chosen) utter.voice = chosen;
  if (card._refs.rateInput) utter.rate = Math.max(0.5, Math.min(2, 1 + Number(card._refs.rateInput.value) / 100));

  const started = performance.now();
  card._refs.meta.textContent = "朗讀中…";
  utter.onend = () => {
    card._refs.meta.textContent = `完成 · ${((performance.now() - started) / 1000).toFixed(1)} s`;
  };
  utter.onerror = (e) => {
    showError(card, `朗讀失敗：${e.error || "unknown"}`);
    card._refs.meta.textContent = "";
  };
  synth.speak(utter);
}

function buildBrowserCard() {
  const hasApi = "speechSynthesis" in window;
  const voices = hasApi ? browserVoices() : [];
  const engine = {
    id: "browser",
    category: "baseline",
    name: "瀏覽器語音",
    vendor: "Web Speech API",
    kind: "local",
    description: "直接使用作業系統的粵語語音（Windows／macOS／Android 內建），不經伺服器。",
    homepage: "https://developer.mozilla.org/docs/Web/API/SpeechSynthesis",
    supports_rate: true,
    available: hasApi && voices.length > 0,
    detail: !hasApi
      ? "此瀏覽器不支援 Web Speech API"
      : voices.length
        ? `系統粵語語音：${voices.length} 個`
        : "系統未安裝 zh-HK 粵語語音（可於系統設定新增）",
    voices: voices.map((v) => ({ id: v.name, label: `${v.name} (${v.lang})`, note: v.localService ? "離線" : "在線" })),
  };
  return makeCard(engine);
}

/* ---------------- orchestration ---------------- */

async function runAll() {
  if (state.running) return;
  const text = textarea.value.trim();
  if (!text) { textarea.focus(); return; }
  if (text.length > MAX_CHARS) return;

  const cards = [...document.querySelectorAll(".card")].filter(
    (c) =>
      c.dataset.id !== "browser" &&
      c.dataset.category !== "paid" &&
      c.dataset.available === "true",
  );
  if (!cards.length) return;

  state.running = true;
  const runBtn = $("#runAll");
  const label = runBtn.querySelector(".label");
  const spinner = runBtn.querySelector(".spinner");
  runBtn.disabled = true;
  spinner.hidden = false;

  try {
    for (let i = 0; i < cards.length; i++) {
      label.textContent = `合成中 ${i + 1}/${cards.length}`;
      const engine = state.engines.find((e) => e.id === cards[i].dataset.id);
      await handleSynth(cards[i], engine, { fromAll: true });
    }
  } finally {
    state.running = false;
    runBtn.disabled = false;
    spinner.hidden = true;
    label.textContent = "全部合成";
    $("#playAll").disabled = !document.querySelector("audio[src]");
  }
}

let currentAudio = null;

async function playAll() {
  if (state.playing) {
    state.stopPlay = true;
    currentAudio?.pause();
    return;
  }
  const audios = [...document.querySelectorAll(".card audio")]
    .filter((a) => a.src && !a.closest(".card").classList.contains("offline"));
  if (!audios.length) return;

  state.playing = true;
  state.stopPlay = false;
  const btn = $("#playAll");
  btn.textContent = "停止播放";

  for (const audio of audios) {
    if (state.stopPlay) break;
    currentAudio = audio;
    audio.currentTime = 0;
    try {
      await playToEnd(audio);
    } catch { /* ignore */ }
  }

  btn.textContent = "依次試聽";
  state.playing = false;
  currentAudio = null;
}

function playToEnd(audio) {
  return new Promise((resolve, reject) => {
    const done = () => { cleanup(); resolve(); };
    const fail = () => { cleanup(); reject(new Error("playback failed")); };
    const cleanup = () => {
      audio.removeEventListener("ended", done);
      audio.removeEventListener("error", fail);
    };
    audio.addEventListener("ended", done, { once: true });
    audio.addEventListener("error", fail, { once: true });
    audio.play().catch(fail);
  });
}

/* ---------------- boot ---------------- */

async function boot() {
  renderSamples();
  const saved = localStorage.getItem("cantonese.text");
  if (saved) textarea.value = saved;
  updateCount();

  textarea.addEventListener("input", updateCount);

  $("#clear").addEventListener("click", () => setText(""));
  $("#runAll").addEventListener("click", runAll);
  $("#playAll").addEventListener("click", playAll);

  textarea.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      runAll();
    }
  });

  try {
    const resp = await fetch("/api/engines");
    state.engines = await resp.json();
  } catch {
    state.engines = [];
  }

  const root = $("#engines");
  root.innerHTML = "";

  const GROUPS = [
    { id: "quality", title: "免費 · 推薦音質", note: "自然度較好，優先比較這幾個。" },
    { id: "baseline", title: "免費 · 基線對照", note: "小模型或傳統合成，音質明顯較舊，僅作對照。" },
    { id: "selfhost", title: "免費 · 需自行部署", note: "開源模型，需先啟動服務並在 .env 填入地址。" },
    { id: "paid", title: "需要 API Key · 非免費", note: "按調用量收費，預設不參與「全部合成」。" },
  ];

  for (const group of GROUPS) {
    const items = state.engines.filter((e) => (e.category || "ready") === group.id);
    if (!items.length && group.id !== "paid") continue;

    const section = el("section", "section");
    section.dataset.group = group.id;
    const head = el("div", "section-head");
    head.append(el("h2", null, group.title), el("p", null, group.note));
    const grid = el("div", "grid");
    items.forEach((engine) => grid.append(makeCard(engine)));
    if (group.id === "baseline") grid.append(buildBrowserCard());
    section.append(head, grid);
    root.append(section);
  }

  const available = state.engines.filter((e) => e.available).length;
  $("#statEngines").textContent = String(available + (browserVoices().length ? 1 : 0));

  // System voices can arrive late (Chrome).
  if ("speechSynthesis" in window) {
    speechSynthesis.addEventListener("voiceschanged", () => {
      const old = root.querySelector('[data-id="browser"]');
      if (old) old.replaceWith(buildBrowserCard());
    });
  }

  $("#runAll").disabled = state.engines.every((e) => !e.available);
}

boot();
