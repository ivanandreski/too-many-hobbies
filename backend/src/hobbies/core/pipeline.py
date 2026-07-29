"""
Abstract base class for all data pipeline features.

Defines the standard pipeline skeleton:
    fetch → parse → map → write

Each feature subclass implements its own version of each step.
The orchestration is handled here by the run() method.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from hobbies.core.writers.json_writer import JsonPayload


class DataPipeline(ABC):
    """
    Template base class for a fetch → parse → map → write data pipeline.

    Subclasses must implement all abstract methods. The run() method
    orchestrates the steps in order.
    """

    def __init__(self, output_path: str | Path) -> None:
        self._output_path = Path(output_path)
    @abstractmethod
    def fetch(self) -> str:
        """
        Fetch raw data from an external source (API, RSS feed, web page, etc.).

        Returns:
            Raw response content as a string.
        """
        ...

    @abstractmethod
    def parse(self, raw_data: str) -> list:
        """
        Parse raw response content into a list of intermediate data objects.

        Args:
            raw_data: The raw string returned by fetch().

        Returns:
            List of intermediate objects (e.g. dataclass instances).
        """
        ...

    @abstractmethod
    def map(self, parsed_items: list) -> JsonPayload:
        """
        Map intermediate data objects into the final JSON payload.

        Args:
            parsed_items: The list returned by parse().

        Returns:
            Either a list of DTO dicts, or a dict mapping keys to DTO dicts for
            features whose JSON is a keyed object rather than an array.
        """
        ...

    @abstractmethod
    def write(self, dto_entries: JsonPayload) -> None:
        """
        Write the final payload to its destination (e.g. a JSON file).

        Args:
            dto_entries: The payload returned by map().
        """
        ...

    def run(self) -> None:
        """
        Execute the full pipeline in order: fetch → parse → map → write.
        """
        raw_data = self.fetch()
        parsed_items = self.parse(raw_data)
        dto_entries = self.map(parsed_items)
        self.write(dto_entries)
