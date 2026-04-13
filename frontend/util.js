const parseJson = async (path) => {
  try {
    const response = await fetch(path);
    return (await response.json())["data"];
  } catch (e) {
    console.error(e);
    return [];
  }
}