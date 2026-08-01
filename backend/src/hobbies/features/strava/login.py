"""
Interactive Strava login.

Run once to establish a session the scraper can reuse:

    cd backend
    .venv/bin/python -m hobbies.features.strava.login

Opens a real, visible browser. If STRAVA_EMAIL and STRAVA_PASSWORD are set in
backend/.env the form is filled for you; otherwise — or if Strava shows a bot
challenge, a device verification step, or you sign in with Google — complete it
by hand in the window. The session is saved when you press Enter.

This exists because a headless browser cannot solve a challenge and cannot do a
Google OAuth sign-in. Doing it once in a real browser sidesteps both.
"""

from hobbies.core.browser_session import BrowserSession
from hobbies.core.env import DEFAULT_ENV_FILENAME, load_env_file
from hobbies.features.strava.constants import (
    SESSION_FILE_NAME,
    STRAVA_LOGIN_URL,
    STRAVA_SESSION_CHECK_URL,
)
from hobbies.features.strava.scraper import StravaCredentials

SETTLE_MS = 2500


def main() -> None:
    load_env_file(DEFAULT_ENV_FILENAME)

    try:
        credentials = StravaCredentials.from_environment()
    except RuntimeError:
        # Only the athlete id is strictly required, and it is not needed to log in.
        credentials = StravaCredentials(athlete_id="")

    with BrowserSession(SESSION_FILE_NAME, headless=False) as session:
        page = session.new_page()
        page.goto(STRAVA_LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(SETTLE_MS)

        if credentials.can_log_in_automatically:
            print("Pre-filling the login form from backend/.env …")
            _try_prefill(page, credentials)
        else:
            print("No STRAVA_EMAIL / STRAVA_PASSWORD set — log in by hand.")

        print(
            "\nA browser window is open.\n"
            "  1. Finish logging in (solve any challenge, or use Sign in with Google).\n"
            "  2. Make sure you can see your own Strava dashboard.\n"
            "  3. Come back here and press Enter to save the session.\n"
        )
        input("Press Enter once you are logged in: ")

        page.goto(STRAVA_SESSION_CHECK_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(SETTLE_MS)

        if "/login" in page.url:
            print(
                "\nStill logged out — nothing useful to save. "
                "Re-run this and complete the login before pressing Enter."
            )
            return

        session.save_session()
        print(f"\nLogged in. Session saved to backend/{SESSION_FILE_NAME}")
        print("Treat that file as a password: it is gitignored, keep it that way.")


def _try_prefill(page, credentials: StravaCredentials) -> None:
    """Fill the form if we recognise it; failure here is not fatal."""
    try:
        page.fill("input[type='email'], #email, input[name='email']", credentials.email)
        page.fill(
            "input[type='password'], #password, input[name='password']",
            credentials.password,
        )
        print("Form filled — press Log In in the browser window.")
    except Exception as error:  # noqa: BLE001 - Playwright raises many types
        print(f"Could not pre-fill the form ({error}). Log in by hand.")


if __name__ == "__main__":
    main()
