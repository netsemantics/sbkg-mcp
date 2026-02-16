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

| Function (tool)              | Purpose                                                                 | Key Parameters                                                                                                   |
|------------------------------|-------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| sbkg_add_note                | Create a new note (markdown content) and add its triples.              | title (required), content, note_type, tags, links, project, area, status                                       |
| sbkg_add_bookmark            | Create a new bookmark entry.                                           | title, url, description, tags, status                                                                           |
| sbkg_extract_from_markdown  | Parse a local .md file and import its triples.                         | path                                                                                                            |
| sbkg_query_sparql           | Run an arbitrary SPARQL query (SELECT/ASK/CONSTRUCT/DESCRIBE).         | sparql                                                                                                          |
| sbkg_query_natural          | Get ontology context & guidance for turning a natural-language question into SPARQL. | question                                                                                                        |
| sbkg_get_related_notes      | Find notes related to a given note via tags, links, project/area.      | title, max_results                                                                                              |
| sbkg_get_stats              | Retrieve statistics about the graph (triple count, entity counts).     | (none)                                                                                                          |
| sbkg_export_triples         | Export the whole graph (or a subset) in an RDF serialization.          | format (turtle, ntriples, nquads, trig, rdfxml), path (optional)                                               |
| sbkg_import_triples         | Import RDF triples from a file into the graph.                         | path, format                                                                                                    |
| sbkg_get_ontology           | Return the SBKG ontology definition.                                   | format (summary or turtle)                                                                                      |
| sbkg_delete_note            | Delete a note (and all its triples).                                   | title                                                                                                           |
| sbkg_delete_bookmark        | Delete a bookmark (and its triples).                                   | title                                                                                                           |
| sbkg_clear_all              | Wipe all triples from the graph and reload the ontology (dangerous).   | confirm (must be true)                                                                                          |



## License

MIT
