"""
Data models for the Strava gear pipeline.

RawGearItem holds values as Strava returns them — notably distance in metres,
before conversion to the kilometres that bikes.json records.
"""

from dataclasses import dataclass


@dataclass
class RawGearItem:
    """A single bike as returned in the athlete response's "bikes" array."""
    gear_id: str            # Strava gear id, e.g. "b12345678987655"
    name: str               # Athlete-assigned name, e.g. "Trek Emonda S"
    distance_metres: float  # Lifetime distance logged against this gear
    is_primary: bool        # Whether Strava marks this as the default bike
