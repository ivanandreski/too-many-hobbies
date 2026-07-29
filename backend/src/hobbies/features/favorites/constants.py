"""Shared constants for the Letterboxd favorites scraper pipeline."""

from hobbies.features.diary.constants import LETTERBOXD_BASE_URL

# Profile page URL template — format with username to get a user's profile
LETTERBOXD_PROFILE_URL_TEMPLATE = f"{LETTERBOXD_BASE_URL}/{{username}}/"

# --- Page structure -------------------------------------------------------
# Letterboxd spells the section "favourites" in markup, "favorites" in copy.
FAVORITES_SECTION_ID = "favourites"

# Each favorite is a LazyPoster component div whose data-* attributes carry the
# film identity, wrapping an <img class="image"> whose src stays a placeholder
# until client-side scripts swap in the real poster.
POSTER_COMPONENT_CLASS = "LazyPoster"
POSTER_IMAGE_CLASS = "image"

# Substring present in the placeholder poster served before scripts run.
EMPTY_POSTER_MARKER = "empty-poster"

# --- Browser waits --------------------------------------------------------
FAVORITES_IMAGE_SELECTOR = f"#{FAVORITES_SECTION_ID} img.{POSTER_IMAGE_CLASS}"

# Polled in the page until every favorite poster is a real image, not a placeholder.
POSTERS_RESOLVED_PREDICATE = f"""
    () => {{
        const images = [...document.querySelectorAll('{FAVORITES_IMAGE_SELECTOR}')];
        return images.length > 0
            && images.every(image => image.src && !image.src.includes('{EMPTY_POSTER_MARKER}'));
    }}
"""

# --- Poster sizing --------------------------------------------------------
# Poster URLs encode their crop dimensions, e.g.
#   .../51552-rear-window-0-150-0-225-crop.jpg?v=855a2e3070
# The profile page renders 150x225 thumbnails; rewriting the dimensions in the
# URL asks the CDN for a larger crop of the same image.
POSTER_WIDTH = 1000
POSTER_HEIGHT = 1500
