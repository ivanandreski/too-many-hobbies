"""
Integration test for the Letterboxd favorites pipeline.

Flow under test:
    FavoritesPipeline.run():
        fetch_rendered_html() → extract_raw_favorite_items()
        → map_raw_favorite_item_to_dto() → write_json()

The headless-browser fetch is replaced by returning the contents of a trimmed
profile fixture, so the test runs fully offline and needs no browser binary.
The fixture is a real rendered profile section (posters already swapped in by
Letterboxd's scripts) plus two deliberate traps:

  * a decoy poster grid outside the favorites section, which must be ignored
  * a nested <section> inside the favorites section, which must not end it
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from hobbies.features.favorites.constants import LETTERBOXD_PROFILE_URL_TEMPLATE
from hobbies.features.favorites.mapper import map_raw_favorite_item_to_dto
from hobbies.features.favorites.parser import extract_raw_favorite_items
from hobbies.features.favorites.pipeline import FavoritesPipeline

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PROFILE_PATH = FIXTURES_DIR / "letterboxd_profile_rendered_sample.html"
EXPECTED_JSON_PATH = FIXTURES_DIR / "favorites_expected.json"

TEST_USERNAME = "anzurakiz"
LETTERBOXD_PROFILE_URL = LETTERBOXD_PROFILE_URL_TEMPLATE.format(username=TEST_USERNAME)

DECOY_FILM_NAME = "Not A Favorite"


def _load_sample_profile() -> str:
    return SAMPLE_PROFILE_PATH.read_text(encoding="utf-8")


def _load_expected_favorites() -> dict:
    return json.loads(EXPECTED_JSON_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers / assertions
# ---------------------------------------------------------------------------

def _assert_favorite_entry_matches(actual_entry: dict, expected_entry: dict, index: int) -> None:
    """Compare every field of a single favorite entry, with clear failure messages."""
    for field_name, expected_value in expected_entry.items():
        actual_value = actual_entry.get(field_name)
        assert actual_value == expected_value, (
            f"Entry [{index}] field '{field_name}': "
            f"expected {expected_value!r}, got {actual_value!r}"
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLetterboxdFavoritesPipeline:

    def test_parser_extracts_four_favorites(self):
        """A profile's favorites grid holds exactly four films."""
        raw_items = extract_raw_favorite_items(_load_sample_profile())

        assert len(raw_items) == 4

    def test_parser_ignores_poster_grids_outside_favorites_section(self):
        """The decoy grid uses identical markup but must not be scraped."""
        raw_items = extract_raw_favorite_items(_load_sample_profile())

        scraped_names = [item.film_name for item in raw_items]
        assert not any(DECOY_FILM_NAME in name for name in scraped_names), (
            f"Scraper picked up a poster from outside the favorites section: {scraped_names}"
        )

    def test_parser_raises_when_favorites_section_is_missing(self):
        """
        A page without the favorites section means a failed load or changed
        markup. It must raise rather than quietly produce an empty list, which
        would overwrite good data with nothing.
        """
        with pytest.raises(ValueError, match="favourites"):
            extract_raw_favorite_items("<html><body><p>no favorites here</p></body></html>")

    def test_mapper_splits_title_and_year(self):
        """The display name "Raiders of the Lost Ark (1981)" splits into name + year."""
        raw_items = extract_raw_favorite_items(_load_sample_profile())

        dto = map_raw_favorite_item_to_dto(raw_items[0])

        assert dto["name"] == "Raiders of the Lost Ark"
        assert dto["releaseYear"] == 1981

    def test_mapper_upscales_thumbnail_poster_url(self):
        """
        The profile renders 150x225 thumbnails; the DTO must request the
        full-size crop encoded in the same URL.
        """
        raw_items = extract_raw_favorite_items(_load_sample_profile())

        dto = map_raw_favorite_item_to_dto(raw_items[0])

        assert "-0-150-0-225-crop" in raw_items[0].poster_src
        assert "-0-1000-0-1500-crop" in dto["poster"]

    def test_mapper_produces_absolute_canonical_film_urls(self):
        """Site-relative film links become absolute letterboxd.com/film/<slug>/ URLs."""
        raw_items = extract_raw_favorite_items(_load_sample_profile())

        dto_entries = [map_raw_favorite_item_to_dto(item) for item in raw_items]

        for dto in dto_entries:
            assert dto["url"].startswith("https://letterboxd.com/film/")

    def test_mapper_produces_correct_dtos_for_all_entries(self):
        """Every mapped DTO must match the corresponding fixture entry field-by-field."""
        expected_entries = _load_expected_favorites()["data"]

        raw_items = extract_raw_favorite_items(_load_sample_profile())
        dto_entries = [map_raw_favorite_item_to_dto(item) for item in raw_items]

        for index, (dto, expected_entry) in enumerate(zip(dto_entries, expected_entries)):
            _assert_favorite_entry_matches(dto, expected_entry, index)

    def test_full_pipeline_run_output_matches_fixture(self):
        """
        End-to-end: FavoritesPipeline.run() with a mocked render writes the
        correct JSON. Nothing here touches the network, a browser, or the real
        frontend directory.
        """
        expected_favorites = _load_expected_favorites()

        with (
            tempfile.TemporaryDirectory() as temporary_output_dir,
            patch(
                "hobbies.features.favorites.pipeline.fetch_rendered_html",
                return_value=_load_sample_profile(),
            ) as mock_fetch,
        ):
            output_json_path = Path(temporary_output_dir) / "favorites.json"
            FavoritesPipeline(username=TEST_USERNAME, output_path=output_json_path).run()

            written_favorites = json.loads(output_json_path.read_text(encoding="utf-8"))

        assert mock_fetch.call_args.args[0] == LETTERBOXD_PROFILE_URL
        assert written_favorites == expected_favorites, (
            "Full pipeline output does not match the expected fixture."
        )
