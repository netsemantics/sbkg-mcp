"""FastMCP server with SBKG tools."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pyoxigraph import DefaultGraph, Literal, NamedNode, Quad

from .markdown_parser import extract_triples, note_to_markdown, parse_markdown
from .models import Bookmark, Note
from .ontology import get_ontology_summary, get_ontology_turtle
from .store import KnowledgeStore
from .utils import (
    SBKG_NS,
    make_bookmark_uri,
    make_concept_uri,
    make_note_uri,
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
    tags = tags or []
    slug = slugify(title)
    bm_uri = NamedNode(make_bookmark_uri(slug))
    graph = DefaultGraph()
    quads: list[Quad] = []

    def q(s, p, o):
        quads.append(Quad(s, p, o, graph))

    q(bm_uri, _RDF_TYPE, NamedNode(f"{SBKG_NS}Bookmark"))
    q(bm_uri, NamedNode(f"{SBKG_NS}title"), Literal(title))
    q(bm_uri, NamedNode(f"{SBKG_NS}sourceUrl"), Literal(url))
    if description:
        q(bm_uri, NamedNode(f"{SBKG_NS}content"), Literal(description))
    for tag in tags:
        concept_uri = NamedNode(make_concept_uri(tag))
        q(concept_uri, _RDF_TYPE, NamedNode(f"{SBKG_NS}Concept"))
        q(concept_uri, NamedNode(f"{SBKG_NS}title"), Literal(tag))
        q(bm_uri, NamedNode(f"{SBKG_NS}hasTag"), concept_uri)
    if status:
        q(bm_uri, NamedNode(f"{SBKG_NS}hasStatus"), NamedNode(f"{SBKG_NS}{status}"))
    q(bm_uri, NamedNode(f"{SBKG_NS}createdAt"), Literal(now_iso(), datatype=_XSD_DT))

    store.insert_triples(quads)
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
            "All SBKG entities use the namespace PREFIX sbkg: <http://secondbrain.ai/kg/>. "
            "Notes have type sbkg:Note (or subtypes), bookmarks sbkg:Bookmark, tags sbkg:Concept."
        ),
        "example_queries": [
            {
                "description": "List all notes",
                "sparql": "PREFIX sbkg: <http://secondbrain.ai/kg/> SELECT ?note ?title WHERE { ?note a sbkg:Note . ?note sbkg:title ?title . }",
            },
            {
                "description": "Find notes with a specific tag",
                "sparql": "PREFIX sbkg: <http://secondbrain.ai/kg/> SELECT ?note ?title WHERE { ?note sbkg:hasTag ?tag . ?tag sbkg:title \"python\" . ?note sbkg:title ?title . }",
            },
            {
                "description": "Find notes in a project",
                "sparql": "PREFIX sbkg: <http://secondbrain.ai/kg/> SELECT ?note ?title WHERE { ?note sbkg:belongsToProject ?proj . ?proj sbkg:title \"my-project\" . ?note sbkg:title ?title . }",
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
    PREFIX sbkg: <http://secondbrain.ai/kg/>

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
# Tool 12: sbkg_get_ontology (was 10)
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
# Tool 16: sbkg_usage_guide
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
