"""FastMCP server with SBKG tools."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pyoxigraph import Literal, NamedNode

from .email_parser import parse_email
from .markdown_parser import (
    extract_bookmark_triples,
    extract_project_triples,
    extract_triples,
    note_to_markdown,
    parse_markdown,
)
from .models import Bookmark, Note, Project
from .ontology import get_ontology_summary, get_ontology_turtle
from .store import KnowledgeStore
from .utils import (
    FOAF_NS,
    SBKG_NS,
    SKOS_NS,
    make_bookmark_uri,
    make_note_uri,
    make_person_uri,
    make_project_uri,
    now_iso,
    slugify,
)

mcp = FastMCP("sbkg")

_GUIDE_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "llm-usage-guide.md"


def _read_guide() -> str:
    """Read the LLM usage guide markdown file."""
    return _GUIDE_PATH.read_text(encoding="utf-8")

_store: KnowledgeStore | None = None
_RDF_TYPE = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
_XSD_DT = NamedNode("http://www.w3.org/2001/XMLSchema#dateTime")


def _get_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store


# ---------------------------------------------------------------------------
# Tool 1: sbkg_add_note
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_add_note(
    title: str,
    content: str = "",
    note_type: str = "Note",
    tags: list[str] | None = None,
    links: list[str] | None = None,
    project: str | None = None,
    area: str | None = None,
    status: str | None = None,
) -> str:
    """
    Create a note in the knowledge graph with metadata and triples.

    Args:
        title: The note title
        content: Markdown body content
        note_type: One of Note, DailyNote, ProjectNote, AreaNote, ResourceNote, FleetingNote
        tags: List of tag strings
        links: List of related note titles (wikilink targets)
        project: Project name this note belongs to
        area: Area name this note belongs to
        status: Freeform status string

    Returns:
        str: JSON with the created note URI and metadata
    """
    store = _get_store()
    note = Note(
        title=title,
        content=content,
        note_type=note_type,
        tags=tags or [],
        links=links or [],
        project=project,
        area=area,
        status=status,
        created_at=now_iso(),
    )
    quads = extract_triples(note)
    store.insert_triples(quads)

    slug = slugify(title)
    return json.dumps({
        "uri": make_note_uri(slug),
        "title": title,
        "type": note_type,
        "tags": note.tags,
        "triples_added": len(quads),
    })


# ---------------------------------------------------------------------------
# Tool 2: sbkg_add_bookmark
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_add_bookmark(
    title: str,
    url: str,
    description: str = "",
    tags: list[str] | None = None,
    status: str = "ToRead",
) -> str:
    """
    Create a bookmark in the knowledge graph.

    Args:
        title: Bookmark title
        url: The source URL
        description: Optional description
        tags: List of tag strings
        status: One of ToRead, Reading, Read, Reference

    Returns:
        str: JSON with the created bookmark URI and metadata
    """
    store = _get_store()
    bookmark = Bookmark(
        title=title,
        url=url,
        description=description,
        tags=tags or [],
        status=status,
        created_at=now_iso(),
    )
    quads = extract_bookmark_triples(bookmark)
    store.insert_triples(quads)

    slug = slugify(title)
    return json.dumps({
        "uri": make_bookmark_uri(slug),
        "title": title,
        "url": url,
        "status": status,
        "triples_added": len(quads),
    })


# ---------------------------------------------------------------------------
# Tool 3: sbkg_extract_from_markdown
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_extract_from_markdown(path: str) -> str:
    """
    Parse a markdown file and add its triples to the knowledge graph.

    Args:
        path: Absolute path to the .md file

    Returns:
        str: JSON with parsed note metadata and triple count
    """
    store = _get_store()
    note = parse_markdown(path)
    quads = extract_triples(note)
    store.insert_triples(quads)

    return json.dumps({
        "uri": make_note_uri(slugify(note.title)),
        "title": note.title,
        "type": note.note_type,
        "tags": note.tags,
        "links": note.links,
        "triples_added": len(quads),
    })


# ---------------------------------------------------------------------------
# Tool 4: sbkg_query_sparql
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_query_sparql(sparql: str) -> str:
    """
    Execute a SPARQL query against the knowledge graph.

    Args:
        sparql: A SPARQL SELECT, ASK, CONSTRUCT, or DESCRIBE query

    Returns:
        str: JSON array of result bindings (for SELECT) or triples
    """
    store = _get_store()
    results = store.query_sparql_raw(sparql)
    return json.dumps(results)


# ---------------------------------------------------------------------------
# Tool 5: sbkg_query_natural
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_query_natural(question: str) -> str:
    """
    Get ontology context and instructions for translating a natural language
    question into a SPARQL query. The calling LLM should use this context
    to generate SPARQL and then call sbkg_query_sparql.

    Args:
        question: A natural language question about the knowledge graph

    Returns:
        str: JSON with ontology summary, example queries, and instructions
    """
    summary = get_ontology_summary()
    return json.dumps({
        "question": question,
        "ontology": summary,
        "instructions": (
            "Use the ontology above to write a SPARQL query that answers the question. "
            "Then call sbkg_query_sparql with the generated SPARQL. "
            "All SBKG entities use the namespace PREFIX sbkg: <http://sb.ai/kg/>. "
            "Notes have type sbkg:Note (or subtypes), bookmarks sbkg:Bookmark, tags sbkg:Concept. "
            "Tip: for simple lookups, prefer sbkg_get_note (fetch by title), "
            "sbkg_search (title substring search), or sbkg_update_note (modify fields) "
            "instead of writing SPARQL."
        ),
        "example_queries": [
            {
                "description": "List all notes",
                "sparql": "PREFIX sbkg: <http://sb.ai/kg/> SELECT ?note ?title WHERE { ?note a sbkg:Note . ?note sbkg:title ?title . }",
            },
            {
                "description": "Find notes with a specific tag",
                "sparql": "PREFIX sbkg: <http://sb.ai/kg/> SELECT ?note ?title WHERE { ?note sbkg:hasTag ?tag . ?tag sbkg:title \"python\" . ?note sbkg:title ?title . }",
            },
            {
                "description": "Find notes in a project",
                "sparql": "PREFIX sbkg: <http://sb.ai/kg/> SELECT ?note ?title WHERE { ?note sbkg:belongsToProject ?proj . ?proj sbkg:title \"my-project\" . ?note sbkg:title ?title . }",
            },
        ],
    })


# ---------------------------------------------------------------------------
# Tool 6: sbkg_get_related_notes
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_get_related_notes(title: str, max_results: int = 20) -> str:
    """
    Find notes related to a given note via shared tags, links, or project/area.

    Args:
        title: The title of the note to find relations for
        max_results: Maximum number of related notes to return

    Returns:
        str: JSON array of related notes with relationship type
    """
    store = _get_store()
    slug = slugify(title)
    note_uri = make_note_uri(slug)

    sparql = f"""
    PREFIX sbkg: <http://sb.ai/kg/>

    SELECT DISTINCT ?related ?relTitle ?relType WHERE {{
      BIND(<{note_uri}> AS ?source)

      {{
        # Shared tags
        ?source sbkg:hasTag ?tag .
        ?related sbkg:hasTag ?tag .
        BIND("shared_tag" AS ?relType)
      }} UNION {{
        # Direct links from source
        ?source sbkg:linksTo ?related .
        BIND("links_to" AS ?relType)
      }} UNION {{
        # Incoming links to source
        ?related sbkg:linksTo ?source .
        BIND("linked_from" AS ?relType)
      }} UNION {{
        # Same project
        ?source sbkg:belongsToProject ?proj .
        ?related sbkg:belongsToProject ?proj .
        BIND("same_project" AS ?relType)
      }} UNION {{
        # Same area
        ?source sbkg:belongsToArea ?area .
        ?related sbkg:belongsToArea ?area .
        BIND("same_area" AS ?relType)
      }}

      ?related sbkg:title ?relTitle .
      FILTER(?related != ?source)
    }}
    LIMIT {max_results}
    """
    results = store.query_sparql(sparql)
    return json.dumps(results)


# ---------------------------------------------------------------------------
# Tool 7: sbkg_get_stats
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_get_stats() -> str:
    """
    Get statistics about the knowledge graph.

    Returns:
        str: JSON with total triples, entity counts by type
    """
    store = _get_store()
    stats = store.get_stats()
    return json.dumps(stats)


# ---------------------------------------------------------------------------
# Tool 8: sbkg_export_triples
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_export_triples(format: str = "turtle", path: str | None = None) -> str:
    """
    Export the knowledge graph to an RDF serialization format.

    Args:
        format: RDF format — turtle, ntriples, nquads, trig, rdfxml
        path: Optional file path to write to. If omitted, returns the content.

    Returns:
        str: JSON with export status and content or file path
    """
    store = _get_store()
    result = store.export(fmt=format, path=path)
    if path:
        return json.dumps({"exported_to": result, "format": format})
    # Truncate if very large
    if len(result) > 50000:
        return json.dumps({
            "format": format,
            "content_truncated": True,
            "content": result[:50000],
            "total_length": len(result),
        })
    return json.dumps({"format": format, "content": result})


# ---------------------------------------------------------------------------
# Tool 9: sbkg_import_triples
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_import_triples(path: str, format: str = "turtle") -> str:
    """
    Import triples from an RDF file into the knowledge graph.

    Args:
        path: Absolute path to the RDF file
        format: RDF format — turtle, ntriples, nquads, trig, rdfxml

    Returns:
        str: JSON with import status and approximate triple count added
    """
    store = _get_store()
    count = store.import_rdf(path=path, fmt=format)
    return json.dumps({
        "imported_from": path,
        "format": format,
        "triples_added": count,
    })


# ---------------------------------------------------------------------------
# Tool 10: sbkg_update_sparql
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_update_sparql(update: str) -> str:
    """
    Execute a SPARQL 1.1 UPDATE against the knowledge graph.

    Supports INSERT DATA, DELETE DATA, DELETE/INSERT WHERE, and other
    SPARQL Update operations. Updates are applied transactionally.

    Use this for batch operations — e.g. inserting many triples at once,
    bulk-tagging, or modifying existing data in place.

    Args:
        update: A SPARQL 1.1 Update string (INSERT DATA, DELETE DATA, etc.)

    Returns:
        str: JSON with execution status and triple count delta
    """
    store = _get_store()
    before = store._count_triples()
    store.sparql_update(update)
    after = store._count_triples()
    return json.dumps({
        "success": True,
        "triples_before": before,
        "triples_after": after,
        "triples_delta": after - before,
    })


# ---------------------------------------------------------------------------
# Tool 11: sbkg_bulk_import
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_bulk_import(data: str, format: str = "turtle") -> str:
    """
    Bulk-import RDF triples from an in-memory string.

    Optimized for large payloads — streams data to disk without holding
    all triples in memory. Use this instead of sbkg_import_triples when
    the data is generated programmatically rather than read from a file.

    Args:
        data: RDF content as a string (Turtle, N-Triples, etc.)
        format: RDF format — turtle, ntriples, nquads, trig, rdfxml

    Returns:
        str: JSON with import status and approximate triple count added
    """
    store = _get_store()
    count = store.bulk_load_string(data=data, fmt=format)
    return json.dumps({
        "success": True,
        "format": format,
        "triples_added": count,
    })


# ---------------------------------------------------------------------------
# Tool 12: sbkg_get_ontology
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_get_ontology(format: str = "summary") -> str:
    """
    Return the SBKG ontology schema.

    Args:
        format: One of 'summary', 'turtle'. Summary gives a concise overview.

    Returns:
        str: JSON with the ontology in the requested format
    """
    if format == "turtle":
        return json.dumps({"format": "turtle", "content": get_ontology_turtle()})
    return json.dumps({"format": "summary", "content": get_ontology_summary()})


# ---------------------------------------------------------------------------
# Tool 13: sbkg_delete_note
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_delete_note(title: str) -> str:
    """
    Delete a note and all its triples from the knowledge graph.

    Args:
        title: The title of the note to delete

    Returns:
        str: JSON with deletion status and triple count removed
    """
    store = _get_store()
    slug = slugify(title)
    note_uri = NamedNode(make_note_uri(slug))

    # Remove triples where note is subject
    removed_as_subject = store.remove_triples(subject=note_uri)
    # Remove triples where note is object (incoming links)
    removed_as_object = store.remove_triples(obj=note_uri)

    total = removed_as_subject + removed_as_object
    if total == 0:
        return json.dumps({
            "deleted": False,
            "uri": make_note_uri(slug),
            "message": f"No note found with title '{title}'",
        })
    return json.dumps({
        "deleted": True,
        "uri": make_note_uri(slug),
        "triples_removed": total,
    })


# ---------------------------------------------------------------------------
# Tool 14: sbkg_delete_bookmark
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_delete_bookmark(title: str) -> str:
    """
    Delete a bookmark and all its triples from the knowledge graph.

    Args:
        title: The title of the bookmark to delete

    Returns:
        str: JSON with deletion status and triple count removed
    """
    store = _get_store()
    slug = slugify(title)
    bm_uri = NamedNode(make_bookmark_uri(slug))

    removed_as_subject = store.remove_triples(subject=bm_uri)
    removed_as_object = store.remove_triples(obj=bm_uri)

    total = removed_as_subject + removed_as_object
    if total == 0:
        return json.dumps({
            "deleted": False,
            "uri": make_bookmark_uri(slug),
            "message": f"No bookmark found with title '{title}'",
        })
    return json.dumps({
        "deleted": True,
        "uri": make_bookmark_uri(slug),
        "triples_removed": total,
    })


# ---------------------------------------------------------------------------
# Tool 15: sbkg_clear_all
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_clear_all(confirm: bool = False) -> str:
    """
    Delete ALL triples from the knowledge graph, then reload the ontology.
    Use this to reset after testing. Requires confirm=True as a safety check.

    Args:
        confirm: Must be True to proceed. Prevents accidental wipes.

    Returns:
        str: JSON with deletion status
    """
    if not confirm:
        return json.dumps({
            "cleared": False,
            "message": "Safety check: pass confirm=True to wipe all data.",
        })

    store = _get_store()
    before = store._count_triples()
    # Remove everything
    store.remove_triples()
    # Reload ontology
    store._ensure_ontology()
    after = store._count_triples()
    return json.dumps({
        "cleared": True,
        "triples_removed": before,
        "ontology_triples_reloaded": after,
    })


# ---------------------------------------------------------------------------
# Tool 16: sbkg_add_project
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_add_project(
    name: str,
    description: str = "",
    homepage: str | None = None,
    repository: str | None = None,
    programming_language: str | None = None,
    platform: str | None = None,
    maintainers: list[str] | None = None,
    developers: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """
    Create a project in the knowledge graph with DOAP properties.

    Args:
        name: The project name
        description: Project description
        homepage: Project homepage URL
        repository: Source code repository URL
        programming_language: Primary programming language
        platform: Target platform
        maintainers: List of maintainer names
        developers: List of developer names
        tags: List of tag strings

    Returns:
        str: JSON with the created project URI, name, and triple count
    """
    store = _get_store()
    project = Project(
        name=name,
        description=description,
        homepage=homepage,
        repository=repository,
        programming_language=programming_language,
        platform=platform,
        maintainers=maintainers or [],
        developers=developers or [],
        tags=tags or [],
        created_at=now_iso(),
    )
    quads = extract_project_triples(project)
    store.insert_triples(quads)

    return json.dumps({
        "uri": make_project_uri(name),
        "name": name,
        "triples_added": len(quads),
    })


# ---------------------------------------------------------------------------
# Tool 17: sbkg_add_note_from_email
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_add_note_from_email(raw_email: str) -> str:
    """
    Create a note from a raw RFC 2822 email string.

    Parses subject, body, sender, recipients, date, and attachments
    from the email and creates a FleetingNote in the knowledge graph.

    Args:
        raw_email: The raw email text (RFC 2822 format)

    Returns:
        str: JSON with the created note URI, title, creator, tags, and triple count
    """
    store = _get_store()
    note = parse_email(raw_email)
    quads = extract_triples(note)
    store.insert_triples(quads)

    slug = slugify(note.title)
    return json.dumps({
        "uri": make_note_uri(slug),
        "title": note.title,
        "creator": note.creator,
        "tags": note.tags,
        "triples_added": len(quads),
    })


# ---------------------------------------------------------------------------
# Tool 18: sbkg_get_note
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_get_note(title: str) -> str:
    """
    Fetch all properties of a note by title.

    Args:
        title: The title of the note to fetch

    Returns:
        str: JSON with found, title, content, type, tags, links, status,
             project_uri, area_uri, created_at, modified_at, mentions
    """
    store = _get_store()
    slug = slugify(title)
    note_uri = make_note_uri(slug)

    # Check if note exists
    sparql = (
        f"SELECT ?pred ?obj WHERE {{ <{note_uri}> ?pred ?obj }}"
    )
    results = store.query_sparql(sparql)
    if not results:
        return json.dumps({"found": False, "title": title})

    # Build response from predicate-object pairs
    props: dict[str, list[str]] = {}
    for row in results:
        pred = row["pred"]
        obj = row["obj"]
        props.setdefault(pred, []).append(obj)

    def first(pred: str) -> str | None:
        vals = props.get(pred)
        return vals[0] if vals else None

    def all_vals(pred: str) -> list[str]:
        return props.get(pred, [])

    # Resolve tag URIs to label strings
    tag_uris = all_vals(f"{SBKG_NS}hasTag")
    tags: list[str] = []
    for tag_uri in tag_uris:
        tag_sparql = f'SELECT ?label WHERE {{ <{tag_uri}> <{SBKG_NS}title> ?label }}'
        tag_results = store.query_sparql(tag_sparql)
        if tag_results:
            tags.append(tag_results[0]["label"])

    # Resolve mention person URIs to names
    mention_uris = all_vals(f"{SBKG_NS}mentions")
    mentions: list[str] = []
    for person_uri in mention_uris:
        name_sparql = f'SELECT ?name WHERE {{ <{person_uri}> <{FOAF_NS}name> ?name }}'
        name_results = store.query_sparql(name_sparql)
        if name_results:
            mentions.append(name_results[0]["name"])

    # Extract link targets
    link_uris = all_vals(f"{SBKG_NS}linksTo")
    links: list[str] = []
    for link_uri in link_uris:
        link_sparql = f'SELECT ?title WHERE {{ <{link_uri}> <{SBKG_NS}title> ?title }}'
        link_results = store.query_sparql(link_sparql)
        if link_results:
            links.append(link_results[0]["title"])
        else:
            # Extract slug from URI as fallback
            links.append(link_uri.split("/note/")[-1])

    return json.dumps({
        "found": True,
        "title": first(f"{SBKG_NS}title") or title,
        "content": first(f"{SBKG_NS}content"),
        "type": first("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
        "tags": tags,
        "links": links,
        "status": first(f"{SBKG_NS}hasStatus"),
        "project_uri": first(f"{SBKG_NS}belongsToProject"),
        "area_uri": first(f"{SBKG_NS}belongsToArea"),
        "created_at": first(f"{SBKG_NS}createdAt"),
        "modified_at": first(f"{SBKG_NS}modifiedAt"),
        "mentions": mentions,
    })


# ---------------------------------------------------------------------------
# Tool 19: sbkg_update_note
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_update_note(
    title: str,
    content: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    project: str | None = None,
    area: str | None = None,
    links: list[str] | None = None,
    note_type: str | None = None,
) -> str:
    """
    Update an existing note. Only supplied fields are changed; omitted fields
    retain current values. Tags and links, if supplied, replace existing sets.

    Args:
        title: The title of the note to update (used to find it)
        content: New body content
        tags: New tag list (replaces all existing tags)
        status: New status string
        project: New project name
        area: New area name
        links: New link list (replaces all existing links)
        note_type: New note type

    Returns:
        str: JSON with update status, URI, and updated fields
    """
    store = _get_store()
    slug = slugify(title)
    note_uri_str = make_note_uri(slug)
    note_uri = NamedNode(note_uri_str)

    # Fetch current state
    current = json.loads(sbkg_get_note(title))
    if not current.get("found"):
        return json.dumps({
            "updated": False,
            "uri": note_uri_str,
            "message": f"No note found with title '{title}'",
        })

    # Resolve current project name from URI
    current_project: str | None = None
    proj_uri = current.get("project_uri")
    if proj_uri:
        proj_sparql = f'SELECT ?name WHERE {{ <{proj_uri}> <{SBKG_NS}title> ?name }}'
        proj_results = store.query_sparql(proj_sparql)
        if proj_results:
            current_project = proj_results[0]["name"]

    # Resolve current area name from URI
    current_area: str | None = None
    area_uri = current.get("area_uri")
    if area_uri:
        area_sparql = f'SELECT ?name WHERE {{ <{area_uri}> <{SBKG_NS}title> ?name }}'
        area_results = store.query_sparql(area_sparql)
        if area_results:
            current_area = area_results[0]["name"]

    # Resolve current note_type from full URI
    current_type = "Note"
    type_uri = current.get("type")
    if type_uri and type_uri.startswith(SBKG_NS):
        current_type = type_uri[len(SBKG_NS):]

    # Resolve current status from URI or literal
    current_status = current.get("status")
    if current_status and current_status.startswith(SBKG_NS):
        current_status = current_status[len(SBKG_NS):]

    # Merge: caller-supplied values override current
    merged_content = content if content is not None else (current.get("content") or "")
    merged_tags = tags if tags is not None else current.get("tags", [])
    merged_links = links if links is not None else current.get("links", [])
    merged_status = status if status is not None else current_status
    merged_project = project if project is not None else current_project
    merged_area = area if area is not None else current_area
    merged_type = note_type if note_type is not None else current_type

    # Remove all existing triples for this note (as subject)
    store.remove_triples(subject=note_uri)

    # Build new Note and re-extract triples
    new_note = Note(
        title=current.get("title") or title,
        content=merged_content,
        note_type=merged_type,
        tags=merged_tags,
        links=merged_links,
        project=merged_project,
        area=merged_area,
        status=merged_status,
        created_at=current.get("created_at"),
        modified_at=now_iso(),
    )
    quads = extract_triples(new_note)
    store.insert_triples(quads)

    return json.dumps({
        "updated": True,
        "uri": note_uri_str,
        "title": new_note.title,
        "triples_added": len(quads),
    })


# ---------------------------------------------------------------------------
# Tool 20: sbkg_search
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_search(
    query: str,
    entity_type: str | None = None,
    tag: str | None = None,
    limit: int = 20,
) -> str:
    """
    Search notes and bookmarks by title substring (case-insensitive).
    Optional filters by type and tag.

    Args:
        query: Search string to match against titles
        entity_type: Filter by type — "note", "bookmark", or None for both
        tag: Filter by tag name
        limit: Maximum results to return (default 20)

    Returns:
        str: JSON array of {uri, title, type}
    """
    store = _get_store()

    # Escape quotes and backslashes in the query string
    safe_query = query.replace("\\", "\\\\").replace('"', '\\"')

    type_filter = ""
    if entity_type:
        et = entity_type.lower()
        if et == "note":
            type_filter = f"FILTER(?type != <{SBKG_NS}Bookmark> && ?type != <{SBKG_NS}Concept>)"
        elif et == "bookmark":
            type_filter = f"FILTER(?type = <{SBKG_NS}Bookmark>)"

    tag_clause = ""
    if tag:
        safe_tag = tag.replace("\\", "\\\\").replace('"', '\\"')
        tag_clause = (
            f'?entity <{SBKG_NS}hasTag> ?tagUri . '
            f'?tagUri <{SBKG_NS}title> "{safe_tag}" . '
        )

    sparql = f"""
    SELECT DISTINCT ?entity ?title ?type WHERE {{
      ?entity <{SBKG_NS}title> ?title .
      ?entity a ?type .
      FILTER(?type != <{SBKG_NS}Concept>)
      FILTER(CONTAINS(LCASE(?title), LCASE("{safe_query}")))
      {type_filter}
      {tag_clause}
    }}
    LIMIT {limit}
    """
    results = store.query_sparql(sparql)
    items = []
    for row in results:
        items.append({
            "uri": row["entity"],
            "title": row["title"],
            "type": row["type"],
        })
    return json.dumps(items)


# ---------------------------------------------------------------------------
# Resource: LLM Usage Guide
# ---------------------------------------------------------------------------
@mcp.resource(
    "sbkg://guide/llm-usage",
    name="llm-usage-guide",
    title="SBKG LLM Usage Guide",
    description="Comprehensive guide for LLMs on how to use the SBKG MCP tools, "
                "data model, SPARQL patterns, and best practices.",
    mime_type="text/markdown",
)
def llm_usage_guide() -> str:
    """Return the LLM usage guide as a markdown resource."""
    return _read_guide()


# ---------------------------------------------------------------------------
# Tool 18: sbkg_usage_guide
# ---------------------------------------------------------------------------
@mcp.tool()
def sbkg_usage_guide() -> str:
    """
    Load the SBKG usage guide for LLMs.

    Call this tool at the start of a session or whenever you need guidance on
    how to use the SBKG tools effectively. Returns a comprehensive markdown
    document covering the data model, tool selection, SPARQL patterns, and
    best practices.

    Returns:
        str: Markdown content of the LLM usage guide
    """
    return _read_guide()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
