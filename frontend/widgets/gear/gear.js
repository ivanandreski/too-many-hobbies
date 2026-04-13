const initGear = async () => {
  const gearData = await fetchJsonData("/data/gear/bikes.json");

  const mainBikeEntryEl = document.getElementById("main-bike-entry");
  renderBikeData(mainBikeEntryEl, gearData["mainBike"]);

  const commuterBikeEntry = document.getElementById("commuter-bike-entry");
  renderBikeData(commuterBikeEntry, gearData["commuter"]);
}

const renderBikeData = (entryEl, bikeData) => {
  entryEl.querySelector(".bike-name-title").innerText = bikeData.name;
  entryEl.querySelector(".bike-milage-title").innerText = bikeData.milage + " KM ridden";
}

export const GearData = {
  init: async () => {
    await Promise.all([
      initGear()
    ]);
  }
}