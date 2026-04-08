window.onload = async () => {
  const diaryList = await parseJson();

  const templateEl = document.getElementById("letterboxd-widget-template");
  diaryList.forEach(movie => {
    const clone = document.importNode(templateEl.content, true);
    const dateWatched = new Date(movie.dateWatched);

    const dayMonthEl = clone.querySelector(".letterboxd-day-month");
    dayMonthEl.innerText = `${dateWatched.toLocaleString('en-US', { month: 'short' })} ${dateWatched.getDate()}`;
    const yearEl = clone.querySelector(".letterboxd-year");
    yearEl.innerText = dateWatched.getFullYear();

    const imageEl = clone.querySelector(".movie-image img");
    imageEl.src = movie.poster;

    const movieNameEl = clone.querySelector(".movie-name");
    movieNameEl.innerText = movie.name;

    const releaseYearEl = clone.querySelector(".movie-release-year");
    releaseYearEl.innerText = movie.releaseYear;

    // TODO: render ratings

    if (movie.like) {
      const likeEl = clone.querySelector(".movie-like");

      const heartEl = document.createElement('span')
      heartEl.className = "fa fa-heart";
      likeEl.appendChild(heartEl);
    }

    templateEl.parentNode.appendChild(clone);
  });
}

const parseJson = async () => {
  try {
    const response = await fetch("./data/diary.json");
    return (await response.json())["data"];
  } catch (e) {
    console.error(e);
    return [];
  }
}