"""
Integration test for the Strava gear pipeline.

Flow under test:
    GearPipeline.run():
        fetch_access_token() + get_text() → extract_raw_gear_items()
        → build_bikes_payload() → write_json()

Both network calls are mocked, so the test needs no Strava credentials and runs
offline. The athlete fixture follows the response shape documented in Strava's
Swagger spec, with distances in metres and a third bike that no role config
claims — the mapping must select by name, not by position.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from hobbies.features.gear.auth import StravaCredentials
from hobbies.features.gear.config import BikeRoleConfig
from hobbies.features.gear.mapper import build_bikes_payload
from hobbies.features.gear.parser import extract_raw_gear_items
from hobbies.features.gear.pipeline import GearPipeline

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_ATHLETE_PATH = FIXTURES_DIR / "strava_athlete_sample.json"

FAKE_CREDENTIALS = StravaCredentials(
    client_id="12345",
    client_secret="not-a-real-secret",
    refresh_token="not-a-real-refresh-token",
)

TEST_ROLE_CONFIGS = [
    BikeRoleConfig(role_key="mainBike", strava_gear_name="Trek Emonda S"),
    BikeRoleConfig(
        role_key="commuter",
        strava_gear_name="ROG Elite",
        image="https://example.test/rog-elite.jpg",
    ),
]


def _load_sample_athlete() -> str:
    return SAMPLE_ATHLETE_PATH.read_text(encoding="utf-8")


class TestStravaGearParser:

    def test_extracts_only_bikes_not_shoes(self):
        """The athlete response carries shoes too; this feature ignores them."""
        raw_items = extract_raw_gear_items(_load_sample_athlete())

        assert len(raw_items) == 3
        assert all("Adidas" not in item.name for item in raw_items)

    def test_extracts_bike_fields(self):
        """Fields map straight across, with distance still in metres."""
        raw_items = extract_raw_gear_items(_load_sample_athlete())

        main_bike = raw_items[0]
        assert main_bike.gear_id == "b1231"
        assert main_bike.name == "Trek Emonda S"
        assert main_bike.distance_metres == 1002700
        assert main_bike.is_primary is True

    def test_raises_with_scope_hint_when_bikes_field_is_absent(self):
        """
        Strava omits gear from the summary athlete representation. That means a
        missing scope, so the error must say so rather than report zero bikes.
        """
        summary_athlete = json.dumps({"id": 1, "username": "test", "resource_state": 2})

        with pytest.raises(ValueError, match="profile:read_all"):
            extract_raw_gear_items(summary_athlete)


class TestStravaGearMapper:

    def test_converts_metres_to_kilometres(self):
        """1002700 metres is the 1002.7 km the data file records."""
        raw_items = extract_raw_gear_items(_load_sample_athlete())

        payload = build_bikes_payload(raw_items, TEST_ROLE_CONFIGS)

        assert payload["mainBike"]["milage"] == 1002.7
        assert payload["commuter"]["milage"] == 795.0

    def test_matches_bikes_by_name_ignoring_unclaimed_gear(self):
        """The fixture's third bike belongs to no role and must not appear."""
        raw_items = extract_raw_gear_items(_load_sample_athlete())

        payload = build_bikes_payload(raw_items, TEST_ROLE_CONFIGS)

        assert list(payload) == ["mainBike", "commuter"]
        assert payload["mainBike"]["name"] == "Trek Emonda S"
        assert payload["commuter"]["name"] == "ROG Elite"

    def test_includes_image_only_when_config_supplies_one(self):
        """Strava has no gear photos, so images are opt-in per role."""
        raw_items = extract_raw_gear_items(_load_sample_athlete())

        payload = build_bikes_payload(raw_items, TEST_ROLE_CONFIGS)

        assert "image" not in payload["mainBike"]
        assert payload["commuter"]["image"] == "https://example.test/rog-elite.jpg"

    def test_matches_gear_name_case_insensitively(self):
        """Strava names are athlete-entered, so casing should not be load-bearing."""
        raw_items = extract_raw_gear_items(_load_sample_athlete())
        configs = [BikeRoleConfig(role_key="mainBike", strava_gear_name="trek EMONDA s")]

        payload = build_bikes_payload(raw_items, configs)

        assert payload["mainBike"]["name"] == "Trek Emonda S"

    def test_raises_listing_available_names_when_role_matches_nothing(self):
        """
        A silently missing role key would break the widget, which indexes roles
        directly. Fail instead, and name the gear that is actually available.
        """
        raw_items = extract_raw_gear_items(_load_sample_athlete())
        configs = [BikeRoleConfig(role_key="mainBike", strava_gear_name="Nonexistent Bike")]

        with pytest.raises(ValueError, match="Trek Emonda S"):
            build_bikes_payload(raw_items, configs)


class TestStravaGearPipeline:

    def test_full_pipeline_run_writes_keyed_payload(self):
        """
        End-to-end with both network calls mocked. Asserts the envelope is a
        keyed object, matching frontend/data/gear/bikes.json.
        """
        with (
            tempfile.TemporaryDirectory() as temporary_output_dir,
            patch(
                "hobbies.features.gear.pipeline.fetch_access_token",
                return_value="fake-access-token",
            ),
            patch(
                "hobbies.features.gear.pipeline.get_text",
                return_value=_load_sample_athlete(),
            ) as mock_get_text,
        ):
            output_json_path = Path(temporary_output_dir) / "bikes.json"
            GearPipeline(
                output_path=output_json_path,
                credentials=FAKE_CREDENTIALS,
                role_configs=TEST_ROLE_CONFIGS,
            ).run()

            written = json.loads(output_json_path.read_text(encoding="utf-8"))

        assert written == {
            "data": {
                "mainBike": {"name": "Trek Emonda S", "milage": 1002.7},
                "commuter": {
                    "name": "ROG Elite",
                    "milage": 795.0,
                    "image": "https://example.test/rog-elite.jpg",
                },
            }
        }

        # The bearer token must actually reach the request.
        sent_headers = mock_get_text.call_args.kwargs["headers"]
        assert sent_headers["Authorization"] == "Bearer fake-access-token"

    def test_pipeline_does_not_touch_environment_when_credentials_injected(self):
        """Injected credentials must short-circuit the environment lookup."""
        with (
            tempfile.TemporaryDirectory() as temporary_output_dir,
            patch(
                "hobbies.features.gear.pipeline.fetch_access_token",
                return_value="fake-access-token",
            ) as mock_fetch_token,
            patch(
                "hobbies.features.gear.pipeline.get_text",
                return_value=_load_sample_athlete(),
            ),
            patch(
                "hobbies.features.gear.auth.StravaCredentials.from_environment",
                side_effect=AssertionError("should not read the environment"),
            ),
        ):
            GearPipeline(
                output_path=Path(temporary_output_dir) / "bikes.json",
                credentials=FAKE_CREDENTIALS,
                role_configs=TEST_ROLE_CONFIGS,
            ).run()

        assert mock_fetch_token.call_args.args[0] == FAKE_CREDENTIALS
