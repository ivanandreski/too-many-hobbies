import { LetterboxdData } from "./widgets/letterboxd/letterboxd.js";
import { GearData } from "./widgets/gear/gear.js"

window.onload = async () => {
  await Promise.all([
    LetterboxdData.init(),
    GearData.init()
  ]);
}