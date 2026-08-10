"""
Interactive Strava login.

Run once to establish a session the scraper can reuse:

    cd backend
    .venv/bin/python -m hobbies.features.strava.login

Opens a real, visible browser and drives as much of Strava's staged login as it
can — dismiss the cookie banner, enter the email, switch from the one-time-code
offer to password entry, enter the password. It stops and hands over whenever a
stage needs you: a bot challenge, a device verification, or a Google sign-in.

This exists because a headless browser cannot solve a challenge, and because the
session it saves is what makes every later run unattended.
"""

import argparse

from hobbies.core.browser_session import BrowserSession
from hobbies.core.env import DEFAULT_ENV_FILENAME, load_env_file
from hobbies.features.strava.constants import (
    SESSION_FILE_NAME,
    STRAVA_LOGIN_URL,
    STRAVA_SESSION_CHECK_URL,
    USE_PASSWORD_TEXTS,
)
from hobbies.features.strava.login_form import (
    PASSWORD_STAGE_ALREADY_SHOWING,
    PASSWORD_STAGE_CLICKED,
    LoginFormError,
    choose_password_login,
    dismiss_cookie_banner,
    dump_login_page,
    read_form_error,
    submit_email,
    submit_password,
)
from hobbies.features.strava.scraper import StravaCredentials

SETTLE_MS = 2500


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hobbies.features.strava.login",
        description="Establish a reusable Strava session in a visible browser.",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Touch nothing: open the browser and let you log in entirely by "
             "hand. Use this to find out whether the automation is what Strava "
             "is rejecting, and to capture the markup of the later stages.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Log in again even if the stored session still works, discarding it.",
    )
    return parser


def main() -> None:
    arguments = _build_argument_parser().parse_args()
    load_env_file(DEFAULT_ENV_FILENAME)

    try:
        credentials = StravaCredentials.from_environment()
    except RuntimeError:
        # Only the athlete id is strictly required, and it is not needed to log in.
        credentials = StravaCredentials(athlete_id="")

    # Checked in its own throwaway context. Without this the script logged in over
    # a working session, and submitting the login form while already authenticated
    # is itself an error — which looked exactly like a broken login.
    if not arguments.fresh and _stored_session_works():
        print(
            "Already logged in — the stored session is still valid.\n"
            "Nothing to do. Run the probe to see what the scrapers can read:\n"
            "    .venv/bin/python -m hobbies.features.strava.probe"
        )
        return

    # Log in with an empty jar. Restoring a dead session onto the login page also
    # restores its localStorage, which is what filled the email field with stale
    # junk — and typing into a field that already has content produces an invalid
    # address and Strava's generic error.
    print("Starting from a clean browser state (no stored cookies or localStorage).")

    with BrowserSession(SESSION_FILE_NAME, headless=False, fresh=True) as session:
        page = session.new_page()
        _record_login_posts(page)

        page.goto(STRAVA_LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(SETTLE_MS)

        if arguments.manual:
            _run_manual_session(page)
        elif credentials.can_log_in_automatically:
            _attempt_staged_login(page, credentials)
            _wait_for_manual_finish()
        else:
            print(
                "No STRAVA_EMAIL / STRAVA_PASSWORD in backend/.env — "
                "log in by hand in the browser window."
            )
            _wait_for_manual_finish()

        page.goto(STRAVA_SESSION_CHECK_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(SETTLE_MS)

        if "/login" in page.url:
            print(
                "\nStill logged out — nothing useful to save. Re-run this and "
                "complete the login before finishing."
            )
            return

        session.save_session()
        print(f"\nLogged in. Session saved to backend/{SESSION_FILE_NAME}")
        print("Treat that file as a password: it is gitignored, keep it that way.")


def _stored_session_works() -> bool:
    """
    Whether the stored session still reaches an authenticated page.

    Runs headless in its own context and never saves, so checking can neither
    disturb the stored session nor leave state behind.
    """
    session = BrowserSession(SESSION_FILE_NAME, headless=True)
    if not session.has_saved_session:
        return False

    with session:
        page = session.new_page()
        page.goto(STRAVA_SESSION_CHECK_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(SETTLE_MS)
        return "/login" not in page.url


def _wait_for_manual_finish() -> None:
    print(
        "\nA browser window is open.\n"
        "  1. Finish anything still outstanding (a challenge, a verification\n"
        "     code, or Sign in with Google).\n"
        "  2. Make sure you can see your own Strava dashboard.\n"
        "  3. Come back here and press Enter to save the session.\n"
    )
    input("Press Enter once you are logged in: ")


def _run_manual_session(page) -> None:
    """
    Hands-off mode: nothing is clicked or typed for you.

    You drive the browser; this only captures what is on screen when you ask. The
    point is to compare a by-hand login against the automated one — if yours
    succeeds where the script fails, Strava is rejecting the automation rather
    than the input, and the captures reveal the markup of the stages the script
    never reaches.
    """
    print(
        "\nMANUAL MODE — nothing will be typed or clicked for you.\n"
        "A browser window is open at the Strava login page.\n\n"
        "Log in by hand. Whenever something interesting is on screen, come back\n"
        "here and capture it.\n\n"
        "  [Enter]  capture what is on screen right now\n"
        "  done     finish, then save the session\n"
        "  quit     stop without saving\n"
    )

    capture_index = 0
    while True:
        answer = input("manual> ").strip().lower()

        if answer == "done":
            return
        if answer == "quit":
            raise SystemExit("Stopped without saving.")

        capture_index += 1
        label = f"manual_{capture_index:02d}"
        summary = dump_login_page(page, label=label)
        print(f"  captured -> backend/{summary}")
        print(f"  url: {page.url}")

        error = read_form_error(page)
        if error:
            print(f"  page is showing an error: {error}")


def _record_login_posts(page) -> None:
    """
    Log the field *names* of any form POST, never the values.

    This is how we find out whether Strava expects a field we are not sending —
    the empty "country" input being the current suspect. Values are deliberately
    not touched: one of them is the password.
    """
    def on_request(request) -> None:
        if request.method != "POST" or "strava.com" not in request.url:
            return

        try:
            data = request.post_data or ""
        except Exception:  # noqa: BLE001 - some requests expose no body
            data = ""

        names = sorted({pair.split("=", 1)[0] for pair in data.split("&") if pair})
        print(f"\n[network] POST {request.url}")
        print(f"[network] field names sent: {names or '(none / not form-encoded)'}")

    page.on("request", on_request)


def _attempt_staged_login(page, credentials: StravaCredentials) -> None:
    """
    Walk the stages, reporting each one, and stop at the first that needs a human.

    Failures are printed rather than raised: the browser is open and the whole
    point is that you can finish by hand. Whatever was on screen at the point of
    failure is written to backend/output/ — that dump is the only way to tell a
    renamed control apart from a rejected submission.
    """
    if dismiss_cookie_banner(page):
        print("Dismissed the cookie banner.")

    try:
        submit_email(page, credentials.email)
        print("Entered the email and advanced.")
    except LoginFormError as error:
        print(f"\nStalled at the email stage:\n{error}")
        _dump(page, "login_email_stage")
        return

    outcome = choose_password_login(page)
    if outcome == PASSWORD_STAGE_CLICKED:
        print("Switched from the one-time code to password entry.")
    elif outcome == PASSWORD_STAGE_ALREADY_SHOWING:
        print("A password field was already showing — no switch needed.")
    else:
        print(
            "\nCould not find a control to switch to password entry. None of the "
            f"phrasings in USE_PASSWORD_TEXTS matched:\n  {USE_PASSWORD_TEXTS}"
        )
        _dump(page, "login_choice_stage")
        return

    try:
        submit_password(page, credentials.password)
        print("Submitted the password.")
    except LoginFormError as error:
        print(f"\nStalled at the password stage:\n{error}")
        _dump(page, "login_password_stage")


def _dump(page, label: str) -> None:
    summary = dump_login_page(page, label=label)
    print(f"\nWrote what was on screen to:\n  backend/{summary}\n  backend/{summary.with_suffix('.html')}")


if __name__ == "__main__":
    main()
