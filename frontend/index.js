import { LetterboxdData } from "./widgets/letterboxd/letterboxd.js";

window.onload = async () => {
  await Promise.all([
    LetterboxdData.init()
  ]);
}