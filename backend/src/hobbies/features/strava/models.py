"""
Data models for the Strava scraping pipelines.

The Raw* types hold values already converted out of display text (metres,
seconds) but before any grouping, filtering or role assignment is applied.
ScrapedStrava is the whole harvest from one browser session — one login, one
pass over the pages, everything three output files need.
"""

from dataclasses import dataclass, field


@dataclass
class RawBike:
    """A bike from the profile's gear section, with its all-time distance."""
    name: str
    distance_metres: float


@dataclass
class RawSportTotals:
    """
    Aggregate totals for one sport over one period.

    count is optional: Strava's totals panels do not always show an activity
    count, and a missing count must not be silently reported as zero.
    """
    distance_metres: float
    moving_time_seconds: int
    activity_count: int | None = None


@dataclass
class RawActivity:
    """
    One row from the paginated activity list.

    activity_id is Strava's own numeric id, taken from the row's link. It is
    optional because a row that renders without a link is still worth publishing
    as text; it just cannot have a route map captured for it.
    """
    name: str
    start_date_local: str      # local ISO timestamp, midnight precision
    distance_metres: float
    moving_time_seconds: int
    sport: str                 # Strava's displayed sport, e.g. "Ride", "Trail Run"
    is_commute: bool
    activity_id: str | None = None


@dataclass
class ScrapedStrava:
    """
    Everything one scraping run collected.

    Both totals dicts are keyed by the sport keys used in constants
    (SPORT_SELECTOR_KEYWORDS): "ride" and "run". A key is absent when that
    sport's panel could not be read, which callers must handle rather than
    treating as zero.

    route_maps maps an activity id to the site-relative path of its captured
    route image. Absent keys are the normal case for anything not selected for
    publication, and for a capture that failed.
    """
    bikes: list[RawBike] = field(default_factory=list)
    year_totals: dict[str, RawSportTotals] = field(default_factory=dict)
    all_time_totals: dict[str, RawSportTotals] = field(default_factory=dict)
    activities: list[RawActivity] = field(default_factory=list)
    route_maps: dict[str, str] = field(default_factory=dict)
    pages_read: int = 0
