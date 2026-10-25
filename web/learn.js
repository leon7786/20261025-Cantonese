/* 跟讀學粵語 — 離線音頻、粵拼 ruby、點句播放 */
(() => {
  const $ = (id) => document.getElementById(id);
  const player = $("player");
  const statusEl = $("status");
  const tabsEl = $("tabs");
  const proseEl = $("prose");
  const titleEl = $("artTitle");
  const tagEl = $("artTag");
  const metaEl = $("artMeta");
  const playAllBtn = $("playAll");
  const stopBtn = $("stop");

  const PUNCT = /[，。！？；：、,.!?;:]/;
  const state = { articles: [], art: 0, playing: false, stop: false, current: null };

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
    state.articles.forEach((art, i) => {
      const btn = el("button", "tab" + (i === state.art ? " active" : ""));
      btn.type = "button";
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", String(i === state.art));
      btn.append(el("span", "tab-title", art.title), el("span", "tab-count", `${art.segments.length} 句`));
      btn.addEventListener("click", () => selectArticle(i));
      tabsEl.append(btn);
    });
  }

  function renderSegment(span, zh, jy) {
    span.append(el("span", "seg-jy", jy.trim()));
    span.append(el("span", "seg-zh", zh));
  }

  function renderArticle() {
    const art = state.articles[state.art];
    if (!art) return;
    titleEl.textContent = art.title;
    tagEl.textContent = art.tag;
    metaEl.textContent = `共 ${art.segments.length} 句 · ${art.duration}s`;
    proseEl.innerHTML = "";

    art.segments.forEach((seg, i) => {
      const span = el("span", "seg");
      span.tabIndex = 0;
      span.setAttribute("role", "button");
      span.setAttribute("aria-label", `播放第 ${i + 1} 句`);
      span.dataset.i = String(i);
      renderSegment(span, seg.zh, seg.jy);
      span.addEventListener("click", () => playOne(i));
      span.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          playOne(i);
        }
      });
      proseEl.append(span);
    });
  }

  function selectArticle(i) {
    stopPlayback();
    state.art = i;
    renderTabs();
    renderArticle();
    setStatus("點句子即播放");
  }

  function segEl(i) {
    return proseEl.querySelector(`.seg[data-i="${i}"]`);
  }

  function highlight(i) {
    proseEl.querySelectorAll(".seg.is-playing").forEach((n) => n.classList.remove("is-playing"));
    const node = segEl(i);
    if (node) node.classList.add("is-playing");
  }

  function playFile(url) {
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
    if (state.playing && !chain) return;
    const art = state.articles[state.art];
    const seg = art.segments[i];
    if (!seg) return;

    state.current = i;
    highlight(i);
    setStatus(`第 ${i + 1} / ${art.segments.length} 句`);
    if (!chain) stopBtn.disabled = false;

    await playFile(seg.audio);

    if (!chain) {
      stopBtn.disabled = true;
      if (!state.stop) setStatus("點句子即播放");
      if (!state.stop) highlight(-1);
    }
  }

  async function playAll() {
    if (state.playing) return;
    state.playing = true;
    state.stop = false;
    playAllBtn.disabled = true;
    stopBtn.disabled = false;

    const total = state.articles[state.art].segments.length;
    for (let i = 0; i < total; i++) {
      if (state.stop) break;
      await playOne(i, { chain: true });
    }
    state.playing = false;
    playAllBtn.disabled = false;
    stopBtn.disabled = true;
    highlight(-1);
    if (!state.stop) setStatus("全篇播放完畢");
  }

  function stopPlayback() {
    state.stop = true;
    state.playing = false;
    player.pause();
    player.removeAttribute("src");
    player.hidden = true;
    highlight(-1);
    playAllBtn.disabled = false;
    stopBtn.disabled = true;
  }

  async function init() {
    try {
      const resp = await fetch("/lessons.json", { cache: "no-cache" });
      const data = await resp.json();
      state.articles = data.articles || [];
    } catch {
      setStatus("音頻資料載入失敗", "error");
      return;
    }
    if (!state.articles.length) {
      setStatus("未找到文章", "error");
      return;
    }
    renderTabs();
    renderArticle();
    playAllBtn.addEventListener("click", playAll);
    stopBtn.addEventListener("click", () => {
      stopPlayback();
      setStatus("已停止");
    });
    player.addEventListener("play", () => setStatus("播放中…"));
  }

  init();
})();
