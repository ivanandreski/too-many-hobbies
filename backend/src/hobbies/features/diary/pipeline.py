"""
Diary pipeline implementation.

Concrete DataPipeline that fetches the Letterboxd RSS diary feed,
parses and maps it into diary entry dicts, and writes them to JSON.
"""

from pathlib import Path

from hobbies.core.fetcher import fetch_url
from hobbies.core.pipeline import DataPipeline
from hobbies.core.writers.json_writer import write_json
from hobbies.features.diary.constants import LETTERBOXD_RSS_URL_TEMPLATE
from hobbies.features.diary.mapper import map_raw_diary_item_to_dto
from hobbies.features.diary.models import RawDiaryItem
from hobbies.features.diary.parser import extract_raw_diary_items


class DiaryPipeline(DataPipeline):

    def __init__(self, username: str, output_path: str | Path) -> None:
        super().__init__(output_path)
        self._rss_url = LETTERBOXD_RSS_URL_TEMPLATE.format(username=username)

    def fetch(self) -> str:
        return fetch_url(self._rss_url)

    def parse(self, raw_data: str) -> list[RawDiaryItem]:
        return extract_raw_diary_items(raw_data)

    def map(self, parsed_items: list[RawDiaryItem]) -> list[dict]:
        return [map_raw_diary_item_to_dto(item) for item in parsed_items]

    def write(self, dto_entries: list[dict]) -> None:
        write_json(dto_entries, self._output_path)
