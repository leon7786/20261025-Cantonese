/* 詩詞頁：兩欄錯落排版，點詩句或按鈕朗讀 */
(() => {
  const $ = (id) => document.getElementById(id);
  const player = $("poemPlayer");
  const root = $("poemSections");
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  let poems = [];
  let active = null; // { card, btn }

  function resetBtn(btn) {
    btn.classList.remove("is-playing");
    btn.textContent = "▶ 朗讀";
  }

  function clearPlaying() {
    if (active) {
      active.card.classList.remove("playing");
      resetBtn(active.btn);
    }
    active = null;
    root.querySelectorAll(".poem-card.playing").forEach((n) => n.classList.remove("playing"));
  }

  function toggle(poem, card, btn) {
    const same = active && active.card === card;
    if (same && !player.paused) {
      player.pause();
      btn.classList.remove("is-playing");
      btn.textContent = "▶ 繼續";
      return;
    }
    if (same && player.paused) {
      player.play().catch(() => {});
      btn.classList.add("is-playing");
      btn.textContent = "⏸ 暫停";
      return;
    }
    clearPlaying();
    active = { card, btn };
    card.classList.add("playing");
    btn.classList.add("is-playing");
    btn.textContent = "⏸ 暫停";
    player.pause();
    player.src = poem.audio;
    player.play().catch(() => {});
  }

  function renderPoem(poem, idx) {
    const card = el("article", "poem-card");
    const head = el("div", "poem-head");
    head.append(
      el("span", "poem-num", String(idx + 1).padStart(2, "0")),
      el("h3", "poem-title", `《${poem.title}》`),
      el("span", "poem-author", poem.author)
    );

    const body = el("button", "poem-body");
    body.type = "button";
    body.setAttribute("aria-label", `朗讀 ${poem.title}`);
    poem.lines.forEach((line) => body.append(el("span", "line", line)));

    const btn = el("button", "poem-play", "▶ 朗讀");
    btn.type = "button";
    btn.addEventListener("click", (e) => { e.stopPropagation(); toggle(poem, card, btn); });
    body.addEventListener("click", () => toggle(poem, card, btn));

    const actions = el("div", "poem-actions");
    actions.append(btn);

    const note = el("p", "poem-note", poem.note);
    card.append(head, body, actions, note);
    return card;
  }

  function layout() {
    clearPlaying();
    root.innerHTML = "";
    const twoCol = window.innerWidth >= 760;
    if (!twoCol) {
      const grid = el("div", "poem-grid single");
      poems.forEach((p, i) => grid.append(renderPoem(p, i)));
      root.append(grid);
      return;
    }
    const wrap = el("div", "poem-columns");
    const left = el("div", "poem-col");
    const right = el("div", "poem-col");
    poems.forEach((p, i) => (i % 2 === 0 ? left : right).append(renderPoem(p, i)));
    wrap.append(left, right);
    root.append(wrap);
  }

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(layout, 180);
  });

  async function init() {
    player.addEventListener("ended", clearPlaying);
    let data;
    try {
      const resp = await fetch("/poems.json", { cache: "no-cache" });
      data = await resp.json();
    } catch {
      root.textContent = "資料載入失敗";
      return;
    }
    poems = (data.sections || []).flatMap((sec) => sec.poems || []);
    layout();
  }

  init();
})();
