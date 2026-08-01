import { LetterboxdData } from "./widgets/letterboxd/letterboxd.js";
import { GearData } from "./widgets/gear/gear.js"
import { StravaData } from "./widgets/strava/strava.js"
import { HifiData } from "./widgets/hifi/hifi.js"
import { LegoData } from "./widgets/lego/lego.js"
import { MusicData } from "./widgets/music/music.js"

window.onload = async () => {
  // Components must all be in the DOM before any widget populates them —
  // StravaData.init() finds its widgets by querying the rendered markup.
  await Promise.all([
    renderComponent("film"),
    renderComponent("running"),
    renderComponent("gear"),
    renderComponent("cycling"),
    renderComponent("hifi"),
    renderComponent("lego"),
    renderComponent("music"),
  ]);

  await Promise.all([
    LetterboxdData.init(),
    GearData.init(),
    StravaData.init(),
    HifiData.init(),
    LegoData.init(),
    MusicData.init()
  ]);
}

const renderComponent = async (componentName) => {
  const componentHtml = await fetchComponent(componentName);
  const componentEl = document.getElementById(`${componentName}-component`);

  componentEl.innerHTML = componentHtml;
}