const initHifi = async () => {
  const componentList = await fetchJsonData("/data/hifi/setup.json");

  const templateEl = document.getElementById("hifi-widget-template");
  componentList.forEach(component => {
    const clone = document.importNode(templateEl.content, true);

    const iconEl = clone.querySelector(".hifi-image");
    iconEl.innerText = component.icon;

    const categoryEl = clone.querySelector(".hifi-category");
    categoryEl.innerText = component.category;

    const nameEl = clone.querySelector(".hifi-name");
    nameEl.innerText = component.name;

    const descriptionEl = clone.querySelector(".hifi-description");
    descriptionEl.innerText = component.description;

    templateEl.parentNode.appendChild(clone);
  });
}

export const HifiData = {
  init: async () => {
    await Promise.all([
      initHifi()
    ]);
  }
}
