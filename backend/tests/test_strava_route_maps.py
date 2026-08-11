"""
Unit tests for route map capture.

Only the browser-free parts are covered: which activities get photographed, and
the paths the JSON ends up pointing at. The capture itself needs a logged-in
Chromium and a live activity page, so it is exercised by running a real scrape
rather than by a test.
"""

from pathlib import Path

from hobbies.features.strava.models import RawActivity
from hobbies.features.strava.route_maps import (
    IMAGE_EXTENSION,
    ROUTE_ASSET_URL_PREFIX,
    _deduplicate,
    capture_route_maps,
    existing_route_maps,
)


def activity(name: str, activity_id: str | None) -> RawActivity:
    return RawActivity(
        name=name,
        start_date_local="2026-08-10T00:00:00",
        distance_metres=28460,
        moving_time_seconds=3568,
        sport="Ride",
        is_commute=False,
        activity_id=activity_id,
    )


class TestDeduplicate:

    def test_drops_repeats_of_the_same_activity(self):
        """
        Cycling asks for rides and commutes from the same list, so one activity
        can be requested twice. Capturing it twice costs seven seconds for a
        byte-identical file.
        """
        activities = [
            activity("Morning Ride", "1"),
            activity("Evening Ride", "2"),
            activity("Morning Ride", "1"),
        ]

        assert [a.activity_id for a in _deduplicate(activities)] == ["1", "2"]

    def test_drops_activities_with_no_id(self):
        """Without an id there is no page to open and no filename to write."""
        activities = [activity("Morning Ride", None), activity("Evening Ride", "2")]

        assert [a.activity_id for a in _deduplicate(activities)] == ["2"]

    def test_preserves_order(self):
        activities = [activity("c", "3"), activity("a", "1"), activity("b", "2")]

        assert [a.activity_id for a in _deduplicate(activities)] == ["3", "1", "2"]


class TestCaptureGuards:

    def test_returns_empty_without_opening_a_browser_when_nothing_has_an_id(self):
        """
        The session is used only if there is something to capture, so passing None
        here proves no browser work was attempted.
        """
        activities = [activity("Morning Ride", None)]

        assert capture_route_maps(None, activities, Path("/nonexistent")) == {}

    def test_returns_empty_for_no_activities(self):
        assert capture_route_maps(None, [], Path("/nonexistent")) == {}

    def test_does_not_create_the_output_directory_when_there_is_nothing_to_write(
        self, tmp_path
    ):
        """An empty run must not leave an empty routes/ directory behind."""
        output_dir = tmp_path / "routes"

        capture_route_maps(None, [activity("Morning Ride", None)], output_dir)

        assert not output_dir.exists()


class TestExistingRouteMaps:
    """
    Skipping the capture must not drop the pictures.

    Before this existed, a skipped run rewrote the JSON with every routeImage null
    while the image files sat untouched on disk — the maps disappeared from the site
    and it looked like a scraping failure.
    """

    def test_references_images_that_are_on_disk(self, tmp_path):
        (tmp_path / "1.jpg").write_bytes(b"jpeg")

        found = existing_route_maps([activity("Morning Ride", "1")], tmp_path)

        assert found == {"1": "/assets/strava/routes/1.jpg"}

    def test_omits_activities_with_no_image(self, tmp_path):
        (tmp_path / "1.jpg").write_bytes(b"jpeg")

        found = existing_route_maps(
            [activity("Morning Ride", "1"), activity("Evening Ride", "2")], tmp_path
        )

        assert found == {"1": "/assets/strava/routes/1.jpg"}

    def test_returns_empty_for_a_directory_that_does_not_exist(self, tmp_path):
        found = existing_route_maps([activity("Morning Ride", "1")], tmp_path / "nope")

        assert found == {}

    def test_paths_match_what_a_capture_would_have_produced(self, tmp_path):
        """
        The two code paths write the same JSON, so a skipped run and a captured run
        differ only in freshness.
        """
        (tmp_path / "19676568129.jpg").write_bytes(b"jpeg")

        found = existing_route_maps([activity("Morning Ride", "19676568129")], tmp_path)

        assert found["19676568129"] == (
            f"{ROUTE_ASSET_URL_PREFIX}/19676568129{IMAGE_EXTENSION}"
        )


class TestAssetPaths:

    def test_the_url_prefix_matches_the_sites_asset_layout(self):
        """
        The images are written into frontend/assets/strava/routes and requested
        from /assets/strava/routes. These two have to agree, and nothing at
        runtime checks that they do.
        """
        assert ROUTE_ASSET_URL_PREFIX == "/assets/strava/routes"
        assert IMAGE_EXTENSION == ".jpg"
