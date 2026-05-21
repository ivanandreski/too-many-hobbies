"""
Letterboxd RSS mapper.

Responsible for mapping a RawDiaryItem (extracted by the parser) into a
diary entry dict matching the schema used in frontend/data/movies/diary.json.

Diary entry schema:
{
    "name": str,
    "releaseYear": int,
    "rating": float,
    "like": bool,
    "dateWatched": str,   # original pubDate string from the RSS feed
    "poster": str,        # poster image URL
    "url": str            # canonical film URL (letterboxd.com/film/<slug>/)
}
"""

import re

from hobbies.features.diary.constants import LETTERBOXD_BASE_URL, LETTERBOXD_DOMAIN
from hobbies.features.diary.models import RawDiaryItem


def map_raw_diary_item_to_dto(raw_item: RawDiaryItem) -> dict:
    """
    Map a RawDiaryItem into a diary entry dict.

    Applies type conversions (str → int/float/bool) and URL transformations.
    """
    return {
        "name": raw_item.film_title,
        "releaseYear": int(raw_item.film_year) if raw_item.film_year else None,
        "rating": float(raw_item.member_rating) if raw_item.member_rating else None,
        "like": raw_item.member_liked.lower() == "yes",
        "dateWatched": raw_item.pub_date,
        "poster": _extract_poster_url(raw_item.description_html),
        "url": _diary_entry_link_to_film_url(raw_item.diary_link),
    }


def _extract_poster_url(description_html: str) -> str:
    """Pull the first <img src="..."> URL out of the item description HTML."""
    image_tag_match = re.search(r'<img[^>]+src="([^"]+)"', description_html)
    return image_tag_match.group(1) if image_tag_match else ""


def _diary_entry_link_to_film_url(diary_entry_link: str) -> str:
    """
    Convert a user diary entry link to a canonical film URL.

    Diary entry link:   https://letterboxd.com/<username>/film/<film-slug>/
    Canonical film URL: https://letterboxd.com/film/<film-slug>/
    """
    film_slug_match = re.search(rf"{re.escape(LETTERBOXD_DOMAIN)}/[^/]+/film/([^/]+)", diary_entry_link)
    if film_slug_match:
        film_slug = film_slug_match.group(1)
        return f"{LETTERBOXD_BASE_URL}/film/{film_slug}/"
    return diary_entry_link
