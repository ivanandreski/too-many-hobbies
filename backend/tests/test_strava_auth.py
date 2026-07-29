"""
Unit tests for Strava OAuth token handling.

These cover the refresh-token grant without any network access: the form fields
posted to Strava, the handling of a rotated refresh token, and the credential
lookup from the environment.
"""

import os
import urllib.parse
from unittest.mock import patch

import pytest

from hobbies.core.env import load_env_file, require_env
from hobbies.features.gear.auth import (
    StravaCredentials,
    authorization_url,
    fetch_access_token,
)
from hobbies.features.gear.constants import (
    CLIENT_ID_ENV_VAR,
    CLIENT_SECRET_ENV_VAR,
    GRANT_TYPE_REFRESH_TOKEN,
    REFRESH_TOKEN_ENV_VAR,
    STRAVA_REQUIRED_SCOPE,
    STRAVA_TOKEN_URL,
)

CREDENTIALS = StravaCredentials(
    client_id="12345",
    client_secret="shhh",
    refresh_token="stored-refresh-token",
)


def _percent_encoded(value: str) -> str:
    """Percent-encode a value the way urlencode does, for substring assertions."""
    return urllib.parse.quote(value, safe="")


def _token_response(refresh_token: str = "stored-refresh-token") -> dict:
    return {
        "token_type": "Bearer",
        "access_token": "fresh-access-token",
        "refresh_token": refresh_token,
        "expires_at": 1_800_000_000,
        "expires_in": 21600,
    }


class TestFetchAccessToken:

    def test_posts_refresh_token_grant_to_strava(self):
        """The refresh grant must carry all four fields Strava requires."""
        with patch(
            "hobbies.features.gear.auth.post_form", return_value=_token_response()
        ) as mock_post:
            access_token = fetch_access_token(CREDENTIALS)

        assert access_token == "fresh-access-token"

        posted_url, posted_fields = mock_post.call_args.args
        assert posted_url == STRAVA_TOKEN_URL
        assert posted_fields == {
            "client_id": "12345",
            "client_secret": "shhh",
            "grant_type": GRANT_TYPE_REFRESH_TOKEN,
            "refresh_token": "stored-refresh-token",
        }

    def test_warns_when_strava_rotates_the_refresh_token(self, capsys):
        """
        A rotated refresh token makes the stored secret stale, and the next run
        would fail. The new token must be printed so it can be saved.
        """
        rotated = _token_response(refresh_token="brand-new-refresh-token")

        with patch("hobbies.features.gear.auth.post_form", return_value=rotated):
            fetch_access_token(CREDENTIALS)

        output = capsys.readouterr().out
        assert "brand-new-refresh-token" in output
        assert REFRESH_TOKEN_ENV_VAR in output

    def test_stays_quiet_when_refresh_token_is_unchanged(self, capsys):
        """The common case must not print a spurious warning."""
        with patch("hobbies.features.gear.auth.post_form", return_value=_token_response()):
            fetch_access_token(CREDENTIALS)

        assert "WARNING" not in capsys.readouterr().out


class TestCredentialLookup:

    def test_reads_all_three_credentials_from_environment(self, monkeypatch):
        monkeypatch.setenv(CLIENT_ID_ENV_VAR, "42")
        monkeypatch.setenv(CLIENT_SECRET_ENV_VAR, "secret")
        monkeypatch.setenv(REFRESH_TOKEN_ENV_VAR, "refresh")

        credentials = StravaCredentials.from_environment()

        assert credentials == StravaCredentials("42", "secret", "refresh")

    def test_names_the_missing_variable(self, monkeypatch):
        """A first-time setup failure should say exactly what to set."""
        monkeypatch.setenv(CLIENT_ID_ENV_VAR, "42")
        monkeypatch.setenv(CLIENT_SECRET_ENV_VAR, "secret")
        monkeypatch.delenv(REFRESH_TOKEN_ENV_VAR, raising=False)

        with pytest.raises(RuntimeError, match=REFRESH_TOKEN_ENV_VAR):
            StravaCredentials.from_environment()


class TestAuthorizationUrl:

    def test_requests_the_scope_that_exposes_gear(self):
        """Without profile:read_all the athlete response has no bikes at all."""
        url = authorization_url("12345")

        assert "client_id=12345" in url
        assert _percent_encoded(STRAVA_REQUIRED_SCOPE) in url
        assert "response_type=code" in url
        assert "approval_prompt=force" in url


class TestEnvFileLoading:

    def test_loads_values_and_ignores_comments_and_blanks(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# a comment\n"
            "\n"
            "STRAVA_TEST_ONE=value-one\n"
            'STRAVA_TEST_TWO="quoted-value"\n',
            encoding="utf-8",
        )
        monkeypatch.delenv("STRAVA_TEST_ONE", raising=False)
        monkeypatch.delenv("STRAVA_TEST_TWO", raising=False)

        loaded_count = load_env_file(env_file)

        assert loaded_count == 2
        assert os.environ["STRAVA_TEST_ONE"] == "value-one"
        assert os.environ["STRAVA_TEST_TWO"] == "quoted-value"

    def test_real_environment_wins_over_file(self, tmp_path, monkeypatch):
        """A CI secret must never be clobbered by a stale local file."""
        env_file = tmp_path / ".env"
        env_file.write_text("STRAVA_TEST_THREE=from-file\n", encoding="utf-8")
        monkeypatch.setenv("STRAVA_TEST_THREE", "from-environment")

        load_env_file(env_file)

        assert require_env("STRAVA_TEST_THREE") == "from-environment"

    def test_missing_file_is_not_an_error(self, tmp_path):
        """Credentials may come purely from the environment."""
        assert load_env_file(tmp_path / "does-not-exist.env") == 0
