"""
XML extraction config for the Letterboxd diary RSS feed.

Defines which fields to extract from each <item> element and how to find them.
Consumed by the generic xml_parser to produce a raw field dict.
"""

from hobbies.core.xml_parser import XmlFieldConfig
from hobbies.features.diary.constants import LETTERBOXD_XML_NAMESPACE

DIARY_ITEM_FIELD_CONFIGS: list[XmlFieldConfig] = [
    XmlFieldConfig(field="film_title",      tag="filmTitle",     namespace=LETTERBOXD_XML_NAMESPACE, fallback_tag="title"),
    XmlFieldConfig(field="film_year",       tag="filmYear",      namespace=LETTERBOXD_XML_NAMESPACE),
    XmlFieldConfig(field="member_rating",   tag="memberRating",  namespace=LETTERBOXD_XML_NAMESPACE),
    XmlFieldConfig(field="member_liked",    tag="memberLike",    namespace=LETTERBOXD_XML_NAMESPACE),
    XmlFieldConfig(field="diary_link",      tag="link"),
    XmlFieldConfig(field="pub_date",        tag="pubDate"),
    XmlFieldConfig(field="description_html", tag="description"),
]
