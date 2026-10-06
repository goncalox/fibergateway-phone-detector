"""Literal, case-insensitive name matching without device registration."""
import re
from .const import DEFAULT_NAMES
from .models import Detection


def parse_name_keywords(text: str) -> tuple[str, ...]:
    """Accept commas or newlines, preserving spaces within device names."""
    if not isinstance(text, str) or any(ord(c) < 32 and c not in "\r\n\t" for c in text):
        raise ValueError("Enter name keywords separated by commas or newlines")
    keywords = tuple(dict.fromkeys(part.strip().casefold() for part in re.split(r"[,\r\n]+", text) if part.strip()))
    if not keywords:
        raise ValueError("Enter at least one name keyword")
    return keywords


def classify(client, keywords: tuple[str, ...] | None = None) -> Detection:
    """Match only the router-reported hostname."""
    if keywords is None:
        keywords = parse_name_keywords(DEFAULT_NAMES)
    name = (client.hostname or "").casefold()
    return Detection(client, tuple(keyword for keyword in keywords if keyword in name))
