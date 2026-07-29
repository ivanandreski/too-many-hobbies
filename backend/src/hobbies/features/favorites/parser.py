"""
Letterboxd profile favorites scraper.

Walks the rendered profile HTML with the stdlib HTML parser, isolates the
favorites section, and yields one RawFavoriteItem per poster in that grid.

Scoping to the favorites section matters: a profile page contains several
poster grids (recent activity, watchlist, lists), all using the same markup.
"""

from html.parser import HTMLParser

from hobbies.features.favorites.constants import (
    FAVORITES_SECTION_ID,
    POSTER_COMPONENT_CLASS,
    POSTER_IMAGE_CLASS,
)
from hobbies.features.favorites.models import RawFavoriteItem

SECTION_TAG = "section"
IMAGE_TAG = "img"


def extract_raw_favorite_items(profile_html: str) -> list[RawFavoriteItem]:
    """
    Scrape the favorites grid out of a rendered Letterboxd profile page.

    Args:
        profile_html: Rendered HTML of a profile page. Must come from a
                      JavaScript-capable fetch, otherwise every poster src is
                      still a placeholder.

    Returns:
        List of RawFavoriteItem in the order they appear on the profile.

    Raises:
        ValueError: If the page contains no favorites section at all, which
                    signals the page failed to load or Letterboxd changed its
                    markup — either way, silently writing an empty file would
                    wipe good data downstream.
    """
    scraper = _FavoritesSectionScraper()
    scraper.feed(profile_html)

    if not scraper.found_favorites_section:
        raise ValueError(
            f"Profile page has no <{SECTION_TAG} id='{FAVORITES_SECTION_ID}'> element"
        )

    return scraper.items


class _FavoritesSectionScraper(HTMLParser):
    """
    Collects favorite poster data while inside the favorites <section>.

    Each favorite spans two elements: a component div carrying the film's
    identity in data-* attributes, followed by a nested <img> carrying the
    poster URL. The div opens a pending item; the image completes it.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[RawFavoriteItem] = []
        self.found_favorites_section = False
        self._open_section_depth = 0
        self._pending_film: dict[str, str] | None = None

    @property
    def _inside_favorites_section(self) -> bool:
        return self._open_section_depth > 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}

        if tag == SECTION_TAG:
            self._handle_section_start(attributes)
            return

        if not self._inside_favorites_section:
            return

        if attributes.get("data-component-class") == POSTER_COMPONENT_CLASS:
            self._start_pending_film(attributes)
        elif tag == IMAGE_TAG and _has_class(attributes, POSTER_IMAGE_CLASS):
            self._complete_pending_film(attributes)

    def handle_endtag(self, tag: str) -> None:
        # Nested sections are counted so an inner </section> does not end ours.
        if tag == SECTION_TAG and self._inside_favorites_section:
            self._open_section_depth -= 1

    def _handle_section_start(self, attributes: dict[str, str]) -> None:
        if self._inside_favorites_section:
            self._open_section_depth += 1
        elif attributes.get("id") == FAVORITES_SECTION_ID:
            self.found_favorites_section = True
            self._open_section_depth = 1

    def _start_pending_film(self, attributes: dict[str, str]) -> None:
        self._pending_film = {
            "film_name": attributes.get("data-item-name", ""),
            "film_link": attributes.get("data-item-link", ""),
        }

    def _complete_pending_film(self, attributes: dict[str, str]) -> None:
        if self._pending_film is None:
            return

        self.items.append(
            RawFavoriteItem(
                film_name=self._pending_film["film_name"],
                film_link=self._pending_film["film_link"],
                poster_src=attributes.get("src", ""),
            )
        )
        self._pending_film = None


def _has_class(attributes: dict[str, str], class_name: str) -> bool:
    """Check for a class token, so 'image' does not match 'image-wrapper'."""
    return class_name in attributes.get("class", "").split()
