/* 詩詞頁：分行顯示，點詩句或按鈕朗讀全首 */
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

  let active = null; // { card, btn }

  function resetBtn(btn) {
    btn.classList.remove("is-playing");
    btn.textContent = "▶ 粵語朗讀";
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

  function renderPoem(poem) {
    const card = el("article", "poem-card");
    const head = el("div", "poem-head");
    head.append(el("span", "poem-title", poem.title), el("span", "poem-author", poem.author));
    const btn = el("button", "poem-play", "▶ 粵語朗讀");
    btn.type = "button";
    btn.addEventListener("click", (e) => { e.stopPropagation(); toggle(poem, card, btn); });
    head.append(btn);

    const body = el("button", "poem-body");
    body.type = "button";
    body.setAttribute("aria-label", `朗讀 ${poem.title}`);
    poem.lines.forEach((line) => body.append(el("span", "line", line), el("br")));
    body.addEventListener("click", () => toggle(poem, card, btn));

    card.append(head, body, el("p", "poem-note", poem.note));
    return card;
  }

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
    (data.sections || []).forEach((sec) => {
      const section = el("section", "poem-section");
      const head = el("div", "poem-section-head");
      head.append(el("h2", null, sec.title), el("p", null, sec.intro));
      const grid = el("div", "poem-grid");
      sec.poems.forEach((p) => grid.append(renderPoem(p)));
      section.append(head, grid);
      root.append(section);
    });
  }

  init();
})();
