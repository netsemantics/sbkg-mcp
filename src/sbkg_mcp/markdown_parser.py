"""Markdown ↔ RDF: parse frontmatter, wikilinks, extract triples."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pyoxigraph import DefaultGraph, Literal, NamedNode, Quad

from .models import Note
from .utils import (
    SBKG_NS,
    make_area_uri,
    make_concept_uri,
    make_note_uri,
    make_project_uri,
    now_iso,
    slugify,
)


_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z][\w/-]*)", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

_RDF_TYPE = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")


def parse_markdown(path: str | Path) -> Note:
    """Parse a markdown file into a Note dataclass."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    # Extract frontmatter
    frontmatter: dict = {}
    content = text
    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match:
        try:
            frontmatter = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            frontmatter = {}
        content = text[fm_match.end():]

    # Extract wikilinks from content
    wikilinks = _WIKILINK_RE.findall(content)

    # Extract inline tags from content
    inline_tags = _TAG_RE.findall(content)

    # Merge frontmatter tags with inline tags
    fm_tags = frontmatter.get("tags", [])
    if isinstance(fm_tags, str):
        fm_tags = [t.strip() for t in fm_tags.split(",")]
    all_tags = list(dict.fromkeys(fm_tags + inline_tags))  # dedupe, preserve order

    # Build links from frontmatter + wikilinks
    fm_links = frontmatter.get("links", [])
    if isinstance(fm_links, str):
        fm_links = [fm_links]
    all_links = list(dict.fromkeys(fm_links + wikilinks))

    title = frontmatter.get("title", path.stem)
    note_type = frontmatter.get("type", "Note")
    project = frontmatter.get("project")
    area = frontmatter.get("area")
    status = frontmatter.get("status")
    created_at = frontmatter.get("created", frontmatter.get("date"))
    modified_at = frontmatter.get("modified")

    if created_at is not None:
        created_at = str(created_at)
    if modified_at is not None:
        modified_at = str(modified_at)

    return Note(
        title=title,
        content=content.strip(),
        note_type=note_type,
        tags=all_tags,
        links=all_links,
        project=project,
        area=area,
        status=status,
        markdown_path=str(path),
        created_at=created_at,
        modified_at=modified_at,
    )


def extract_triples(note: Note) -> list[Quad]:
    """Convert a Note to RDF quads for insertion into the store."""
    slug = slugify(note.title)
    note_uri = NamedNode(make_note_uri(slug))
    graph = DefaultGraph()
    quads: list[Quad] = []

    def q(s, p, o):
        quads.append(Quad(s, p, o, graph))

    # Type
    type_map = {
        "Note": "Note",
        "DailyNote": "DailyNote",
        "ProjectNote": "ProjectNote",
        "AreaNote": "AreaNote",
        "ResourceNote": "ResourceNote",
        "FleetingNote": "FleetingNote",
    }
    rdf_type = type_map.get(note.note_type, "Note")
    q(note_uri, _RDF_TYPE, NamedNode(f"{SBKG_NS}{rdf_type}"))

    # Title
    q(note_uri, NamedNode(f"{SBKG_NS}title"), Literal(note.title))

    # Content (store first 500 chars as preview)
    if note.content:
        preview = note.content[:500]
        q(note_uri, NamedNode(f"{SBKG_NS}content"), Literal(preview))

    # Tags → Concepts
    for tag in note.tags:
        concept_uri = NamedNode(make_concept_uri(tag))
        q(concept_uri, _RDF_TYPE, NamedNode(f"{SBKG_NS}Concept"))
        q(concept_uri, NamedNode(f"{SBKG_NS}title"), Literal(tag))
        q(note_uri, NamedNode(f"{SBKG_NS}hasTag"), concept_uri)

    # Wikilinks → linksTo
    for link in note.links:
        target_uri = NamedNode(make_note_uri(slugify(link)))
        q(note_uri, NamedNode(f"{SBKG_NS}linksTo"), target_uri)

    # Project
    if note.project:
        proj_uri = NamedNode(make_project_uri(note.project))
        q(proj_uri, _RDF_TYPE, NamedNode(f"{SBKG_NS}Project"))
        q(proj_uri, NamedNode(f"{SBKG_NS}title"), Literal(note.project))
        q(note_uri, NamedNode(f"{SBKG_NS}belongsToProject"), proj_uri)

    # Area
    if note.area:
        area_uri = NamedNode(make_area_uri(note.area))
        q(area_uri, _RDF_TYPE, NamedNode(f"{SBKG_NS}Area"))
        q(area_uri, NamedNode(f"{SBKG_NS}title"), Literal(note.area))
        q(note_uri, NamedNode(f"{SBKG_NS}belongsToArea"), area_uri)

    # Timestamps
    ts_type = NamedNode("http://www.w3.org/2001/XMLSchema#dateTime")
    created = note.created_at or now_iso()
    q(note_uri, NamedNode(f"{SBKG_NS}createdAt"), Literal(created, datatype=ts_type))
    if note.modified_at:
        q(note_uri, NamedNode(f"{SBKG_NS}modifiedAt"), Literal(note.modified_at, datatype=ts_type))

    # Status
    if note.status:
        q(note_uri, NamedNode(f"{SBKG_NS}hasStatus"), Literal(note.status))

    # Markdown path
    if note.markdown_path:
        q(note_uri, NamedNode(f"{SBKG_NS}markdownPath"), Literal(note.markdown_path))

    return quads


def note_to_markdown(note: Note) -> str:
    """Generate a markdown string with YAML frontmatter from a Note."""
    fm: dict = {"title": note.title}
    if note.note_type != "Note":
        fm["type"] = note.note_type
    if note.tags:
        fm["tags"] = note.tags
    if note.project:
        fm["project"] = note.project
    if note.area:
        fm["area"] = note.area
    if note.status:
        fm["status"] = note.status
    if note.created_at:
        fm["created"] = note.created_at
    if note.modified_at:
        fm["modified"] = note.modified_at

    frontmatter = yaml.dump(fm, default_flow_style=False, sort_keys=False).strip()
    parts = [f"---\n{frontmatter}\n---\n"]

    if note.content:
        parts.append(note.content)

    return "\n".join(parts) + "\n"
