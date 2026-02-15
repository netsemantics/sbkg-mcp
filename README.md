# sbkg-mcp

Second Brain Knowledge Graph MCP Server — stores notes, bookmarks, and their relationships as RDF triples using Oxigraph.

## Features

- Store notes and bookmarks as RDF triples in a persistent Oxigraph database
- Parse Markdown files with YAML frontmatter and wikilinks into the knowledge graph
- SPARQL querying with natural language assistance
- Find related notes via shared tags, links, projects, and areas
- Export/import RDF in multiple formats (Turtle, N-Triples, etc.)
- Cross-platform (macOS, Linux, Windows) with XDG-compliant data paths

## Installation

```bash
uv pip install sbkg-mcp
```

## Usage

Add to your Claude Code MCP config:

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

## Tools

| Tool | Description |
|------|-------------|
| `sbkg_add_note` | Create a note with metadata and triples |
| `sbkg_add_bookmark` | Create a bookmark |
| `sbkg_extract_from_markdown` | Parse a .md file into triples |
| `sbkg_query_sparql` | Execute SPARQL queries |
| `sbkg_query_natural` | Get ontology context for NL→SPARQL |
| `sbkg_get_related_notes` | Find related notes |
| `sbkg_get_stats` | Graph statistics |
| `sbkg_export_triples` | Export to RDF formats |
| `sbkg_import_triples` | Import from RDF files |
| `sbkg_get_ontology` | Return ontology schema |

## License

MIT
