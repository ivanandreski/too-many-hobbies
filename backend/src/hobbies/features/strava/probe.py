"""
Diagnostic probe for the Strava scrapers.

Run this after the interactive login to see exactly what the extractors find:

    cd backend
    .venv/bin/python -m hobbies.features.strava.probe

For the profile page and the first training page it reports which regions were
located, prints the raw text captured from each, and dumps the full HTML to
backend/output/ for inspection. When a region is missing it lists the headings
and buttons the page actually has, which is what you need to fix the text
anchors in constants.py.

This is the fast loop for correcting the scraper. The selectors and anchors were
written without a logged-in view of these pages, so expect to run this first.
"""

from pathlib import Path

from hobbies.core.browser_session import BrowserSession
from hobbies.core.env import DEFAULT_ENV_FILENAME, load_env_file
from hobbies.features.strava import extractors
from hobbies.features.strava.constants import (
    ALL_TIME_SECTION_HEADINGS,
    GEAR_SECTION_HEADINGS,
    SESSION_FILE_NAME,
    SPORT_SELECTOR_ATTRIBUTES,
    SPORT_SELECTOR_KEYWORDS,
    STRAVA_PROFILE_URL_TEMPLATE,
    STRAVA_SESSION_CHECK_URL,
    STRAVA_TRAINING_URL_TEMPLATE,
    YEAR_SECTION_HEADINGS,
)
from hobbies.features.strava.page_parser import parse_activity_rows, parse_bikes, parse_sport_totals
from hobbies.features.strava.scraper import StravaCredentials

OUTPUT_DIR = Path("output")
SETTLE_MS = 3000


def main() -> None:
    load_env_file(DEFAULT_ENV_FILENAME)
    credentials = StravaCredentials.from_environment()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with BrowserSession(SESSION_FILE_NAME, headless=True) as session:
        page = session.new_page()

        page.goto(STRAVA_SESSION_CHECK_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(SETTLE_MS)
        if "/login" in page.url:
            print(
                "Not logged in. Run the interactive login first:\n"
                "    .venv/bin/python -m hobbies.features.strava.login"
            )
            return
        print("Session OK.\n")

        _probe_profile(page, credentials.athlete_id)
        _probe_training(page)

    print(f"\nHTML dumps written to backend/{OUTPUT_DIR}/ for inspection.")


def _probe_profile(page, athlete_id: str) -> None:
    print("=" * 70)
    print("PROFILE PAGE")
    print("=" * 70)

    page.goto(
        STRAVA_PROFILE_URL_TEMPLATE.format(athlete_id=athlete_id),
        wait_until="domcontentloaded",
    )
    page.wait_for_timeout(SETTLE_MS)
    _dump(page, "probe_profile.html")
    _report_outline(page)

    gear_text = page.evaluate(extractors.SECTION_TEXT_BY_HEADING, GEAR_SECTION_HEADINGS)
    _report_section("GEAR", gear_text, lambda text: [
        f"{bike.name}: {bike.distance_metres / 1000:.1f} km" for bike in parse_bikes(text)
    ])

    _report_sport_controls(page)

    # Panel text per sport, so an unresponsive icon shows up as a duplicate.
    panels_seen: dict[str, str] = {}

    for sport_key, keywords in SPORT_SELECTOR_KEYWORDS.items():
        clicked = page.evaluate(
            extractors.CLICK_SPORT_CONTROL,
            {"keywords": keywords, "attributes": SPORT_SELECTOR_ATTRIBUTES},
        )
        page.wait_for_timeout(SETTLE_MS)
        print(f"\n--- sport '{sport_key}': clicked {clicked!r}")
        _dump(page, f"probe_profile_{sport_key}.html")

        for label, headings in (
            ("YEAR", YEAR_SECTION_HEADINGS),
            ("ALL-TIME", ALL_TIME_SECTION_HEADINGS),
        ):
            text = page.evaluate(extractors.SECTION_TEXT_BY_HEADING, headings)
            _report_section(
                f"{label} totals [{sport_key}]",
                text,
                lambda t: [str(parse_sport_totals(t))],
            )

            if not text:
                continue
            duplicate_of = panels_seen.get(f"{label}:{text}")
            if duplicate_of:
                print(
                    f"    !! IDENTICAL to the {label} panel for '{duplicate_of}' — "
                    "the sport icon did not switch anything. Fix the keywords in "
                    "SPORT_SELECTOR_KEYWORDS using the control list above."
                )
            else:
                panels_seen[f"{label}:{text}"] = sport_key


def _report_sport_controls(page) -> None:
    """List every plausible sport switcher with its identifying attributes."""
    print("\n--- SPORT SWITCHER CANDIDATES")
    candidates = page.evaluate(
        extractors.SPORT_CONTROL_CANDIDATES, SPORT_SELECTOR_ATTRIBUTES
    )

    interesting = [
        row for row in candidates
        if row["icons"] or row["attributes"].get("aria-label") or row["attributes"].get("title")
    ]
    print(f"    {len(candidates)} clickable elements, {len(interesting)} with icons or labels")

    for row in interesting[:25]:
        print(f"    <{row['tag']}> text={row['text']!r}")
        for name, value in row["attributes"].items():
            print(f"        {name}={value!r}")
        for icon in row["icons"][:2]:
            print(f"        icon: {icon}")


def _probe_training(page) -> None:
    print("\n" + "=" * 70)
    print("TRAINING PAGE 1")
    print("=" * 70)

    page.goto(STRAVA_TRAINING_URL_TEMPLATE.format(page=1), wait_until="domcontentloaded")
    page.wait_for_timeout(SETTLE_MS)
    _dump(page, "probe_training_page1.html")
    _report_outline(page)

    rows = page.evaluate(extractors.ACTIVITY_ROWS)
    print(f"\nrows extracted: {len(rows)}")

    for index, row in enumerate(rows[:5]):
        print(f"\n  row[{index}] commuteMarkup={row['commuteMarkup']} url={row['activityUrl']}")
        print("    text:", repr(row["text"][:200]))

    parsed = parse_activity_rows(rows)
    print(f"\nparsed activities: {len(parsed)} of {len(rows)} rows")
    for activity in parsed[:8]:
        print(
            f"  {activity.start_date_local} | {activity.name!r} | "
            f"{activity.distance_metres / 1000:.1f} km | "
            f"{activity.moving_time_seconds}s | sport={activity.sport!r} | "
            f"commute={activity.is_commute}"
        )

    if rows and not parsed:
        print("\n  Rows were found but none parsed — inspect markupSample:")
        print("  ", repr(rows[0]["markupSample"][:400]))


def _report_section(label: str, text: str | None, summarise) -> None:
    print(f"\n--- {label}")
    if not text:
        print("    NOT FOUND — the text anchors in constants.py need updating")
        return

    print(f"    captured text:\n{_indent(text)}")
    try:
        for line in summarise(text):
            print(f"    parsed -> {line}")
    except Exception as error:  # noqa: BLE001 - diagnostics must never crash
        print(f"    PARSE FAILED: {error}")


def _report_outline(page) -> None:
    outline = page.evaluate(extractors.PAGE_OUTLINE)
    print(f"url: {outline['url']}")
    print(f"title: {outline['title']}")
    print(f"headings: {outline['headings']}")
    print(f"buttons/tabs: {outline['buttons']}")


def _dump(page, filename: str) -> None:
    (OUTPUT_DIR / filename).write_text(page.content(), encoding="utf-8")


def _indent(text: str, limit: int = 800) -> str:
    clipped = text if len(text) <= limit else f"{text[:limit]}…"
    return "\n".join(f"      {line}" for line in clipped.splitlines())


if __name__ == "__main__":
    main()
