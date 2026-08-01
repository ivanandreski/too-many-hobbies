"""
Strava pipeline implementations.

Three pipelines, one scrape. Each takes the same StravaScraper, whose result is
memoised, so generating all three files logs in once and reads each page once.

These differ from the Letterboxd pipelines in that fetch() returns a structured
object rather than raw text — the scraper has already turned pages into data,
because collecting it needs browser interaction (switching sport tabs, paging)
that cannot be expressed as a single URL fetch.
"""

from pathlib import Path

from hobbies.core.pipeline import DataPipeline
from hobbies.core.writers.json_writer import write_json
from hobbies.features.strava.mappers import (
    build_bikes_payload,
    build_cycling_payload,
    build_running_payload,
)
from hobbies.features.strava.models import ScrapedStrava
from hobbies.features.strava.scraper import StravaScraper


class _StravaPipeline(DataPipeline):
    """Shared plumbing: scrape once, map, write."""

    def __init__(self, output_path: str | Path, scraper: StravaScraper | None = None) -> None:
        super().__init__(output_path)
        self._scraper = scraper or StravaScraper()

    def fetch(self) -> ScrapedStrava:
        return self._scraper.scrape()

    def parse(self, raw_data: ScrapedStrava) -> ScrapedStrava:
        # Parsing already happened inside the scraper, which had to interpret each
        # page as it went in order to know when to stop paging.
        return raw_data

    def write(self, dto_entries) -> None:
        write_json(dto_entries, self._output_path)


class GearPipeline(_StravaPipeline):
    """Writes frontend/data/gear/bikes.json from the profile's gear section."""

    def map(self, parsed_items: ScrapedStrava) -> dict[str, dict]:
        return build_bikes_payload(parsed_items.bikes)


class CyclingPipeline(_StravaPipeline):
    """Writes frontend/data/strava/cycling.json — year ride totals plus groups."""

    def map(self, parsed_items: ScrapedStrava) -> dict:
        return build_cycling_payload(parsed_items)


class RunningPipeline(_StravaPipeline):
    """Writes frontend/data/strava/running.json — year run totals plus runs."""

    def map(self, parsed_items: ScrapedStrava) -> dict:
        return build_running_payload(parsed_items)
