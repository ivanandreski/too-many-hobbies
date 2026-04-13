import {init as letterboxdInit, initFavorites} from "./widgets/letterboxd/letterboxd.js";

window.onload = async () => {
  await Promise.all([
    letterboxdInit(),
    initFavorites(),
  ]);
}