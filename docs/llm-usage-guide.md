# SBKG MCP — LLM Usage Guide

This guide explains how an LLM should use the SBKG MCP server to manage a
personal knowledge graph.

## Overview

SBKG stores **notes**, **bookmarks**, and **concepts** as RDF triples in an
Oxigraph database. The graph is queryable via SPARQL and exposed through
MCP tools. Think of it as a structured knowledge base that an LLM can read
from and write to across conversations.

## Core Data Model

| Type | URI Pattern | Purpose |
|------|-------------|---------|
| `sbkg:Note` | `sbkg:note/{slug}` | Knowledge notes (subtypes: DailyNote, ProjectNote, AreaNote, ResourceNote, FleetingNote) |
| `sbkg:Bookmark` | `sbkg:bookmark/{slug}` | Saved URLs with metadata |
| `sbkg:Concept` | `sbkg:concept/{slug}` | Tags/topics — aligned with `skos:Concept` for hierarchy |
| `sbkg:Project` | `sbkg:project/{slug}` | Project groupings |
| `sbkg:Area` | `sbkg:area/{slug}` | Areas of responsibility |
| `foaf:Person` | `sbkg:person/{slug}` | People — email senders, project maintainers/developers |

### Key Properties

- `sbkg:title` — display name (string)
- `sbkg:content` — body text or description (string)
- `sbkg:hasTag` — links entity → Concept
- `sbkg:linksTo` — directional link between notes (wikilinks)
- `sbkg:sourceUrl` — bookmark URL
- `sbkg:hasStatus` — bookmark status (ToRead, Reading, Read, Reference)
- `sbkg:belongsToProject` / `sbkg:belongsToArea` — organizational links
- `sbkg:createdAt` / `sbkg:modifiedAt` — timestamps (xsd:dateTime)
- `sbkg:mentions` — links note → Person (e.g. email To/CC recipients)
- `foaf:mbox` — email address on a Person (as `mailto:` URI, emitted from email ingestion)
- `dcterms:description` / `dcterms:creator` / `dcterms:language` / `dcterms:license` — Dublin Core metadata on notes
- `doap:name` / `doap:repository` / `doap:maintainer` / `doap:developer` / `doap:programming-language` — DOAP properties on projects

### Extended Vocabularies

**SKOS** (`skos:`) — Use for concept hierarchies:
- `skos:broader` / `skos:narrower` — parent/child tag relationships
- `skos:related` — associative links between concepts
- `skos:prefLabel` / `skos:altLabel` — canonical and alternative names
- `skos:ConceptScheme` / `skos:inScheme` — group concepts into schemes

**Dublin Core** (`dcterms:`) — Use for rich metadata:
- `dcterms:creator`, `dcterms:contributor` — people
- `dcterms:created`, `dcterms:modified`, `dcterms:issued` — dates
- `dcterms:license`, `dcterms:format`, `dcterms:language`
- `dcterms:isPartOf`, `dcterms:hasPart`, `dcterms:references`

**DOAP** (`doap:`) — Use for software project descriptions:
- `doap:Project`, `doap:Repository`, `doap:GitRepository`, `doap:Version`
- `doap:programming-language`, `doap:homepage`, `doap:bug-database`
- `doap:maintainer`, `doap:developer` (→ `foaf:Person`)

## Tool Selection Guide

### Creating Data

| Scenario | Tool | Why |
|----------|------|-----|
| Add a single note | `sbkg_add_note` | Handles slug generation, timestamps, tag creation |
| Add a single bookmark | `sbkg_add_bookmark` | Same conveniences as add_note |
| Ingest an existing .md file | `sbkg_extract_from_markdown` | Parses frontmatter + wikilinks automatically |
| Register a software project | `sbkg_add_project` | Creates DOAP-backed project with repo, maintainers, language |
| Ingest a raw email | `sbkg_add_note_from_email` | Parses RFC 2822 → FleetingNote with sender, recipients, tags |
| Add many items at once | `sbkg_bulk_import` | Pass a Turtle or N-Triples string — fastest for batch creation |
| Complex batch operations | `sbkg_update_sparql` | Use INSERT DATA for bulk inserts with full control over URIs and properties |

### Querying Data

| Scenario | Tool | Why |
|----------|------|-----|
| Fetch a note by title | `sbkg_get_note` | Returns all properties without writing SPARQL |
| Search by title substring | `sbkg_search` | Case-insensitive search with optional type/tag filters |
| Structured queries | `sbkg_query_sparql` | Full SPARQL SELECT, ASK, CONSTRUCT, DESCRIBE |
| "What do I have about X?" | `sbkg_query_natural` → `sbkg_query_sparql` | Get ontology context first, then write SPARQL |
| Find related notes | `sbkg_get_related_notes` | Finds connections via shared tags, links, project, area |
| Graph overview | `sbkg_get_stats` | Quick count of triples and entities by type |
| Browse the schema | `sbkg_get_ontology` | Returns ontology as summary or Turtle |

### Modifying Data

| Scenario | Tool | Why |
|----------|------|-----|
| Update a note's fields | `sbkg_update_note` | Update content, tags, status, etc. without raw SPARQL |
| Delete a note | `sbkg_delete_note` | Removes all triples (as subject and object) |
| Delete a bookmark | `sbkg_delete_bookmark` | Same as above |
| Rename, re-tag, or update | `sbkg_update_sparql` | Use DELETE/INSERT WHERE patterns for complex updates |
| Bulk re-tag | `sbkg_update_sparql` | Pattern-match and transform in one operation |
| Full reset | `sbkg_clear_all` | Wipes everything, reloads ontology (requires confirm=True) |

### Exporting Data

| Scenario | Tool | Why |
|----------|------|-----|
| Export graph to file | `sbkg_export_triples` | Turtle, N-Triples, N-Quads, TriG, RDF/XML |
| Import from file | `sbkg_import_triples` | Load .ttl or other RDF files from disk |
| Import from string | `sbkg_bulk_import` | Load RDF from generated content without writing a file |

## SPARQL Patterns

### Required Prefixes

```sparql
PREFIX sbkg:    <http://sb.ai/kg/>
PREFIX skos:    <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX doap:    <http://usefulinc.com/ns/doap#>
PREFIX foaf:    <http://xmlns.com/foaf/0.1/>
```

### Important: URI Escaping

Prefixed names cannot contain `/`. Since SBKG URIs use paths like
`sbkg:bookmark/my-slug`, you **must use full IRIs** in SPARQL:

```sparql
# WRONG — will error
sbkg:bookmark/my-slug sbkg:title ?title .

# CORRECT
<http://sb.ai/kg/bookmark/my-slug> sbkg:title ?title .
```

This applies in `sbkg_query_sparql`, `sbkg_update_sparql`, and Turtle
passed to `sbkg_bulk_import`. However, class and property names work
fine with prefixes: `sbkg:Bookmark`, `sbkg:title`, `sbkg:hasTag`.

### Common Queries

**List all bookmarks:**
```sparql
PREFIX sbkg: <http://sb.ai/kg/>
SELECT ?title ?url WHERE {
  ?b a sbkg:Bookmark .
  ?b sbkg:title ?title .
  ?b sbkg:sourceUrl ?url .
}
```

**Find bookmarks by tag:**
```sparql
PREFIX sbkg: <http://sb.ai/kg/>
SELECT ?title ?url WHERE {
  ?b a sbkg:Bookmark .
  ?b sbkg:hasTag ?tag .
  ?tag sbkg:title "python" .
  ?b sbkg:title ?title .
  ?b sbkg:sourceUrl ?url .
}
```

**Count bookmarks per tag:**
```sparql
PREFIX sbkg: <http://sb.ai/kg/>
SELECT ?tag (COUNT(DISTINCT ?b) AS ?count) WHERE {
  ?b a sbkg:Bookmark .
  ?b sbkg:hasTag ?tagUri .
  ?tagUri sbkg:title ?tag .
} GROUP BY ?tag ORDER BY DESC(?count)
```

**Find all projects by programming language:**
```sparql
PREFIX doap: <http://usefulinc.com/ns/doap#>
SELECT ?name ?desc WHERE {
  ?p a doap:Project .
  ?p doap:name ?name .
  ?p doap:programming-language "Python" .
  OPTIONAL { ?p doap:shortdesc ?desc }
}
```

**Find notes from a specific person:**
```sparql
PREFIX sbkg: <http://sb.ai/kg/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?title WHERE {
  ?n a sbkg:Note .
  ?n sbkg:title ?title .
  { ?n dcterms:creator ?person } UNION { ?n sbkg:mentions ?person }
  ?person foaf:name "Jane Developer" .
}
```

**Search by content (FILTER + CONTAINS):**
```sparql
PREFIX sbkg: <http://sb.ai/kg/>
SELECT ?title ?desc WHERE {
  ?b a sbkg:Bookmark .
  ?b sbkg:title ?title .
  ?b sbkg:content ?desc .
  FILTER(CONTAINS(LCASE(?desc), "troubleshoot"))
}
```

### Common Updates

**Batch insert bookmarks:**
```sparql
PREFIX sbkg: <http://sb.ai/kg/>
INSERT DATA {
  <http://sb.ai/kg/bookmark/example-1> a sbkg:Bookmark ;
    sbkg:title "Example 1" ;
    sbkg:sourceUrl "https://example.com/1" ;
    sbkg:hasStatus sbkg:ToRead .
  <http://sb.ai/kg/bookmark/example-2> a sbkg:Bookmark ;
    sbkg:title "Example 2" ;
    sbkg:sourceUrl "https://example.com/2" ;
    sbkg:hasStatus sbkg:ToRead .
}
```

**Rename a tag across all items:**
```sparql
PREFIX sbkg: <http://sb.ai/kg/>
DELETE { ?concept sbkg:title "old-name" }
INSERT { ?concept sbkg:title "new-name" }
WHERE  { ?concept sbkg:title "old-name" }
```

**Add SKOS hierarchy between concepts:**
```sparql
PREFIX sbkg: <http://sb.ai/kg/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
INSERT DATA {
  <http://sb.ai/kg/concept/react> skos:broader <http://sb.ai/kg/concept/frontend> .
  <http://sb.ai/kg/concept/frontend> skos:narrower <http://sb.ai/kg/concept/react> .
}
```

## Best Practices

1. **Start with `sbkg_get_stats`** to understand what's in the graph before
   querying or modifying.

2. **Use `sbkg_query_natural` first** when unsure how to structure a SPARQL
   query — it returns the ontology context to inform query construction.

3. **Prefer `sbkg_update_sparql`** for batch operations over looping
   `sbkg_add_note` or `sbkg_add_bookmark`.

4. **Prefer `sbkg_bulk_import`** when you can generate complete Turtle — it's
   the fastest path for large imports.

5. **Use full IRIs** (not prefixed names) when referencing entities with `/`
   in their URI path.

6. **Use SKOS relationships** to build tag hierarchies rather than creating
   flat, redundant tags.

7. **Check before creating** — query first to avoid duplicate entries. The
   store does not enforce uniqueness.

8. **Use `sbkg_get_ontology`** (format=summary) if you need a quick reminder
   of available classes, properties, and prefixes.

9. **Use `sbkg_add_project`** for software project tracking instead of raw
   SPARQL — it handles DOAP triples, repository, maintainers, and tags
   automatically.

10. **Use `sbkg_add_note_from_email`** for email ingestion instead of manual
    note creation — it parses RFC 2822 headers, extracts sender/recipients as
    `foaf:Person` entities with `foaf:mbox`, and auto-tags with "email".

11. **Use `sbkg_get_note`** to fetch a note's full state before deciding what
    to update — it resolves tags, links, and mentions without SPARQL.

12. **Use `sbkg_update_note`** for simple field changes (content, tags, status)
    instead of writing DELETE/INSERT SPARQL. Tags and links replace existing
    sets; omitted fields keep their current values.

13. **Use `sbkg_search`** for quick title-based lookups — it's faster and
    simpler than writing SPARQL FILTER queries. Use the `entity_type` and
    `tag` parameters to narrow results.
