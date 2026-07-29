"""
Gear pipeline implementation.

Concrete DataPipeline that reads the authenticated athlete's bikes from the
Strava API and writes them to JSON as a keyed object.

Two things set this pipeline apart from the Letterboxd ones:

  * It authenticates. A short-lived access token is minted from the stored
    refresh token at the start of each run — see features/gear/auth.py.
  * Its payload is a keyed object, not a list, because the gear widget looks
    bikes up by role ("mainBike", "commuter") rather than iterating.
"""

from pathlib import Path

from hobbies.core.http import get_text
from hobbies.core.pipeline import DataPipeline
from hobbies.core.writers.json_writer import write_json
from hobbies.features.gear.auth import StravaCredentials, fetch_access_token
from hobbies.features.gear.config import BIKE_ROLE_CONFIGS, BikeRoleConfig
from hobbies.features.gear.constants import STRAVA_ATHLETE_URL
from hobbies.features.gear.mapper import build_bikes_payload
from hobbies.features.gear.models import RawGearItem
from hobbies.features.gear.parser import extract_raw_gear_items


class GearPipeline(DataPipeline):

    def __init__(
        self,
        output_path: str | Path,
        credentials: StravaCredentials | None = None,
        role_configs: list[BikeRoleConfig] | None = None,
    ) -> None:
        """
        Args:
            output_path:  Destination JSON file.
            credentials:  Strava credentials. Read from the environment when
                          omitted, which is the normal path; injectable so tests
                          never need real secrets.
            role_configs: Role mapping. Defaults to BIKE_ROLE_CONFIGS.
        """
        super().__init__(output_path)
        self._credentials = credentials
        self._role_configs = BIKE_ROLE_CONFIGS if role_configs is None else role_configs

    def fetch(self) -> str:
        credentials = self._credentials or StravaCredentials.from_environment()
        access_token = fetch_access_token(credentials)

        return get_text(
            STRAVA_ATHLETE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def parse(self, raw_data: str) -> list[RawGearItem]:
        return extract_raw_gear_items(raw_data)

    def map(self, parsed_items: list[RawGearItem]) -> dict[str, dict]:
        return build_bikes_payload(parsed_items, self._role_configs)

    def write(self, dto_entries: dict[str, dict]) -> None:
        write_json(dto_entries, self._output_path)
