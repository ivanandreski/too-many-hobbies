"""
Data models for the Letterboxd favorites scraper pipeline.

RawFavoriteItem holds raw string values scraped directly from the rendered
profile HTML, before any URL transformation is applied.
"""

from dataclasses import dataclass


@dataclass
class RawFavoriteItem:
    """Raw field values scraped from a single favorites grid item."""
    film_name: str      # e.g. "Rear Window (1954)"
    film_link: str      # site-relative, e.g. "/film/rear-window/"
    poster_src: str     # absolute CDN URL at thumbnail size
