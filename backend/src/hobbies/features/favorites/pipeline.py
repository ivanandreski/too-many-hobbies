"""
Favorites pipeline implementation.

Concrete DataPipeline that renders a Letterboxd profile page in a headless
browser, scrapes the favorites grid, and writes the entries to JSON.

Unlike the diary pipeline, this one cannot use a plain HTTP fetch: profile
posters are lazily loaded, so an unrendered page yields only placeholders.
"""

from pathlib import Path

from hobbies.core.pipeline import DataPipeline
from hobbies.core.rendered_fetcher import fetch_rendered_html
from hobbies.core.writers.json_writer import write_json
from hobbies.features.favorites.constants import (
    FAVORITES_IMAGE_SELECTOR,
    LETTERBOXD_PROFILE_URL_TEMPLATE,
    POSTERS_RESOLVED_PREDICATE,
)
from hobbies.features.favorites.mapper import map_raw_favorite_item_to_dto
from hobbies.features.favorites.models import RawFavoriteItem
from hobbies.features.favorites.parser import extract_raw_favorite_items


class FavoritesPipeline(DataPipeline):

    def __init__(self, username: str, output_path: str | Path) -> None:
        super().__init__(output_path)
        self._profile_url = LETTERBOXD_PROFILE_URL_TEMPLATE.format(username=username)

    def fetch(self) -> str:
        return fetch_rendered_html(
            self._profile_url,
            wait_for_selector=FAVORITES_IMAGE_SELECTOR,
            wait_for_function=POSTERS_RESOLVED_PREDICATE,
        )

    def parse(self, raw_data: str) -> list[RawFavoriteItem]:
        return extract_raw_favorite_items(raw_data)

    def map(self, parsed_items: list[RawFavoriteItem]) -> list[dict]:
        return [map_raw_favorite_item_to_dto(item) for item in parsed_items]

    def write(self, dto_entries: list[dict]) -> None:
        write_json(dto_entries, self._output_path)
