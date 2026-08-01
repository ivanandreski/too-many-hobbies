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

# Loading this while logged out redirects to the login page — that redirect is
# how we detect an expired session.
STRAVA_SESSION_CHECK_URL = f"{STRAVA_BASE_URL}/athlete/training"

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
