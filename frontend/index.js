import {init as letterboxdInit} from "./widgets/letterboxd/diary.js";

window.onload = async () => {
  await letterboxdInit();
}