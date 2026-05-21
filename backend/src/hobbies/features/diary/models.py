"""
Data models for the Letterboxd parser pipeline.

RawDiaryItem holds raw string values extracted directly from the RSS XML,
before any type conversion or transformation is applied.
"""

from dataclasses import dataclass


@dataclass
class RawDiaryItem:
    """Raw field values extracted directly from a single RSS <item> element."""
    film_title: str
    film_year: str
    member_rating: str
    member_liked: str
    diary_link: str
    pub_date: str
    description_html: str
