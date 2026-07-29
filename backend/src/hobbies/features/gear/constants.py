"""Shared constants for the Strava gear pipeline."""

STRAVA_BASE_URL = "https://www.strava.com"
STRAVA_API_BASE_URL = f"{STRAVA_BASE_URL}/api/v3"

# --- OAuth ----------------------------------------------------------------
# One-time, interactive: grant the app access and get an authorization code.
STRAVA_AUTHORIZE_URL = f"{STRAVA_BASE_URL}/oauth/authorize"

# Non-interactive: swap an authorization code or refresh token for an access token.
STRAVA_TOKEN_URL = f"{STRAVA_API_BASE_URL}/oauth/token"

# Bikes and shoes live on the *detailed* athlete representation, which Strava
# only returns for tokens carrying this scope. A plain "read" token returns the
# summary representation, with no gear at all.
STRAVA_REQUIRED_SCOPE = "profile:read_all"

# Strava only whitelists localhost/127.0.0.1 as redirect targets for local use.
# Nothing listens on this port — the code is copied out of the browser's URL bar.
STRAVA_LOCAL_REDIRECT_URI = "http://localhost/exchange_token"

GRANT_TYPE_REFRESH_TOKEN = "refresh_token"
GRANT_TYPE_AUTHORIZATION_CODE = "authorization_code"

# --- Endpoints ------------------------------------------------------------
# Returns the authenticated athlete, including "bikes" and "shoes" arrays.
STRAVA_ATHLETE_URL = f"{STRAVA_API_BASE_URL}/athlete"

# Detailed gear by id: adds brand_name, model_name, frame_type and description.
STRAVA_GEAR_URL_TEMPLATE = f"{STRAVA_API_BASE_URL}/gear/{{gear_id}}"

# --- Credentials ----------------------------------------------------------
CLIENT_ID_ENV_VAR = "STRAVA_CLIENT_ID"
CLIENT_SECRET_ENV_VAR = "STRAVA_CLIENT_SECRET"
REFRESH_TOKEN_ENV_VAR = "STRAVA_REFRESH_TOKEN"

# --- Response fields ------------------------------------------------------
ATHLETE_BIKES_FIELD = "bikes"

# --- Units ----------------------------------------------------------------
# Strava reports gear distance in metres; bikes.json records kilometres.
METRES_PER_KILOMETRE = 1000

# bikes.json rounds mileage to one decimal place (e.g. 1002.7).
MILEAGE_DECIMAL_PLACES = 1
