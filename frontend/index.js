import {init as letterboxdInit} from "./widgets/letterboxd/letterboxd.js";

window.onload = async () => {
  await letterboxdInit();
}