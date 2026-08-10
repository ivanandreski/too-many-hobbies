"""
Unit tests for credential handling.

This file also held tests for an identical-panel guard, which existed because the
totals were read by clicking a sport icon and could silently keep showing the
previous sport. Panels are now addressed by index, so one sport's figures cannot
be attributed to another and the guard was removed along with the clicking.
"""

from hobbies.features.strava.scraper import StravaCredentials

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
