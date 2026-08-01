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
    ALL_TIME_SECTION_HEADINGS,
    ATHLETE_ID_ENV_VAR,
    EMAIL_ENV_VAR,
    GEAR_SECTION_HEADINGS,
    PASSWORD_ENV_VAR,
    SESSION_FILE_NAME,
    SPORT_SELECTOR_ATTRIBUTES,
    SPORT_SELECTOR_KEYWORDS,
    STRAVA_LOGIN_URL,
    STRAVA_PROFILE_URL_TEMPLATE,
    STRAVA_SESSION_CHECK_URL,
    STRAVA_TRAINING_URL_TEMPLATE,
    YEAR_SECTION_HEADINGS,
)
from hobbies.features.strava.models import ScrapedStrava
from hobbies.features.strava.page_parser import (
    PageParseError,
    parse_activity_rows,
    parse_bikes,
    parse_sport_totals,
)
from hobbies.features.strava.selection import describe_unmet, targets_satisfied, unmet_targets

# Time for client-side rendering to settle after a navigation or a tab click.
RENDER_SETTLE_MS = 2500
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

        with BrowserSession(self._session_path, headless=self._headless) as session:
            page = session.new_page()
            self._ensure_logged_in(page, session, credentials)

            scraped = ScrapedStrava()
            self._read_profile(page, credentials.athlete_id, scraped)
            self._read_activities(page, scraped)
            return scraped

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
            raise StravaScrapeError(
                "Login did not take effect. Strava most likely presented a "
                "verification step or a bot challenge that cannot be solved "
                "headlessly. Run the interactive login once and solve it by hand:\n"
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
        """Fill and submit the email/password form."""
        page.goto(STRAVA_LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(TAB_SETTLE_MS)

        try:
            page.fill("input[type='email'], #email, input[name='email']", credentials.email)
            page.fill(
                "input[type='password'], #password, input[name='password']",
                credentials.password,
            )
            page.click(
                "button[type='submit'], #login-button, button:has-text('Log In')"
            )
        except Exception as error:  # noqa: BLE001 - Playwright raises many types
            raise StravaScrapeError(
                f"Could not drive the Strava login form: {error}. "
                "The form markup may have changed, or a challenge was shown."
            ) from error

        page.wait_for_timeout(RENDER_SETTLE_MS)

    # --- Profile page -----------------------------------------------------

    def _read_profile(self, page, athlete_id: str, scraped: ScrapedStrava) -> None:
        """
        Read gear plus the year and all-time totals for both sports.

        The sport switcher is a row of icons. If a click silently fails the panel
        keeps showing the previous sport, which would quietly file cycling totals
        under running — the worst possible outcome, because the numbers look
        plausible. So the captured text is compared against what the previous
        sport produced, and an unchanged panel is discarded rather than recorded.
        """
        profile_url = STRAVA_PROFILE_URL_TEMPLATE.format(athlete_id=athlete_id)
        page.goto(profile_url, wait_until="domcontentloaded")
        page.wait_for_timeout(RENDER_SETTLE_MS)

        scraped.bikes = self._read_bikes(page)

        seen_panel_text: dict[str, str] = {}

        for sport_key, keywords in SPORT_SELECTOR_KEYWORDS.items():
            selected = self._select_sport(page, sport_key, keywords)

            for label, headings, destination in (
                ("year", YEAR_SECTION_HEADINGS, scraped.year_totals),
                ("all-time", ALL_TIME_SECTION_HEADINGS, scraped.all_time_totals),
            ):
                panel_text = page.evaluate(extractors.SECTION_TEXT_BY_HEADING, headings)
                if not panel_text:
                    print(f"[strava] WARNING: no {label} panel found for '{sport_key}'")
                    continue

                previous_sport = self._sport_showing_same_panel(
                    seen_panel_text, label, panel_text
                )
                if previous_sport is not None:
                    print(
                        f"[strava] WARNING: {label} panel for '{sport_key}' is identical "
                        f"to '{previous_sport}'. The sport switcher did not respond, so "
                        f"'{sport_key}' {label} totals are being skipped rather than "
                        f"filled with {previous_sport} data. Selection result: {selected}"
                    )
                    continue

                seen_panel_text[f"{label}:{sport_key}"] = panel_text

                totals = self._parse_totals(panel_text, sport_key, label)
                if totals is not None:
                    destination[sport_key] = totals

    @staticmethod
    def _sport_showing_same_panel(
        seen_panel_text: dict[str, str], label: str, panel_text: str
    ) -> str | None:
        """Return the sport that already produced this exact panel text, if any."""
        for key, previous_text in seen_panel_text.items():
            previous_label, previous_sport = key.split(":", 1)
            if previous_label == label and previous_text == panel_text:
                return previous_sport
        return None

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

    def _select_sport(self, page, sport_key: str, keywords: list[str]) -> str:
        """
        Click the sport icon that switches the totals panels.

        Returns a short description of what happened, used in warnings. Failure is
        not raised here: cycling is preselected, so a failed click is harmless for
        it, and the identical-panel guard in _read_profile catches the case where
        it matters.
        """
        result = page.evaluate(
            extractors.CLICK_SPORT_CONTROL,
            {"keywords": keywords, "attributes": SPORT_SELECTOR_ATTRIBUTES},
        )

        if result is None:
            print(
                f"[strava] WARNING: no sport control matched {keywords} for "
                f"'{sport_key}'. Run the probe to see the available controls."
            )
            return "no control matched"

        page.wait_for_timeout(TAB_SETTLE_MS)
        return f"clicked <{result['tag']}> matching {result['matched']!r}"

    def _parse_totals(self, panel_text: str, sport_key: str, label: str):
        """Parse a totals panel, tolerating unreadable content."""
        try:
            return parse_sport_totals(panel_text)
        except (PageParseError, ValueError) as error:
            print(f"[strava] WARNING: could not read {label} totals for '{sport_key}': {error}")
            return None

    # --- Activity list ----------------------------------------------------

    def _read_activities(self, page, scraped: ScrapedStrava) -> None:
        """
        Page through the activity list until every target is met.

        Stops early on an empty page (end of history) and hard-stops at
        MAX_TRAINING_PAGES so a parsing regression cannot walk years of data.
        """
        for page_number in range(1, MAX_TRAINING_PAGES + 1):
            page.goto(
                STRAVA_TRAINING_URL_TEMPLATE.format(page=page_number),
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(RENDER_SETTLE_MS)

            rows = page.evaluate(extractors.ACTIVITY_ROWS)
            scraped.pages_read = page_number

            if not rows:
                print(f"[strava] no activity rows on page {page_number} — stopping")
                break

            parsed = parse_activity_rows(rows)
            scraped.activities.extend(parsed)
            print(
                f"[strava] page {page_number}: {len(rows)} rows, "
                f"{len(parsed)} parsed, {len(scraped.activities)} total"
            )

            if targets_satisfied(scraped.activities, self._targets):
                break

        if not scraped.activities:
            raise StravaScrapeError(
                "No activities could be parsed from the training pages. "
                "Run the probe to inspect the markup:\n"
                "    .venv/bin/python -m hobbies.features.strava.probe"
            )

        still_unmet = unmet_targets(scraped.activities, self._targets)
        if still_unmet:
            # Not fatal: fewer than five commutes is a legitimate state for a
            # quiet month. Say so rather than silently writing a short list.
            print(
                "[strava] WARNING: ran out of pages before filling every target — "
                f"{describe_unmet(still_unmet, scraped.activities)}"
            )
