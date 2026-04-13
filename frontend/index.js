import { LetterboxdData } from "./widgets/letterboxd/letterboxd.js";
import { GearData } from "./widgets/gear/gear.js"

window.onload = async () => {
  await Promise.all([
    renderComponent("film"),
    renderComponent("running"),
    renderComponent("gear"),
    renderComponent("cycling"),
  ]);

  await Promise.all([
    LetterboxdData.init(),
    GearData.init()
  ]);
}

const renderComponent = async (componentName) => {
  const componentHtml = await fetchComponent(componentName);
  const componentEl = document.getElementById(`${componentName}-component`);

  componentEl.innerHTML = componentHtml;
}