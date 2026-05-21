"""
Letterboxd RSS parser.

Traverses the RSS channel structure to find <item> elements, then delegates
field extraction to the generic xml_parser using the diary field config.
"""

import xml.etree.ElementTree as ET

from hobbies.core.xml_parser import extract_fields
from hobbies.features.diary.config import DIARY_ITEM_FIELD_CONFIGS
from hobbies.features.diary.models import RawDiaryItem


def extract_raw_diary_items(rss_text: str) -> list[RawDiaryItem]:
    """
    Parse a Letterboxd diary RSS feed and return one RawDiaryItem per entry.

    Args:
        rss_text: Raw XML string of the RSS feed.

    Returns:
        List of RawDiaryItem instances ordered as they appear in the feed (newest first).
    """
    rss_root = ET.fromstring(rss_text)
    channel = rss_root.find("channel")
    if channel is None:
        raise ValueError("RSS feed has no <channel> element")

    return [
        RawDiaryItem(**extract_fields(item, DIARY_ITEM_FIELD_CONFIGS))
        for item in channel.findall("item")
    ]

