/* 九聲六調：渲染卡片、點字播放、整句播放 */
(() => {
  const $ = (id) => document.getElementById(id);
  const player = $("tonePlayer");
  const root = $("sections");
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  let activeLine = null;

  function clearPlaying() {
    if (activeLine) activeLine.classList.remove("playing");
    activeLine = null;
    root.querySelectorAll(".tone-line.playing").forEach((n) => n.classList.remove("playing"));
  }

  function play(url, line, status, label) {
    clearPlaying();
    if (line) {
      line.classList.add("playing");
      activeLine = line;
    }
    player.pause();
    player.src = url;
    player.play().catch(() => {});
    if (status) status.textContent = label;
  }

  function renderLine(item, status) {
    const line = el("div", "tone-line");
    line.tabIndex = 0;
    line.setAttribute("role", "button");
    line.setAttribute("aria-label", `播放整段：${item.title}`);
    item.chars.forEach((ch) => {
      const unit = el("span", "unit");
      unit.append(el("span", "ch", ch.c), el("span", "jy", ch.jy));
      line.append(unit);
    });
    const go = () => play(item.audio, line, status, `整段播放中 · ${item.duration}s`);
    line.addEventListener("click", go);
    line.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        go();
      }
    });
    return line;
  }

  function renderTips(item) {
    if (!item.tips || !item.tips.length) return null;
    const box = el("div", "tone-tips");
    box.append(el("div", "tone-tips-head", "易讀錯 · 正確發音"));
    const ul = el("ul");
    item.tips.forEach((t) => {
      const li = el("li");
      const word = el("b", null, t.word);
      const jy = el("span", "jy", t.jy);
      li.append(word, jy, el("span", null, ` — ${t.note}`));
      ul.append(li);
    });
    box.append(ul);
    return box;
  }

  function renderItem(item) {
    const card = el("article", "tone-card");
    const top = el("div", "tone-top");
    top.append(el("span", "tone-tag", item.tag), el("span", "tone-dur", `整句 ${item.duration}s`));
    card.append(top);

    const status = el("span", "tone-status");
    const line = renderLine(item, status);
    line.title = item.title;
    card.append(line, el("p", "tone-note", item.note));

    const tips = renderTips(item);
    if (tips) card.append(tips);

    const actions = el("div", "tone-actions");
    const all = el("button", "btn ghost", "▶ 整段播放");
    all.type = "button";
    all.addEventListener("click", () => {
      play(item.audio, card.querySelector(".tone-line"), status, `整段播放中 · ${item.duration}s`);
    });
    actions.append(all, status);
    card.append(actions);

    return card;
  }

  async function init() {
    player.addEventListener("ended", clearPlaying);
    let data;
    try {
      const resp = await fetch("/tones.json", { cache: "no-cache" });
      data = await resp.json();
    } catch {
      root.textContent = "資料載入失敗";
      return;
    }

    (data.sections || []).forEach((sec) => {
      const section = el("section", "tone-section");
      const head = el("div", "tone-section-head");
      const titleRow = el("div", "tone-section-title");
      titleRow.append(el("h2", null, sec.title), el("span", "tone-count", `${sec.items.length} 組`));
      head.append(titleRow, el("p", null, sec.subtitle));
      const grid = el("div", "tone-grid");
      sec.items.forEach((item) => grid.append(renderItem(item)));
      section.append(head, grid);
      root.append(section);
    });
  }

  init();
})();
