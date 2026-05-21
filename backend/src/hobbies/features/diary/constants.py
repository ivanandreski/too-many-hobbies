"""Shared constants for the Letterboxd parser pipeline."""

LETTERBOXD_DOMAIN = "letterboxd.com"
LETTERBOXD_BASE_URL = f"https://{LETTERBOXD_DOMAIN}"

# XML namespace declared in the Letterboxd RSS root element
LETTERBOXD_XML_NAMESPACE = LETTERBOXD_BASE_URL

# RSS feed URL template — format with username to get a user's diary feed
LETTERBOXD_RSS_URL_TEMPLATE = f"{LETTERBOXD_BASE_URL}/{{username}}/rss/"
