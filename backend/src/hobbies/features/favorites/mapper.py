"""
Letterboxd favorites mapper.

Responsible for mapping a RawFavoriteItem (scraped by the parser) into a
favorite entry dict matching the schema used in
frontend/data/movies/favorites.json.

Favorite entry schema:
{
    "name": str,          # film title without the year
    "releaseYear": int,   # None if the profile did not include a year
    "poster": str,        # poster image URL, upscaled from the thumbnail URL
    "url": str            # canonical film URL (letterboxd.com/film/<slug>/)
}
"""

import re

from hobbies.features.diary.constants import LETTERBOXD_BASE_URL
from hobbies.features.favorites.constants import POSTER_HEIGHT, POSTER_WIDTH
from hobbies.features.favorites.models import RawFavoriteItem

# Matches the crop dimensions Letterboxd encodes into resized poster URLs,
# e.g. the "-0-150-0-225-crop" in ".../51552-rear-window-0-150-0-225-crop.jpg".
POSTER_CROP_DIMENSIONS_PATTERN = re.compile(r"-0-\d+-0-\d+-crop")

# Matches a trailing "(1954)" in a film's display name.
DISPLAY_NAME_YEAR_PATTERN = re.compile(r"^(?P<title>.*?)\s*\((?P<year>\d{4})\)$")


def map_raw_favorite_item_to_dto(raw_item: RawFavoriteItem) -> dict:
    """
    Map a RawFavoriteItem into a favorite entry dict.

    Splits the display name into title and year, upscales the thumbnail poster
    URL, and turns the site-relative film link into an absolute URL.
    """
    film_title, release_year = _split_display_name(raw_item.film_name)

    return {
        "name": film_title,
        "releaseYear": release_year,
        "poster": _upscale_poster_url(raw_item.poster_src),
        "url": _absolute_film_url(raw_item.film_link),
    }


def _split_display_name(display_name: str) -> tuple[str, int | None]:
    """
    Split "Rear Window (1954)" into ("Rear Window", 1954).

    Falls back to (name, None) when no trailing year is present.
    """
    year_match = DISPLAY_NAME_YEAR_PATTERN.match(display_name.strip())
    if year_match:
        return year_match.group("title"), int(year_match.group("year"))
    return display_name.strip(), None


def _upscale_poster_url(poster_url: str) -> str:
    """
    Ask the CDN for a larger crop of the same poster.

    The profile page renders 150x225 thumbnails. The requested size is encoded
    in the URL, so swapping the dimensions yields a full-size poster without a
    second request. Returns the URL unchanged if it carries no crop dimensions.
    """
    return POSTER_CROP_DIMENSIONS_PATTERN.sub(
        f"-0-{POSTER_WIDTH}-0-{POSTER_HEIGHT}-crop", poster_url
    )


def _absolute_film_url(film_link: str) -> str:
    """
    Turn a site-relative film link into an absolute canonical film URL.

    Film link:          /film/rear-window/
    Canonical film URL: https://letterboxd.com/film/rear-window/
    """
    if not film_link:
        return ""
    if film_link.startswith("http"):
        return film_link
    return f"{LETTERBOXD_BASE_URL}{film_link}"
