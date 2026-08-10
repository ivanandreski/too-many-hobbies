"""
Reusable authenticated browser session.

core/rendered_fetcher.py handles one-shot anonymous page loads. Scraping a site
that requires a login needs more: a cookie jar that survives between runs, so a
single sign-in covers many later invocations.

Playwright calls that jar a "storage state" — a JSON blob of cookies and local
storage. This module loads it on start and writes it back on exit, so a session
established once (interactively, if the site challenges us) keeps working until
the site expires it.

The session file is a live credential: anyone holding it is logged in as you.
Keep it out of version control.
"""

from pathlib import Path
from types import TracebackType

DEFAULT_TIMEOUT_MS = 30_000
DEFAULT_VIEWPORT = {"width": 1400, "height": 1600}

# A real desktop UA. Headless Chromium otherwise advertises "HeadlessChrome",
# which is the first thing bot detection looks at.
DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class BrowserSession:
    """
    A Playwright browser whose cookies persist across runs.

    Use as a context manager:

        with BrowserSession(session_path=".strava-session.json") as session:
            page = session.new_page()
            page.goto(url)

    On exit the current cookies are written back to session_path, so a login
    performed during this run is available to the next one.
    """

    def __init__(
        self,
        session_path: str | Path,
        headless: bool = True,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        fresh: bool = False,
    ) -> None:
        """
        Args:
            session_path: Where the cookie jar is read from and written to.
            headless:     Whether to show the browser.
            timeout_ms:   Default per-action timeout.
            fresh:        Start with an empty jar, ignoring any stored session.

        A Playwright context is already incognito-like: nothing is written to a
        browser profile on disk. The only persistence is the storage state this
        class restores — and restoring a stale one onto a login page brings back
        old localStorage, which can repopulate form fields with junk. `fresh`
        skips the restore for exactly that case, while still allowing the result
        to be saved afterwards.
        """
        self._session_path = Path(session_path)
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._fresh = fresh
        self._playwright = None
        self._browser = None
        self._context = None

    @property
    def has_saved_session(self) -> bool:
        """Whether a stored session exists to restore from."""
        return self._session_path.is_file()

    @property
    def _restores_session(self) -> bool:
        return self.has_saved_session and not self._fresh

    def __enter__(self) -> "BrowserSession":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - environment problem
            raise RuntimeError(
                "Playwright is required for scraping. Install it with: "
                "pip install playwright && playwright install chromium"
            ) from exc

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        self._context = self._browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            user_agent=DESKTOP_USER_AGENT,
            storage_state=str(self._session_path) if self._restores_session else None,
        )
        self._context.set_default_timeout(self._timeout_ms)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        # Deliberately does NOT save. Saving here once seemed helpful — a login
        # might have succeeded before a later failure — but it cuts the wrong way:
        # a run that ends logged out would overwrite a perfectly good stored
        # session with an empty one, silently costing another interactive sign-in.
        # Callers save explicitly, only once they have confirmed they are logged in.
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def new_page(self):
        """Open a new tab in the shared, cookie-bearing context."""
        if self._context is None:
            raise RuntimeError("BrowserSession must be used as a context manager")
        return self._context.new_page()

    def save_session(self) -> None:
        """Write current cookies to the session file."""
        if self._context is None:
            return
        self._session_path.parent.mkdir(parents=True, exist_ok=True)
        self._context.storage_state(path=str(self._session_path))

    def clear_session(self) -> None:
        """Delete the stored session, forcing a fresh login next run."""
        self._session_path.unlink(missing_ok=True)
