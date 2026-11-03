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

  let activeChip = null;

  function clearPlaying() {
    if (activeChip) activeChip.classList.remove("playing");
    activeChip = null;
    root.querySelectorAll(".tone-chip.playing").forEach((n) => n.classList.remove("playing"));
  }

  function play(url, chip, status, label) {
    clearPlaying();
    if (chip) {
      chip.classList.add("playing");
      activeChip = chip;
    }
    player.pause();
    player.src = url;
    player.play().catch(() => {});
    if (status) status.textContent = label;
  }

  function renderChar(item, chip, status) {
    const btn = el("button", "tone-chip");
    btn.type = "button";
    btn.setAttribute("aria-label", `${chip.c} ${chip.jy}`);
    btn.append(el("span", "ch", chip.c), el("span", "jy", chip.jy));
    btn.addEventListener("click", () => {
      play(chip.audio, btn, status, `${chip.c} ${chip.jy} · ${chip.dur}s`);
    });
    return btn;
  }

  function renderItem(item) {
    const card = el("article", "tone-card");
    const top = el("div", "tone-top");
    top.append(el("span", "tone-tag", item.tag), el("span", "tone-dur", `整句 ${item.duration}s`));
    card.append(top, el("h3", null, item.title));

    const chips = el("div", "tone-chips");
    const status = el("span", "tone-status");
    item.chars.forEach((ch) => chips.append(renderChar(item, ch, status)));
    card.append(chips, el("p", "tone-note", item.note));

    const actions = el("div", "tone-actions");
    const all = el("button", "btn ghost", "▶ 整句播放");
    all.type = "button";
    all.addEventListener("click", () => {
      play(item.audio, null, status, `整句播放中 · ${item.duration}s`);
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
      head.append(el("h2", null, sec.title), el("p", null, sec.subtitle));
      const grid = el("div", "tone-grid");
      sec.items.forEach((item) => grid.append(renderItem(item)));
      section.append(head, grid);
      root.append(section);
    });
  }

  init();
})();
