"""
Parsers for the text the in-page extractors hand back.

Everything here is a pure function over strings, so it is fully unit-testable
without a browser. When Strava restyles a page the extractors may need new
anchors, but these parsers keep working as long as the words and numbers are
still on screen in roughly the same order.

Totals panels render as label/value pairs, either on one line ("Distance
1,234.5 km") or on consecutive lines. Both layouts are handled.
"""

import re

from hobbies.features.strava.config import COMMUTE_NAME_PATTERNS
from hobbies.features.strava.constants import (
    COUNT_LABELS,
    DISTANCE_LABELS,
    RIDE_SPORT_KEYWORDS,
    RUN_SPORT_KEYWORDS,
    SPORT_CELL_LABELS,
    TIME_LABELS,
)
from hobbies.features.strava.models import RawActivity, RawBike, RawSportTotals
from hobbies.features.strava.text import (
    TextParseError,
    parse_activity_date,
    parse_count,
    parse_distance_metres,
    parse_duration_seconds,
)

# A value looks like a number, optionally with a unit or clock punctuation.
_VALUE_PATTERN = re.compile(r"\d")

# Distances inside a mixed line, e.g. the "1,002.7 km" in "Trek Emonda S 1,002.7 km".
_DISTANCE_IN_LINE = re.compile(
    r"\d[\d,\s]*(?:\.\d+)?\s*(?:km|kilometers?|mi|miles?)\b", re.IGNORECASE
)

# Durations inside a mixed line: "12h 34m", "1:11:23", "42:38".
_DURATION_IN_LINE = re.compile(
    r"(?:\d+\s*h\s*\d*\s*m?(?:\s*\d+\s*s)?|\d+\s*m\s*\d*\s*s?|\d{1,2}:\d{2}(?::\d{2})?)",
    re.IGNORECASE,
)


class PageParseError(ValueError):
    """A page region was found but did not contain what we expected."""


# ---------------------------------------------------------------------------
# Totals panels (This Year / All-Time)
# ---------------------------------------------------------------------------

def parse_sport_totals(section_text: str) -> RawSportTotals:
    """
    Read a totals panel into distance, moving time and (when shown) a count.

    Args:
        section_text: Visible text of the panel, one stat per line or per pair
                      of lines.

    Raises:
        PageParseError: If no distance could be found. Distance is the one field
                        every output needs, so its absence means the wrong region
                        was captured and the run should fail rather than write
                        zeroes over good data.
    """
    pairs = _label_value_pairs(section_text)

    distance_text = _first_matching_value(pairs, DISTANCE_LABELS)
    if distance_text is None:
        raise PageParseError(
            "No distance found in totals panel. Captured text was:\n"
            f"{_truncate(section_text)}"
        )

    time_text = _first_matching_value(pairs, TIME_LABELS)
    count_text = _first_matching_value(pairs, COUNT_LABELS)

    return RawSportTotals(
        distance_metres=parse_distance_metres(distance_text),
        moving_time_seconds=parse_duration_seconds(time_text) if time_text else 0,
        activity_count=_try_parse_count(count_text),
    )


def _label_value_pairs(section_text: str) -> list[tuple[str, str]]:
    """
    Pull (label, value) pairs out of a panel's text.

    Handles both layouts Strava uses:
        "Distance 1,234.5 km"   -> label and value on one line
        "Distance" / "1,234.5"  -> label then value on the next line
    """
    lines = [line.strip() for line in section_text.splitlines() if line.strip()]
    pairs: list[tuple[str, str]] = []

    for index, line in enumerate(lines):
        label_part, value_part = _split_label_and_value(line)

        if value_part:
            pairs.append((label_part.lower(), value_part))
            continue

        # No number on this line, so the value may be on the following one. Only
        # pair when that next line is a *bare* value: otherwise a section heading
        # swallows the first stat line as its own value. "All-Time" is the case
        # that bites — it contains the word "time", so it would be picked up as
        # the moving-time label and handed the distance as its value.
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if not next_line or not _VALUE_PATTERN.search(next_line):
            continue

        next_label, next_value = _split_label_and_value(next_line)
        if next_value and not next_label:
            pairs.append((line.lower(), next_line))

    return pairs


def _split_label_and_value(line: str) -> tuple[str, str]:
    """Split a single line into its wordy part and its numeric part."""
    if not _VALUE_PATTERN.search(line):
        return line, ""

    # Prefer a full measurement (number + unit) over a bare number, so
    # "Distance 1,234.5 km" yields "1,234.5 km" rather than "1,234.5".
    for pattern in (_DISTANCE_IN_LINE, _DURATION_IN_LINE):
        match = pattern.search(line)
        if match:
            label = (line[: match.start()] + line[match.end():]).strip(" \t:·|-")
            return label, match.group().strip()

    number_match = re.search(r"\d[\d,\s]*(?:\.\d+)?", line)
    if not number_match:
        return line, ""

    label = (line[: number_match.start()] + line[number_match.end():]).strip(" \t:·|-")
    return label, number_match.group().strip()


def _first_matching_value(pairs: list[tuple[str, str]], labels: list[str]) -> str | None:
    """Find the value whose label contains any of `labels`."""
    for label, value in pairs:
        if any(wanted in label for wanted in labels):
            return value
    return None


def _try_parse_count(count_text: str | None) -> int | None:
    """Counts are optional; a malformed one is reported as absent, not zero."""
    if not count_text:
        return None
    try:
        return parse_count(count_text)
    except TextParseError:
        return None


# ---------------------------------------------------------------------------
# Gear section
# ---------------------------------------------------------------------------

def parse_bikes(section_text: str) -> list[RawBike]:
    """
    Read the profile's gear section into one RawBike per line that has a distance.

    Lines pair a bike name with its all-time distance ("Trek Emonda S 1,002.7 km");
    lines without a distance are headings and are skipped. The gear section holds
    only bikes for this account, so no sport filtering is applied — and even if
    other gear appeared, only names listed in BIKE_ROLE_CONFIGS reach the output.
    """
    bikes: list[RawBike] = []

    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        distance_match = _DISTANCE_IN_LINE.search(line)
        if not distance_match:
            continue

        name = line[: distance_match.start()].strip(" \t:·|-")
        if not name:
            continue

        bikes.append(
            RawBike(
                name=name,
                distance_metres=parse_distance_metres(distance_match.group()),
            )
        )

    return bikes


# ---------------------------------------------------------------------------
# Activity rows
# ---------------------------------------------------------------------------

def parse_activity_rows(rows: list[dict]) -> list[RawActivity]:
    """
    Turn extracted activity rows into RawActivity, skipping unreadable ones.

    A row missing a distance or a date is skipped rather than fatal: the activity
    list mixes in header rows, and one odd entry should not abort a scrape that
    is otherwise fine. Rows are returned in the order given (newest first).
    """
    activities: list[RawActivity] = []

    for row in rows:
        activity = _parse_activity_row(row)
        if activity is not None:
            activities.append(activity)

    return activities


def _parse_activity_row(row: dict) -> RawActivity | None:
    """Parse one row, returning None when it does not look like an activity."""
    text = row.get("text", "")
    lines = _row_cells(text)
    if not lines:
        return None

    distance_match = _DISTANCE_IN_LINE.search(text)
    if not distance_match:
        return None

    # The duration must not be the distance again, so search past it.
    duration_match = _DURATION_IN_LINE.search(text, distance_match.end())
    if duration_match is None:
        duration_match = _DURATION_IN_LINE.search(text[: distance_match.start()])

    start_date_local = _first_parsable_date(lines)
    if start_date_local is None:
        return None

    name = _activity_name(lines, start_date_local)
    sport = _activity_sport(text)

    return RawActivity(
        name=name,
        start_date_local=start_date_local,
        distance_metres=parse_distance_metres(distance_match.group()),
        moving_time_seconds=(
            parse_duration_seconds(duration_match.group()) if duration_match else 0
        ),
        sport=sport,
        is_commute=bool(row.get("commuteMarkup")) or _looks_like_commute(name),
    )


def _row_cells(row_text: str) -> list[str]:
    """
    Split a row's visible text into its cells.

    innerText separates table cells with tabs and block elements with newlines,
    so both are delimiters. Splitting on newlines alone would collapse a whole
    table row into one string and read the entire row as the activity title.
    """
    return [cell.strip() for cell in re.split(r"[\n\t]+", row_text) if cell.strip()]


def _first_parsable_date(lines: list[str]) -> str | None:
    """Return the first line that reads as a date."""
    for line in lines:
        try:
            return parse_activity_date(line)
        except TextParseError:
            continue
    return None


def _activity_name(lines: list[str], parsed_date: str) -> str:
    """
    Pick the activity title from a row's cells.

    The title is the first cell that is not the date, not a bare measurement and
    not the sport-type cell. Skipping the type cell matters because its position
    relative to the title is not guaranteed.
    """
    for line in lines:
        if _DISTANCE_IN_LINE.fullmatch(line) or _DURATION_IN_LINE.fullmatch(line):
            continue
        if line.casefold() in SPORT_CELL_LABELS:
            continue
        try:
            if parse_activity_date(line) == parsed_date:
                continue
        except TextParseError:
            pass
        return line
    return lines[0]


def _activity_sport(text: str) -> str:
    """
    Identify the sport from a row's text.

    Returns Strava's own wording when a known keyword appears, so downstream
    classification stays keyword-based rather than an exact-match whitelist.
    """
    lowered = text.lower()
    for keyword in RIDE_SPORT_KEYWORDS + RUN_SPORT_KEYWORDS:
        if keyword in lowered:
            return keyword
    return ""


def _looks_like_commute(name: str) -> bool:
    """Fallback commute detection by activity name."""
    lowered = name.lower()
    return any(pattern in lowered for pattern in COMMUTE_NAME_PATTERNS)


def _truncate(text: str, limit: int = 400) -> str:
    return text if len(text) <= limit else f"{text[:limit]}…"
