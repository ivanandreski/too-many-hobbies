const fetchJsonData = async (path) => {
  try {
    const prefix = ENV_PROD
    ? "/too-many-hobbies"
    : "";
    console.log(prefix + path);

    const response = await fetch(prefix + path);
    return (await response.json())["data"];
  } catch (e) {
    console.error(e);
    return [];
  }
}