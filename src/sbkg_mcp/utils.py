"""Utility functions: slugify, URI generation, date helpers."""

import re
import unicodedata
from datetime import datetime, timezone


SBKG_NS = "http://sb.ai/kg/"
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
DCTERMS_NS = "http://purl.org/dc/terms/"
DOAP_NS = "http://usefulinc.com/ns/doap#"
FOAF_NS = "http://xmlns.com/foaf/0.1/"


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


def make_person_uri(name: str) -> str:
    """Generate a URI for a person."""
    return f"{SBKG_NS}person/{slugify(name)}"


def make_tool_uri(name: str) -> str:
    """Generate a URI for a tool."""
    return f"{SBKG_NS}tool/{slugify(name)}"


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso(date_str: str) -> datetime:
    """Parse an ISO 8601 date string."""
    return datetime.fromisoformat(date_str)
