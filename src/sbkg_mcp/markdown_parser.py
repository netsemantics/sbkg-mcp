"""Markdown ↔ RDF: parse frontmatter, wikilinks, extract triples."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pyoxigraph import DefaultGraph, Literal, NamedNode, Quad

from .models import Bookmark, Note, Project
from .utils import (
    DCTERMS_NS,
    DOAP_NS,
    FOAF_NS,
    SBKG_NS,
    SKOS_NS,
    make_area_uri,
    make_concept_uri,
    make_note_uri,
    make_person_uri,
    make_project_uri,
    now_iso,
    slugify,
)


_WIKILINK_RE = re.compile(r"(!?)\[\[([^\]]+)\]\]")
_TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z][\w/-]*)", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

_RDF_TYPE = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
_XSD_DT = NamedNode("http://www.w3.org/2001/XMLSchema#dateTime")
_XSD_ANYURI = NamedNode("http://www.w3.org/2001/XMLSchema#anyURI")

_KNOWN_STATUSES = {"ToRead", "Reading", "Read", "Reference"}


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

    # Extract wikilinks from content (skip ![[...]] image embeds, strip |alias)
    wikilinks = [
        m.split("|")[0].strip()
        for prefix, m in _WIKILINK_RE.findall(content)
        if not prefix  # skip ![[...]] image embeds
    ]

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

    # DC metadata
    description = frontmatter.get("description")
    creator = frontmatter.get("creator")
    language = frontmatter.get("language")
    license_ = frontmatter.get("license")

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
        description=description,
        creator=creator,
        language=language,
        license=license_,
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

    # Content
    if note.content:
        q(note_uri, NamedNode(f"{SBKG_NS}content"), Literal(note.content))

    # Tags → Concepts with skos:prefLabel
    for tag in note.tags:
        concept_uri = NamedNode(make_concept_uri(tag))
        q(concept_uri, _RDF_TYPE, NamedNode(f"{SBKG_NS}Concept"))
        q(concept_uri, NamedNode(f"{SBKG_NS}title"), Literal(tag))
        q(concept_uri, NamedNode(f"{SKOS_NS}prefLabel"), Literal(tag))
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
    created = note.created_at or now_iso()
    q(note_uri, NamedNode(f"{SBKG_NS}createdAt"), Literal(created, datatype=_XSD_DT))
    if note.modified_at:
        q(note_uri, NamedNode(f"{SBKG_NS}modifiedAt"), Literal(note.modified_at, datatype=_XSD_DT))

    # Status — known statuses as NamedNode, freeform as Literal
    if note.status:
        if note.status in _KNOWN_STATUSES:
            q(note_uri, NamedNode(f"{SBKG_NS}hasStatus"), NamedNode(f"{SBKG_NS}{note.status}"))
        else:
            q(note_uri, NamedNode(f"{SBKG_NS}hasStatus"), Literal(note.status))

    # Dublin Core metadata
    if note.description:
        q(note_uri, NamedNode(f"{DCTERMS_NS}description"), Literal(note.description))
    if note.creator:
        if note.creator_email:
            # Creator with email → foaf:Person node with name + mbox
            creator_person_uri = NamedNode(make_person_uri(note.creator))
            q(creator_person_uri, _RDF_TYPE, NamedNode(f"{FOAF_NS}Person"))
            q(creator_person_uri, NamedNode(f"{FOAF_NS}name"), Literal(note.creator))
            q(creator_person_uri, NamedNode(f"{FOAF_NS}mbox"), NamedNode(f"mailto:{note.creator_email}"))
            q(note_uri, NamedNode(f"{DCTERMS_NS}creator"), creator_person_uri)
        else:
            q(note_uri, NamedNode(f"{DCTERMS_NS}creator"), Literal(note.creator))
    if note.language:
        q(note_uri, NamedNode(f"{DCTERMS_NS}language"), Literal(note.language))
    if note.license:
        q(note_uri, NamedNode(f"{DCTERMS_NS}license"), Literal(note.license))

    # Mentions → Person URIs
    for person_name in note.mentions:
        person_uri = NamedNode(make_person_uri(person_name))
        q(person_uri, _RDF_TYPE, NamedNode(f"{FOAF_NS}Person"))
        q(person_uri, NamedNode(f"{FOAF_NS}name"), Literal(person_name))
        # Emit foaf:mbox if email address is known
        email_addr = note.mention_emails.get(person_name)
        if email_addr:
            q(person_uri, NamedNode(f"{FOAF_NS}mbox"), NamedNode(f"mailto:{email_addr}"))
        q(note_uri, NamedNode(f"{SBKG_NS}mentions"), person_uri)

    # Markdown path
    if note.markdown_path:
        q(note_uri, NamedNode(f"{SBKG_NS}markdownPath"), Literal(note.markdown_path))

    return quads


def extract_bookmark_triples(bookmark: Bookmark) -> list[Quad]:
    """Convert a Bookmark to RDF quads for insertion into the store."""
    slug = slugify(bookmark.title)
    from .utils import make_bookmark_uri
    bm_uri = NamedNode(make_bookmark_uri(slug))
    graph = DefaultGraph()
    quads: list[Quad] = []

    def q(s, p, o):
        quads.append(Quad(s, p, o, graph))

    q(bm_uri, _RDF_TYPE, NamedNode(f"{SBKG_NS}Bookmark"))
    q(bm_uri, NamedNode(f"{SBKG_NS}title"), Literal(bookmark.title))
    q(bm_uri, NamedNode(f"{SBKG_NS}sourceUrl"), Literal(bookmark.url))

    if bookmark.description:
        q(bm_uri, NamedNode(f"{SBKG_NS}content"), Literal(bookmark.description))

    # Tags → Concepts with skos:prefLabel
    for tag in bookmark.tags:
        concept_uri = NamedNode(make_concept_uri(tag))
        q(concept_uri, _RDF_TYPE, NamedNode(f"{SBKG_NS}Concept"))
        q(concept_uri, NamedNode(f"{SBKG_NS}title"), Literal(tag))
        q(concept_uri, NamedNode(f"{SKOS_NS}prefLabel"), Literal(tag))
        q(bm_uri, NamedNode(f"{SBKG_NS}hasTag"), concept_uri)

    # Status — known statuses as NamedNode, freeform as Literal
    if bookmark.status:
        if bookmark.status in _KNOWN_STATUSES:
            q(bm_uri, NamedNode(f"{SBKG_NS}hasStatus"), NamedNode(f"{SBKG_NS}{bookmark.status}"))
        else:
            q(bm_uri, NamedNode(f"{SBKG_NS}hasStatus"), Literal(bookmark.status))

    # Timestamps
    created = bookmark.created_at or now_iso()
    q(bm_uri, NamedNode(f"{SBKG_NS}createdAt"), Literal(created, datatype=_XSD_DT))
    if bookmark.modified_at:
        q(bm_uri, NamedNode(f"{SBKG_NS}modifiedAt"), Literal(bookmark.modified_at, datatype=_XSD_DT))

    return quads


def extract_project_triples(project: Project) -> list[Quad]:
    """Convert a Project to RDF quads using DOAP vocabulary."""
    proj_uri = NamedNode(make_project_uri(project.name))
    graph = DefaultGraph()
    quads: list[Quad] = []

    def q(s, p, o):
        quads.append(Quad(s, p, o, graph))

    # Type
    q(proj_uri, _RDF_TYPE, NamedNode(f"{SBKG_NS}Project"))
    q(proj_uri, _RDF_TYPE, NamedNode(f"{DOAP_NS}Project"))

    # DOAP properties
    q(proj_uri, NamedNode(f"{DOAP_NS}name"), Literal(project.name))
    if project.description:
        q(proj_uri, NamedNode(f"{DOAP_NS}description"), Literal(project.description))
    if project.homepage:
        q(proj_uri, NamedNode(f"{DOAP_NS}homepage"), Literal(project.homepage, datatype=_XSD_ANYURI))
    if project.repository:
        repo_uri = NamedNode(f"{SBKG_NS}repo/{slugify(project.name)}")
        q(repo_uri, _RDF_TYPE, NamedNode(f"{DOAP_NS}GitRepository"))
        q(repo_uri, NamedNode(f"{DOAP_NS}location"), Literal(project.repository, datatype=_XSD_ANYURI))
        q(proj_uri, NamedNode(f"{DOAP_NS}repository"), repo_uri)
    if project.programming_language:
        q(proj_uri, NamedNode(f"{DOAP_NS}programming-language"), Literal(project.programming_language))
    if project.platform:
        q(proj_uri, NamedNode(f"{DOAP_NS}platform"), Literal(project.platform))

    # Maintainers → foaf:Person
    for name in project.maintainers:
        person_uri = NamedNode(make_person_uri(name))
        q(person_uri, _RDF_TYPE, NamedNode(f"{FOAF_NS}Person"))
        q(person_uri, NamedNode(f"{FOAF_NS}name"), Literal(name))
        q(proj_uri, NamedNode(f"{DOAP_NS}maintainer"), person_uri)

    # Developers → foaf:Person
    for name in project.developers:
        person_uri = NamedNode(make_person_uri(name))
        q(person_uri, _RDF_TYPE, NamedNode(f"{FOAF_NS}Person"))
        q(person_uri, NamedNode(f"{FOAF_NS}name"), Literal(name))
        q(proj_uri, NamedNode(f"{DOAP_NS}developer"), person_uri)

    # Tags → Concepts with skos:prefLabel
    for tag in project.tags:
        concept_uri = NamedNode(make_concept_uri(tag))
        q(concept_uri, _RDF_TYPE, NamedNode(f"{SBKG_NS}Concept"))
        q(concept_uri, NamedNode(f"{SBKG_NS}title"), Literal(tag))
        q(concept_uri, NamedNode(f"{SKOS_NS}prefLabel"), Literal(tag))
        q(proj_uri, NamedNode(f"{SBKG_NS}hasTag"), concept_uri)

    # SBKG title (for consistency with query patterns)
    q(proj_uri, NamedNode(f"{SBKG_NS}title"), Literal(project.name))

    # Timestamp
    created = project.created_at or now_iso()
    q(proj_uri, NamedNode(f"{SBKG_NS}createdAt"), Literal(created, datatype=_XSD_DT))

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
    # DC metadata
    if note.description:
        fm["description"] = note.description
    if note.creator:
        fm["creator"] = note.creator
    if note.language:
        fm["language"] = note.language
    if note.license:
        fm["license"] = note.license

    frontmatter = yaml.dump(fm, default_flow_style=False, sort_keys=False).strip()
    parts = [f"---\n{frontmatter}\n---\n"]

    if note.content:
        parts.append(note.content)

    return "\n".join(parts) + "\n"
