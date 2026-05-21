"""
Generic config-driven XML item extractor.

XmlFieldConfig describes how to extract a single field from an XML element.
extract_fields() uses a list of configs to extract all fields at once,
returning a plain dict that can be unpacked into a dataclass.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass
class XmlFieldConfig:
    """
    Describes how to extract one field from an XML element.

    Attributes:
        field:        Target key name in the resulting dict.
        tag:          XML tag name to look up.
        namespace:    Optional XML namespace URI. If provided, the namespaced
                      tag is tried first before falling back to the plain tag.
        fallback_tag: Optional alternative plain tag tried if the primary tag
                      (namespaced or plain) yields no result.
    """
    field: str
    tag: str
    namespace: str | None = None
    fallback_tag: str | None = None


def extract_fields(item: ET.Element, field_configs: list[XmlFieldConfig]) -> dict:
    """
    Extract multiple fields from a single XML element using a list of configs.

    Args:
        item:          The XML element to extract from.
        field_configs: List of XmlFieldConfig describing each field to extract.

    Returns:
        Dict mapping field names to their extracted string values.
        Missing fields default to an empty string.
    """
    return {config.field: _extract_field(item, config) for config in field_configs}


def _extract_field(item: ET.Element, config: XmlFieldConfig) -> str:
    """Extract a single field value from an XML element according to its config."""
    if config.namespace:
        value = _get_namespaced_text(item, config.tag, config.namespace)
        if value is not None:
            return value

    plain_value = _get_element_text(item, config.tag)
    if plain_value:
        return plain_value

    if config.fallback_tag:
        return _get_element_text(item, config.fallback_tag)

    return ""


def _get_namespaced_text(item: ET.Element, tag: str, namespace: str) -> str | None:
    """Return text of a namespaced element, or None if not present."""
    element = item.find(f"{{{namespace}}}{tag}")
    if element is not None:
        return (element.text or "").strip()
    return None


def _get_element_text(item: ET.Element, tag: str) -> str:
    """Return the stripped text content of a plain (non-namespaced) XML element."""
    element = item.find(tag)
    return (element.text or "").strip() if element is not None else ""
