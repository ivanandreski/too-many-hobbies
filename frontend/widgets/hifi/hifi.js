// Renders the hi-fi system from data/hifi/setup.json.
//
// Components split two ways. Speakers become the towers flanking the cabinet —
// one data entry renders both, since a pair is one item you own. Everything else
// becomes a faceplate in the rack.
//
// Faceplate artwork is pure CSS, picked by a class derived from the component's
// category, so adding a component is a JSON edit and a new *kind* of component
// only needs a matching block in hifi.css. Unknown categories get a plain
// faceplate.
//
// Selecting anything lights it and prints its details to the readout below,
// which is how descriptions stay visible without putting paragraphs on a rack.

const ACTIVE_UNIT_CLASS = "hifi-unit-active";
const SPEAKER_CATEGORY_SLUG = "speakers";

const initHifi = async () => {
  const componentList = await fetchJsonData("/data/hifi/setup.json");

  const rackComponents = componentList.filter(c => !isSpeaker(c));
  const speakerComponent = componentList.find(isSpeaker);

  renderRack(rackComponents);
  if (speakerComponent) renderSpeakers(speakerComponent);

  // Power up the first rack unit so the readout is never empty. Deliberately
  // .hifi-unit and not [data-hifi-selectable]: the left speaker tower comes
  // first in the DOM, so the generic selector lit the speakers while showing the
  // turntable's details.
  const firstRackEl = document.querySelector(".hifi-unit");
  if (firstRackEl && rackComponents.length) {
    selectUnit(firstRackEl, rackComponents[0]);
    return;
  }

  // Speakers-only setup: fall back to the pair.
  const firstSpeakerEl = document.querySelector(".hifi-speaker");
  if (firstSpeakerEl && speakerComponent) selectUnit(firstSpeakerEl, speakerComponent);
}

const renderRack = (rackComponents) => {
  const templateEl = document.getElementById("hifi-widget-template");

  rackComponents.forEach(component => {
    const clone = document.importNode(templateEl.content, true);

    const unitEl = clone.querySelector(".hifi-unit");
    // Drives which faceplate artwork CSS draws for this unit.
    unitEl.classList.add(`hifi-unit--${categorySlug(component.category)}`);
    unitEl.addEventListener("click", () => selectUnit(unitEl, component));

    applyPhoto(unitEl, clone.querySelector(".hifi-unit-photo"), component, "hifi-unit-has-photo");

    const categoryEl = clone.querySelector(".hifi-unit-category");
    categoryEl.innerText = component.category;

    const nameEl = clone.querySelector(".hifi-unit-name");
    nameEl.innerText = component.name;

    templateEl.parentNode.appendChild(clone);
  });
}

// One pair of speakers, drawn as two towers. Selecting either lights both, since
// they are a single item in the data.
const renderSpeakers = (component) => {
  const templateEl = document.getElementById("hifi-speaker-template");

  document.querySelectorAll(".hifi-speakers").forEach(containerEl => {
    const clone = document.importNode(templateEl.content, true);

    const speakerEl = clone.querySelector(".hifi-speaker");
    speakerEl.addEventListener("click", () => selectUnit(speakerEl, component));

    applyPhoto(speakerEl, clone.querySelector(".hifi-speaker-photo"), component, "hifi-speaker-has-photo");

    const labelEl = clone.querySelector(".hifi-speaker-label");
    labelEl.innerText = component.category;

    containerEl.appendChild(clone);
  });
}

const selectUnit = (unitEl, component) => {
  document.querySelectorAll("[data-hifi-selectable]").forEach(otherEl => {
    otherEl.classList.remove(ACTIVE_UNIT_CLASS);
    otherEl.setAttribute("aria-pressed", "false");
  });

  // A speaker pair is one item, so both towers light together.
  const toActivate = unitEl.classList.contains("hifi-speaker")
    ? document.querySelectorAll(".hifi-speaker")
    : [unitEl];

  toActivate.forEach(el => {
    el.classList.add(ACTIVE_UNIT_CLASS);
    el.setAttribute("aria-pressed", "true");
  });

  renderReadout(component, null);
}

// Renders the panel below the cabinet. `parent` is set when showing a
// sub-component, which adds a link back to the unit it belongs to.
//
// Opening a part deliberately does not change which unit is lit: the cartridge
// is on the turntable, so the turntable stays powered while you read about it.
const renderReadout = (component, parent) => {
  document.getElementById("hifi-readout-icon").innerText = component.icon;
  document.getElementById("hifi-readout-category").innerText = component.category;
  document.getElementById("hifi-readout-name").innerText = component.name;
  document.getElementById("hifi-readout-description").innerText = component.description;

  renderBackLink(parent);
  renderSpecs(component.specs || []);
  renderParts(component.parts || [], component);
}

const renderBackLink = (parent) => {
  const backEl = document.getElementById("hifi-readout-back");

  backEl.hidden = !parent;
  if (!parent) return;

  backEl.innerText = `‹ ${parent.name}`;
  backEl.onclick = () => renderReadout(parent, null);
}

const renderParts = (parts, parentComponent) => {
  const containerEl = document.getElementById("hifi-readout-parts");
  const templateEl = document.getElementById("hifi-part-template");

  containerEl.querySelectorAll(".hifi-part").forEach(chipEl => chipEl.remove());
  containerEl.hidden = parts.length === 0;

  parts.forEach(part => {
    const clone = document.importNode(templateEl.content, true);

    const chipEl = clone.querySelector(".hifi-part");
    chipEl.addEventListener("click", () => renderReadout(part, parentComponent));

    const iconEl = clone.querySelector(".hifi-part-icon");
    iconEl.innerText = part.icon;

    const categoryEl = clone.querySelector(".hifi-part-category");
    categoryEl.innerText = part.category;

    const nameEl = clone.querySelector(".hifi-part-name");
    nameEl.innerText = part.name;

    containerEl.appendChild(clone);
  });
}

// Specs are optional per component — the cartridge on the turntable, power on the
// amp — so the list is emptied and hidden when a component has none.
const renderSpecs = (specs) => {
  const listEl = document.getElementById("hifi-readout-specs");
  const templateEl = document.getElementById("hifi-spec-template");

  listEl.querySelectorAll(".hifi-spec").forEach(rowEl => rowEl.remove());
  listEl.hidden = specs.length === 0;

  specs.forEach(spec => {
    const clone = document.importNode(templateEl.content, true);

    const labelEl = clone.querySelector(".hifi-spec-label");
    labelEl.innerText = spec.label;

    const valueEl = clone.querySelector(".hifi-spec-value");
    valueEl.innerText = spec.value;

    listEl.appendChild(clone);
  });
}

// A component may supply a photo; the CSS artwork is the fallback when it does
// not, so photos can be added one at a time without the rack looking unfinished.
//
// The src goes through the same `prefix` as fetchJsonData: GitHub Pages serves
// the site from a subpath, and a root-relative path would resolve outside it.
const applyPhoto = (containerEl, imageEl, component, hasPhotoClass) => {
  if (!component.photo) return;

  imageEl.src = prefix + component.photo;
  imageEl.alt = `${component.category} — ${component.name}`;
  imageEl.hidden = false;
  containerEl.classList.add(hasPhotoClass);
}

const isSpeaker = (component) =>
  categorySlug(component.category) === SPEAKER_CATEGORY_SLUG;

// "Cassette Deck" -> "cassette-deck", to match the CSS artwork classes.
const categorySlug = (category) =>
  (category || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

export const HifiData = {
  init: async () => {
    await Promise.all([
      initHifi()
    ]);
  }
}
