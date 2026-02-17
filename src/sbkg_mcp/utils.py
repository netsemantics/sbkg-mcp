"""Utility functions: slugify, URI generation, date helpers."""

import re
import unicodedata
from datetime import datetime, timezone


SBKG_NS = "http://sb.ai/kg/"


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-") or "untitled"


def make_note_uri(slug: str) -> str:
    """Generate a URI for a note."""
    return f"{SBKG_NS}note/{slug}"


def make_bookmark_uri(slug: str) -> str:
    """Generate a URI for a bookmark."""
    return f"{SBKG_NS}bookmark/{slug}"


def make_concept_uri(name: str) -> str:
    """Generate a URI for a concept (tag/topic)."""
    return f"{SBKG_NS}concept/{slugify(name)}"


def make_project_uri(name: str) -> str:
    """Generate a URI for a project."""
    return f"{SBKG_NS}project/{slugify(name)}"


def make_area_uri(name: str) -> str:
    """Generate a URI for an area."""
    return f"{SBKG_NS}area/{slugify(name)}"


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso(date_str: str) -> datetime:
    """Parse an ISO 8601 date string."""
    return datetime.fromisoformat(date_str)
