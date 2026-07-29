"""
Strava OAuth2 token handling.

Strava's API needs a bearer token that expires after six hours, so it cannot be
stored and reused indefinitely. The long-lived credential is a *refresh token*,
which this module swaps for a fresh access token on every run. That keeps the
pipeline non-interactive and safe to run from CI.

Getting the initial refresh token is a one-time manual step; see
authorization_url() and exchange_authorization_code() below, or run:

    python -m hobbies.features.gear.authorize
"""

from dataclasses import dataclass
import urllib.parse

from hobbies.core.env import require_env
from hobbies.core.http import post_form
from hobbies.features.gear.constants import (
    CLIENT_ID_ENV_VAR,
    CLIENT_SECRET_ENV_VAR,
    GRANT_TYPE_AUTHORIZATION_CODE,
    GRANT_TYPE_REFRESH_TOKEN,
    REFRESH_TOKEN_ENV_VAR,
    STRAVA_AUTHORIZE_URL,
    STRAVA_LOCAL_REDIRECT_URI,
    STRAVA_REQUIRED_SCOPE,
    STRAVA_TOKEN_URL,
)


@dataclass(frozen=True)
class StravaCredentials:
    """The three secrets needed to mint an access token without user interaction."""
    client_id: str
    client_secret: str
    refresh_token: str

    @classmethod
    def from_environment(cls) -> "StravaCredentials":
        """
        Read credentials from environment variables.

        Raises:
            RuntimeError: If any variable is missing, naming which one.
        """
        return cls(
            client_id=require_env(CLIENT_ID_ENV_VAR),
            client_secret=require_env(CLIENT_SECRET_ENV_VAR),
            refresh_token=require_env(REFRESH_TOKEN_ENV_VAR),
        )


@dataclass(frozen=True)
class StravaTokens:
    """A token response from Strava's OAuth endpoint."""
    access_token: str
    refresh_token: str
    expires_at: int

    @classmethod
    def from_response(cls, response: dict) -> "StravaTokens":
        return cls(
            access_token=response["access_token"],
            refresh_token=response["refresh_token"],
            expires_at=response.get("expires_at", 0),
        )


def fetch_access_token(credentials: StravaCredentials) -> str:
    """
    Exchange a refresh token for a short-lived access token.

    Strava may return a *new* refresh token in this response. When it does, the
    stored secret is now stale and the next run will fail with a 400, so this
    warns loudly rather than failing silently later.

    Args:
        credentials: Client id/secret plus the stored refresh token.

    Returns:
        A bearer access token, valid for roughly six hours.
    """
    tokens = refresh_tokens(credentials)

    if tokens.refresh_token != credentials.refresh_token:
        print(
            f"[strava] WARNING: Strava rotated the refresh token. Update "
            f"{REFRESH_TOKEN_ENV_VAR} to:\n    {tokens.refresh_token}"
        )

    return tokens.access_token


def refresh_tokens(credentials: StravaCredentials) -> StravaTokens:
    """POST the refresh-token grant and return the full token response."""
    response = post_form(
        STRAVA_TOKEN_URL,
        {
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "grant_type": GRANT_TYPE_REFRESH_TOKEN,
            "refresh_token": credentials.refresh_token,
        },
    )
    return StravaTokens.from_response(response)


# ---------------------------------------------------------------------------
# One-time interactive setup
# ---------------------------------------------------------------------------

def authorization_url(client_id: str) -> str:
    """
    Build the URL to open in a browser to grant this app access.

    After approving, Strava redirects to the (non-listening) local redirect URI
    with a ?code=... parameter. Copy that code and pass it to
    exchange_authorization_code() to get the long-lived refresh token.
    """
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": STRAVA_LOCAL_REDIRECT_URI,
            "response_type": "code",
            "scope": STRAVA_REQUIRED_SCOPE,
            # Always show the consent screen, so re-running after a scope change
            # actually re-grants rather than silently reusing the old scope.
            "approval_prompt": "force",
        }
    )
    return f"{STRAVA_AUTHORIZE_URL}?{query}"


def exchange_authorization_code(
    client_id: str, client_secret: str, authorization_code: str
) -> StravaTokens:
    """Swap a one-time authorization code for an access + refresh token pair."""
    response = post_form(
        STRAVA_TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": authorization_code,
            "grant_type": GRANT_TYPE_AUTHORIZATION_CODE,
        },
    )
    return StravaTokens.from_response(response)
