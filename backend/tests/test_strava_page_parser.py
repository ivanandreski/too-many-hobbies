"""
Unit tests for parsing the text captured from Strava pages.

Important caveat: the sample strings below are *representative*, not verified.
They were written without a logged-in view of Strava, so the real captured text
may be laid out differently. What these tests pin down is the parser's handling
of the layout *patterns* it has to cope with — label and value on one line, on
two lines, extra stats interleaved, mixed units — which is the part that has to
be right regardless of exact wording.

Run `python -m hobbies.features.strava.probe` against a real session to get the
actual text, then add it here as a regression case.
"""

import pytest

from hobbies.features.strava.selection import classify_sport
from hobbies.features.strava.page_parser import (
    PageParseError,
    parse_activity_rows,
    parse_bikes,
    parse_sport_totals,
)

# Label and value on the same line.
INLINE_TOTALS = """\
This Year
Distance 3,240.0 km
Time 116h 5m
Elev Gain 34,120 m
Rides 94
"""

# Label and value on consecutive lines — the other layout Strava has used.
STACKED_TOTALS = """\
This Year
Distance
3,240.0 km
Time
116h 5m
Rides
94
"""

TOTALS_WITHOUT_COUNT = """\
All-Time
Distance 41,882.0 km
Time 1,402h 11m
"""


class TestParseSportTotals:

    @pytest.mark.parametrize("section_text", [INLINE_TOTALS, STACKED_TOTALS])
    def test_reads_both_layouts_identically(self, section_text):
        totals = parse_sport_totals(section_text)

        assert totals.distance_metres == pytest.approx(3240000)
        assert totals.moving_time_seconds == 417900
        assert totals.activity_count == 94

    def test_does_not_mistake_elevation_for_distance(self):
        """Elevation is also a distance-with-unit; the label must disambiguate."""
        totals = parse_sport_totals(INLINE_TOTALS)

        assert totals.distance_metres == pytest.approx(3240000)

    def test_reports_missing_count_as_none_not_zero(self):
        """A panel without a count must not claim zero activities."""
        totals = parse_sport_totals(TOTALS_WITHOUT_COUNT)

        assert totals.distance_metres == pytest.approx(41882000)
        assert totals.activity_count is None

    def test_raises_when_no_distance_present(self):
        """
        Distance is the one field every output needs. Its absence means the wrong
        region was captured, and writing zeroes would wipe good site data.
        """
        with pytest.raises(PageParseError, match="No distance"):
            parse_sport_totals("Following\n12\nFollowers\n34\n")


class TestParseBikes:

    GEAR_SECTION = """\
Gear
Trek Emonda S 1,002.7 km
ROG Elite 795.0 km
Shoes
Adidas Adizero 412.5 km
"""

    def test_reads_each_line_with_a_distance(self):
        bikes = parse_bikes(self.GEAR_SECTION)

        names = [bike.name for bike in bikes]
        assert "Trek Emonda S" in names
        assert "ROG Elite" in names

    def test_converts_distances_to_metres(self):
        bikes = {bike.name: bike.distance_metres for bike in parse_bikes(self.GEAR_SECTION)}

        assert bikes["Trek Emonda S"] == pytest.approx(1002700)
        assert bikes["ROG Elite"] == pytest.approx(795000)

    def test_skips_heading_lines_without_a_distance(self):
        bikes = parse_bikes(self.GEAR_SECTION)

        assert all(bike.name not in ("Gear", "Shoes") for bike in bikes)

    def test_returns_empty_for_text_with_no_distances(self):
        assert parse_bikes("Gear\nNo bikes yet\n") == []


class TestParseActivityRows:

    def _row(self, text: str, commute_markup: bool = False) -> dict:
        return {"text": text, "isCommute": commute_markup, "activityUrl": None}

    def test_reads_name_date_distance_and_time(self):
        rows = [self._row("Weekend Loop\nJul 26, 2026\nRide\n58.1 km\n2:04:10")]

        activities = parse_activity_rows(rows)

        assert len(activities) == 1
        activity = activities[0]
        assert activity.name == "Weekend Loop"
        assert activity.start_date_local == "2026-07-26T00:00:00"
        assert activity.distance_metres == pytest.approx(58100)
        assert activity.moving_time_seconds == 7450

    def test_trusts_a_checked_commute_control_over_the_name(self):
        """A genuinely checked commute control wins even when the name says nothing."""
        rows = [self._row("Evening pootle\nJul 26, 2026\nRide\n14.0 km\n31:40", True)]

        assert parse_activity_rows(rows)[0].is_commute is True

    def test_falls_back_to_name_when_markup_has_no_flag(self):
        """Strava's list may not expose the flag; the name is the backstop."""
        rows = [self._row("Commute to work\nJul 28, 2026\nRide\n14.2 km\n33:01")]

        assert parse_activity_rows(rows)[0].is_commute is True

    def test_leaves_ordinary_rides_unflagged(self):
        rows = [self._row("Hill Repeats\nJul 19, 2026\nRide\n41.8 km\n1:38:40")]

        assert parse_activity_rows(rows)[0].is_commute is False

    def test_identifies_sport_from_row_text(self):
        rows = [
            self._row("Morning Ride\nJul 22, 2026\nRide\n32.4 km\n1:11:23"),
            self._row("Long Run\nJul 20, 2026\nRun\n12.1 km\n1:06:33"),
        ]

        activities = parse_activity_rows(rows)

        # Returned verbatim from the row's sport cell; classify_sport folds case.
        assert activities[0].sport == "Ride"
        assert activities[1].sport == "Run"
        assert classify_sport(activities[0].sport) == "ride"
        assert classify_sport(activities[1].sport) == "run"

    def test_skips_rows_without_a_distance_rather_than_failing(self):
        """Header and spacer rows come through the same selector."""
        rows = [
            self._row("Date\nActivity\nDistance"),
            self._row("Morning Ride\nJul 22, 2026\nRide\n32.4 km\n1:11:23"),
        ]

        assert len(parse_activity_rows(rows)) == 1

    def test_skips_rows_without_a_readable_date(self):
        rows = [self._row("Mystery Ride\nRide\n32.4 km\n1:11:23")]

        assert parse_activity_rows(rows) == []

    def test_does_not_read_the_distance_as_the_duration(self):
        """'58.1 km' must not be consumed by the duration pattern."""
        rows = [self._row("Weekend Loop\nJul 26, 2026\nRide\n58.1 km\n2:04:10")]

        assert parse_activity_rows(rows)[0].moving_time_seconds == 7450

    def test_reads_tab_separated_table_cells(self):
        """
        innerText joins table cells with tabs, not newlines. Splitting on newlines
        alone collapsed the whole row into one string and titled the activity with
        the entire row's text.
        """
        rows = [self._row("Jul 26, 2026\tWeekend Loop\tRide\t58.1 km\t2:04:10")]

        activities = parse_activity_rows(rows)

        assert len(activities) == 1
        assert activities[0].name == "Weekend Loop"
        assert activities[0].distance_metres == pytest.approx(58100)
        assert activities[0].moving_time_seconds == 7450

    def test_skips_the_sport_type_cell_when_choosing_a_title(self):
        """A leading type cell must not become the activity name."""
        rows = [self._row("Ride\tJul 26, 2026\tWeekend Loop\t58.1 km\t2:04:10")]

        assert parse_activity_rows(rows)[0].name == "Weekend Loop"

    def test_keeps_a_title_that_merely_contains_a_sport_word(self):
        """'Morning Ride' is a title, not a type cell — only exact matches skip."""
        rows = [self._row("Jul 22, 2026\tMorning Ride\tRide\t32.4 km\t1:11:23")]

        assert parse_activity_rows(rows)[0].name == "Morning Ride"


class TestRealActivityRowFormat:
    """
    Regression tests taken from the live training page rather than guessed at.

    A real row's innerText is tab separated in this order:
        Sport | Date | Title | Time | Distance | Elevation | controls
    e.g. 'Ride\tMon, 8/10/2026\tMorning Ride\t59:28\t28.46 km\t250 m\t\t\nEdit Delete Share'

    Every one of these cases was a live failure before the parser worked on cells.
    """

    REAL_ROW = "Ride\tMon, 8/10/2026\tMorning Ride\t59:28\t28.46 km\t250 m\t\t\nEdit Delete Share"

    def _parse(self, text: str):
        return parse_activity_rows([{"text": text, "isCommute": False, "activityUrl": None}])

    def test_parses_a_real_row(self):
        activities = self._parse(self.REAL_ROW)

        assert len(activities) == 1, "the whole row was dropped"
        activity = activities[0]
        assert activity.name == "Morning Ride"
        assert activity.start_date_local == "2026-08-10T00:00:00"
        assert activity.distance_metres == pytest.approx(28460)
        assert activity.moving_time_seconds == 3568

    def test_does_not_read_elevation_as_the_duration(self):
        """
        '250 m' sits after the distance. Scanning forward for a duration matched it
        as 250 minutes — 15,000 seconds instead of the real 3,568.
        """
        assert self._parse(self.REAL_ROW)[0].moving_time_seconds == 3568

    def test_does_not_use_the_controls_cell_as_the_title(self):
        assert "Edit" not in self._parse(self.REAL_ROW)[0].name

    def test_reads_a_commute_from_its_name(self):
        row = "Ride\tThu, 8/7/2026\tMorning Commute\t21:28\t7.55 km\t60 m\t\t\nEdit Delete Share"

        activity = self._parse(row)[0]
        assert activity.name == "Morning Commute"
        assert activity.is_commute is True

    def test_ignores_the_hidden_edit_form_rows(self):
        """Each activity ships a hidden edit form that matches the same selector."""
        form_row = "Title\n\n\n\nSport\nRide\nRun\nHike\nSwim\nWalk\nTrail Run"

        assert self._parse(form_row) == []
