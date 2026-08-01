const initLego = async () => {
  const setList = await fetchJsonData("/data/lego/sets.json");

  const totalEl = document.getElementById("lego-total");
  totalEl.innerText = `${totalPieces(setList).toLocaleString()} pcs total`;

  const templateEl = document.getElementById("lego-widget-template");
  setList.forEach(set => {
    const clone = document.importNode(templateEl.content, true);

    const nameEl = clone.querySelector(".lego-set-name");
    nameEl.innerText = set.name;

    const metaEl = clone.querySelector(".lego-set-meta");
    metaEl.innerText = `${set.number} · ${set.pieces.toLocaleString()} pieces · ${set.year}`;

    const themeEl = clone.querySelector(".lego-set-theme");
    themeEl.innerText = set.theme;

    templateEl.parentNode.appendChild(clone);
  });
}

// Derived rather than stored, so it can never disagree with the set list.
const totalPieces = (setList) =>
  setList.reduce((runningTotal, set) => runningTotal + set.pieces, 0);

export const LegoData = {
  init: async () => {
    await Promise.all([
      initLego()
    ]);
  }
}
