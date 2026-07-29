"""
One-time interactive Strava authorization.

Run this once to turn a Strava API application's client id/secret into the
long-lived refresh token that the gear pipeline needs:

    cd backend
    .venv/bin/python -m hobbies.features.gear.authorize

Prerequisites: create an app at https://www.strava.com/settings/api and set its
"Authorization Callback Domain" to `localhost`. Put the client id and secret in
backend/.env, then run this and follow the prompts.

Nothing listens on the redirect URI — the browser will fail to load the page,
which is expected. The authorization code is in that failed URL's query string.
"""

import urllib.parse

from hobbies.core.env import DEFAULT_ENV_FILENAME, load_env_file, require_env
from hobbies.features.gear.auth import authorization_url, exchange_authorization_code
from hobbies.features.gear.constants import (
    CLIENT_ID_ENV_VAR,
    CLIENT_SECRET_ENV_VAR,
    REFRESH_TOKEN_ENV_VAR,
    STRAVA_REQUIRED_SCOPE,
)

AUTHORIZATION_CODE_PARAMETER = "code"


def _extract_authorization_code(pasted_input: str) -> str:
    """
    Pull the authorization code out of whatever the user pasted.

    Accepts either the bare code or the whole redirected URL, since copying the
    full URL out of the address bar is the path of least resistance.
    """
    pasted_input = pasted_input.strip()
    if AUTHORIZATION_CODE_PARAMETER not in pasted_input:
        return pasted_input

    query_string = urllib.parse.urlparse(pasted_input).query
    query_parameters = urllib.parse.parse_qs(query_string)
    codes = query_parameters.get(AUTHORIZATION_CODE_PARAMETER, [])
    return codes[0] if codes else pasted_input


def main() -> None:
    load_env_file(DEFAULT_ENV_FILENAME)
    client_id = require_env(CLIENT_ID_ENV_VAR)
    client_secret = require_env(CLIENT_SECRET_ENV_VAR)

    print("1. Open this URL in your browser and click Authorize:\n")
    print(f"   {authorization_url(client_id)}\n")
    print(
        f"   (Requesting the '{STRAVA_REQUIRED_SCOPE}' scope — without it Strava\n"
        f"    returns a summary athlete with no bikes.)\n"
    )
    print("2. The browser will fail to load a localhost page. That is expected.")
    print("   Copy the whole URL from the address bar, or just the 'code' value.\n")

    pasted_input = input("Paste it here: ")
    authorization_code = _extract_authorization_code(pasted_input)
    if not authorization_code:
        raise SystemExit("No authorization code provided.")

    tokens = exchange_authorization_code(client_id, client_secret, authorization_code)

    print(f"\n3. Success. Add this line to backend/{DEFAULT_ENV_FILENAME}:\n")
    print(f"   {REFRESH_TOKEN_ENV_VAR}={tokens.refresh_token}\n")
    print(
        "   Authorization codes are single-use, so re-run this script if you\n"
        "   need to do it again. The refresh token itself is long-lived."
    )


if __name__ == "__main__":
    main()
