"""
Browser tests for the in-page extraction snippets.

These run the real JavaScript against local mock pages. What they establish:

  * the snippets are syntactically valid and return the expected shapes
  * sections are found via visible text, not class names
  * the sport switcher is matched by icon attributes, with no text to go on
  * an inert control is detected as such, instead of silently leaving one sport's
    totals showing while they get filed under another

What they do NOT establish is that any of this works against Strava — the mocks
are intentionally not copies of Strava's markup. Their value is proving the
extractors do not depend on details they should not depend on.

Skipped when Playwright or its browser binary is unavailable.
"""

from pathlib import Path

import pytest

from hobbies.features.strava import extractors
from hobbies.features.strava.constants import (
    ALL_TIME_SECTION_HEADINGS,
    GEAR_SECTION_HEADINGS,
    SPORT_SELECTOR_ATTRIBUTES,
    SPORT_SELECTOR_KEYWORDS,
    YEAR_SECTION_HEADINGS,
)
from hobbies.features.strava.page_parser import (
    parse_activity_rows,
    parse_bikes,
    parse_sport_totals,
)
from hobbies.features.strava.selection import classify_sport

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PROFILE_MOCK = FIXTURES_DIR / "strava_profile_mock.html"
TRAINING_MOCK = FIXTURES_DIR / "strava_training_mock.html"

SETTLE_MS = 150


@pytest.fixture(scope="module")
def browser():
    """A headless browser, or skip the module if one is not available."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("Playwright is not installed")

    playwright = sync_playwright().start()
    try:
        instance = playwright.chromium.launch()
    except Exception as error:  # noqa: BLE001 - any launch failure means skip
        playwright.stop()
        pytest.skip(f"Chromium unavailable: {error}")

    yield instance
    instance.close()
    playwright.stop()


@pytest.fixture
def profile_page(browser):
    page = browser.new_page()
    page.goto(PROFILE_MOCK.as_uri())
    yield page
    page.close()


@pytest.fixture
def training_page(browser):
    page = browser.new_page()
    page.goto(TRAINING_MOCK.as_uri())
    yield page
    page.close()


def _click_sport(page, sport_key: str):
    return page.evaluate(
        extractors.CLICK_SPORT_CONTROL,
        {
            "keywords": SPORT_SELECTOR_KEYWORDS[sport_key],
            "attributes": SPORT_SELECTOR_ATTRIBUTES,
        },
    )


def _year_text(page) -> str:
    return page.evaluate(extractors.SECTION_TEXT_BY_HEADING, YEAR_SECTION_HEADINGS)


class TestSectionLocation:

    def test_finds_the_gear_section_by_its_heading(self, profile_page):
        text = profile_page.evaluate(
            extractors.SECTION_TEXT_BY_HEADING, GEAR_SECTION_HEADINGS
        )

        bikes = {bike.name: bike.distance_metres for bike in parse_bikes(text)}
        assert bikes["Trek Emonda S"] == pytest.approx(1002700)
        assert bikes["ROG Elite"] == pytest.approx(795000)

    def test_finds_the_year_panel_and_reads_its_totals(self, profile_page):
        totals = parse_sport_totals(_year_text(profile_page))

        assert totals.distance_metres == pytest.approx(3240000)
        assert totals.moving_time_seconds == 417900
        assert totals.activity_count == 182

    def test_distinguishes_the_all_time_panel_from_the_year_panel(self, profile_page):
        all_time = parse_sport_totals(
            profile_page.evaluate(
                extractors.SECTION_TEXT_BY_HEADING, ALL_TIME_SECTION_HEADINGS
            )
        )

        assert all_time.distance_metres == pytest.approx(41882000)
        assert all_time.activity_count == 1204

    def test_returns_none_when_no_heading_matches(self, profile_page):
        assert profile_page.evaluate(
            extractors.SECTION_TEXT_BY_HEADING, ["nonexistent heading"]
        ) is None


class TestSportSwitcher:

    def test_clicks_the_bike_icon_with_no_text_to_match_on(self, profile_page):
        """The control is an icon-only button; matching relies on aria-label/href."""
        result = _click_sport(profile_page, "ride")

        assert result is not None
        assert result["tag"] == "button"

    def test_switching_to_running_changes_the_panel(self, profile_page):
        before = _year_text(profile_page)

        assert _click_sport(profile_page, "run") is not None
        profile_page.wait_for_timeout(SETTLE_MS)
        after = _year_text(profile_page)

        assert after != before
        assert parse_sport_totals(after).distance_metres == pytest.approx(318000)
        assert parse_sport_totals(after).activity_count == 41

    def test_switching_back_restores_the_cycling_panel(self, profile_page):
        _click_sport(profile_page, "run")
        profile_page.wait_for_timeout(SETTLE_MS)
        _click_sport(profile_page, "ride")
        profile_page.wait_for_timeout(SETTLE_MS)

        assert parse_sport_totals(_year_text(profile_page)).activity_count == 182

    def test_an_inert_control_leaves_the_panel_identical(self, profile_page):
        """
        The mock's Swim button is clickable but changes nothing — the exact failure
        the scraper guards against, since unchanged totals would otherwise be
        recorded under the wrong sport.
        """
        before = _year_text(profile_page)

        clicked = profile_page.evaluate(
            extractors.CLICK_SPORT_CONTROL,
            {"keywords": ["swim"], "attributes": SPORT_SELECTOR_ATTRIBUTES},
        )
        profile_page.wait_for_timeout(SETTLE_MS)

        assert clicked is not None, "the control was found and clicked"
        assert _year_text(profile_page) == before, "but nothing changed — detectable"

    def test_reports_none_when_no_control_matches(self, profile_page):
        assert profile_page.evaluate(
            extractors.CLICK_SPORT_CONTROL,
            {"keywords": ["kayaking"], "attributes": SPORT_SELECTOR_ATTRIBUTES},
        ) is None


class TestActivityRows:

    def test_extracts_every_activity_row(self, training_page):
        rows = training_page.evaluate(extractors.ACTIVITY_ROWS)

        # Six activities plus the header row, which the parser discards.
        assert len(rows) >= 6

    def test_parses_rows_into_activities(self, training_page):
        rows = training_page.evaluate(extractors.ACTIVITY_ROWS)

        activities = parse_activity_rows(rows)
        names = [activity.name for activity in activities]

        assert "Weekend Loop" in names
        assert "Long Run" in names

    def test_discards_the_header_row(self, training_page):
        rows = training_page.evaluate(extractors.ACTIVITY_ROWS)

        names = [activity.name for activity in parse_activity_rows(rows)]
        assert "Date" not in names

    def test_detects_a_commute_from_its_badge_when_the_name_gives_nothing(self, training_page):
        rows = training_page.evaluate(extractors.ACTIVITY_ROWS)

        by_name = {a.name: a for a in parse_activity_rows(rows)}
        assert by_name["Evening pootle"].is_commute is True

    def test_detects_a_commute_from_its_name_when_there_is_no_badge(self, training_page):
        rows = training_page.evaluate(extractors.ACTIVITY_ROWS)

        by_name = {a.name: a for a in parse_activity_rows(rows)}
        assert by_name["Commute to work"].is_commute is True

    def test_leaves_ordinary_rides_unflagged(self, training_page):
        rows = training_page.evaluate(extractors.ACTIVITY_ROWS)

        by_name = {a.name: a for a in parse_activity_rows(rows)}
        assert by_name["Weekend Loop"].is_commute is False

    def test_reads_distance_and_duration_correctly(self, training_page):
        rows = training_page.evaluate(extractors.ACTIVITY_ROWS)

        by_name = {a.name: a for a in parse_activity_rows(rows)}
        weekend_loop = by_name["Weekend Loop"]
        assert weekend_loop.distance_metres == pytest.approx(58100)
        assert weekend_loop.moving_time_seconds == 7450

    def test_swim_is_classified_as_neither_sport(self, training_page):
        """Non-ride, non-run activities must drop out entirely."""
        rows = training_page.evaluate(extractors.ACTIVITY_ROWS)

        by_name = {a.name: a for a in parse_activity_rows(rows)}
        assert classify_sport(by_name["Pool session"].sport) is None
