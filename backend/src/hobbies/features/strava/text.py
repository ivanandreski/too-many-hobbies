"""
Parsers for the display strings Strava renders.

Scraping yields formatted text, not numbers: "1,002.7 km", "12h 34m", "5 Rides",
"Jul 26, 2026". These helpers turn that into the metres / seconds / ISO
timestamps the JSON schema stores. All of this is markup-independent, so it is
the part of the scraper that stays correct when Strava restyles a page.
"""

import re
from datetime import date, datetime, timedelta

from hobbies.features.strava.constants import METRES_PER_KILOMETRE, METRES_PER_MILE

# "1,002.7 km" / "12.4 mi" / "800m". Thousands separators optional.
_DISTANCE_PATTERN = re.compile(
    r"(?P<value>\d[\d,\s]*(?:\.\d+)?)\s*(?P<unit>km|kilometers?|mi|miles?|m\b)?",
    re.IGNORECASE,
)

# "12h 34m 56s", "1h 11m", "34m", "45s"
_HOURS_MINUTES_PATTERN = re.compile(
    r"(?:(?P<hours>\d+)\s*h)?\s*(?:(?P<minutes>\d+)\s*m(?!i))?\s*(?:(?P<seconds>\d+)\s*s)?",
    re.IGNORECASE,
)

# "1:11:23" or "42:38"
_CLOCK_PATTERN = re.compile(r"^(?:(?P<hours>\d+):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{2})$")

_INTEGER_PATTERN = re.compile(r"\d[\d,\s]*")

# "Jul 26, 2026" / "26 Jul 2026" / "July 26, 2026"
_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class TextParseError(ValueError):
    """A display string did not look like anything we know how to read."""


def parse_distance_metres(text: str) -> float:
    """
    Read a distance and return metres.

    Handles kilometres, miles and bare metres, plus thousands separators, so the
    result is correct whichever unit preference the account uses.

        "1,002.7 km" -> 1002700.0
        "12.4 mi"    -> 19955.9
    """
    if not text:
        raise TextParseError("Empty distance string")

    match = _DISTANCE_PATTERN.search(text)
    if not match or not match.group("value").strip():
        raise TextParseError(f"Could not read a distance from {text!r}")

    value = float(_strip_separators(match.group("value")))
    unit = (match.group("unit") or "km").lower()

    if unit.startswith("mi"):
        return value * METRES_PER_MILE
    if unit == "m":
        return value
    return value * METRES_PER_KILOMETRE


def parse_duration_seconds(text: str) -> int:
    """
    Read a duration and return whole seconds.

        "12h 34m"  -> 45240
        "1:11:23"  -> 4283
        "42:38"    -> 2558
    """
    if not text:
        raise TextParseError("Empty duration string")

    stripped = text.strip()

    clock_match = _CLOCK_PATTERN.match(stripped)
    if clock_match:
        return _to_seconds(
            clock_match.group("hours"),
            clock_match.group("minutes"),
            clock_match.group("seconds"),
        )

    unit_match = _HOURS_MINUTES_PATTERN.search(stripped)
    if unit_match and any(unit_match.group(part) for part in ("hours", "minutes", "seconds")):
        return _to_seconds(
            unit_match.group("hours"),
            unit_match.group("minutes"),
            unit_match.group("seconds"),
        )

    raise TextParseError(f"Could not read a duration from {text!r}")


def parse_count(text: str) -> int:
    """
    Read an activity count, ignoring any label beside it.

        "12"       -> 12
        "94 Rides" -> 94
        "1,204"    -> 1204
    """
    if not text:
        raise TextParseError("Empty count string")

    match = _INTEGER_PATTERN.search(text)
    if not match:
        raise TextParseError(f"Could not read a count from {text!r}")
    return int(_strip_separators(match.group()))


def parse_activity_date(text: str, today: date | None = None) -> str:
    """
    Read an activity date and return it as a local ISO timestamp at midnight.

    Strava's activity list shows absolute dates for older entries and relative
    words for the newest ones. Only the month and day are displayed by the
    frontend, so a midnight time is sufficient and avoids inventing precision
    the page never showed.

        "Jul 26, 2026" -> "2026-07-26T00:00:00"
        "Today"        -> today's date

    Args:
        text:  The displayed date string.
        today: Reference date for relative words. Defaults to the real today;
               injectable so tests do not depend on the calendar.
    """
    if not text:
        raise TextParseError("Empty date string")

    reference_date = today or date.today()
    normalised = text.strip().lower()

    if "today" in normalised:
        return _midnight_iso(reference_date)
    if "yesterday" in normalised:
        return _midnight_iso(reference_date - timedelta(days=1))

    parsed = _parse_absolute_date(text, reference_date)
    if parsed is None:
        raise TextParseError(f"Could not read a date from {text!r}")
    return _midnight_iso(parsed)


def _parse_numeric_date(text: str) -> date | None:
    """
    Parse a slash-separated date, e.g. the "Mon, 8/10/2026" the activity list uses.

    8/10 is ambiguous, so the weekday name decides: both readings are tried and
    the one whose weekday matches wins. That is stronger than assuming a locale —
    it is derived from the page itself. With no weekday to check, month-first is
    assumed, which is what Strava renders in English.
    """
    match = re.search(r"\b(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})\b", text)
    if not match:
        return None

    first, second, year = (int(group) for group in match.groups())
    weekday_match = re.search(r"\b(mon|tue|wed|thu|fri|sat|sun)", text, re.IGNORECASE)
    weekday = weekday_match.group(1).lower() if weekday_match else None

    candidates = []
    for month, day in ((first, second), (second, first)):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue

    if not candidates:
        return None

    if weekday:
        for candidate in candidates:
            if candidate.strftime("%a").lower() == weekday:
                return candidate

    return candidates[0]


def _parse_absolute_date(text: str, reference_date: date) -> date | None:
    """Parse a written date, defaulting a missing year to the reference year."""
    numeric = _parse_numeric_date(text)
    if numeric is not None:
        return numeric

    month_match = re.search(r"[A-Za-z]{3,}", text)
    day_match = re.search(r"\b(\d{1,2})\b(?!:)", text)
    if not month_match or not day_match:
        return None

    month = _MONTH_NAMES.get(month_match.group()[:3].lower())
    if month is None:
        return None

    year_match = re.search(r"\b(20\d{2})\b", text)
    # Strava omits the year on recent activities; assume the reference year, and
    # roll back if that would place the activity in the future.
    year = int(year_match.group()) if year_match else reference_date.year
    day = int(day_match.group(1))

    try:
        parsed = date(year, month, day)
    except ValueError:
        return None

    if not year_match and parsed > reference_date:
        parsed = date(year - 1, month, day)
    return parsed


def _midnight_iso(value: date) -> str:
    return datetime(value.year, value.month, value.day).isoformat(timespec="seconds")


def _to_seconds(hours: str | None, minutes: str | None, seconds: str | None) -> int:
    return int(hours or 0) * 3600 + int(minutes or 0) * 60 + int(seconds or 0)


def _strip_separators(value: str) -> str:
    """Remove thousands separators and stray whitespace from a number string."""
    return value.replace(",", "").replace(" ", "").replace(" ", "")
