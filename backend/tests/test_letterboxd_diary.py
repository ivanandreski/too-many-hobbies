"""
Integration test for the Letterboxd diary pipeline.

Flow under test:
    DiaryPipeline.run():
        fetch_url() → extract_raw_diary_items() → map_raw_diary_item_to_dto() → write_json()

The network fetch is replaced by returning the contents of the sample RSS fixture,
so the test runs fully offline. The final JSON written to disk is then compared
field-by-field against the expected fixture generated from the same RSS sample.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from hobbies.core.writers.json_writer import write_json
from hobbies.features.diary.constants import LETTERBOXD_RSS_URL_TEMPLATE
from hobbies.features.diary.mapper import map_raw_diary_item_to_dto
from hobbies.features.diary.parser import extract_raw_diary_items
from hobbies.features.diary.pipeline import DiaryPipeline

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_RSS_PATH = FIXTURES_DIR / "letterboxd_diary_rss_sample.xml"
EXPECTED_JSON_PATH = FIXTURES_DIR / "diary_expected.json"

TEST_USERNAME = "anzurakiz"
LETTERBOXD_RSS_URL = LETTERBOXD_RSS_URL_TEMPLATE.format(username=TEST_USERNAME)


def _load_sample_rss() -> str:
    return SAMPLE_RSS_PATH.read_text(encoding="utf-8")


def _load_expected_diary() -> dict:
    return json.loads(EXPECTED_JSON_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers / assertions
# ---------------------------------------------------------------------------

def _assert_diary_entry_matches(actual_entry: dict, expected_entry: dict, index: int) -> None:
    """Compare every field of a single diary entry, with clear failure messages."""
    for field_name, expected_value in expected_entry.items():
        actual_value = actual_entry.get(field_name)
        assert actual_value == expected_value, (
            f"Entry [{index}] field '{field_name}': "
            f"expected {expected_value!r}, got {actual_value!r}"
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLetterboxdDiaryPipeline:

    def test_parser_extracts_correct_entry_count(self):
        """Parser should produce one RawDiaryItem per <item> in the sample RSS."""
        sample_rss = _load_sample_rss()
        expected_count = len(_load_expected_diary()["data"])

        raw_items = extract_raw_diary_items(sample_rss)

        assert len(raw_items) == expected_count

    def test_mapper_produces_correct_dto_fields(self):
        """Mapper should convert the first RawDiaryItem into the expected DTO dict."""
        sample_rss = _load_sample_rss()
        expected_first_entry = _load_expected_diary()["data"][0]

        raw_items = extract_raw_diary_items(sample_rss)
        dto = map_raw_diary_item_to_dto(raw_items[0])

        _assert_diary_entry_matches(dto, expected_first_entry, index=0)

    def test_mapper_produces_correct_dtos_for_all_entries(self):
        """Every mapped DTO must match the corresponding fixture entry field-by-field."""
        sample_rss = _load_sample_rss()
        expected_entries = _load_expected_diary()["data"]

        raw_items = extract_raw_diary_items(sample_rss)
        dto_entries = [map_raw_diary_item_to_dto(item) for item in raw_items]

        for index, (dto, expected_entry) in enumerate(zip(dto_entries, expected_entries)):
            _assert_diary_entry_matches(dto, expected_entry, index)

    def test_writer_produces_correct_envelope(self):
        """write_json should wrap entries in the { "data": [...] } envelope."""
        sample_entries = [{"name": "Test Film", "releaseYear": 2000}]

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="r") as tmp:
            output_path = Path(tmp.name)

        write_json(sample_entries, output_path)
        written = json.loads(output_path.read_text(encoding="utf-8"))

        assert "data" in written
        assert written["data"] == sample_entries

    def test_full_pipeline_run_output_matches_fixture(self):
        """
        End-to-end: DiaryPipeline.run() with a mocked fetch writes the correct JSON.
        Nothing in this test touches the network or the real frontend directory.
        """
        sample_rss = _load_sample_rss()
        expected_diary = _load_expected_diary()

        with (
            tempfile.TemporaryDirectory() as temporary_output_dir,
            patch("hobbies.core.fetcher.urllib.request.urlopen") as mock_urlopen,
        ):
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                sample_rss.encode("utf-8")
            )

            output_json_path = Path(temporary_output_dir) / "diary.json"
            DiaryPipeline(username=TEST_USERNAME, output_path=output_json_path).run()

            written_diary = json.loads(output_json_path.read_text(encoding="utf-8"))

        assert written_diary == expected_diary, (
            "Full pipeline output does not match the expected fixture."
        )
