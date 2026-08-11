const prefix = ENV_PROD
  ? "/too-many-hobbies"
  : "";

// Cache-busting stamp for everything this page requests from its own origin.
//
// GitHub Pages serves every file with `cache-control: max-age=600`, so a
// regenerated data file or a re-captured image can keep being served from the
// browser cache for ten minutes after a deploy — and longer in a tab that was
// already open. That turns "I pushed a fix" into "the site still looks broken".
//
// One stamp per page load, not per call: the point is to defeat caching *between*
// visits, while two fetches of the same URL within a single load should still
// share one response rather than each going to the network.
const CACHE_BUSTER = String(Date.now());

// Appends this load's stamp to a URL served by this site.
//
// Same-origin only. An external URL — a Letterboxd poster CDN, say — gains
// nothing from a query parameter it does not understand, may treat it as a
// different object and miss its own cache, and in the worst case rejects the
// request outright. Those URLs also change whenever their content does, so they
// have no staleness problem to solve.
//
// Note what this cannot reach: index.css, index.js, util.js and the widget
// modules are requested by tags in index.html, before any of this code runs, so
// they are still subject to the ten-minute window. Only a version stamp written
// into index.html itself could bust those.
const bustCache = (url) => {
  if (/^[a-z]+:\/\//i.test(url)) return url;
  return `${url}${url.includes("?") ? "&" : "?"}v=${CACHE_BUSTER}`;
};

const fetchJsonData = async (path) => {
  try {
    const response = await fetch(bustCache(prefix + path));
    return (await response.json())["data"];
  } catch (e) {
    console.error(e);
    return [];
  }
}

const fetchComponent = async (componentName) => {
  try {
    // Needs the same prefix as fetchJsonData: on GitHub Pages the site is served
    // from a subpath, so a root-relative path resolves outside the site and 404s.
    const response = await fetch(bustCache(`${prefix}/components/${componentName}.html`));
    if (!response.ok) throw new Error(`${response.status} fetching ${componentName} component`);
    return (await response.text());
  } catch (error) {
    console.error(error);
    // Returning undefined would render the literal string "undefined".
    return "";
  }
}
