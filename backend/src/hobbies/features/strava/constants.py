"""
Constants for the Strava scraping pipelines.

Strava's public API moved behind a paid subscription in June 2026, so this
feature reads the logged-in web pages instead. Everything version-fragile lives
here: URLs, the text anchors used to find each section, and the credential
variable names.
"""

STRAVA_BASE_URL = "https://www.strava.com"

# --- Pages ----------------------------------------------------------------
STRAVA_LOGIN_URL = f"{STRAVA_BASE_URL}/login"

# Athlete profile: carries the year totals, the all-time totals and the gear list.
STRAVA_PROFILE_URL_TEMPLATE = f"{STRAVA_BASE_URL}/athletes/{{athlete_id}}"

# Activity list, paginated. Page 1 is the newest activities.
STRAVA_TRAINING_URL_TEMPLATE = f"{STRAVA_BASE_URL}/athlete/training?page={{page}}"

# The same list filtered to one sport. Verified against the page's own search
# form, whose sport_type select offers "Ride", "Run", "Hike", … as values.
#
# Filtering matters for more than tidiness: unfiltered, twelve pages of this
# account's history held 240 rides and not one run, because runs are seasonal.
# Asking for runs directly finds them on the first page.
STRAVA_TRAINING_SPORT_URL_TEMPLATE = (
    f"{STRAVA_BASE_URL}/athlete/training?sport_type={{sport_type}}&page={{page}}"
)

# sport_type filter value per sport key.
SPORT_TYPE_FILTERS = {
    "ride": "Ride",
    "run": "Run",
}

# Loading this while logged out redirects to the login page — that redirect is
# how we detect an expired session.
STRAVA_SESSION_CHECK_URL = f"{STRAVA_BASE_URL}/athlete/training"

# --- Login form -----------------------------------------------------------
# Strava's login is staged: enter the email, submit, then choose "use password"
# rather than a one-time code, then enter the password. There is no single form
# holding both fields.
#
# Two traps in this page, both verified by inspecting it:
#   * The email input exists twice — a hidden #mobile-email and the visible
#     #desktop-email — and the hidden one comes first in the DOM. Every selector
#     below is therefore matched against visible elements only.
#   * A text input named "country" sits beside the email carrying
#     autocomplete="new-password". It is a bot trap. Never fill it.
COOKIE_DISMISS_SELECTORS = [
    # Prefer declining: consent has nothing to do with the session cookie.
    "#CybotCookiebotDialogBodyButtonDecline",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "button:has-text('Reject Non-Essential')",
    "button:has-text('Accept All')",
]

EMAIL_INPUT_SELECTORS = [
    "#desktop-email",
    "input[type='email'][name='email']:visible",
    "input[type='email']:visible",
]

EMAIL_SUBMIT_SELECTORS = [
    "#desktop-login-button",
    "button[type='submit']:visible",
]

# Second stage: Strava offers a one-time emailed code by default, so this is the
# control that switches to password entry. Matched on text, case-insensitively,
# because the wording is more stable than the generated class names.
USE_PASSWORD_TEXTS = [
    "use password",
    "password instead",
    "log in with password",
    "sign in with password",
    "enter password",
    "use my password",
]

PASSWORD_INPUT_SELECTORS = [
    "#desktop-password",
    "input[type='password'][name='password']:visible",
    "input[type='password']:visible",
]

# "Remember me" is what makes the login worth saving. Without it Strava issues a
# session-only cookie that dies with the browser, so every run would need a fresh
# interactive sign-in. Often a custom-styled checkbox, hence visually hidden.
REMEMBER_ME_SELECTORS = [
    "#desktop_remember_me",
    "input[name='desktop_remember_me']",
    "input[type='checkbox'][name*='remember']",
    "input[type='checkbox'][id*='remember']",
]

PASSWORD_SUBMIT_SELECTORS = [
    "#desktop-login-button",
    "button[type='submit']:visible",
]

# If these appear with no password field, we landed on the one-time-code step and
# cannot continue unattended.
OTP_HINT_TEXTS = ["one-time", "one time code", "verification code", "check your email"]

# Where Strava renders a login failure. Verified: submitting an unknown address
# yields "An unexpected error occurred" rather than saying the account is unknown,
# so the text is worth reporting verbatim instead of guessing at the cause.
FORM_ERROR_SELECTORS = [
    "[role='alert']:visible",
    ".alert-message:visible",
    "[class*='error']:visible",
]

# --- Credentials ----------------------------------------------------------
ATHLETE_ID_ENV_VAR = "STRAVA_ATHLETE_ID"
EMAIL_ENV_VAR = "STRAVA_EMAIL"
PASSWORD_ENV_VAR = "STRAVA_PASSWORD"

# Cookie jar produced by a successful login. Live credential — gitignored.
SESSION_FILE_NAME = ".strava-session.json"

# --- Text anchors ---------------------------------------------------------
# Extraction is anchored on the words Strava renders, not on CSS class names.
# Class names are generated and churn between deploys; these headings are user
# facing and change far less often. Each is matched case-insensitively.
YEAR_SECTION_HEADINGS = ["this year", "year to date", "ytd"]
ALL_TIME_SECTION_HEADINGS = ["all-time", "all time"]
GEAR_SECTION_HEADINGS = ["gear", "bikes", "my bikes"]

# Labels beside each number inside a totals section.
DISTANCE_LABELS = ["distance"]
TIME_LABELS = ["time", "moving time"]
COUNT_LABELS = ["activities", "rides", "runs", "count"]

# Sport tab buttons name themselves via a title attribute, and their class gives
# the panel index: button.sport-0-tab[title="Ride"] pairs with div.sport-0 and
# tbody#sport-0-ytd. Verified against the live profile page.
SPORT_TAB_TITLES = {
    "ride": ["ride"],
    "run": ["run"],
}

# Marks the tbody holding the selected year's figures.
YEAR_TBODY_ID_SUFFIX = "-ytd"

# The single-row header tbody that precedes the lifetime figures.
ALL_TIME_HEADER = "all-time"

# The totals panels are switched with a row of sport *icons*, which carry no
# visible text. So a control is matched on any of its identifying attributes —
# accessible name, title, data-* value, class name, icon reference — not just
# its text content. Keywords are matched case-insensitively as substrings.
SPORT_SELECTOR_KEYWORDS = {
    "ride": ["ride", "bike", "bicycle", "cycl"],
    "run": ["run", "shoe", "footwear"],
}

# Attributes inspected on a candidate control and on any icon nested inside it.
# Order matters only for diagnostics; a hit on any one is enough.
SPORT_SELECTOR_ATTRIBUTES = [
    "aria-label",
    "title",
    "alt",
    "data-sport",
    "data-sport-type",
    "data-activity-type",
    "data-testid",
    "href",
    "id",
    "class",
]

# --- Sport classification -------------------------------------------------
# Strava's sport_type strings are numerous ("Ride", "Virtual Ride", "Gravel
# Ride", "Mountain Bike Ride", "E-Bike Ride", "Trail Run", …). Matching on a
# substring covers the variants without enumerating all of them. Anything that
# matches neither list is ignored, per the requirement.
RIDE_SPORT_KEYWORDS = ["ride", "cycl", "bike", "biking"]
RUN_SPORT_KEYWORDS = ["run"]

# Exact cell values that name a sport rather than an activity. An activity row
# has a "type" cell alongside the title, and without this list a row whose type
# cell comes first would be titled "Ride". Matched on the whole cell, case
# insensitively — a substring test would wrongly discard "Morning Ride".
SPORT_CELL_LABELS = {
    "ride", "rides", "virtual ride", "e-bike ride", "ebike ride", "gravel ride",
    "mountain bike ride", "mtb ride", "handcycle", "velomobile",
    "run", "runs", "trail run", "virtual run", "treadmill run",
    "swim", "walk", "hike", "workout", "weight training", "yoga", "rowing",
    "alpine ski", "nordic ski", "snowboard", "elliptical", "stair stepper",
}

# Virtual/indoor rides are still rides; listed separately so it is easy to
# exclude them later by removing a keyword above.

# --- Units ----------------------------------------------------------------
METRES_PER_KILOMETRE = 1000
METRES_PER_MILE = 1609.344
MILEAGE_DECIMAL_PLACES = 1
