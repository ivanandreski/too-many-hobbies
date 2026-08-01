"""
Tunable configuration for the Strava scraping pipelines.

Two kinds of thing live here: how many activities each output needs (which
decides when paging can stop), and the bike-name-to-role mapping plus the
hand-curated fields Strava does not expose, such as gear photos.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BikeRoleConfig:
    """
    Maps one Strava bike onto one role key in bikes.json.

    Bike photos are deliberately not here. Strava exposes no gear images, and the
    photos never change, so they live in components/gear.html as plain markup
    rather than being round-tripped through generated data.

    Attributes:
        role_key:         Output key in bikes.json, read directly by gear.js.
        strava_gear_name: Bike name on Strava, matched case-insensitively.
    """
    role_key: str
    strava_gear_name: str


BIKE_ROLE_CONFIGS: list[BikeRoleConfig] = [
    BikeRoleConfig(role_key="mainBike", strava_gear_name="Trek Emonda S"),
    BikeRoleConfig(role_key="commuter", strava_gear_name="ROG Elite"),
]


@dataclass(frozen=True)
class ActivityTarget:
    """
    How many activities of one kind to collect before paging can stop.

    Attributes:
        key:        Identifier used by the mappers, e.g. "commutes".
        sport:      Sport key to match, "ride" or "run".
        is_commute: Required commute flag, or None to accept either.
        count:      How many are needed.
    """
    key: str
    sport: str
    is_commute: bool | None
    count: int


# Paging stops as soon as every target below is satisfied.
ACTIVITY_TARGETS: list[ActivityTarget] = [
    ActivityTarget(key="rides", sport="ride", is_commute=False, count=5),
    ActivityTarget(key="commutes", sport="ride", is_commute=True, count=5),
    ActivityTarget(key="runs", sport="run", is_commute=None, count=5),
]

# Safety net: a hard cap so a markup change that stops the parser from
# recognising rows cannot walk the entire activity history.
MAX_TRAINING_PAGES = 12

# Fallback commute detection. Strava's activity list may not expose the commute
# flag as markup; when it does not, an activity whose name matches this is
# treated as a commute. Case-insensitive substring match.
COMMUTE_NAME_PATTERNS = ["commute", "to work", "from work", "work ride"]
