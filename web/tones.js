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
    root.querySelectorAll(".playing").forEach((n) => n.classList.remove("playing"));
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
    const line = el("div", "tone-line" + (item.chars.length >= 7 ? " compact" : ""));
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
    const head = el("div", "tone-tips-head", "嘴型提示");
    if (item.tips.some((t) => t.audio)) head.append(el("span", "tips-hint", "撳提示聽讀音"));
    box.append(head);
    const ul = el("ul");
    item.tips.forEach((t) => {
      const li = el("li", t.audio ? "has-audio" : null);
      li.append(el("b", "tip-word", t.word), el("span", null, ` — ${t.note}`));
      if (t.audio) {
        li.tabIndex = 0;
        li.setAttribute("role", "button");
        li.setAttribute("aria-label", `朗讀這條提示：${t.word}`);
        const go = () => play(t.audio, li, null, "");
        li.addEventListener("click", go);
        li.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            go();
          }
        });
      }
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
      const section = el("section", "tone-section" + (sec.id === "entering" ? " tone-boss" : ""));
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
