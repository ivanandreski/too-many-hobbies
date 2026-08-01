// Renders the bikes widget from data/gear/bikes.json.
//
// The payload is a keyed object rather than a list — each role ("mainBike",
// "commuter") maps to one bike — so entries are looked up by role and rendered
// into the matching block in components/gear.html.
//
// Mileage is each bike's all-time distance as Strava reports it.

// Roles in the data, paired with the element that displays them.
const BIKE_ROLES = [
  { key: "mainBike", elementId: "main-bike-entry" },
  { key: "commuter", elementId: "commuter-bike-entry" },
];

const initGear = async () => {
  const gearData = await fetchJsonData("/data/gear/bikes.json");

  // fetchJsonData returns [] on failure, so bail rather than throw on lookup.
  if (!gearData || Array.isArray(gearData)) {
    console.error("No gear data");
    return;
  }

  BIKE_ROLES.forEach(({ key, elementId }) => {
    const entryEl = document.getElementById(elementId);
    if (entryEl) renderBikeData(entryEl, gearData[key]);
  });
};

// Only the name and mileage come from data. The photos are static markup in
// components/gear.html — Strava has no gear images and the bikes do not change,
// so there is nothing to generate.
const renderBikeData = (entryEl, bikeData) => {
  if (!bikeData) return;

  entryEl.querySelector(".bike-name-title").innerText = bikeData.name;
  entryEl.querySelector(".bike-milage-title").innerText =
    `${formatKilometres(bikeData.milage)} KM ridden`;
};

// Thousands separated, with a pointless ".0" trimmed: 1002.7 -> "1,002.7".
const formatKilometres = (kilometres) =>
  Number(Number(kilometres).toFixed(1)).toLocaleString("en-US");

export const GearData = {
  init: async () => {
    await Promise.all([
      initGear()
    ]);
  }
}
