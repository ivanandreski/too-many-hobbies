"""
Headless-browser fetcher for pages whose content is rendered by JavaScript.

The plain urllib fetcher in core/fetcher.py is enough for RSS feeds, but some
pages (e.g. a Letterboxd profile) ship placeholder markup and only swap in the
real content once client-side scripts run. This fetcher drives a real Chromium
via Playwright so the returned HTML is the fully rendered DOM.

Requires the browser binary to be installed once per machine:
    playwright install chromium
"""

DEFAULT_TIMEOUT_MS = 30_000

# Large enough that lazily-loaded content near the top of the page is in view.
DEFAULT_VIEWPORT = {"width": 1400, "height": 1200}


def fetch_rendered_html(
    url: str,
    wait_for_selector: str | None = None,
    wait_for_function: str | None = None,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> str:
    """
    Load a URL in headless Chromium and return the rendered HTML.

    Args:
        url:               Page to load.
        wait_for_selector: Optional CSS selector to wait for before reading the
                           DOM. Use this to wait until the region you care about
                           has been rendered at all.
        wait_for_function: Optional JavaScript expression (a function body
                           returning a boolean) polled until it returns true.
                           Use this to wait until placeholder content has been
                           replaced by the real thing.
        timeout_ms:        Per-wait timeout in milliseconds.

    Returns:
        The page's rendered HTML as a string.

    Raises:
        RuntimeError: If Playwright is not installed.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment problem, not logic
        raise RuntimeError(
            "Playwright is required to fetch JavaScript-rendered pages. "
            "Install it with: pip install playwright && playwright install chromium"
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport=DEFAULT_VIEWPORT)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            if wait_for_selector:
                page.wait_for_selector(wait_for_selector, timeout=timeout_ms)

            if wait_for_function:
                page.wait_for_function(wait_for_function, timeout=timeout_ms)

            return page.content()
        finally:
            browser.close()
