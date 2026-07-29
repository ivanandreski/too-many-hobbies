"""
Strava gear mapper.

Maps RawGearItems onto the keyed object used in frontend/data/gear/bikes.json,
assigning each configured role its matching bike.

Bike entry schema:
{
    "name": str,      # bike name as it appears on Strava
    "milage": float,  # kilometres ridden, one decimal place
    "image": str      # optional; only present when config supplies one
}

Note the output key is "milage", not "mileage". It is misspelled in the existing
data file and read verbatim by frontend/widgets/gear/gear.js, so the typo is
load-bearing until both sides change together.
"""

from hobbies.features.gear.config import BIKE_ROLE_CONFIGS, BikeRoleConfig
from hobbies.features.gear.constants import (
    METRES_PER_KILOMETRE,
    MILEAGE_DECIMAL_PLACES,
)
from hobbies.features.gear.models import RawGearItem

MILEAGE_FIELD = "milage"


def build_bikes_payload(
    raw_items: list[RawGearItem],
    role_configs: list[BikeRoleConfig] | None = None,
) -> dict[str, dict]:
    """
    Assemble the keyed bikes payload from Strava gear and the role config.

    Args:
        raw_items:    Bikes scraped from the athlete response.
        role_configs: Role mapping to apply. Defaults to BIKE_ROLE_CONFIGS.

    Returns:
        Dict mapping each configured role key to its bike entry, in config order.

    Raises:
        ValueError: If a configured role matches no Strava bike. Omitting the key
                    would break the widget, which indexes roles directly, so this
                    fails with the list of available names instead.
    """
    role_configs = BIKE_ROLE_CONFIGS if role_configs is None else role_configs

    return {
        config.role_key: map_raw_gear_item_to_dto(_find_matching_bike(raw_items, config), config)
        for config in role_configs
    }


def map_raw_gear_item_to_dto(raw_item: RawGearItem, config: BikeRoleConfig) -> dict:
    """
    Map a RawGearItem into a bike entry dict.

    Converts Strava's metres into the kilometres bikes.json records, and layers
    on the hand-curated image when the config supplies one.
    """
    entry = {
        "name": raw_item.name,
        MILEAGE_FIELD: _metres_to_kilometres(raw_item.distance_metres),
    }

    if config.image:
        entry["image"] = config.image

    return entry


def _metres_to_kilometres(distance_metres: float) -> float:
    """Convert Strava's metres to kilometres, rounded as bikes.json records it."""
    return round(distance_metres / METRES_PER_KILOMETRE, MILEAGE_DECIMAL_PLACES)


def _find_matching_bike(raw_items: list[RawGearItem], config: BikeRoleConfig) -> RawGearItem:
    """Find the Strava bike named by a role config, matching case-insensitively."""
    target_name = config.strava_gear_name.casefold()

    for raw_item in raw_items:
        if raw_item.name.casefold() == target_name:
            return raw_item

    available_names = ", ".join(repr(item.name) for item in raw_items) or "none"
    raise ValueError(
        f"No Strava bike named {config.strava_gear_name!r} for role "
        f"{config.role_key!r}. Your bikes on Strava are: {available_names}. "
        f"Update strava_gear_name in hobbies/features/gear/config.py to match."
    )
