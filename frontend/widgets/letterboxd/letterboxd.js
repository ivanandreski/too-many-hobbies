const initDiary = async () => {
  const diaryList = await parseJson("../../data/movies/diary.json");

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

    renderRatings(clone, movie.rating);

    if (movie.like) {
      const likeEl = clone.querySelector(".movie-like");

      const heartEl = document.createElement('span')
      heartEl.className = "fa fa-heart";
      likeEl.appendChild(heartEl);
    }

    templateEl.parentNode.appendChild(clone);
  });
}

const renderRatings = (clone, rating) => {
  const ratingEl = clone.querySelector(".movie-rating");
  for (let i = 0; i < parseInt(rating); i++) {
    const starEl = document.createElement('span');
    starEl.className = "fa fa-star";
    ratingEl.appendChild(starEl);
  }

  if (rating % 2 !== 0) {
    const starEl = document.createElement('span');
    starEl.className = "fa fa-star-half";
    ratingEl.appendChild(starEl);
  }
}

const initFavorites = async () => {
  const favoritesList = await parseJson("../../data/movies/favorites.json");

  const templateEl = document.getElementById("letterboxd-favorites-template");
  favoritesList.forEach(movie => {
    const clone = document.importNode(templateEl.content, true);

    const entryEl = clone.querySelector("div");
    const imgEl = document.createElement("img");
    imgEl.src = movie.poster;
    entryEl.appendChild(imgEl);

    templateEl.parentNode.appendChild(clone);
  });
}

export const LetterboxdData = {
  init: async () => {
    await Promise.all([
      initDiary(),
      initFavorites(),
    ]);
  }
}

