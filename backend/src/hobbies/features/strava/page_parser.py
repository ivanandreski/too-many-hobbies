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
    ALL_TIME_HEADER,
    COUNT_LABELS,
    DISTANCE_LABELS,
    RIDE_SPORT_KEYWORDS,
    RUN_SPORT_KEYWORDS,
    SPORT_CELL_LABELS,
    TIME_LABELS,
    YEAR_TBODY_ID_SUFFIX,
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

# A cell that is entirely a distance: "28.46 km". Excludes "250 m" elevation.
_DISTANCE_CELL = re.compile(r"^\d[\d,\s]*(?:\.\d+)?\s*(?:km|kilometers?|mi|miles?)$", re.IGNORECASE)

# A cell that is entirely a duration: "59:28", "1:18:57", "1h 5m". Deliberately
# does not match a bare "250 m" — that is elevation, not 250 minutes.
_DURATION_CELL = re.compile(
    r"^(?:\d{1,3}:\d{2}(?::\d{2})?|\d+\s*h(?:\s*\d+\s*m)?(?:\s*\d+\s*s)?)$", re.IGNORECASE
)

# A cell that is entirely an elevation: "250 m".
_ELEVATION_CELL = re.compile(r"^\d[\d,\s]*(?:\.\d+)?\s*m$", re.IGNORECASE)

# Cells that are row controls rather than data.
_ACTION_CELL = re.compile(r"^(?:edit|delete|share)(?:\s+(?:edit|delete|share))*$", re.IGNORECASE)

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


def parse_sport_stats_panel(panel: dict) -> tuple[RawSportTotals | None, RawSportTotals | None]:
    """
    Read one sport's panel into (year totals, all-time totals).

    The panel arrives as a list of tbodies with their rows already split into
    cells, so this is structural rather than textual: the year figures are the
    tbody whose id ends in "-ytd", and the lifetime figures are the tbody that
    follows the one-row "All-Time" header.

    Either may be None — a sport with no recorded activity has no rows — which
    the caller must treat as absent rather than zero.
    """
    tbodies = panel.get("tbodies") or []

    year_rows = next(
        (tb["rows"] for tb in tbodies if tb.get("id", "").endswith(YEAR_TBODY_ID_SUFFIX)),
        None,
    )
    all_time_rows = _rows_after_header(tbodies, ALL_TIME_HEADER)

    return _rows_to_totals(year_rows), _rows_to_totals(all_time_rows)


def _rows_after_header(tbodies: list[dict], header: str) -> list[list[str]] | None:
    """
    Find the first data tbody following a single-row header tbody.

    The lifetime figures have no id of their own; they are simply the block after
    a tbody containing just "All-Time".
    """
    for index, tbody in enumerate(tbodies):
        rows = tbody.get("rows") or []
        is_header = len(rows) == 1 and len(rows[0]) == 1 and rows[0][0].strip().lower() == header

        if not is_header:
            continue

        for following in tbodies[index + 1:]:
            following_rows = following.get("rows") or []
            if any(len(row) >= 2 for row in following_rows):
                return following_rows
    return None


def _rows_to_totals(rows: list[list[str]] | None) -> RawSportTotals | None:
    """
    Convert label/value cell pairs into totals.

    Reuses parse_sport_totals by rendering the rows back into the "Label value"
    lines it already handles, so the unit conversions and the label matching stay
    in one tested place.
    """
    if not rows:
        return None

    lines = [f"{row[0]} {row[1]}" for row in rows if len(row) >= 2]
    if not lines:
        return None

    try:
        return parse_sport_totals("\n".join(lines))
    except (PageParseError, ValueError):
        return None


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
    """
    Parse one row, returning None when it does not look like an activity.

    Works cell by cell rather than scanning the row's whole text. That matters
    because a row reads Sport | Date | Title | Time | Distance | Elevation, and
    scanning for a duration after the distance picks up the *elevation* — "250 m"
    parsed as 250 minutes. Identifying each value by the shape of its own cell
    keeps metres and minutes apart.
    """
    cells = _row_cells(row.get("text", ""))
    if not cells:
        return None

    distance_cell = next((cell for cell in cells if _DISTANCE_CELL.match(cell)), None)
    if distance_cell is None:
        return None

    start_date_local = _first_parsable_date(cells)
    if start_date_local is None:
        return None

    duration_cell = next((cell for cell in cells if _DURATION_CELL.match(cell)), None)
    name = _activity_name(cells, start_date_local)

    return RawActivity(
        name=name,
        start_date_local=start_date_local,
        distance_metres=parse_distance_metres(distance_cell),
        moving_time_seconds=parse_duration_seconds(duration_cell) if duration_cell else 0,
        sport=_activity_sport(cells),
        is_commute=bool(row.get("isCommute")) or _looks_like_commute(name),
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


def _activity_name(cells: list[str], parsed_date: str) -> str:
    """
    Pick the activity title from a row's cells.

    The title is the first cell that is not the date, a measurement, the
    sport-type cell, or the row's Edit/Delete/Share controls.
    """
    for cell in cells:
        if _DISTANCE_CELL.match(cell) or _DURATION_CELL.match(cell):
            continue
        if _ELEVATION_CELL.match(cell) or _ACTION_CELL.match(cell):
            continue
        if cell.casefold() in SPORT_CELL_LABELS:
            continue
        try:
            if parse_activity_date(cell) == parsed_date:
                continue
        except TextParseError:
            pass
        return cell
    return cells[0]


def _activity_sport(cells: list[str]) -> str:
    """
    Identify the sport from a row's cells.

    Prefers a cell that is *exactly* a sport name — the row has a dedicated sport
    column — and only falls back to keyword matching across the row when no such
    cell exists.
    """
    for cell in cells:
        if cell.casefold() in SPORT_CELL_LABELS:
            return cell

    joined = " ".join(cells).lower()
    for keyword in RIDE_SPORT_KEYWORDS + RUN_SPORT_KEYWORDS:
        if keyword in joined:
            return keyword
    return ""


def _looks_like_commute(name: str) -> bool:
    """Fallback commute detection by activity name."""
    lowered = name.lower()
    return any(pattern in lowered for pattern in COMMUTE_NAME_PATTERNS)


def _truncate(text: str, limit: int = 400) -> str:
    return text if len(text) <= limit else f"{text[:limit]}…"
