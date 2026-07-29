"""
Role mapping config for the Strava gear pipeline.

Strava returns a flat list of bikes, but frontend/data/gear/bikes.json is a
keyed object — "mainBike" and "commuter" — because the gear widget looks each
role up by name. Strava has no concept of "my commuter", so the mapping from
gear name to role lives here.

This config also carries the fields Strava does not expose at all. Gear photos
are the notable one: Strava has no gear image, so any image URL is supplied by
hand and preserved across regenerations.

Editing this file is the expected way to add a bike or change a photo. The gear
names must match the names on Strava exactly (case-insensitively) — the pipeline
fails loudly listing your actual gear names when one does not match, rather than
writing a JSON file missing a key the widget requires.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BikeRoleConfig:
    """
    Maps one Strava bike onto one role key in bikes.json.

    Attributes:
        role_key:         Output key in bikes.json, read directly by gear.js.
        strava_gear_name: Bike name on Strava, matched case-insensitively.
        image:            Optional photo URL. Strava provides no gear images,
                          so this is curated by hand. Omitted from the output
                          when None, matching how mainBike has no image today.
    """
    role_key: str
    strava_gear_name: str
    image: str | None = None


BIKE_ROLE_CONFIGS: list[BikeRoleConfig] = [
    BikeRoleConfig(
        role_key="mainBike",
        strava_gear_name="Trek Emonda S",
    ),
    BikeRoleConfig(
        role_key="commuter",
        strava_gear_name="ROG Elite",
        image="https://www.njuskalo.hr/image-w920x690/cestovni-bicikli/rog-elite-slika-180379053.jpg",
    ),
]
