"""Generic HTTP fetcher. Returns raw response bytes or text."""

import urllib.request


def fetch_url(url: str, timeout: int = 10) -> str:
    """Fetch a URL and return the response body as a UTF-8 string."""
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8")
