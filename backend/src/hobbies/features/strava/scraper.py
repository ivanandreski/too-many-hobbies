"""
Strava scraping orchestration.

One run: restore or establish a session, read the profile page (gear, year
totals, all-time totals, for both sports), then walk the paginated activity list
until every target is met. The result is memoised, so generating all three JSON
files costs a single login and a single pass over the pages.

Session handling is self-healing when a password is configured: an expired
session triggers a fresh sign-in automatically. Without a password — or when
Strava presents a challenge — it raises with instructions to run the interactive
login once.
"""

from dataclasses import dataclass
from pathlib import Path

from hobbies.core.browser_session import BrowserSession
from hobbies.core.env import require_env
from hobbies.features.strava import extractors
from hobbies.features.strava.config import (
    ACTIVITY_TARGETS,
    MAX_TRAINING_PAGES,
    ActivityTarget,
)
from hobbies.features.strava.constants import (
    ATHLETE_ID_ENV_VAR,
    EMAIL_ENV_VAR,
    GEAR_SECTION_HEADINGS,
    PASSWORD_ENV_VAR,
    SESSION_FILE_NAME,
    SPORT_TAB_TITLES,
    STRAVA_LOGIN_URL,
    STRAVA_PROFILE_URL_TEMPLATE,
    SPORT_TYPE_FILTERS,
    STRAVA_SESSION_CHECK_URL,
    STRAVA_TRAINING_SPORT_URL_TEMPLATE,
)
from hobbies.features.strava.login_form import (
    LoginFormError,
    dismiss_cookie_banner,
    read_form_error,
    submit_login,
)
from hobbies.features.strava.models import ScrapedStrava
from hobbies.features.strava.page_parser import (
    parse_activity_rows,
    parse_bikes,
    parse_sport_stats_panel,
)
from hobbies.features.strava.selection import describe_unmet, targets_satisfied, unmet_targets

# Time for client-side rendering to settle after a navigation or a tab click.
RENDER_SETTLE_MS = 2500

# The filtered activity list loads client-side; the ride list is the slow one.
ACTIVITY_ROWS_TIMEOUT_MS = 20000
TAB_SETTLE_MS = 1200


class StravaScrapeError(RuntimeError):
    """Scraping could not complete — session, markup or missing configuration."""


@dataclass(frozen=True)
class StravaCredentials:
    """
    Login details. Only the athlete id is always required.

    Email and password are optional: without them a session established by the
    interactive login is still usable, it just cannot be renewed automatically.
    """
    athlete_id: str
    email: str | None = None
    password: str | None = None

    @classmethod
    def from_environment(cls) -> "StravaCredentials":
        import os

        return cls(
            athlete_id=require_env(ATHLETE_ID_ENV_VAR),
            email=os.environ.get(EMAIL_ENV_VAR) or None,
            password=os.environ.get(PASSWORD_ENV_VAR) or None,
        )

    @property
    def can_log_in_automatically(self) -> bool:
        return bool(self.email and self.password)


class StravaScraper:
    """
    Collects everything the Strava-backed JSON files need, once.

    scrape() is memoised, so three pipelines sharing one scraper share one
    browser session.
    """

    def __init__(
        self,
        credentials: StravaCredentials | None = None,
        session_path: str | Path = SESSION_FILE_NAME,
        targets: list[ActivityTarget] | None = None,
        headless: bool = True,
    ) -> None:
        self._credentials = credentials
        self._session_path = Path(session_path)
        self._targets = ACTIVITY_TARGETS if targets is None else targets
        self._headless = headless
        self._scraped: ScrapedStrava | None = None

    def scrape(self) -> ScrapedStrava:
        """Scrape once and reuse the result for later calls."""
        if self._scraped is None:
            self._scraped = self._perform_scrape()
        return self._scraped

    # --- Orchestration ----------------------------------------------------

    def _perform_scrape(self) -> ScrapedStrava:
        credentials = self._credentials or StravaCredentials.from_environment()

        # Decide before opening the real context whether the stored session is any
        # good, because a dead one must not be restored onto the login page. Doing
        # so brings back its stale _GRECAPTCHA cookie and captcha localStorage, and
        # the login page then starts with an expired token — a strong candidate for
        # the generic "unexpected error" the email step returns.
        needs_login = not self._stored_session_works()

        with BrowserSession(
            self._session_path, headless=self._headless, fresh=needs_login
        ) as session:
            page = session.new_page()

            if needs_login:
                self._ensure_logged_in(page, session, credentials)

            scraped = ScrapedStrava()
            self._read_profile(page, credentials.athlete_id, scraped)
            self._read_activities(page, scraped)
            return scraped

    def _stored_session_works(self) -> bool:
        """
        Test the stored session in a throwaway context that never saves.

        Separate from the scraping context so that checking cannot disturb what is
        stored, and so a failed check leaves no state to pollute the login.
        """
        probe = BrowserSession(self._session_path, headless=True)
        if not probe.has_saved_session:
            return False

        with probe:
            return self._is_logged_in(probe.new_page())

    def _ensure_logged_in(self, page, session: BrowserSession, credentials: StravaCredentials) -> None:
        """Verify the restored session, logging in again if it has expired."""
        if self._is_logged_in(page):
            return

        if not credentials.can_log_in_automatically:
            raise StravaScrapeError(
                "Not logged in to Strava and no saved session to restore.\n"
                "Run the interactive login once:\n"
                "    .venv/bin/python -m hobbies.features.strava.login\n"
                f"Or set {EMAIL_ENV_VAR} and {PASSWORD_ENV_VAR} in backend/.env "
                "so the session can be renewed automatically."
            )

        print("[strava] session expired or missing — logging in")
        self._submit_login_form(page, credentials)

        if not self._is_logged_in(page):
            # Every failure mode leaves us on /login, so quote Strava's own error
            # rather than guessing between a wrong password and a challenge.
            reported = read_form_error(page)
            detail = f"\nStrava said: {reported}" if reported else ""
            raise StravaScrapeError(
                "Login did not take effect. Strava most likely presented a "
                "verification step or a bot challenge that cannot be solved "
                f"headlessly.{detail}\n"
                "Run the interactive login once and solve it by hand:\n"
                "    .venv/bin/python -m hobbies.features.strava.login"
            )

        session.save_session()
        print("[strava] logged in, session saved")

    def _is_logged_in(self, page) -> bool:
        """
        Load an authenticated-only page and see whether we stay there.

        Strava bounces logged-out visitors to the login page, so the final URL
        is a more reliable signal than hunting for an avatar element.
        """
        page.goto(STRAVA_SESSION_CHECK_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(TAB_SETTLE_MS)
        return "/login" not in page.url

    def _submit_login_form(self, page, credentials: StravaCredentials) -> None:
        """
        Drive Strava's staged login: email, then "use password", then password.

        The stages live in login_form.py, shared with the interactive login so
        both behave the same way.
        """
        page.goto(STRAVA_LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(TAB_SETTLE_MS)

        try:
            submit_login(page, credentials.email, credentials.password)
        except LoginFormError as error:
            # Already a stage-specific, actionable message.
            raise StravaScrapeError(str(error)) from error
        except Exception as error:  # noqa: BLE001 - Playwright raises many types
            raise StravaScrapeError(
                f"Could not drive the Strava login form: {error}. "
                "A bot challenge may have been shown. Run the interactive login "
                "and complete it by hand:\n"
                "    .venv/bin/python -m hobbies.features.strava.login"
            ) from error

    # --- Profile page -----------------------------------------------------

    def _read_profile(self, page, athlete_id: str, scraped: ScrapedStrava) -> None:
        """Read gear plus the year and all-time totals for both sports."""
        profile_url = STRAVA_PROFILE_URL_TEMPLATE.format(athlete_id=athlete_id)
        page.goto(profile_url, wait_until="domcontentloaded")
        page.wait_for_timeout(RENDER_SETTLE_MS)

        # The consent dialog overlays the page and would swallow clicks.
        if dismiss_cookie_banner(page):
            print("[strava] dismissed the cookie banner")

        scraped.bikes = self._read_bikes(page)
        self._read_sport_totals(page, scraped)

    def _read_sport_totals(self, page, scraped: ScrapedStrava) -> None:
        """
        Read both sports' totals straight out of their panels.

        No switching and no text anchors. Every sport's panel is already in the
        DOM — only the active one is displayed — and each is addressed by the index
        in its tab's class, so the figures cannot be attributed to the wrong sport.

        This replaced an approach that clicked a sport icon and then searched for a
        "This Year" heading. Neither existed: the profile has no such heading, the
        year figures live behind a year selector, and the "All-Time" anchor matched
        "All-Time PRs" and captured personal records instead of distances.
        """
        panels = page.evaluate(extractors.SPORT_STATS, SPORT_TAB_TITLES)

        for sport_key, panel in panels.items():
            if panel is None:
                print(
                    f"[strava] WARNING: no stats panel for '{sport_key}'. Expected a "
                    f"tab button titled one of {SPORT_TAB_TITLES[sport_key]}."
                )
                continue

            year, all_time = parse_sport_stats_panel(panel)

            if year is not None:
                scraped.year_totals[sport_key] = year
            else:
                print(f"[strava] WARNING: no year totals in the '{sport_key}' panel")

            if all_time is not None:
                scraped.all_time_totals[sport_key] = all_time
            else:
                print(f"[strava] WARNING: no all-time totals in the '{sport_key}' panel")

    def _read_bikes(self, page):
        section_text = page.evaluate(
            extractors.SECTION_TEXT_BY_HEADING, GEAR_SECTION_HEADINGS
        )
        if not section_text:
            raise StravaScrapeError(
                "Could not find the gear section on the profile page. "
                "Run the probe to see what the page contains:\n"
                "    .venv/bin/python -m hobbies.features.strava.probe"
            )

        bikes = parse_bikes(section_text)
        if not bikes:
            raise StravaScrapeError(
                f"Gear section found but no bikes parsed from:\n{section_text[:400]}"
            )
        return bikes

    # --- Activity list ----------------------------------------------------

    def _read_activities(self, page, scraped: ScrapedStrava) -> None:
        """
        Collect activities, asking for one sport at a time.

        The list is fetched per sport using the page's own sport_type filter,
        rather than paged through unfiltered. That is not an optimisation so much
        as a correctness fix: unfiltered, twelve pages of this account held 240
        rides and zero runs, because runs are seasonal and rides are daily. Asking
        for runs directly finds them immediately.
        """
        for sport_key, sport_type in SPORT_TYPE_FILTERS.items():
            targets = [t for t in self._targets if t.sport == sport_key]
            if not targets:
                continue
            self._read_sport_activities(page, scraped, sport_key, sport_type, targets)

        if not scraped.activities:
            raise StravaScrapeError(
                "No activities could be parsed from the training pages. "
                "Run the probe to inspect the markup:\n"
                "    .venv/bin/python -m hobbies.features.strava.probe"
            )

        still_unmet = unmet_targets(scraped.activities, self._targets)
        if still_unmet:
            # Not fatal: fewer than five commutes is a legitimate state for a quiet
            # month. Say so rather than silently publishing a short list.
            print(
                "[strava] WARNING: ran out of pages before filling every target — "
                f"{describe_unmet(still_unmet, scraped.activities)}"
            )

    @staticmethod
    def _wait_for_activity_rows(page) -> None:
        """
        Wait for the filtered list to render rather than trusting a fixed pause.

        The sport-filtered list arrives client-side behind a "Loading…" row, and
        the ride list is slow enough that a fixed wait saw only that placeholder
        and concluded the history was empty.
        """
        try:
            page.wait_for_function(
                extractors.ACTIVITY_ROWS_READY, timeout=ACTIVITY_ROWS_TIMEOUT_MS
            )
        except Exception:  # noqa: BLE001 - proceed and let the row parse report
            print("[strava] WARNING: activity rows did not settle before the timeout")

    def _read_sport_activities(
        self,
        page,
        scraped: ScrapedStrava,
        sport_key: str,
        sport_type: str,
        targets: list[ActivityTarget],
    ) -> None:
        """Page through one sport's list until its own targets are met."""
        collected: list = []

        for page_number in range(1, MAX_TRAINING_PAGES + 1):
            page.goto(
                STRAVA_TRAINING_SPORT_URL_TEMPLATE.format(
                    sport_type=sport_type, page=page_number
                ),
                wait_until="domcontentloaded",
            )
            self._wait_for_activity_rows(page)
            scraped.pages_read += 1

            rows = page.evaluate(extractors.ACTIVITY_ROWS)
            if not rows:
                print(f"[strava] {sport_type} page {page_number}: no rows — stopping")
                break

            parsed = parse_activity_rows(rows)
            collected.extend(parsed)
            print(
                f"[strava] {sport_type} page {page_number}: {len(rows)} rows, "
                f"{len(parsed)} parsed, {len(collected)} for this sport"
            )

            if targets_satisfied(collected, targets):
                break

        scraped.activities.extend(collected)
