"""
Mappers from scraped Strava data to the frontend's JSON payloads.

Three outputs come from one scrape:

  bikes.json    keyed object of role → bike name and all-time kilometres
  cycling.json  year totals for rides, plus two activity groups
  running.json  year totals for runs, plus one activity group

Note on the cycling summary: Strava's year panel reports one total for *all*
rides, commutes included — there is no per-commute breakdown to scrape short of
aggregating every activity of the year. So the summary is sport-level and lives
at the top of the payload, while the tabs below filter only the activity lists.
"""

from hobbies.features.strava.config import (
    ACTIVITY_TARGETS,
    BIKE_ROLE_CONFIGS,
    ActivityTarget,
    BikeRoleConfig,
)
from hobbies.features.strava.constants import (
    METRES_PER_KILOMETRE,
    MILEAGE_DECIMAL_PLACES,
    STRAVA_ACTIVITY_URL_TEMPLATE,
)
from hobbies.features.strava.models import RawActivity, RawBike, RawSportTotals, ScrapedStrava
from hobbies.features.strava.selection import RIDE_SPORT_KEY, RUN_SPORT_KEY, select_for_targets

MILEAGE_FIELD = "milage"  # Misspelled in the data file and read verbatim by gear.js.

CYCLING_PERIOD_LABEL = "This Year"
RUNNING_PERIOD_LABEL = "This Year"

# Tab / count labels per group key.
GROUP_LABELS = {
    "rides": "Rides",
    "commutes": "Commutes",
    "runs": "Runs",
}

# Which group keys make up each sport's payload, in display order.
CYCLING_GROUP_KEYS = ["rides", "commutes"]
RUNNING_GROUP_KEYS = ["runs"]


class GearMappingError(ValueError):
    """A configured bike role matched no scraped bike."""


# ---------------------------------------------------------------------------
# bikes.json
# ---------------------------------------------------------------------------

def build_bikes_payload(
    bikes: list[RawBike],
    role_configs: list[BikeRoleConfig] | None = None,
) -> dict[str, dict]:
    """
    Assemble the keyed bikes payload from scraped gear and the role config.

    Raises:
        GearMappingError: If a configured role matches no bike. Omitting the key
                          would break gear.js, which indexes roles directly, so
                          this fails with the available names instead.
    """
    role_configs = BIKE_ROLE_CONFIGS if role_configs is None else role_configs

    return {
        config.role_key: _map_bike(_find_bike(bikes, config))
        for config in role_configs
    }


def _map_bike(bike: RawBike) -> dict:
    """Scraped name and all-time distance. Photos are static markup, not data."""
    return {
        "name": bike.name,
        MILEAGE_FIELD: _metres_to_kilometres(bike.distance_metres),
    }


def _find_bike(bikes: list[RawBike], config: BikeRoleConfig) -> RawBike:
    target_name = config.strava_gear_name.casefold()

    for bike in bikes:
        if bike.name.casefold() == target_name:
            return bike

    available = ", ".join(repr(bike.name) for bike in bikes) or "none"
    raise GearMappingError(
        f"No Strava bike named {config.strava_gear_name!r} for role "
        f"{config.role_key!r}. Scraped bikes: {available}. "
        f"Update strava_gear_name in hobbies/features/strava/config.py to match."
    )


# ---------------------------------------------------------------------------
# cycling.json / running.json
# ---------------------------------------------------------------------------

def build_cycling_payload(
    scraped: ScrapedStrava,
    targets: list[ActivityTarget] | None = None,
) -> dict:
    """Year ride totals plus rides and commutes activity groups."""
    return _build_sport_payload(
        scraped=scraped,
        sport="cycling",
        sport_key=RIDE_SPORT_KEY,
        period=CYCLING_PERIOD_LABEL,
        group_keys=CYCLING_GROUP_KEYS,
        count_label=GROUP_LABELS["rides"],
        targets=targets,
    )


def build_running_payload(
    scraped: ScrapedStrava,
    targets: list[ActivityTarget] | None = None,
) -> dict:
    """Year run totals plus a single runs activity group."""
    return _build_sport_payload(
        scraped=scraped,
        sport="running",
        sport_key=RUN_SPORT_KEY,
        period=RUNNING_PERIOD_LABEL,
        group_keys=RUNNING_GROUP_KEYS,
        count_label=GROUP_LABELS["runs"],
        targets=targets,
    )


def _build_sport_payload(
    scraped: ScrapedStrava,
    sport: str,
    sport_key: str,
    period: str,
    group_keys: list[str],
    count_label: str,
    targets: list[ActivityTarget] | None,
) -> dict:
    targets = ACTIVITY_TARGETS if targets is None else targets
    selected = select_for_targets(scraped.activities, targets)

    payload = {
        "sport": sport,
        "period": period,
        "countLabel": count_label,
        "summary": _map_totals(scraped.year_totals.get(sport_key)),
        "groups": [
            {
                "key": group_key,
                "label": GROUP_LABELS.get(group_key, group_key.title()),
                "activities": [
                    _map_activity(activity, scraped.route_maps)
                    for activity in selected.get(group_key, [])
                ],
            }
            for group_key in group_keys
        ],
    }

    all_time = scraped.all_time_totals.get(sport_key)
    if all_time is not None:
        payload["allTime"] = _map_totals(all_time)

    return payload


def _map_totals(totals: RawSportTotals | None) -> dict:
    """
    Map a totals panel to the summary schema.

    A missing panel yields zeroes with a null count rather than raising: the
    activity lists are still worth publishing, and the widget renders a dash for
    an absent count.
    """
    if totals is None:
        return {"distanceMetres": 0, "movingTimeSeconds": 0, "activityCount": None}

    return {
        "distanceMetres": round(totals.distance_metres),
        "movingTimeSeconds": totals.moving_time_seconds,
        "activityCount": totals.activity_count,
    }


def _map_activity(activity: RawActivity, route_maps: dict[str, str] | None = None) -> dict:
    """
    Map one activity, attaching its route image and its link to Strava.

    routeImage and stravaUrl are always present, as a value or null, so the widget
    can branch on them without treating a missing key differently from a missing
    value. An indoor ride has no GPS and so never gets a picture; an activity whose
    row rendered without a link has no id and so gets neither.
    """
    route_maps = route_maps or {}
    activity_id = activity.activity_id

    return {
        "name": activity.name,
        "startDateLocal": activity.start_date_local,
        "distanceMetres": round(activity.distance_metres),
        "movingTimeSeconds": activity.moving_time_seconds,
        "routeImage": route_maps.get(activity_id or ""),
        "stravaUrl": (
            STRAVA_ACTIVITY_URL_TEMPLATE.format(activity_id=activity_id)
            if activity_id
            else None
        ),
    }


def _metres_to_kilometres(distance_metres: float) -> float:
    return round(distance_metres / METRES_PER_KILOMETRE, MILEAGE_DECIMAL_PLACES)
