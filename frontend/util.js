const prefix = ENV_PROD
  ? "/too-many-hobbies"
  : "";

const fetchJsonData = async (path) => {
  try {
    const response = await fetch(prefix + path);
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
    const response = await fetch(`${prefix}/components/${componentName}.html`);
    if (!response.ok) throw new Error(`${response.status} fetching ${componentName} component`);
    return (await response.text());
  } catch (error) {
    console.error(error);
    // Returning undefined would render the literal string "undefined".
    return "";
  }
}