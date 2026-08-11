"""
Route map thumbnails for the activity lists.

Five rows reading "Evening Ride" tell you nothing about which ride was which, so
each published activity gets a small picture of where it actually went. The route
lives on Strava's activity page as a WebGL canvas, which means it cannot be read
out of the markup like everything else in this feature — it has to be captured as
an image.

So this module is the one place in the Strava feature that produces a binary
asset rather than JSON. The images land in frontend/assets/, and the JSON refers
to them by path.

Cost: one page load per activity, and the map needs several seconds to fetch its
tiles before the canvas is worth photographing. That is slow enough that capture
is limited to the handful of activities actually published, not everything
scraped, and a failure is always a warning rather than a fatal error — a widget
with no thumbnail still reads perfectly well.

Three behaviours worth knowing about:

  * The capture happens in a cloned browser context at 2x pixel ratio, so a
    176px thumbnail is a crisp 352px image. Rendering the whole scrape at 2x to
    achieve the same thing would multiply the pixels of every page read.

  * The map container is squared by an init script, before the map exists, so the
    route is fitted to a square from the start. Squaring it afterwards crops
    instead of re-fitting. The framing is then pulled back by keyboard zoom, which
    is the only lever available — the map re-fits to any size it is given, so the
    container cannot control how much surrounding area is shown.

  * Strava draws the parts of a route inside a privacy zone as a pale "hidden"
    line rather than omitting them, and it draws them for the activity's owner —
    which is who we are logged in as. At this thumbnail size those segments are
    a few pixels of off-white and the ~250m they cover is sub-pixel, so they are
    left as they are. Anything published at a substantially larger size would
    need them dealt with properly.
"""

from pathlib import Path

from hobbies.features.strava import extractors
from hobbies.features.strava.constants import (
    MAP_CANVAS_SELECTOR,
    MAP_CHROME_HIDING_CSS,
    STRAVA_ACTIVITY_URL_TEMPLATE,
)
from hobbies.features.strava.login_form import dismiss_cookie_banner
from hobbies.features.strava.models import RawActivity

# Thumbnail edge in CSS pixels, captured at CAPTURE_PIXEL_RATIO for the real
# file. 176 at 2x gives a 352px image of about 15-30KB — enough for a 72px slot on
# a retina screen, with headroom, and small enough that a dozen of them do not
# dominate the page weight.
THUMBNAIL_SIDE_PX = 176
CAPTURE_PIXEL_RATIO = 2

# How far to zoom out from Strava's own framing, in Mapbox zoom levels.
#
# Strava fits the route tight to the frame, which answers "what shape was it?" but
# not "where was it?" — the thing a thumbnail is actually useful for. Two levels
# out puts the route at roughly half the frame: a commute sits in a recognisable
# piece of the city, and a lake ride shows the lake.
#
# Achieved by pressing "-" rather than by resizing the container. Container size
# cannot do it: the map re-fits the route to whatever size it is given, so a
# bigger frame just yields a bigger picture of the same extent.
MAP_ZOOM_OUT_STEPS = 2
ZOOM_STEP_SETTLE_MS = 600

# JPEG, not PNG: these are photographs of terrain, where PNG spends 167KB on
# what JPEG conveys in 14KB with no visible difference at this size.
IMAGE_FORMAT = "jpeg"
IMAGE_QUALITY = 82
IMAGE_EXTENSION = ".jpg"

# Where the files go, and how the JSON refers to them. The asset directory is
# passed in; this is the path prefix the browser will request.
ROUTE_ASSET_URL_PREFIX = "/assets/strava/routes"

# The page is server-rendered, but the map is not: it boots Mapbox, requests
# tiles and paints.
PAGE_SETTLE_MS = 2500
BANNER_SETTLE_MS = 1200

# Tile readiness is decided by watching the network go quiet rather than by
# waiting a fixed time.
#
# A fixed wait produced a silent, specific failure: the route drew — it is vector
# geometry, already in the page — over a blank green field, because the raster
# basemap had not arrived. The result was a plausible-looking 6KB image among
# 28KB ones, which is exactly the kind of thing that reaches the site unnoticed.
#
# Anything URL-matching a map tile counts; the map is idle once none has been
# requested for TILE_QUIET_MS.
TILE_URL_MARKERS = ("tile", "mapbox", "maps.strava")
TILE_QUIET_MS = 1500
TILE_WAIT_TIMEOUT_MS = 15000
TILE_POLL_MS = 250


def capture_route_maps(
    session,
    activities: list[RawActivity],
    output_dir: Path,
) -> dict[str, str]:
    """
    Capture a route thumbnail for each activity that has an id.

    Args:
        session:    An open BrowserSession, already logged in.
        activities: The activities to capture, usually just the published ones.
        output_dir: Directory to write the images into; created if absent.

    Returns:
        Activity id → site-relative image path, holding only the successes. A
        failed capture is reported as a warning and omitted, so callers must
        treat a missing key as "no picture" rather than an error.
    """
    targets = _deduplicate(activities)
    if not targets:
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)
    captured: dict[str, str] = {}

    boot_script = extractors.SIZE_MAP_AT_BOOT.replace("__SIDE__", str(THUMBNAIL_SIDE_PX))

    with session.cloned_context(
        device_scale_factor=CAPTURE_PIXEL_RATIO, init_script=boot_script
    ) as context:
        page = context.new_page()
        tiles = _watch_tile_requests(page)

        # The consent dialog covers the map, and it only needs dismissing once
        # for the whole context.
        #
        # This load is then thrown away rather than captured. Dismissing the
        # banner part-way through the map's own startup left it on a blank
        # basemap that it never re-requested tiles for, so the first activity
        # came out as a route drawn over an empty field. Every activity now gets
        # a clean load with consent already settled.
        page.goto(_activity_url(targets[0].activity_id), wait_until="domcontentloaded")
        page.wait_for_timeout(PAGE_SETTLE_MS)
        if dismiss_cookie_banner(page):
            print("[strava] dismissed the cookie banner before capturing maps")
        page.wait_for_timeout(BANNER_SETTLE_MS)

        for activity in targets:
            image_path = _capture_one(page, activity, output_dir, tiles)
            if image_path is not None:
                captured[activity.activity_id] = image_path

    print(f"[strava] captured {len(captured)}/{len(targets)} route maps")
    return captured


def _capture_one(page, activity: RawActivity, output_dir: Path, tiles: dict) -> str | None:
    """Photograph one activity's map, returning its site-relative path or None."""
    activity_id = activity.activity_id
    file_path = output_dir / f"{activity_id}{IMAGE_EXTENSION}"

    try:
        page.goto(_activity_url(activity_id), wait_until="domcontentloaded")
        page.wait_for_timeout(PAGE_SETTLE_MS)

        canvas = page.locator(MAP_CANVAS_SELECTOR)
        if not canvas.count():
            # Normal for an indoor ride or a treadmill run: no GPS, no map.
            print(f"[strava] no map on activity {activity_id} ({activity.name}) — skipping")
            return None

        page.add_style_tag(content=MAP_CHROME_HIDING_CSS)
        canvas.first.scroll_into_view_if_needed()

        # The container was squared before the map booted, so the route is already
        # fitted to a square; all that is left is to wait for its tiles.
        if not _wait_for_tiles(page, tiles):
            print(
                f"[strava] WARNING: tiles for {activity_id} were still arriving after "
                f"{TILE_WAIT_TIMEOUT_MS}ms — its thumbnail may show a blank basemap"
            )

        _zoom_out(page, tiles, activity_id)

        canvas.first.screenshot(path=str(file_path), type=IMAGE_FORMAT, quality=IMAGE_QUALITY)
    except Exception as error:  # noqa: BLE001 - Playwright raises many types
        # A missing thumbnail costs a little charm; a failed scrape costs the
        # whole data file. Never let the former become the latter.
        print(f"[strava] WARNING: could not capture map for {activity_id}: {error}")
        return None

    return f"{ROUTE_ASSET_URL_PREFIX}/{activity_id}{IMAGE_EXTENSION}"


def existing_route_maps(activities: list[RawActivity], output_dir: Path) -> dict[str, str]:
    """
    Find already-captured images for these activities, capturing nothing.

    This is what makes skipping the capture useful rather than destructive. Without
    it a skipped run rewrites the JSON with every routeImage null, so the pictures
    vanish from the site while their files sit untouched on disk — worse than not
    running at all, and easy to mistake for a scraping failure.

    Returns:
        Activity id → site-relative path, for the images that are actually there.
    """
    found: dict[str, str] = {}

    for activity in _deduplicate(activities):
        if (output_dir / f"{activity.activity_id}{IMAGE_EXTENSION}").is_file():
            found[activity.activity_id] = (
                f"{ROUTE_ASSET_URL_PREFIX}/{activity.activity_id}{IMAGE_EXTENSION}"
            )

    return found


def _zoom_out(page, tiles: dict, activity_id: str) -> None:
    """
    Pull the view back from Strava's tight fit so the surroundings are visible.

    Does nothing if the canvas cannot take focus, in which case the keypresses
    would go to the document and the thumbnail would quietly keep the tight
    framing — worth a warning rather than a silently different-looking image.
    """
    if not MAP_ZOOM_OUT_STEPS:
        return

    if not page.evaluate(extractors.FOCUS_MAP_CANVAS):
        print(
            f"[strava] WARNING: could not focus the map for {activity_id} — "
            "its thumbnail will be framed tighter than the others"
        )
        return

    for _ in range(MAP_ZOOM_OUT_STEPS):
        page.keyboard.press("Minus")
        page.wait_for_timeout(ZOOM_STEP_SETTLE_MS)

    _wait_for_tiles(page, tiles)


def _watch_tile_requests(page) -> dict:
    """
    Start counting basemap tile requests on a page.

    Returns a mutable counter the waiter reads. A counter rather than a timestamp
    so that the waiter decides what "quiet" means, and so it survives the several
    navigations one page makes over a run.
    """
    tiles = {"count": 0}

    def on_request(request) -> None:
        url = request.url.lower()
        if any(marker in url for marker in TILE_URL_MARKERS):
            tiles["count"] += 1

    page.on("request", on_request)
    return tiles


def _wait_for_tiles(page, tiles: dict) -> bool:
    """
    Wait until no new tile has been requested for TILE_QUIET_MS.

    Returns True once quiet, or False if the timeout arrived first — in which case
    the map is still loading and the capture will be taken regardless, since a
    partly-drawn map is more useful than no thumbnail at all.
    """
    deadline_polls = TILE_WAIT_TIMEOUT_MS // TILE_POLL_MS
    quiet_polls_needed = max(1, TILE_QUIET_MS // TILE_POLL_MS)

    last_count = -1
    quiet_polls = 0

    for _ in range(deadline_polls):
        page.wait_for_timeout(TILE_POLL_MS)

        if tiles["count"] == last_count:
            quiet_polls += 1
            if quiet_polls >= quiet_polls_needed:
                return True
        else:
            last_count = tiles["count"]
            quiet_polls = 0

    return False


def _deduplicate(activities: list[RawActivity]) -> list[RawActivity]:
    """
    One entry per activity id, preserving order.

    Cycling asks for rides and commutes separately and both come from the same
    list, so the same activity can be requested twice. Capturing it twice would
    pay seven seconds for a byte-identical file.
    """
    seen: set[str] = set()
    unique: list[RawActivity] = []

    for activity in activities:
        if not activity.activity_id or activity.activity_id in seen:
            continue
        seen.add(activity.activity_id)
        unique.append(activity)

    return unique


def _activity_url(activity_id: str) -> str:
    return STRAVA_ACTIVITY_URL_TEMPLATE.format(activity_id=activity_id)
