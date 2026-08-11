"""
Unit tests for mapping scraped Strava data onto the frontend JSON payloads.

Covers the schema contracts the widgets depend on: the keyed bikes object read by
gear.js, and the summary-plus-groups shape read by strava.js.
"""

import pytest

from hobbies.features.strava.config import ActivityTarget, BikeRoleConfig
from hobbies.features.strava.mappers import (
    GearMappingError,
    build_bikes_payload,
    build_cycling_payload,
    build_running_payload,
)
from hobbies.features.strava.models import RawActivity, RawBike, RawSportTotals, ScrapedStrava

TARGETS = [
    ActivityTarget(key="rides", sport="ride", is_commute=False, count=2),
    ActivityTarget(key="commutes", sport="ride", is_commute=True, count=2),
    ActivityTarget(key="runs", sport="run", is_commute=None, count=2),
]

ROLE_CONFIGS = [
    BikeRoleConfig(role_key="mainBike", strava_gear_name="Trek Emonda S"),
    BikeRoleConfig(role_key="commuter", strava_gear_name="ROG Elite"),
]


def activity(
    name: str,
    sport: str,
    is_commute: bool = False,
    activity_id: str | None = None,
) -> RawActivity:
    return RawActivity(
        name=name,
        start_date_local="2026-07-26T00:00:00",
        distance_metres=58100,
        moving_time_seconds=7450,
        sport=sport,
        is_commute=is_commute,
        activity_id=activity_id,
    )


def scraped() -> ScrapedStrava:
    return ScrapedStrava(
        bikes=[
            RawBike(name="Trek Emonda S", distance_metres=1002700),
            RawBike(name="ROG Elite", distance_metres=795000),
            RawBike(name="Old Frame", distance_metres=0),
        ],
        year_totals={
            "ride": RawSportTotals(3240000, 417900, 94),
            "run": RawSportTotals(318000, 100230, 41),
        },
        all_time_totals={
            "ride": RawSportTotals(41882000, 5047900, 1204),
            "run": RawSportTotals(2110000, 700000, 260),
        },
        activities=[
            activity("Weekend Loop", "ride"),
            activity("Commute home", "ride", is_commute=True),
            activity("Hill Repeats", "ride"),
            activity("Commute to work", "ride", is_commute=True),
            activity("Long Run", "run"),
            activity("Tempo Run", "run"),
            activity("Pool session", "swim"),
        ],
    )


class TestBikesPayload:

    def test_maps_roles_to_bikes_by_name(self):
        payload = build_bikes_payload(scraped().bikes, ROLE_CONFIGS)

        assert list(payload) == ["mainBike", "commuter"]
        assert payload["mainBike"]["name"] == "Trek Emonda S"

    def test_converts_all_time_metres_to_kilometres(self):
        payload = build_bikes_payload(scraped().bikes, ROLE_CONFIGS)

        assert payload["mainBike"]["milage"] == 1002.7
        assert payload["commuter"]["milage"] == 795.0

    def test_emits_only_name_and_mileage(self):
        """
        Photos are static markup in components/gear.html, not data. Emitting an
        image field would put an unchanging value into a generated file.
        """
        payload = build_bikes_payload(scraped().bikes, ROLE_CONFIGS)

        for entry in payload.values():
            assert set(entry) == {"name", "milage"}

    def test_ignores_bikes_no_role_claims(self):
        payload = build_bikes_payload(scraped().bikes, ROLE_CONFIGS)

        assert all(entry["name"] != "Old Frame" for entry in payload.values())

    def test_raises_listing_scraped_names_when_a_role_matches_nothing(self):
        configs = [BikeRoleConfig(role_key="mainBike", strava_gear_name="Nonexistent")]

        with pytest.raises(GearMappingError, match="Trek Emonda S"):
            build_bikes_payload(scraped().bikes, configs)


class TestCyclingPayload:

    def test_summary_comes_from_the_year_ride_totals(self):
        payload = build_cycling_payload(scraped(), TARGETS)

        assert payload["period"] == "This Year"
        assert payload["summary"]["distanceMetres"] == 3240000
        assert payload["summary"]["movingTimeSeconds"] == 417900
        assert payload["summary"]["activityCount"] == 94

    def test_has_two_groups_split_by_commute_flag(self):
        payload = build_cycling_payload(scraped(), TARGETS)

        groups = {group["key"]: group for group in payload["groups"]}
        assert list(groups) == ["rides", "commutes"]
        assert [a["name"] for a in groups["rides"]["activities"]] == [
            "Weekend Loop",
            "Hill Repeats",
        ]
        assert [a["name"] for a in groups["commutes"]["activities"]] == [
            "Commute home",
            "Commute to work",
        ]

    def test_groups_carry_no_summary_of_their_own(self):
        """
        Strava's year panel has no commute breakdown, so per-group summaries
        cannot be scraped. The summary is sport-level and lives at the top.
        """
        payload = build_cycling_payload(scraped(), TARGETS)

        assert all("summary" not in group for group in payload["groups"])

    def test_includes_all_time_totals(self):
        payload = build_cycling_payload(scraped(), TARGETS)

        assert payload["allTime"]["distanceMetres"] == 41882000

    def test_excludes_runs_and_other_sports(self):
        payload = build_cycling_payload(scraped(), TARGETS)

        names = [a["name"] for group in payload["groups"] for a in group["activities"]]
        assert "Long Run" not in names
        assert "Pool session" not in names

    def test_activities_use_raw_metres_and_seconds(self):
        payload = build_cycling_payload(scraped(), TARGETS)

        first = payload["groups"][0]["activities"][0]
        assert first["distanceMetres"] == 58100
        assert first["movingTimeSeconds"] == 7450
        assert first["startDateLocal"] == "2026-07-26T00:00:00"


class TestRunningPayload:

    def test_summary_comes_from_the_year_run_totals(self):
        payload = build_running_payload(scraped(), TARGETS)

        assert payload["sport"] == "running"
        assert payload["summary"]["distanceMetres"] == 318000
        assert payload["summary"]["activityCount"] == 41

    def test_has_a_single_runs_group(self):
        payload = build_running_payload(scraped(), TARGETS)

        assert [group["key"] for group in payload["groups"]] == ["runs"]
        assert [a["name"] for a in payload["groups"][0]["activities"]] == [
            "Long Run",
            "Tempo Run",
        ]


class TestMissingTotals:

    def test_absent_panel_yields_zeroes_and_a_null_count(self):
        """
        A missing totals panel must not abort the run — the activity lists are
        still publishable — but it must not fake a count either.
        """
        partial = scraped()
        partial.year_totals = {}

        payload = build_cycling_payload(partial, TARGETS)

        assert payload["summary"]["distanceMetres"] == 0
        assert payload["summary"]["activityCount"] is None

    def test_omits_all_time_when_it_was_not_scraped(self):
        partial = scraped()
        partial.all_time_totals = {}

        assert "allTime" not in build_cycling_payload(partial, TARGETS)


class TestRouteImages:
    """
    routeImage is what lets the widget tell five "Evening Ride" rows apart, so
    the schema contract matters: always present, path or null, never missing.
    """

    def test_attaches_the_captured_image_path_by_activity_id(self):
        harvest = ScrapedStrava(
            year_totals={"ride": RawSportTotals(3240000, 417900, 94)},
            activities=[activity("Weekend Loop", "ride", activity_id="19676568129")],
            route_maps={"19676568129": "/assets/strava/routes/19676568129.jpg"},
        )

        payload = build_cycling_payload(harvest, TARGETS)
        first = payload["groups"][0]["activities"][0]

        assert first["routeImage"] == "/assets/strava/routes/19676568129.jpg"

    def test_emits_null_when_no_map_was_captured(self):
        """
        An indoor ride has no GPS trace, so it never gets a picture. The key must
        still be there — the widget branches on the value, not on its presence.
        """
        harvest = ScrapedStrava(
            year_totals={"ride": RawSportTotals(3240000, 417900, 94)},
            activities=[activity("Zwift session", "ride", activity_id="19676568130")],
            route_maps={},
        )

        payload = build_cycling_payload(harvest, TARGETS)
        first = payload["groups"][0]["activities"][0]

        assert "routeImage" in first
        assert first["routeImage"] is None

    def test_emits_null_for_an_activity_with_no_id(self):
        """A row that rendered without a link cannot be matched to an image."""
        harvest = ScrapedStrava(
            year_totals={"ride": RawSportTotals(3240000, 417900, 94)},
            activities=[activity("Weekend Loop", "ride", activity_id=None)],
            route_maps={"19676568129": "/assets/strava/routes/19676568129.jpg"},
        )

        payload = build_cycling_payload(harvest, TARGETS)

        assert payload["groups"][0]["activities"][0]["routeImage"] is None

    def test_runs_carry_their_images_too(self):
        harvest = ScrapedStrava(
            year_totals={"run": RawSportTotals(318000, 100230, 41)},
            activities=[activity("Long Run", "run", activity_id="19366668657")],
            route_maps={"19366668657": "/assets/strava/routes/19366668657.jpg"},
        )

        payload = build_running_payload(harvest, TARGETS)

        assert payload["groups"][0]["activities"][0]["routeImage"] == (
            "/assets/strava/routes/19366668657.jpg"
        )
