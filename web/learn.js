/* 跟讀學粵語 — 左側文章、右側全文播放控制、離線音頻 */
(() => {
  const $ = (id) => document.getElementById(id);
  const player = $("player");
  const statusEl = $("status");
  const sidebarEl = $("sidebar");
  const proseEl = $("prose");
  const titleEl = $("artTitle");
  const tagEl = $("artTag");
  const metaEl = $("artMeta");
  const playBtn = $("playPause");
  const stopBtn = $("stop");
  const replayBtn = $("replay");

  const PUNCT = /[，。！？；：、,.!?;:]/;
  const LS = {
    art: "cantonese.learn.article",
    visited: "cantonese.learn.visited",
    last: "cantonese.learn.last",
  };
  const state = {
    articles: [],
    art: 0,
    playing: false,     // 正在播（含「整篇」與「單句」）
    paused: false,
    single: false,      // 單句模式：播完即停
    index: 0,
    visited: {},        // { articleIndex: [segIndex, ...] }
    last: null,         // { art, seg }
  };

  function loadState() {
    try {
      const art = Number(localStorage.getItem(LS.art));
      if (Number.isInteger(art) && art >= 0 && art < state.articles.length) state.art = art;
      state.visited = JSON.parse(localStorage.getItem(LS.visited) || "{}") || {};
      state.last = JSON.parse(localStorage.getItem(LS.last) || "null");
    } catch { /* ignore */ }
  }

  function saveArt() {
    try { localStorage.setItem(LS.art, String(state.art)); } catch { /* ignore */ }
  }

  function markVisited(i) {
    const key = String(state.art);
    const list = state.visited[key] || [];
    if (!list.includes(i)) list.push(i);
    state.visited[key] = list;
    state.last = { art: state.art, seg: i };
    try {
      localStorage.setItem(LS.visited, JSON.stringify(state.visited));
      localStorage.setItem(LS.last, JSON.stringify(state.last));
    } catch { /* ignore */ }
    const node = segEl(i);
    if (node) node.classList.add("is-visited");
  }

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  const current = () => state.articles[state.art];

  function setStatus(text, kind = "") {
    statusEl.textContent = text;
    statusEl.dataset.kind = kind;
  }

  function syncButton() {
    playBtn.textContent = state.playing && !state.paused ? "暫停" : "播放";
  }

  function renderSidebar() {
    sidebarEl.innerHTML = "";
    state.articles.forEach((art, i) => {
      const btn = el("button", "side-item" + (i === state.art ? " active" : ""));
      btn.type = "button";
      btn.append(el("span", "t", art.title), el("span", "c", `${art.segments.length} 句 · ${art.duration}s`));
      btn.addEventListener("click", () => selectArticle(i, true));
      sidebarEl.append(btn);
    });
  }

  function renderArticle() {
    const art = current();
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
      span.append(el("span", "seg-jy", seg.jy.trim()), el("span", "seg-zh", seg.zh));
      span.addEventListener("click", () => playSegment(i, true));
      span.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          playSegment(i, true);
        }
      });
      proseEl.append(span);
    });

    const visited = state.visited[String(state.art)] || [];
    visited.forEach((i) => {
      const node = segEl(i);
      if (node) node.classList.add("is-visited");
    });

    if (state.last && state.last.art === state.art) {
      const node = segEl(state.last.seg);
      if (node) setTimeout(() => node.scrollIntoView({ block: "center", behavior: "smooth" }), 60);
    }
  }

  function selectArticle(i, autoplay = false) {
    stopPlayback({ quiet: true });
    state.art = i;
    saveArt();
    renderSidebar();
    renderArticle();
    if (autoplay) {
      playWhole();
    } else {
      setStatus("點句子即播放");
    }
  }

  function playWhole() {
    stopPlayback({ quiet: true });
    playSegment(0, false);
  }

  function segEl(i) {
    return proseEl.querySelector(`.seg[data-i="${i}"]`);
  }

  function highlight(i) {
    proseEl.querySelectorAll(".seg.is-playing").forEach((n) => n.classList.remove("is-playing"));
    const node = segEl(i);
    if (node) node.classList.add("is-playing");
  }

  function playSegment(i, single) {
    const art = current();
    const seg = art && art.segments[i];
    if (!seg) return;

    state.index = i;
    if (single) markVisited(i);
    state.single = Boolean(single);
    state.playing = true;
    state.paused = false;
    syncButton();

    highlight(i);
    player.src = seg.audio;
    player.play().catch(() => {});
    setStatus(`第 ${i + 1} / ${art.segments.length} 句`);
  }

  function onEnded() {
    const art = current();
    if (!state.playing) return;

    if (state.single || state.index + 1 >= art.segments.length) {
      state.playing = false;
      state.paused = false;
      highlight(-1);
      syncButton();
      setStatus(state.single ? "點句子即播放" : "全篇播放完畢");
      return;
    }
    playSegment(state.index + 1, false);
  }

  function togglePlay() {
    if (state.playing && !state.paused) {
      player.pause();
      state.paused = true;
      syncButton();
      setStatus("已暫停");
      return;
    }
    if (state.paused && player.src) {
      state.paused = false;
      player.play().catch(() => {});
      syncButton();
      setStatus(`第 ${state.index + 1} / ${current().segments.length} 句`);
      return;
    }
    playWhole();
  }

  function stopPlayback({ quiet = false } = {}) {
    state.playing = false;
    state.paused = false;
    state.single = false;
    state.index = 0;
    player.pause();
    player.removeAttribute("src");
    highlight(-1);
    syncButton();
    if (!quiet) setStatus("已停止");
  }

  function replay() {
    playWhole();
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
    loadState();
    renderSidebar();
    renderArticle();
    syncButton();

    playBtn.addEventListener("click", togglePlay);
    stopBtn.addEventListener("click", () => stopPlayback());
    replayBtn.addEventListener("click", replay);
    player.addEventListener("ended", onEnded);
    player.addEventListener("play", () => {
      if (!state.paused) setStatus(`第 ${state.index + 1} / ${current().segments.length} 句`);
    });
  }

  init();
})();
