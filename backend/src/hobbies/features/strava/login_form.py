"""
Driving Strava's staged login form.

Strava does not present one form with an email and a password. It asks for the
email, then offers a one-time emailed code, and only reaches a password field
once you explicitly choose "use password instead". Each stage is a separate
render, so each needs its own wait, and a failure needs to say which stage it
failed at — "login failed" is useless when there are three places to fail.

Shared by the scraper (unattended) and login.py (interactive), so both drive the
form identically and a fix here fixes both.
"""

from pathlib import Path

from hobbies.features.strava.constants import (
    COOKIE_DISMISS_SELECTORS,
    FORM_ERROR_SELECTORS,
    EMAIL_INPUT_SELECTORS,
    EMAIL_SUBMIT_SELECTORS,
    OTP_HINT_TEXTS,
    PASSWORD_INPUT_SELECTORS,
    PASSWORD_SUBMIT_SELECTORS,
    REMEMBER_ME_SELECTORS,
    USE_PASSWORD_TEXTS,
)

STAGE_SETTLE_MS = 2500
CLICK_TIMEOUT_MS = 5000

# Strava rejects the first email submission with a generic error and re-renders
# the form; the same address is accepted on the next try. Two attempts covers the
# observed behaviour with one to spare.
EMAIL_ATTEMPTS = 3

# Typing delay per character. fill() sets the value in one shot, which a
# JS-controlled form can miss; typing produces the keystroke events it listens for.
TYPE_DELAY_MS = 45

# Pause between typing a value and submitting, so a JS-controlled form registers it.
VALUE_REGISTER_MS = 400

# How long to wait for the screen after the email step to mount. Must be a real
# wait: is_visible() returns immediately and ignores its timeout argument, which
# is what made a present "Use password instead" button look absent.
SWITCH_WAIT_MS = 10000

# Outcomes of choose_password_login. Previously it returned a bare False for both
# "a password field was already showing" and "no control matched", which made the
# interactive login report the wrong reason for a failure.
PASSWORD_STAGE_ALREADY_SHOWING = "already-showing"
PASSWORD_STAGE_CLICKED = "clicked"
PASSWORD_STAGE_NOT_FOUND = "not-found"


class LoginFormError(RuntimeError):
    """A stage of the login form could not be driven."""


def dismiss_cookie_banner(page) -> bool:
    """
    Close the consent dialog if it is up.

    It overlays the page, so a click on the login button silently lands on the
    banner instead. Declining is preferred — consent has no bearing on the
    session cookie we are here for.
    """
    for selector in COOKIE_DISMISS_SELECTORS:
        try:
            element = page.locator(selector).first
            if element.is_visible(timeout=1000):
                element.click(timeout=CLICK_TIMEOUT_MS)
                page.wait_for_timeout(800)
                return True
        except Exception:  # noqa: BLE001 - absence is the common case
            continue
    return False


def submit_login(page, email: str, password: str) -> None:
    """
    Drive all three stages: email, switch to password, password.

    Raises:
        LoginFormError: Naming the stage that failed, so the caller can tell an
                        expired selector apart from a challenge.
    """
    dismiss_cookie_banner(page)

    submit_email(page, email)
    choose_password_login(page)
    submit_password(page, password)


def submit_email(page, email: str, attempts: int = EMAIL_ATTEMPTS) -> None:
    """
    Enter the email and advance to the next stage, retrying on error.

    The retry is not defensive padding — it is the documented behaviour of this
    form. Strava rejects the first submission with a generic "unexpected error"
    and re-renders the page (visibly dropping the social sign-in buttons); the
    same address then submits cleanly. Reproduced by hand as well as here.

    Raises:
        LoginFormError: If the field is missing, or every attempt is rejected.
    """
    last_error: str | None = None

    for attempt in range(1, attempts + 1):
        _enter_email_once(page, email)

        last_error = read_form_error(page)
        if not last_error:
            if attempt > 1:
                print(f"[strava] email accepted on attempt {attempt}")
            return

        print(
            f"[strava] email attempt {attempt} rejected ({last_error}) — "
            "this form rejects the first submission; retrying"
        )
        page.wait_for_timeout(STAGE_SETTLE_MS)

    raise LoginFormError(
        f"Strava rejected the email step {attempts} times. Last message: {last_error}\n"
        "That message is generic — it covers an unrecognised address, a rate "
        "limit, and blocked automation alike. Check the page dump for what was "
        "actually on screen."
    )


def _enter_email_once(page, email: str) -> None:
    """
    One attempt: clear the field, type the address, submit.

    Clearing first matters. The field can arrive with content — restored
    localStorage, or a value left by a rejected attempt — and typing into it
    appends, producing a malformed address and the same generic error.
    """
    field = _first_visible(page, EMAIL_INPUT_SELECTORS)
    if field is None:
        raise LoginFormError(
            "No visible email field on the login page. The form markup has "
            "changed — update EMAIL_INPUT_SELECTORS in constants.py."
        )

    field.click(timeout=CLICK_TIMEOUT_MS)
    field.fill("")
    field.press_sequentially(email, delay=TYPE_DELAY_MS)
    # Deliberately not touching the adjacent "country" input.

    # Give the form a moment to register the value before submitting.
    page.wait_for_timeout(VALUE_REGISTER_MS)

    entered = (field.input_value() or "").strip()
    if entered != email:
        raise LoginFormError(
            f"The email field holds {entered!r} rather than the address given. "
            "The form is rejecting programmatic input."
        )

    button = _first_visible(page, EMAIL_SUBMIT_SELECTORS)
    if button is None:
        raise LoginFormError("Email entered but no visible submit button was found.")

    button.click(timeout=CLICK_TIMEOUT_MS)
    page.wait_for_timeout(STAGE_SETTLE_MS)


def switch_control_selector(visible_only: bool = True) -> str:
    """
    One selector matching any phrasing of the "use password" control.

    visible_only is on by default and matters as much here as it does for the
    email field: this page ships hidden mobile duplicates of its controls, and
    they come first in the DOM. Without it, `.first` resolves to the hidden copy
    and reports the control missing while it is plainly on screen.

    Pass visible_only=False only to count all matches for diagnostics.
    """
    suffix = ":visible" if visible_only else ""
    return ", ".join(
        f"{part}{suffix}"
        for text in USE_PASSWORD_TEXTS
        for part in (
            f"button:has-text('{text}')",
            f"a:has-text('{text}')",
            f"[role='button']:has-text('{text}')",
        )
    )


def choose_password_login(page) -> str:
    """
    Switch from the one-time-code offer to password entry.

    Waits for the next screen before deciding anything. This previously looped
    over candidate selectors calling is_visible() — which, contrary to its
    signature, does not wait — so the whole loop completed in milliseconds while
    the one-time-code screen was still mounting, and a "Use password instead"
    button that was plainly there was reported missing.

    Returns PASSWORD_STAGE_ALREADY_SHOWING, PASSWORD_STAGE_CLICKED or
    PASSWORD_STAGE_NOT_FOUND. Three outcomes, not a boolean: "already showing"
    and "no control found" are opposite situations, and collapsing them made the
    interactive login report a success when it had found nothing.
    """
    switch_selector = switch_control_selector()

    # Whichever arrives first decides the branch: some accounts may go straight to
    # a password field, others land on the code screen with a switch control.
    try:
        page.locator(", ".join([*PASSWORD_INPUT_SELECTORS, switch_selector])).first.wait_for(
            state="visible", timeout=SWITCH_WAIT_MS
        )
    except Exception:  # noqa: BLE001 - fall through and report accurately
        pass

    if _first_visible(page, PASSWORD_INPUT_SELECTORS) is not None:
        return PASSWORD_STAGE_ALREADY_SHOWING

    try:
        control = page.locator(switch_selector).first
        if control.count() > 0:
            control.click(timeout=CLICK_TIMEOUT_MS)
            page.wait_for_timeout(STAGE_SETTLE_MS)
            return PASSWORD_STAGE_CLICKED
    except Exception as error:  # noqa: BLE001 - report rather than swallow
        print(f"[strava] could not click the password switch: {error}")

    _report_missing_switch(page)
    return PASSWORD_STAGE_NOT_FOUND


def _report_missing_switch(page) -> None:
    """
    Say why nothing was clicked, rather than only that nothing was.

    The distinction that matters: a control that exists but is invisible means we
    matched a hidden duplicate, while zero matches means the wording changed.
    """
    try:
        total = page.locator(switch_control_selector(visible_only=False)).count()
        visible = page.locator(switch_control_selector()).count()
    except Exception:  # noqa: BLE001 - diagnostics must never raise
        return

    print(
        f"[strava] no password switch clicked — {total} element(s) match the "
        f"expected wording, {visible} of them visible."
    )
    if total > 0 and visible == 0:
        print(
            "[strava] every match is hidden, so the visible control uses different "
            "wording or sits in another frame."
        )


def ensure_remember_me(page) -> bool:
    """
    Tick "Remember me" if the form offers it.

    This is what decides whether a login is worth saving. Unticked, Strava issues
    a session-only cookie that dies with the browser, so the stored session is
    useless on the next run and every scrape would need an interactive sign-in.

    Returns whether the box ended up checked.
    """
    for selector in REMEMBER_ME_SELECTORS:
        try:
            box = page.locator(selector).first
            if box.count() == 0:
                continue
            if box.is_checked():
                return True

            try:
                box.check(timeout=2000)
            except Exception:  # noqa: BLE001 - usually "element is not visible"
                # Custom-styled checkboxes hide the real input and show a label,
                # so drive it directly rather than through a synthetic click.
                box.evaluate(
                    "el => { el.checked = true; "
                    "el.dispatchEvent(new Event('input', {bubbles: true})); "
                    "el.dispatchEvent(new Event('change', {bubbles: true})); }"
                )
            return box.is_checked()
        except Exception:  # noqa: BLE001 - try the next candidate
            continue
    return False


def submit_password(page, password: str) -> None:
    """Fill the password, ask to be remembered, and log in."""
    field = _first_visible(page, PASSWORD_INPUT_SELECTORS)
    if field is None:
        raise LoginFormError(_no_password_field_message(page))

    field.click(timeout=CLICK_TIMEOUT_MS)
    field.press_sequentially(password, delay=TYPE_DELAY_MS)

    if not ensure_remember_me(page):
        # Not fatal, but the resulting session will not outlive the browser.
        print(
            "[strava] WARNING: could not tick 'Remember me'. Strava will issue a "
            "session-only cookie, so the saved session will not work next run."
        )

    button = _first_visible(page, PASSWORD_SUBMIT_SELECTORS)
    if button is None:
        raise LoginFormError("Password entered but no visible submit button was found.")

    button.click(timeout=CLICK_TIMEOUT_MS)
    page.wait_for_timeout(STAGE_SETTLE_MS)


def read_form_error(page) -> str | None:
    """
    Return the error Strava is showing, if any.

    Worth surfacing: the failure modes are indistinguishable from the outside
    otherwise. A wrong password, a rate limit and a bot challenge all just leave
    you on /login, but the page itself says which.
    """
    for selector in FORM_ERROR_SELECTORS:
        try:
            element = page.locator(selector).first
            if element.is_visible(timeout=800):
                message = (element.inner_text() or "").strip()
                if message:
                    return " ".join(message.split())
        except Exception:  # noqa: BLE001 - no error shown is the good case
            continue
    return None


def dump_login_page(page, output_dir: str | Path = "output", label: str = "login") -> Path:
    """
    Write what is currently on screen to disk, for diagnosing a stuck stage.

    Saves the full HTML plus a short readable summary — visible text, every
    input, every button — because the useful question after a failure is "what
    was actually rendered", and neither a screenshot nor an exception answers it.

    Returns the path of the summary file.
    """
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    html_path = directory / f"{label}_page.html"
    summary_path = directory / f"{label}_page.txt"

    try:
        html_path.write_text(page.content(), encoding="utf-8")
    except Exception:  # noqa: BLE001 - diagnostics are best-effort
        pass

    lines = [f"url: {_safe(lambda: page.url)}", f"title: {_safe(lambda: page.title())}", ""]

    lines.append("--- visible text ---")
    lines.append(_safe(lambda: " / ".join(
        line.strip() for line in page.inner_text("body").splitlines() if line.strip()
    ))[:4000])

    lines += ["", "--- inputs ---"]
    for entry in _safe_eval(page, """() => [...document.querySelectorAll('input')].map(i => ({
        type: i.type, name: i.name, id: i.id, placeholder: i.placeholder,
        autocomplete: i.autocomplete, visible: !!(i.offsetWidth || i.offsetHeight),
        hasValue: !!i.value}))""", []):
        lines.append(f"  {entry}")

    lines += ["", "--- buttons and links ---"]
    for entry in _safe_eval(page, """() => [...document.querySelectorAll('button,a,[role=button]')]
        .filter(e => (e.offsetWidth || e.offsetHeight))
        .map(e => ({tag: e.tagName.toLowerCase(), text: (e.innerText||'').trim().slice(0,60),
                    id: e.id, type: e.getAttribute('type')}))
        .filter(e => e.text)""", []):
        lines.append(f"  {entry}")

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def _safe(getter, default: str = "") -> str:
    try:
        return getter() or default
    except Exception:  # noqa: BLE001 - diagnostics must never raise
        return default


def _safe_eval(page, script: str, default):
    try:
        return page.evaluate(script)
    except Exception:  # noqa: BLE001 - diagnostics must never raise
        return default


def _no_password_field_message(page) -> str:
    """Distinguish landing on the one-time-code step from a changed selector."""
    try:
        body_text = page.inner_text("body").lower()
    except Exception:  # noqa: BLE001 - diagnostics must not mask the real failure
        body_text = ""

    if any(hint in body_text for hint in OTP_HINT_TEXTS):
        return (
            "Stopped on Strava's one-time-code step — the switch to password "
            "entry did not take. Either USE_PASSWORD_TEXTS in constants.py no "
            "longer matches the button, or the account was offered a code only. "
            "Run the interactive login and complete it by hand:\n"
            "    .venv/bin/python -m hobbies.features.strava.login"
        )

    return (
        "No visible password field after choosing password login. The form "
        "markup has probably changed — update PASSWORD_INPUT_SELECTORS in "
        "constants.py, or run the interactive login to see the page."
    )


def _first_visible(page, selectors: list[str]):
    """
    Return the first visible element matching any selector.

    Visibility is the point: the login page renders a hidden mobile copy of the
    email field ahead of the desktop one, so taking the first *match* fills an
    element the user can never see and the form ignores.
    """
    for selector in selectors:
        try:
            element = page.locator(selector).first
            if element.is_visible(timeout=1200):
                return element
        except Exception:  # noqa: BLE001 - a missing selector is expected
            continue
    return None
