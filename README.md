# sbkg-mcp

A **personal knowledge graph** exposed as an [MCP](https://modelcontextprotocol.io/) server. Store notes, bookmarks, concepts, and their relationships as **RDF triples** in a persistent [Oxigraph](https://github.com/oxigraph/oxigraph) database — then query them with **SPARQL** from any MCP-compatible LLM client.

```
  You (via LLM)          MCP Protocol            SBKG Server
 ┌─────────────┐       ┌───────────┐        ┌──────────────────┐
 │ Claude Code  │──────▸│  Tools &  │───────▸│  Oxigraph Store  │
 │ ChatGPT      │◂──────│ Resources │◂───────│  (RDF Triples)   │
 │ Any MCP host │       └───────────┘        └──────────────────┘
 └─────────────┘                                     │
                                              ┌──────┴──────┐
                                              │  Ontologies  │
                                              │  sbkg + SKOS │
                                              │  DC + DOAP   │
                                              └─────────────┘
```

## Why a Knowledge Graph?

Flat notes and bookmarks get lost. A knowledge graph lets you:

- **Connect** information across topics — a bookmark about Enphase microinverters automatically relates to your solar project notes, electrical code references, and installer contacts
- **Query** with precision — "show me all bookmarks tagged `solar` that I haven't read yet" is a single SPARQL query
- **Build hierarchies** — SKOS lets you express that `enphase` is a narrower concept under `solar`, so searching for `solar` finds everything
- **Combine with other MCP servers** — pull emails, calendar events, or GitHub issues from other MCP connectors and link them into your graph

## Quick Start

### Installation

```bash
# Clone and install
git clone https://github.com/netsemantics/sbkg-mcp.git
cd sbkg-mcp
uv pip install -e .
```

### MCP Configuration

Add to your Claude Code MCP config (`~/.claude/settings.json` or project-level):

```json
{
  "mcpServers": {
    "sbkg": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/sbkg-mcp", "sbkg-mcp"]
    }
  }
}
```

### First Steps

Once connected, try these in your LLM client:

```
> "Add a bookmark for https://example.com/article titled 'Great Article' tagged with research"

> "What bookmarks do I have?"

> "Show me everything tagged with 'solar'"
```

## Examples

### Add a bookmark and query it

```
User: Save this link — https://diysolarforum.com/threads/ground-mount.26706/
      Title it "DIY Ground Mount Solar" and tag it with solar and diy.

LLM calls: sbkg_add_bookmark(
  title="DIY Ground Mount Solar",
  url="https://diysolarforum.com/threads/ground-mount.26706/",
  tags=["solar", "diy"],
  status="ToRead"
)
```

```
User: What DIY resources do I have?

LLM calls: sbkg_query_sparql("""
  PREFIX sbkg: <http://secondbrain.ai/kg/>
  SELECT ?title ?url WHERE {
    ?b a sbkg:Bookmark .
    ?b sbkg:hasTag ?tag .
    ?tag sbkg:title "diy" .
    ?b sbkg:title ?title .
    ?b sbkg:sourceUrl ?url .
  }
""")
```

### Batch import with SPARQL UPDATE

Instead of adding bookmarks one at a time, insert many in a single call:

```
User: Add these three bookmarks about Python testing.

LLM calls: sbkg_update_sparql("""
  PREFIX sbkg: <http://secondbrain.ai/kg/>
  INSERT DATA {
    <http://secondbrain.ai/kg/bookmark/pytest-docs> a sbkg:Bookmark ;
      sbkg:title "pytest documentation" ;
      sbkg:sourceUrl "https://docs.pytest.org/" ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/python> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/testing> ;
      sbkg:hasStatus sbkg:Reference .
    <http://secondbrain.ai/kg/bookmark/hypothesis> a sbkg:Bookmark ;
      sbkg:title "Hypothesis property-based testing" ;
      sbkg:sourceUrl "https://hypothesis.readthedocs.io/" ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/python> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/testing> ;
      sbkg:hasStatus sbkg:ToRead .
    <http://secondbrain.ai/kg/bookmark/coverage-py> a sbkg:Bookmark ;
      sbkg:title "Coverage.py" ;
      sbkg:sourceUrl "https://coverage.readthedocs.io/" ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/python> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/testing> ;
      sbkg:hasStatus sbkg:ToRead .
  }
""")
```

### Build concept hierarchies with SKOS

```
User: Set up a tag hierarchy — "enphase" and "solar-thermal" should be
      subtopics of "solar".

LLM calls: sbkg_update_sparql("""
  PREFIX sbkg: <http://secondbrain.ai/kg/>
  PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
  INSERT DATA {
    <http://secondbrain.ai/kg/concept/enphase>
      skos:broader <http://secondbrain.ai/kg/concept/solar> .
    <http://secondbrain.ai/kg/concept/solar-thermal>
      skos:broader <http://secondbrain.ai/kg/concept/solar> .
    <http://secondbrain.ai/kg/concept/solar>
      skos:narrower <http://secondbrain.ai/kg/concept/enphase> ;
      skos:narrower <http://secondbrain.ai/kg/concept/solar-thermal> .
  }
""")
```

Then query "everything under solar" including subtopics:

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?title ?url WHERE {
  ?tag skos:broader* <http://secondbrain.ai/kg/concept/solar> .
  ?b sbkg:hasTag ?tag .
  ?b sbkg:title ?title .
  ?b sbkg:sourceUrl ?url .
}
```

### Multi-MCP workflow: Email to knowledge graph

When SBKG is combined with an email MCP server (e.g. Gmail, Outlook), an LLM can extract knowledge from emails and store it:

```
User: Check my recent emails about the solar permit and save
      any useful info to my knowledge graph.

LLM calls: gmail_search(query="solar permit", max_results=5)
  → Returns 3 emails with permit status updates

LLM calls: sbkg_add_note(
  title="Solar Permit Status - Feb 2026",
  content="Forsyth County approved the electrical permit on 2/10. ..."
  tags=["solar", "permits", "forsyth-county"],
  project="home-solar"
)

LLM calls: sbkg_add_bookmark(
  title="Forsyth County Permit Portal",
  url="https://forsythco.com/permits/status/12345",
  tags=["solar", "permits", "forsyth-county"]
)
```

See [docs/examples.md](docs/examples.md) for more workflows including GitHub integration, calendar events, and research pipelines.

## Tools

### Creating Data

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `sbkg_add_note` | Create a note with metadata and triples | title, content, note_type, tags, links, project, area, status |
| `sbkg_add_bookmark` | Create a bookmark entry | title, url, description, tags, status |
| `sbkg_extract_from_markdown` | Parse a local .md file into the graph | path |
| `sbkg_bulk_import` | Bulk-load RDF from an in-memory string | data, format |
| `sbkg_update_sparql` | Execute SPARQL UPDATE (INSERT/DELETE) | update |

### Querying Data

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `sbkg_query_sparql` | Run SPARQL SELECT/ASK/CONSTRUCT/DESCRIBE | sparql |
| `sbkg_query_natural` | Get ontology context for natural language → SPARQL | question |
| `sbkg_get_related_notes` | Find notes related via tags, links, project/area | title, max_results |
| `sbkg_get_stats` | Graph statistics (triple count, entity counts) | — |
| `sbkg_get_ontology` | Return ontology as summary or Turtle | format |
| `sbkg_usage_guide` | Load the comprehensive LLM usage guide | — |

### Modifying & Managing Data

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `sbkg_update_sparql` | SPARQL UPDATE for batch modify/delete/insert | update |
| `sbkg_delete_note` | Delete a note and all its triples | title |
| `sbkg_delete_bookmark` | Delete a bookmark and its triples | title |
| `sbkg_export_triples` | Export graph in RDF format | format, path |
| `sbkg_import_triples` | Import RDF from a file | path, format |
| `sbkg_clear_all` | Wipe all data and reload ontology | confirm (must be true) |

## Ontology

SBKG uses a modular ontology loaded from `ontology/*.ttl`:

| File | Vocabulary | What it covers |
|------|-----------|----------------|
| `sbkg.ttl` | Core | Notes, Bookmarks, Concepts, Projects, Areas, People, Tools |
| `skos.ttl` | [SKOS](https://www.w3.org/TR/skos-reference/) | Concept hierarchies — broader, narrower, related, ConceptScheme |
| `dc.ttl` | [Dublin Core](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/) | Resource metadata — creator, dates, license, format, relations |
| `doap.ttl` | [DOAP](https://github.com/ewilderj/doap/wiki) | Software projects — repository, language, releases, maintainer |

The core `sbkg:Concept` class is aligned as a subclass of `skos:Concept`, enabling SKOS hierarchy queries to work across all tags.

## Data Storage

- **Database**: `~/Library/Application Support/sbkg/oxigraph/` (macOS) or equivalent XDG path
- **Format**: Oxigraph persistent store (RocksDB-backed)
- **Exports**: `~/Library/Application Support/sbkg/exports/`

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run the server directly
uv run sbkg-mcp
```

## License

MIT
