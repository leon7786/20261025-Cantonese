/* 跟讀學粵語 — 點句播放，Qwen-Audio-3.0-TTS-Plus 女聲 */
(() => {
  const ARTICLES = window.LEARN_ARTICLES || [];
  const ENGINE = "qwen-tts";
  const VOICE = "longanlingxin";
  const INSTRUCTIONS = {
    normal: "请用广东话表达。",
    slow: "请用广东话表达，语速放慢，吐字清晰。",
  };

  const $ = (id) => document.getElementById(id);
  const player = $("player");
  const statusEl = $("status");
  const tabsEl = $("tabs");
  const listEl = $("sentences");
  const titleEl = $("artTitle");
  const tagEl = $("artTag");
  const playAllBtn = $("playAll");
  const stopBtn = $("stop");

  const state = {
    art: 0,
    speed: "normal",
    cache: new Map(),
    stop: false,
    running: false,
    currentRow: null,
  };

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  function setStatus(text, kind = "") {
    statusEl.textContent = text;
    statusEl.dataset.kind = kind;
  }

  function renderTabs() {
    tabsEl.innerHTML = "";
    ARTICLES.forEach((art, i) => {
      const btn = el("button", "tab" + (i === state.art ? " active" : ""));
      btn.type = "button";
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", String(i === state.art));
      btn.append(el("span", "tab-title", art.title), el("span", "tab-count", `${art.sentences.length} 句`));
      btn.addEventListener("click", () => selectArticle(i));
      tabsEl.append(btn);
    });
  }

  function selectArticle(i) {
    if (state.running) stopAll();
    state.art = i;
    renderTabs();
    renderArticle();
    setStatus("點句子即播放");
  }

  function renderArticle() {
    const art = ARTICLES[state.art];
    if (!art) return;
    titleEl.textContent = art.title;
    tagEl.textContent = art.tag;
    listEl.innerHTML = "";

    art.sentences.forEach((sentence, i) => {
      const li = el("li", "sentence");
      li.tabIndex = 0;
      li.setAttribute("role", "button");
      li.setAttribute("aria-label", `播放第 ${i + 1} 句`);

      const num = el("span", "sent-num", String(i + 1).padStart(2, "0"));
      const body = el("div", "sent-body");
      body.append(el("p", "sent-zh", sentence.zh), el("p", "sent-jy", sentence.jy));
      const play = el("span", "sent-play", "▶");
      const badge = el("span", "sent-badge", "");

      li.append(num, body, play, badge);
      li.addEventListener("click", () => playOne(i));
      li.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          playOne(i);
        }
      });
      listEl.append(li);
    });
  }

  function row(i) {
    return listEl.children[i] || null;
  }

  function markRow(li, kind, text = "") {
    if (!li) return;
    li.classList.remove("is-loading", "is-playing", "is-error");
    if (kind) li.classList.add(`is-${kind}`);
    const badge = li.querySelector(".sent-badge");
    if (badge) badge.textContent = text;
  }

  async function synthesize(text) {
    const key = `${state.speed}|${text}`;
    if (state.cache.has(key)) return state.cache.get(key);

    const resp = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        engine: ENGINE,
        text,
        voice: VOICE,
        instruction: INSTRUCTIONS[state.speed],
      }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
    state.cache.set(key, data.url);
    return data.url;
  }

  function playUrl(url) {
    return new Promise((resolve) => {
      player.hidden = false;
      player.src = url;
      const done = () => {
        player.onended = null;
        player.onerror = null;
        player.onpause = null;
        resolve();
      };
      player.onended = done;
      player.onerror = done;
      player.onpause = done;
      player.play().catch(done);
    });
  }

  async function playOne(i, { chain = false } = {}) {
    if (state.running && !chain) return;
    const art = ARTICLES[state.art];
    const sentence = art.sentences[i];
    const li = row(i);
    if (!sentence || !li) return;

    markRow(li, "loading", "生成中…");
    setStatus(`第 ${i + 1} 句生成中，首次約 10 秒…`);

    try {
      const url = await synthesize(sentence.zh);
      if (state.stop) {
        markRow(li, "", "");
        return;
      }
      markRow(li, "playing", "播放中");
      setStatus(`第 ${i + 1} / ${art.sentences.length} 句`);
      if (!chain) stopBtn.disabled = false;
      await playUrl(url);
      markRow(li, "", "");
      if (!chain) {
        stopBtn.disabled = true;
        if (!state.stop) setStatus("點句子即播放");
      }
    } catch (err) {
      markRow(li, "error", "失敗");
      setStatus(`第 ${i + 1} 句失敗：${err.message}`, "error");
      if (!chain) stopBtn.disabled = true;
      throw err;
    }
  }

  async function playAll() {
    if (state.running) return;
    state.running = true;
    state.stop = false;
    playAllBtn.disabled = true;
    stopBtn.disabled = false;

    const total = ARTICLES[state.art].sentences.length;
    try {
      for (let i = 0; i < total; i++) {
        if (state.stop) break;
        await playOne(i, { chain: true });
      }
      if (!state.stop) setStatus("全篇播放完畢");
    } catch {
      /* 錯誤已顯示在對應句子 */
    } finally {
      state.running = false;
      playAllBtn.disabled = false;
      stopBtn.disabled = true;
    }
  }

  function stopAll() {
    state.stop = true;
    state.running = false;
    player.pause();
    player.removeAttribute("src");
    player.hidden = true;
    listEl.querySelectorAll(".sentence").forEach((li) => markRow(li, "", ""));
    playAllBtn.disabled = false;
    stopBtn.disabled = true;
    setStatus("已停止");
  }

  function bindSpeed() {
    $("speed").addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-speed]");
      if (!btn) return;
      state.speed = btn.dataset.speed;
      $("speed").querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
      state.cache.clear();
      setStatus(`語速：${btn.textContent}（已清快取，重新生成）`);
    });
  }

  function init() {
    if (!ARTICLES.length) {
      setStatus("文章資料載入失敗", "error");
      return;
    }
    renderTabs();
    renderArticle();
    bindSpeed();
    playAllBtn.addEventListener("click", playAll);
    stopBtn.addEventListener("click", stopAll);
    player.addEventListener("play", () => setStatus("播放中…"));
  }

  init();
})();
