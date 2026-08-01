"""
Unit tests for sport classification and target satisfaction.

This logic decides when paging can stop, so getting it wrong means either
walking the whole activity history or publishing short lists. It is pure
functions over data, independent of any markup.
"""

import pytest

from hobbies.features.strava.config import ActivityTarget
from hobbies.features.strava.models import RawActivity
from hobbies.features.strava.selection import (
    classify_sport,
    select_for_targets,
    targets_satisfied,
    unmet_targets,
)

TARGETS = [
    ActivityTarget(key="rides", sport="ride", is_commute=False, count=2),
    ActivityTarget(key="commutes", sport="ride", is_commute=True, count=2),
    ActivityTarget(key="runs", sport="run", is_commute=None, count=2),
]


def activity(name: str, sport: str, is_commute: bool = False) -> RawActivity:
    return RawActivity(
        name=name,
        start_date_local="2026-07-26T00:00:00",
        distance_metres=10000,
        moving_time_seconds=1800,
        sport=sport,
        is_commute=is_commute,
    )


class TestClassifySport:

    @pytest.mark.parametrize(
        "sport_text",
        ["Ride", "ride", "Virtual Ride", "Gravel Ride", "Mountain Bike Ride", "E-Bike Ride", "cycling"],
    )
    def test_recognises_cycling_variants(self, sport_text):
        assert classify_sport(sport_text) == "ride"

    @pytest.mark.parametrize("sport_text", ["Run", "run", "Trail Run", "Virtual Run"])
    def test_recognises_running_variants(self, sport_text):
        assert classify_sport(sport_text) == "run"

    @pytest.mark.parametrize(
        "sport_text", ["Swim", "Walk", "Hike", "Weight Training", "Rowing", "", "Yoga"]
    )
    def test_ignores_everything_else(self, sport_text):
        """Anything that is not a ride or a run must be dropped entirely."""
        assert classify_sport(sport_text) is None


class TestSelectForTargets:

    def test_splits_rides_from_commutes(self):
        activities = [
            activity("Weekend Loop", "ride"),
            activity("Commute home", "ride", is_commute=True),
            activity("Hill Repeats", "ride"),
            activity("Commute to work", "ride", is_commute=True),
        ]

        selected = select_for_targets(activities, TARGETS)

        assert [a.name for a in selected["rides"]] == ["Weekend Loop", "Hill Repeats"]
        assert [a.name for a in selected["commutes"]] == ["Commute home", "Commute to work"]

    def test_takes_only_the_required_count(self):
        activities = [activity(f"Run {index}", "run") for index in range(10)]

        selected = select_for_targets(activities, TARGETS)

        assert len(selected["runs"]) == 2

    def test_preserves_input_order(self):
        """Rows arrive newest first and that ordering must survive selection."""
        activities = [activity("newest", "run"), activity("older", "run")]

        selected = select_for_targets(activities, TARGETS)

        assert [a.name for a in selected["runs"]] == ["newest", "older"]

    def test_excludes_other_sports_from_every_group(self):
        activities = [activity("Pool", "Swim"), activity("Stroll", "Walk")]

        selected = select_for_targets(activities, TARGETS)

        assert selected == {"rides": [], "commutes": [], "runs": []}


class TestTargetSatisfaction:

    def _full_set(self) -> list[RawActivity]:
        return [
            activity("Ride A", "ride"),
            activity("Ride B", "ride"),
            activity("Commute A", "ride", is_commute=True),
            activity("Commute B", "ride", is_commute=True),
            activity("Run A", "run"),
            activity("Run B", "run"),
        ]

    def test_satisfied_only_when_every_target_is_full(self):
        assert targets_satisfied(self._full_set(), TARGETS) is True

    def test_not_satisfied_when_one_group_is_short(self):
        """A full ride quota must not mask an empty commute quota."""
        activities = [a for a in self._full_set() if not a.is_commute]

        assert targets_satisfied(activities, TARGETS) is False
        assert [t.key for t in unmet_targets(activities, TARGETS)] == ["commutes"]

    def test_reports_every_unmet_target(self):
        assert len(unmet_targets([], TARGETS)) == 3

    def test_extra_activities_do_not_break_satisfaction(self):
        activities = self._full_set() + [activity("Ride C", "ride")]

        assert targets_satisfied(activities, TARGETS) is True
