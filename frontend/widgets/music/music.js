// The two sections of the widget, each a key in the payload paired with the
// elements that display it.
const MUSIC_SECTIONS = [
  { key: "latestAdditions", listId: "music-additions-list", countId: "music-additions-count" },
  { key: "latestSpins", listId: "music-spins-list", countId: "music-spins-count" },
];

const initMusic = async () => {
  const collection = await fetchJsonData("/data/music/records.json");

  // fetchJsonData returns [] on failure, so bail rather than throw on lookup.
  if (!collection || Array.isArray(collection)) {
    console.error("No music data");
    return;
  }

  const templateEl = document.getElementById("music-widget-template");

  MUSIC_SECTIONS.forEach(({ key, listId, countId }) => {
    renderRecordList(
      document.getElementById(listId),
      document.getElementById(countId),
      templateEl,
      collection[key] || [],
    );
  });
}

const renderRecordList = (listEl, countEl, templateEl, records) => {
  // Counted from the list rather than stored, so it cannot disagree with it.
  countEl.innerText = records.length;

  records.forEach(record => {
    const clone = document.importNode(templateEl.content, true);

    const albumEl = clone.querySelector(".music-record-album");
    albumEl.innerText = record.album;

    const artistEl = clone.querySelector(".music-record-artist");
    artistEl.innerText = `${record.artist} · ${record.year}`;

    const formatEl = clone.querySelector(".music-record-format");
    formatEl.innerText = record.format;

    listEl.appendChild(clone);
  });
}

export const MusicData = {
  init: async () => {
    await Promise.all([
      initMusic()
    ]);
  }
}
