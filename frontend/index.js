import { LetterboxdData } from "./widgets/letterboxd/letterboxd.js";
import { GearData } from "./widgets/gear/gear.js"
import { StravaData } from "./widgets/strava/strava.js"

window.onload = async () => {
  // Components must all be in the DOM before any widget populates them —
  // StravaData.init() finds its widgets by querying the rendered markup.
  await Promise.all([
    renderComponent("film"),
    renderComponent("running"),
    renderComponent("gear"),
    renderComponent("cycling"),
  ]);

  await Promise.all([
    LetterboxdData.init(),
    GearData.init(),
    StravaData.init()
  ]);
}

const renderComponent = async (componentName) => {
  const componentHtml = await fetchComponent(componentName);
  const componentEl = document.getElementById(`${componentName}-component`);

  componentEl.innerHTML = componentHtml;
}