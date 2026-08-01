"""
Unit tests for parsing Strava's display strings.

This is the markup-independent half of the scraper: whatever Strava does to its
CSS, "1,002.7 km" still means 1002.7 kilometres. These tests stay valid across
site redesigns, unlike anything that depends on selectors.
"""

from datetime import date

import pytest

from hobbies.features.strava.text import (
    TextParseError,
    parse_activity_date,
    parse_count,
    parse_distance_metres,
    parse_duration_seconds,
)


class TestParseDistance:

    @pytest.mark.parametrize(
        "text, expected_metres",
        [
            ("1,002.7 km", 1002700),
            ("58.1 km", 58100),
            ("248 km", 248000),
            ("3,240.0 km", 3240000),
            ("14.2km", 14200),
            ("Distance 1,234.5 km", 1234500),
            ("800 m", 800),
        ],
    )
    def test_reads_kilometres_and_metres(self, text, expected_metres):
        assert parse_distance_metres(text) == pytest.approx(expected_metres)

    def test_converts_miles(self):
        """An account set to imperial units must still produce metres."""
        assert parse_distance_metres("10 mi") == pytest.approx(16093.44)

    def test_handles_thousands_separator_without_losing_magnitude(self):
        """A stripped comma must not turn 3,240 km into 3.24 km."""
        assert parse_distance_metres("3,240 km") == pytest.approx(3240000)

    def test_raises_on_unreadable_input(self):
        with pytest.raises(TextParseError):
            parse_distance_metres("no numbers here")


class TestParseDuration:

    @pytest.mark.parametrize(
        "text, expected_seconds",
        [
            ("1:11:23", 4283),
            ("42:38", 2558),
            ("12h 34m", 45240),
            ("1h 11m", 4260),
            ("34m", 2040),
            ("45s", 45),
            ("2h 4m 10s", 7450),
            ("116h 5m", 417900),
        ],
    )
    def test_reads_both_clock_and_unit_formats(self, text, expected_seconds):
        assert parse_duration_seconds(text) == expected_seconds

    def test_does_not_read_miles_as_minutes(self):
        """The 'm' in '10 mi' must not be mistaken for minutes."""
        with pytest.raises(TextParseError):
            parse_duration_seconds("10 mi")

    def test_raises_on_unreadable_input(self):
        with pytest.raises(TextParseError):
            parse_duration_seconds("whenever")


class TestParseCount:

    @pytest.mark.parametrize(
        "text, expected",
        [("12", 12), ("94 Rides", 94), ("1,204", 1204), ("Runs 4", 4)],
    )
    def test_reads_counts_with_or_without_labels(self, text, expected):
        assert parse_count(text) == expected

    def test_raises_on_unreadable_input(self):
        with pytest.raises(TextParseError):
            parse_count("several")


class TestParseActivityDate:

    REFERENCE = date(2026, 7, 29)

    def test_reads_absolute_date_with_year(self):
        assert parse_activity_date("Jul 26, 2026", today=self.REFERENCE) == "2026-07-26T00:00:00"

    def test_reads_full_month_name(self):
        assert parse_activity_date("July 4, 2026", today=self.REFERENCE) == "2026-07-04T00:00:00"

    def test_reads_day_first_format(self):
        assert parse_activity_date("26 Jul 2026", today=self.REFERENCE) == "2026-07-26T00:00:00"

    def test_assumes_reference_year_when_year_is_omitted(self):
        """Strava drops the year on recent activities."""
        assert parse_activity_date("Jul 26", today=self.REFERENCE) == "2026-07-26T00:00:00"

    def test_rolls_back_a_year_rather_than_dating_into_the_future(self):
        """A December date seen in July belongs to last year, not next."""
        assert parse_activity_date("Dec 20", today=self.REFERENCE) == "2025-12-20T00:00:00"

    def test_reads_relative_words(self):
        assert parse_activity_date("Today", today=self.REFERENCE) == "2026-07-29T00:00:00"
        assert parse_activity_date("Yesterday", today=self.REFERENCE) == "2026-07-28T00:00:00"

    def test_raises_on_unreadable_input(self):
        with pytest.raises(TextParseError):
            parse_activity_date("sometime last summer", today=self.REFERENCE)
