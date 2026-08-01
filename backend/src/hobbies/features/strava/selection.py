"""
Sport classification and target satisfaction.

The activity list mixes every sport the athlete records. These helpers decide
which sport a row belongs to, which rows satisfy which target, and — the point
of the exercise — when enough have been collected that paging can stop.

Anything that is neither a ride nor a run is ignored entirely.
"""

from hobbies.features.strava.config import ActivityTarget
from hobbies.features.strava.constants import RIDE_SPORT_KEYWORDS, RUN_SPORT_KEYWORDS
from hobbies.features.strava.models import RawActivity

RIDE_SPORT_KEY = "ride"
RUN_SPORT_KEY = "run"


def classify_sport(sport_text: str) -> str | None:
    """
    Map Strava's sport wording onto "ride", "run", or None to ignore it.

    Keyword matching covers the many variants ("Virtual Ride", "Gravel Ride",
    "Trail Run") without enumerating them. Runs are tested first because
    "run" is the more specific token — no cycling sport name contains it, while
    a name could in principle contain both.
    """
    lowered = (sport_text or "").lower()
    if not lowered:
        return None

    if any(keyword in lowered for keyword in RUN_SPORT_KEYWORDS):
        return RUN_SPORT_KEY
    if any(keyword in lowered for keyword in RIDE_SPORT_KEYWORDS):
        return RIDE_SPORT_KEY
    return None


def matches_target(activity: RawActivity, target: ActivityTarget) -> bool:
    """Whether an activity counts towards a target."""
    if classify_sport(activity.sport) != target.sport:
        return False
    if target.is_commute is None:
        return True
    return activity.is_commute == target.is_commute


def select_for_targets(
    activities: list[RawActivity],
    targets: list[ActivityTarget],
) -> dict[str, list[RawActivity]]:
    """
    Take the first N matching activities for each target.

    Args:
        activities: Scraped activities, newest first.
        targets:    What to collect.

    Returns:
        Target key → up to `count` activities, preserving input order.
    """
    return {
        target.key: [a for a in activities if matches_target(a, target)][: target.count]
        for target in targets
    }


def unmet_targets(
    activities: list[RawActivity],
    targets: list[ActivityTarget],
) -> list[ActivityTarget]:
    """Targets still short of their required count."""
    selected = select_for_targets(activities, targets)
    return [target for target in targets if len(selected[target.key]) < target.count]


def targets_satisfied(
    activities: list[RawActivity],
    targets: list[ActivityTarget],
) -> bool:
    """Whether every target has its full quota — the signal to stop paging."""
    return not unmet_targets(activities, targets)


def describe_unmet(unmet: list[ActivityTarget], activities: list[RawActivity]) -> str:
    """Human-readable shortfall summary, for warning after paging gives up."""
    selected = select_for_targets(activities, unmet)
    return ", ".join(
        f"{target.key}: {len(selected[target.key])}/{target.count}" for target in unmet
    )
