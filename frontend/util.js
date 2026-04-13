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
    const response = await fetch(`/components/${componentName}.html`);
    return (await response.text());
  } catch (error) {
    console.error(error);
  }
}