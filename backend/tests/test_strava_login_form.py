"""
Browser tests for the staged login driver.

Strava will not show stages two and three without a real account's email —
submitting an unknown address just returns a generic error, by design. So the
flow is exercised against a mock page that reproduces the *shape* of the real
one: a consent overlay, a hidden mobile email field ahead of the visible desktop
one, a bot-trap input beside it, and a password field that only exists after
choosing password entry over a one-time code.

What these tests establish is that the driver targets visible elements, leaves
the honeypot untouched, and finds the switch to password entry. Stage one is
additionally verified against the live site by hand; two and three are only
verified here.

Skipped when Playwright or its browser binary is unavailable.
"""

from pathlib import Path

import pytest

from hobbies.features.strava import login_form
from hobbies.features.strava.login_form import (
    PASSWORD_STAGE_ALREADY_SHOWING,
    PASSWORD_STAGE_CLICKED,
    PASSWORD_STAGE_NOT_FOUND,
    LoginFormError,
    choose_password_login,
    dismiss_cookie_banner,
    ensure_remember_me,
    read_form_error,
    submit_email,
    submit_login,
    submit_password,
)

FIXTURE = Path(__file__).parent / "fixtures" / "strava_login_mock.html"

TEST_EMAIL = "rider@example.com"
TEST_PASSWORD = "not-a-real-password"


@pytest.fixture(scope="module")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("Playwright is not installed")

    playwright = sync_playwright().start()
    try:
        instance = playwright.chromium.launch()
    except Exception as error:  # noqa: BLE001 - any launch failure means skip
        playwright.stop()
        pytest.skip(f"Chromium unavailable: {error}")

    yield instance
    instance.close()
    playwright.stop()


@pytest.fixture(autouse=True)
def fast_stage_waits(monkeypatch):
    """
    Shrink the between-stage settle time for tests.

    The real value exists to let Strava's client-side rendering finish; the mock
    switches stages synchronously, so waiting 2.5s per stage would put the bulk of
    the suite's runtime into sleeping. Production keeps the conservative value.
    """
    monkeypatch.setattr(login_form, "STAGE_SETTLE_MS", 50)
    monkeypatch.setattr(login_form, "VALUE_REGISTER_MS", 20)
    monkeypatch.setattr(login_form, "TYPE_DELAY_MS", 0)
    monkeypatch.setattr(login_form, "SWITCH_WAIT_MS", 3000)


@pytest.fixture
def page(browser):
    page = browser.new_page()
    page.goto(FIXTURE.as_uri())
    yield page
    page.close()


def _log(page) -> dict:
    """What the mock recorded about what was actually driven."""
    return page.evaluate("window.__log")


class TestCookieBanner:

    def test_dismisses_the_consent_dialog(self, page):
        assert dismiss_cookie_banner(page) is True
        assert _log(page)["bannerDismissed"] is True

    def test_reports_false_when_no_banner_is_up(self, page):
        dismiss_cookie_banner(page)

        assert dismiss_cookie_banner(page) is False


class TestEmailStage:

    def test_fills_the_visible_field_not_the_hidden_mobile_one(self, page):
        """
        The hidden #mobile-email comes first in the DOM. Filling it would leave
        the real field empty and the form would ignore the submission.
        """
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)

        assert page.eval_on_selector("#desktop-email", "e => e.value") == TEST_EMAIL
        assert page.eval_on_selector("#mobile-email", "e => e.value") == ""
        assert _log(page)["emailSubmitted"] == TEST_EMAIL

    def test_never_fills_the_bot_trap_input(self, page):
        """The 'country' input carries autocomplete=new-password to bait fillers."""
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)

        assert page.eval_on_selector("#desktop-country", "e => e.value") == ""
        assert page.eval_on_selector("#mobile-country", "e => e.value") == ""

    def test_raises_when_no_email_field_exists(self, page):
        page.evaluate("document.getElementById('stage-email').remove()")

        with pytest.raises(LoginFormError, match="email field"):
            submit_email(page, TEST_EMAIL)

    def test_retries_after_the_first_submission_is_rejected(self, page):
        """
        Strava rejects the first submission of a valid address with a generic
        error, re-renders without the social buttons, then accepts the same
        address. The mock reproduces that, so this covers the retry that makes
        the automated login viable at all.
        """
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)

        log = _log(page)
        assert log["emailAttempts"] == 2, "should have needed a second attempt"
        assert log["emailSubmitted"] == TEST_EMAIL
        assert page.is_visible("#otp-code"), "should have advanced past the email stage"

    def test_clears_the_field_before_retyping(self, page):
        """
        The rejected attempt can leave content behind, and typing into a
        non-empty field appends — producing a malformed address and the same
        generic error on every subsequent try.
        """
        dismiss_cookie_banner(page)
        page.eval_on_selector("#desktop-email", "e => e.value = 'stale-junk'")

        submit_email(page, TEST_EMAIL)

        assert _log(page)["emailSubmitted"] == TEST_EMAIL

    def test_gives_up_after_the_configured_attempts(self, page):
        """A form that rejects every attempt must fail, not loop forever."""
        dismiss_cookie_banner(page)
        page.evaluate("window.__failEmailAttempts = 99")

        with pytest.raises(LoginFormError, match="rejected the email step"):
            submit_email(page, TEST_EMAIL, attempts=2)

        assert _log(page)["emailAttempts"] == 2


class TestPasswordChoice:

    def test_switches_from_the_one_time_code_to_password_entry(self, page):
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)

        # The one-time-code step is showing and there is no password field yet.
        assert page.is_visible("#otp-code")
        assert not page.is_visible("#desktop-password")

        assert choose_password_login(page) == PASSWORD_STAGE_CLICKED
        assert page.is_visible("#desktop-password")

    def test_reports_already_showing_when_a_password_field_is_present(self, page):
        """Some accounts may skip straight to a password; clicking would be wrong."""
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)
        choose_password_login(page)

        assert choose_password_login(page) == PASSWORD_STAGE_ALREADY_SHOWING

    def test_waits_for_a_control_that_mounts_after_a_delay(self, page):
        """
        The failure this replaced: the loop called is_visible(), which does not
        wait despite taking a timeout, so it declared a present "Use password
        instead" button missing while the screen was still rendering.
        """
        dismiss_cookie_banner(page)
        page.evaluate("window.__choiceDelayMs = 1500")
        submit_email(page, TEST_EMAIL)

        # Not on screen yet at this point — the old code gave up right here.
        assert not page.is_visible("#switch-to-password")

        assert choose_password_login(page) == PASSWORD_STAGE_CLICKED
        assert page.is_visible("#desktop-password")

    def test_matches_stravas_actual_button_text(self, page):
        """Guards the exact wording reported from the live site."""
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)
        page.eval_on_selector(
            "#switch-to-password", "e => e.textContent = 'Use password instead'"
        )

        assert choose_password_login(page) == PASSWORD_STAGE_CLICKED

    def test_reports_not_found_when_no_control_matches(self, page):
        """
        Distinct from "already showing". Collapsing the two into False is what made
        the interactive login claim a password field was present when it had in
        fact found nothing — the failure this test exists to prevent.
        """
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)
        page.evaluate("document.getElementById('switch-to-password').remove()")

        assert choose_password_login(page) == PASSWORD_STAGE_NOT_FOUND


class TestPasswordStage:

    def test_fills_and_submits_the_password(self, page):
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)
        choose_password_login(page)
        submit_password(page, TEST_PASSWORD)

        assert _log(page)["passwordSubmitted"] == TEST_PASSWORD

    def test_ticks_remember_me_before_submitting(self, page):
        """
        Without this the login is worthless: Strava issues a session-only cookie
        that dies with the browser, so the stored session fails on the next run.
        The mock hides the checkbox with display:none, as a custom-styled one
        would, so this also covers the fallback that drives it directly.
        """
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)
        choose_password_login(page)

        assert page.eval_on_selector("#desktop_remember_me", "e => e.checked") is False
        submit_password(page, TEST_PASSWORD)

        assert _log(page)["rememberMe"] is True

    def test_remember_me_reports_false_when_the_form_has_no_such_box(self, page):
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)
        choose_password_login(page)
        page.evaluate("document.getElementById('desktop_remember_me').remove()")

        assert ensure_remember_me(page) is False

    def test_reports_the_one_time_code_step_when_the_switch_did_not_happen(self, page):
        """
        Stuck on the code step is a different problem from a renamed selector, and
        the message has to say which — one needs a constants edit, the other needs
        the interactive login.
        """
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)

        with pytest.raises(LoginFormError, match="one-time-code step"):
            submit_password(page, TEST_PASSWORD)


class TestFullFlow:

    def test_drives_all_three_stages_end_to_end(self, page):
        submit_login(page, TEST_EMAIL, TEST_PASSWORD)

        log = _log(page)
        assert log["bannerDismissed"] is True
        assert log["emailSubmitted"] == TEST_EMAIL
        assert log["passwordSubmitted"] == TEST_PASSWORD
        assert page.is_visible("#result")


class TestFormError:

    def test_returns_none_when_no_error_is_shown(self, page):
        assert read_form_error(page) is None

    def test_reads_a_rendered_error(self, page):
        page.evaluate(
            "document.body.insertAdjacentHTML('afterbegin',"
            "'<div role=\"alert\">An unexpected error occurred. Please try again.</div>')"
        )

        assert read_form_error(page) == "An unexpected error occurred. Please try again."


class TestHiddenDuplicates:
    """
    This login page renders a hidden mobile copy of its controls, ahead of the
    visible desktop one. That is what made a present "Use password instead"
    button report as missing: `.first` resolved to the copy nobody can see.
    """

    def test_clicks_the_visible_switch_not_the_hidden_duplicate(self, page):
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)

        assert choose_password_login(page) == PASSWORD_STAGE_CLICKED

        log = _log(page)
        assert log["clickedVisibleSwitch"] is True
        assert log["clickedHiddenSwitch"] is False, "clicked the hidden mobile copy"

    def test_reports_not_found_when_only_hidden_copies_exist(self, page):
        """Every match hidden is a distinct diagnosis from no match at all."""
        dismiss_cookie_banner(page)
        submit_email(page, TEST_EMAIL)
        page.eval_on_selector("#switch-to-password", "e => e.style.display = 'none'")

        assert choose_password_login(page) == PASSWORD_STAGE_NOT_FOUND
        assert _log(page)["clickedHiddenSwitch"] is False
