"""
Strava athlete response parser.

Pulls the "bikes" array out of the athlete JSON and turns each entry into a
RawGearItem. Shoes are ignored — this feature only feeds the bikes widget.
"""

import json

from hobbies.features.gear.constants import ATHLETE_BIKES_FIELD, STRAVA_REQUIRED_SCOPE
from hobbies.features.gear.models import RawGearItem


def extract_raw_gear_items(athlete_json: str) -> list[RawGearItem]:
    """
    Parse a Strava athlete response and return one RawGearItem per bike.

    Args:
        athlete_json: Raw JSON body from GET /api/v3/athlete.

    Returns:
        List of RawGearItem, in the order Strava returned them.

    Raises:
        ValueError: If the response carries no "bikes" field. Strava omits it
                    from the summary athlete representation, so the overwhelmingly
                    likely cause is a token without the required scope — a much
                    more useful message than "0 bikes found".
    """
    athlete = json.loads(athlete_json)

    if not isinstance(athlete, dict):
        raise ValueError(f"Expected a JSON object from the athlete endpoint, got {type(athlete).__name__}")

    if ATHLETE_BIKES_FIELD not in athlete:
        raise ValueError(
            f"Athlete response has no '{ATHLETE_BIKES_FIELD}' field. Strava only "
            f"includes gear on the detailed athlete representation, so the access "
            f"token is probably missing the '{STRAVA_REQUIRED_SCOPE}' scope. "
            f"Re-run the authorize step to grant it."
        )

    return [_to_raw_gear_item(bike) for bike in athlete[ATHLETE_BIKES_FIELD]]


def _to_raw_gear_item(bike: dict) -> RawGearItem:
    """Convert one entry of the athlete's "bikes" array into a RawGearItem."""
    return RawGearItem(
        gear_id=bike.get("id", ""),
        name=bike.get("name", ""),
        distance_metres=float(bike.get("distance") or 0.0),
        is_primary=bool(bike.get("primary", False)),
    )
