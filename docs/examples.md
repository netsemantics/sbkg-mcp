# SBKG Examples & Workflows

Extended examples of using sbkg-mcp, including multi-MCP server workflows.

## Table of Contents

- [Basic Operations](#basic-operations)
- [SPARQL Query Patterns](#sparql-query-patterns)
- [Batch Operations](#batch-operations)
- [SKOS Concept Hierarchies](#skos-concept-hierarchies)
- [Software Project Tracking with DOAP](#software-project-tracking-with-doap)
- [Multi-MCP Workflows](#multi-mcp-workflows)
  - [Email → Knowledge Graph](#email--knowledge-graph)
  - [GitHub → Knowledge Graph](#github--knowledge-graph)
  - [Calendar → Knowledge Graph](#calendar--knowledge-graph)
  - [Web Research Pipeline](#web-research-pipeline)
  - [Browser Bookmarks Import](#browser-bookmarks-import)
- [Advanced SPARQL](#advanced-sparql)

---

## Basic Operations

### Add a note with tags and project

```
User: Create a note about our decision to use Enphase IQ8 microinverters.

LLM calls: sbkg_add_note(
  title="Decision: Enphase IQ8 Microinverters",
  content="Chose IQ8+ for the south-facing array. Key factors: ...",
  tags=["solar", "enphase", "decisions"],
  project="home-solar",
  note_type="ProjectNote"
)
```

### Add a bookmark with reading status

```
User: Save this article for later — https://example.com/grid-tied-vs-hybrid

LLM calls: sbkg_add_bookmark(
  title="Grid-Tied vs Hybrid Solar Systems",
  url="https://example.com/grid-tied-vs-hybrid",
  description="Comparison of grid-tied and hybrid solar architectures",
  tags=["solar", "grid-tied", "battery"],
  status="ToRead"
)
```

### Mark a bookmark as read

```
User: I finished reading the grid-tied article.

LLM calls: sbkg_update_sparql("""
  PREFIX sbkg: <http://secondbrain.ai/kg/>
  DELETE {
    <http://secondbrain.ai/kg/bookmark/grid-tied-vs-hybrid-solar-systems>
      sbkg:hasStatus ?oldStatus .
  }
  INSERT {
    <http://secondbrain.ai/kg/bookmark/grid-tied-vs-hybrid-solar-systems>
      sbkg:hasStatus sbkg:Read .
  }
  WHERE {
    <http://secondbrain.ai/kg/bookmark/grid-tied-vs-hybrid-solar-systems>
      sbkg:hasStatus ?oldStatus .
  }
""")
```

### Import a markdown file

```
User: I have meeting notes at ~/notes/solar-meeting-2026-02-10.md — add them.

LLM calls: sbkg_extract_from_markdown(
  path="/Users/kirby/notes/solar-meeting-2026-02-10.md"
)
```

The markdown file should have YAML frontmatter:

```markdown
---
title: Solar Meeting Notes - Feb 10
tags: [solar, meeting, forsyth-county]
project: home-solar
type: ProjectNote
---

Discussed permit timeline with inspector. Key points:
- Electrical permit approved
- Need to schedule rough-in inspection
- See [[Enphase Ensemble Planning Guide]] for panel layout
```

Wikilinks (`[[...]]`) are automatically extracted as `sbkg:linksTo` relationships.

---

## SPARQL Query Patterns

### List all bookmarks I haven't read

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
SELECT ?title ?url WHERE {
  ?b a sbkg:Bookmark .
  ?b sbkg:hasStatus sbkg:ToRead .
  ?b sbkg:title ?title .
  ?b sbkg:sourceUrl ?url .
}
```

### Find notes in a specific project

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
SELECT ?title ?created WHERE {
  ?n a sbkg:Note .
  ?n sbkg:belongsToProject ?proj .
  ?proj sbkg:title "home-solar" .
  ?n sbkg:title ?title .
  ?n sbkg:createdAt ?created .
}
ORDER BY DESC(?created)
```

### Search across titles and content

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
SELECT ?title ?type WHERE {
  { ?item a sbkg:Note . BIND("Note" AS ?type) }
  UNION
  { ?item a sbkg:Bookmark . BIND("Bookmark" AS ?type) }
  ?item sbkg:title ?title .
  OPTIONAL { ?item sbkg:content ?content }
  FILTER(
    CONTAINS(LCASE(?title), "permit") ||
    CONTAINS(LCASE(COALESCE(?content, "")), "permit")
  )
}
```

### Count items by type

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
SELECT ?type (COUNT(?item) AS ?count) WHERE {
  ?item a ?type .
  FILTER(?type IN (sbkg:Note, sbkg:Bookmark, sbkg:Concept))
}
GROUP BY ?type
```

### Find orphan bookmarks (no tags)

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
SELECT ?title ?url WHERE {
  ?b a sbkg:Bookmark .
  ?b sbkg:title ?title .
  ?b sbkg:sourceUrl ?url .
  FILTER NOT EXISTS { ?b sbkg:hasTag ?tag }
}
```

### Find heavily tagged items

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
SELECT ?title (COUNT(?tag) AS ?tagCount) WHERE {
  ?item sbkg:title ?title .
  ?item sbkg:hasTag ?tag .
}
GROUP BY ?title
HAVING (COUNT(?tag) > 3)
ORDER BY DESC(?tagCount)
```

---

## Batch Operations

### Bulk import bookmarks as Turtle

Generate a Turtle document and load it in one call:

```
LLM calls: sbkg_bulk_import(data="""
  @prefix sbkg: <http://secondbrain.ai/kg/> .

  <http://secondbrain.ai/kg/bookmark/react-docs>
    a sbkg:Bookmark ;
    sbkg:title "React Documentation" ;
    sbkg:sourceUrl "https://react.dev/" ;
    sbkg:hasTag <http://secondbrain.ai/kg/concept/javascript> ;
    sbkg:hasTag <http://secondbrain.ai/kg/concept/frontend> ;
    sbkg:hasStatus sbkg:Reference .

  <http://secondbrain.ai/kg/bookmark/nextjs-docs>
    a sbkg:Bookmark ;
    sbkg:title "Next.js Documentation" ;
    sbkg:sourceUrl "https://nextjs.org/docs" ;
    sbkg:hasTag <http://secondbrain.ai/kg/concept/javascript> ;
    sbkg:hasTag <http://secondbrain.ai/kg/concept/frontend> ;
    sbkg:hasStatus sbkg:Reference .
""", format="turtle")
```

### Bulk re-tag: rename a tag everywhere

```
LLM calls: sbkg_update_sparql("""
  PREFIX sbkg: <http://secondbrain.ai/kg/>
  DELETE { <http://secondbrain.ai/kg/concept/js> sbkg:title "js" }
  INSERT { <http://secondbrain.ai/kg/concept/js> sbkg:title "javascript" }
  WHERE  { <http://secondbrain.ai/kg/concept/js> sbkg:title "js" }
""")
```

### Add a tag to all bookmarks matching a pattern

```
LLM calls: sbkg_update_sparql("""
  PREFIX sbkg: <http://secondbrain.ai/kg/>
  INSERT { ?b sbkg:hasTag <http://secondbrain.ai/kg/concept/enphase> }
  WHERE {
    ?b a sbkg:Bookmark .
    ?b sbkg:title ?title .
    FILTER(CONTAINS(LCASE(?title), "enphase"))
  }
""")
```

---

## SKOS Concept Hierarchies

### Set up a topic tree

```
LLM calls: sbkg_update_sparql("""
  PREFIX sbkg: <http://secondbrain.ai/kg/>
  PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
  INSERT DATA {
    <http://secondbrain.ai/kg/concept/renewable-energy> a sbkg:Concept ;
      sbkg:title "renewable-energy" ;
      skos:prefLabel "Renewable Energy" .

    <http://secondbrain.ai/kg/concept/solar>
      skos:broader <http://secondbrain.ai/kg/concept/renewable-energy> ;
      skos:prefLabel "Solar" .

    <http://secondbrain.ai/kg/concept/enphase>
      skos:broader <http://secondbrain.ai/kg/concept/solar> ;
      skos:prefLabel "Enphase" .

    <http://secondbrain.ai/kg/concept/solar-thermal>
      skos:broader <http://secondbrain.ai/kg/concept/solar> ;
      skos:prefLabel "Solar Thermal" .

    <http://secondbrain.ai/kg/concept/gshp>
      skos:broader <http://secondbrain.ai/kg/concept/renewable-energy> ;
      skos:prefLabel "Ground Source Heat Pump" ;
      skos:altLabel "GSHP" ;
      skos:altLabel "geothermal" .
  }
""")
```

### Query entire subtree

Find everything under "renewable-energy" at any depth:

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT DISTINCT ?title ?url WHERE {
  ?tag skos:broader* <http://secondbrain.ai/kg/concept/renewable-energy> .
  ?b sbkg:hasTag ?tag .
  ?b sbkg:title ?title .
  OPTIONAL { ?b sbkg:sourceUrl ?url }
}
```

### Show the concept tree

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?parent ?parentLabel ?child ?childLabel WHERE {
  ?child skos:broader ?parent .
  ?parent sbkg:title ?parentLabel .
  ?child sbkg:title ?childLabel .
}
ORDER BY ?parentLabel ?childLabel
```

---

## Software Project Tracking with DOAP

### Describe a software project

```
LLM calls: sbkg_update_sparql("""
  PREFIX sbkg: <http://secondbrain.ai/kg/>
  PREFIX doap: <http://usefulinc.com/ns/doap#>
  PREFIX foaf: <http://xmlns.com/foaf/0.1/>
  INSERT DATA {
    <http://secondbrain.ai/kg/project/sbkg-mcp> a doap:Project ;
      doap:name "sbkg-mcp" ;
      doap:shortdesc "Second Brain Knowledge Graph MCP Server" ;
      doap:programming-language "Python" ;
      doap:homepage <https://github.com/netsemantics/sbkg-mcp> ;
      doap:bug-database <https://github.com/netsemantics/sbkg-mcp/issues> ;
      doap:license <https://opensource.org/licenses/MIT> ;
      doap:repository [
        a doap:GitRepository ;
        doap:location <https://github.com/netsemantics/sbkg-mcp.git> ;
        doap:browse <https://github.com/netsemantics/sbkg-mcp>
      ] ;
      doap:maintainer [
        a foaf:Person ;
        foaf:name "Ken Kirby"
      ] .
  }
""")
```

### Query all Python projects

```sparql
PREFIX doap: <http://usefulinc.com/ns/doap#>
SELECT ?name ?desc ?repo WHERE {
  ?p a doap:Project .
  ?p doap:name ?name .
  ?p doap:programming-language "Python" .
  OPTIONAL { ?p doap:shortdesc ?desc }
  OPTIONAL { ?p doap:homepage ?repo }
}
```

---

## Multi-MCP Workflows

These examples show SBKG combined with other MCP servers. The LLM
orchestrates data flow between servers using standard tool calls.

### Email → Knowledge Graph

**Setup**: SBKG + Gmail/Outlook MCP server

```
User: Find my recent emails from the solar installer and summarize
      them in my knowledge graph.

Step 1 — LLM calls email MCP:
  gmail_search(query="from:installer@solar-mason.com", max_results=10)
  → Returns 4 emails about installation schedule

Step 2 — LLM synthesizes and calls SBKG:
  sbkg_add_note(
    title="Solar Installation Timeline - Solar Mason",
    content="""
    Summary of recent emails with Solar Mason:
    - 2/5: Confirmed ground mount location in backyard
    - 2/8: Racking materials ordered, ETA 2 weeks
    - 2/12: Inspection scheduled for 2/20
    - 2/14: Asked about Enphase IQ8 vs IQ8+ — recommended IQ8+
    """,
    tags=["solar", "installer", "solar-mason", "timeline"],
    project="home-solar",
    note_type="ProjectNote"
  )

Step 3 — LLM extracts action items:
  sbkg_add_note(
    title="TODO: Confirm inspection date with Forsyth County",
    content="Solar Mason scheduled rough-in inspection for 2/20. Verify with county.",
    tags=["solar", "permits", "forsyth-county", "todo"],
    project="home-solar"
  )
```

### GitHub → Knowledge Graph

**Setup**: SBKG + GitHub MCP server (or `gh` CLI)

```
User: Track the open issues for our sbkg-mcp repo in the knowledge graph.

Step 1 — LLM calls GitHub:
  gh_list_issues(repo="netsemantics/sbkg-mcp", state="open")
  → Returns 3 open issues

Step 2 — LLM batch-imports into SBKG:
  sbkg_update_sparql("""
    PREFIX sbkg: <http://secondbrain.ai/kg/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    INSERT DATA {
      <http://secondbrain.ai/kg/note/gh-issue-12> a sbkg:Note ;
        sbkg:title "GH #12: Add SPARQL UPDATE support" ;
        sbkg:content "Support INSERT DATA, DELETE DATA, and DELETE/INSERT WHERE" ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/sbkg-mcp> ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/feature-request> ;
        sbkg:belongsToProject <http://secondbrain.ai/kg/project/sbkg-mcp> ;
        dcterms:source <https://github.com/netsemantics/sbkg-mcp/issues/12> ;
        sbkg:hasStatus <http://secondbrain.ai/kg/Open> .

      <http://secondbrain.ai/kg/note/gh-issue-15> a sbkg:Note ;
        sbkg:title "GH #15: Bulk import from Turtle string" ;
        sbkg:content "Allow loading RDF from in-memory strings" ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/sbkg-mcp> ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/feature-request> ;
        sbkg:belongsToProject <http://secondbrain.ai/kg/project/sbkg-mcp> ;
        dcterms:source <https://github.com/netsemantics/sbkg-mcp/issues/15> ;
        sbkg:hasStatus <http://secondbrain.ai/kg/Open> .
    }
  """)
```

Later, query all open items across projects:

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
PREFIX dcterms: <http://purl.org/dc/terms/>
SELECT ?title ?source ?project WHERE {
  ?n a sbkg:Note .
  ?n sbkg:title ?title .
  ?n sbkg:hasStatus <http://secondbrain.ai/kg/Open> .
  OPTIONAL { ?n dcterms:source ?source }
  OPTIONAL {
    ?n sbkg:belongsToProject ?proj .
    ?proj sbkg:title ?project .
  }
}
```

### Calendar → Knowledge Graph

**Setup**: SBKG + Google Calendar MCP server

```
User: Add my upcoming solar-related appointments to the knowledge graph.

Step 1 — LLM calls calendar MCP:
  gcal_list_events(query="solar", days_ahead=30)
  → Returns 2 events

Step 2 — LLM stores them:
  sbkg_update_sparql("""
    PREFIX sbkg: <http://secondbrain.ai/kg/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    INSERT DATA {
      <http://secondbrain.ai/kg/note/solar-inspection-feb20> a sbkg:Note ;
        sbkg:title "Solar Rough-In Inspection" ;
        sbkg:content "Forsyth County inspector visiting for rough-in check. ..." ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/solar> ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/permits> ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/calendar> ;
        sbkg:belongsToProject <http://secondbrain.ai/kg/project/home-solar> ;
        dcterms:issued "2026-02-20T09:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime> .
    }
  """)
```

### Web Research Pipeline

**Setup**: SBKG + web search/fetch MCP

```
User: Research ground source heat pump installers in Georgia and
      save what you find.

Step 1 — LLM searches the web:
  web_search(query="ground source heat pump installer Georgia")
  → Returns 5 results

Step 2 — LLM fetches and summarizes key pages:
  web_fetch(url="https://example.com/gshp-georgia",
            prompt="Extract company name, services, service area")
  → "GeoComfort Southeast — residential GSHP, serves metro Atlanta"

Step 3 — LLM bulk-imports findings:
  sbkg_bulk_import(data="""
    @prefix sbkg: <http://secondbrain.ai/kg/> .
    @prefix dcterms: <http://purl.org/dc/terms/> .

    <http://secondbrain.ai/kg/bookmark/geocomfort-se>
      a sbkg:Bookmark ;
      sbkg:title "GeoComfort Southeast" ;
      sbkg:sourceUrl "https://example.com/gshp-georgia" ;
      sbkg:content "Residential GSHP installer serving metro Atlanta" ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/gshp> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/installer> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/georgia> ;
      sbkg:hasStatus sbkg:Reference .
  """, format="turtle")

Step 4 — LLM creates a summary note:
  sbkg_add_note(
    title="GSHP Installer Research - Georgia",
    content="Researched 5 GSHP installers in GA. Top options: ...",
    tags=["gshp", "installer", "georgia", "research"],
    project="home-gshp"
  )
```

### Browser Bookmarks Import

**Setup**: SBKG + filesystem access (read Chrome bookmarks JSON)

```
User: Import my Chrome bookmarks from the "Solar and GSHP" folder.

Step 1 — LLM reads the Chrome bookmarks file:
  read_file("~/Library/Application Support/Google/Chrome/Default/Bookmarks")
  → Parses JSON, extracts the target folder

Step 2 — LLM generates Turtle and bulk-imports:
  sbkg_bulk_import(data="""
    @prefix sbkg: <http://secondbrain.ai/kg/> .

    <http://secondbrain.ai/kg/bookmark/enphase-enlighten>
      a sbkg:Bookmark ;
      sbkg:title "Enphase Enlighten Dashboard" ;
      sbkg:sourceUrl "https://enlighten.enphaseenergy.com/" ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/solar> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/enphase> ;
      sbkg:hasStatus sbkg:Reference .

    ... (more bookmarks)
  """, format="turtle")
```

This is exactly how the bookmarks in this project were originally imported.

---

## Advanced SPARQL

### CONSTRUCT a subgraph

Export a project's data as a self-contained graph:

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
CONSTRUCT {
  ?item ?p ?o .
}
WHERE {
  ?item sbkg:belongsToProject ?proj .
  ?proj sbkg:title "home-solar" .
  ?item ?p ?o .
}
```

### ASK if a concept exists

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
ASK {
  ?c a sbkg:Concept .
  ?c sbkg:title "kubernetes" .
}
```

### DESCRIBE an entity

Get everything known about a specific bookmark:

```sparql
DESCRIBE <http://secondbrain.ai/kg/bookmark/enphase-enlighten-kirby-system-dashboard>
```

### Find concepts that should be linked

Identify concepts that co-occur on items but don't have a `skos:related` link:

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?tag1Label ?tag2Label (COUNT(?item) AS ?cooccurrences) WHERE {
  ?item sbkg:hasTag ?tag1 .
  ?item sbkg:hasTag ?tag2 .
  ?tag1 sbkg:title ?tag1Label .
  ?tag2 sbkg:title ?tag2Label .
  FILTER(STR(?tag1) < STR(?tag2))
  FILTER NOT EXISTS { ?tag1 skos:related ?tag2 }
  FILTER NOT EXISTS { ?tag1 skos:broader ?tag2 }
  FILTER NOT EXISTS { ?tag2 skos:broader ?tag1 }
}
GROUP BY ?tag1Label ?tag2Label
HAVING (COUNT(?item) >= 2)
ORDER BY DESC(?cooccurrences)
```

### Timeline query with Dublin Core dates

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
PREFIX dcterms: <http://purl.org/dc/terms/>
SELECT ?title ?date WHERE {
  ?n a sbkg:Note .
  ?n sbkg:title ?title .
  ?n dcterms:issued ?date .
  ?n sbkg:belongsToProject <http://secondbrain.ai/kg/project/home-solar> .
}
ORDER BY ?date
```
