"""
Unit tests for the scraper's safety guards.

The sport switcher is a row of icons. If a click fails, the totals panel keeps
showing the previous sport, and those numbers would be filed under the wrong
sport — plausible-looking, completely wrong data. The guard tested here is what
prevents that, so it is worth covering directly rather than only through the
browser tests.
"""

from hobbies.features.strava.scraper import StravaCredentials, StravaScraper

RIDE_PANEL = "This Year\nDistance 3,240.0 km\nTime 116h 5m\nRides 182"
RUN_PANEL = "This Year\nDistance 318.0 km\nTime 27h 50m\nRuns 41"


class TestIdenticalPanelGuard:

    def test_detects_a_panel_repeated_for_a_second_sport(self):
        """An unchanged panel means the icon click did nothing."""
        seen = {"year:ride": RIDE_PANEL}

        assert StravaScraper._sport_showing_same_panel(seen, "year", RIDE_PANEL) == "ride"

    def test_accepts_a_genuinely_different_panel(self):
        seen = {"year:ride": RIDE_PANEL}

        assert StravaScraper._sport_showing_same_panel(seen, "year", RUN_PANEL) is None

    def test_compares_only_within_the_same_panel_kind(self):
        """
        A year panel and an all-time panel can legitimately be identical for a
        brand-new account, so the two must not be compared against each other.
        """
        seen = {"all-time:ride": RIDE_PANEL}

        assert StravaScraper._sport_showing_same_panel(seen, "year", RIDE_PANEL) is None

    def test_first_panel_of_a_kind_is_always_accepted(self):
        assert StravaScraper._sport_showing_same_panel({}, "year", RIDE_PANEL) is None


class TestCredentials:

    def test_password_login_requires_both_email_and_password(self):
        """A half-configured credential must not be treated as usable."""
        assert StravaCredentials(athlete_id="1").can_log_in_automatically is False
        assert StravaCredentials(athlete_id="1", email="a@b.c").can_log_in_automatically is False
        assert StravaCredentials(athlete_id="1", password="x").can_log_in_automatically is False

    def test_password_login_available_when_both_are_present(self):
        credentials = StravaCredentials(athlete_id="1", email="a@b.c", password="x")

        assert credentials.can_log_in_automatically is True

    def test_reads_athlete_id_and_optional_login_from_environment(self, monkeypatch):
        monkeypatch.setenv("STRAVA_ATHLETE_ID", "10148337")
        monkeypatch.delenv("STRAVA_EMAIL", raising=False)
        monkeypatch.delenv("STRAVA_PASSWORD", raising=False)

        credentials = StravaCredentials.from_environment()

        assert credentials.athlete_id == "10148337"
        assert credentials.email is None
        assert credentials.can_log_in_automatically is False
