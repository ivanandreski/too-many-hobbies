"""
JSON-over-HTTP helpers for authenticated APIs.

core/fetcher.py covers the simple case: GET a URL, get text back. Talking to an
API needs a little more — request headers for bearer tokens, form-encoded POSTs
for OAuth token exchange, and JSON decoding with useful errors when a call
fails. All stdlib, no new dependencies.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_TIMEOUT_SECONDS = 15


class HttpError(RuntimeError):
    """
    An HTTP request returned a non-2xx status.

    Carries the response body, since APIs put the useful part of the failure
    there — a bare "HTTP 401" does not distinguish an expired token from a
    missing scope.
    """

    def __init__(self, status_code: int, url: str, body: str) -> None:
        super().__init__(f"HTTP {status_code} from {url}: {body}")
        self.status_code = status_code
        self.url = url
        self.body = body


def get_text(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """
    GET a URL and return the raw response body as text.

    Pipelines use this rather than get_json() so their fetch step stays a plain
    "give me the response body" call and their parse step owns decoding — the
    same split the RSS-based pipelines use.

    Args:
        url:     Endpoint to call.
        headers: Optional request headers, e.g. an Authorization bearer token.
        timeout: Socket timeout in seconds.

    Returns:
        The response body, decoded as UTF-8.

    Raises:
        HttpError: If the response status is not 2xx.
    """
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    return _send(request, timeout)


def get_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict | list:
    """
    GET a URL and decode the JSON response.

    Raises:
        HttpError: If the response status is not 2xx.
    """
    return json.loads(get_text(url, headers, timeout))


def post_form(
    url: str,
    form_fields: dict[str, str],
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict | list:
    """
    POST form-encoded fields and decode the JSON response.

    Args:
        url:         Endpoint to call.
        form_fields: Fields to URL-encode into the request body.
        timeout:     Socket timeout in seconds.

    Returns:
        The decoded JSON body.

    Raises:
        HttpError: If the response status is not 2xx.
    """
    body = urllib.parse.urlencode(form_fields).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return json.loads(_send(request, timeout))


def _send(request: urllib.request.Request, timeout: int) -> str:
    """Send a prepared request, surfacing error bodies as HttpError."""
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise HttpError(error.code, request.full_url, error_body) from error
