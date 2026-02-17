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
User: Create a note about our decision to use PostgreSQL for the backend.

LLM calls: sbkg_add_note(
  title="Decision: PostgreSQL for Backend DB",
  content="Chose PostgreSQL over MySQL. Key factors: JSONB support, ...",
  tags=["database", "postgresql", "decisions"],
  project="webapp-v2",
  note_type="ProjectNote"
)
```

### Add a bookmark with reading status

```
User: Save this article for later — https://example.com/microservices-patterns

LLM calls: sbkg_add_bookmark(
  title="Microservices Patterns",
  url="https://example.com/microservices-patterns",
  description="Overview of common microservice architecture patterns",
  tags=["architecture", "microservices", "backend"],
  status="ToRead"
)
```

### Mark a bookmark as read

```
User: I finished reading the microservices article.

LLM calls: sbkg_update_sparql("""
  PREFIX sbkg: <http://secondbrain.ai/kg/>
  DELETE {
    <http://secondbrain.ai/kg/bookmark/microservices-patterns>
      sbkg:hasStatus ?oldStatus .
  }
  INSERT {
    <http://secondbrain.ai/kg/bookmark/microservices-patterns>
      sbkg:hasStatus sbkg:Read .
  }
  WHERE {
    <http://secondbrain.ai/kg/bookmark/microservices-patterns>
      sbkg:hasStatus ?oldStatus .
  }
""")
```

### Import a markdown file

```
User: I have meeting notes at ~/notes/sprint-review-2026-02-10.md — add them.

LLM calls: sbkg_extract_from_markdown(
  path="/home/user/notes/sprint-review-2026-02-10.md"
)
```

The markdown file should have YAML frontmatter:

```markdown
---
title: Sprint Review - Feb 10
tags: [sprint, review, webapp-v2]
project: webapp-v2
type: ProjectNote
---

Discussed deployment timeline with the team. Key points:
- Auth service ready for staging
- Need to finalize API rate limiting
- See [[PostgreSQL Tuning Guide]] for query optimization
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
  ?proj sbkg:title "webapp-v2" .
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
    CONTAINS(LCASE(?title), "deployment") ||
    CONTAINS(LCASE(COALESCE(?content, "")), "deployment")
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
  INSERT { ?b sbkg:hasTag <http://secondbrain.ai/kg/concept/devops> }
  WHERE {
    ?b a sbkg:Bookmark .
    ?b sbkg:title ?title .
    FILTER(CONTAINS(LCASE(?title), "kubernetes") || CONTAINS(LCASE(?title), "docker"))
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
    <http://secondbrain.ai/kg/concept/programming> a sbkg:Concept ;
      sbkg:title "programming" ;
      skos:prefLabel "Programming" .

    <http://secondbrain.ai/kg/concept/frontend>
      skos:broader <http://secondbrain.ai/kg/concept/programming> ;
      skos:prefLabel "Frontend" .

    <http://secondbrain.ai/kg/concept/react>
      skos:broader <http://secondbrain.ai/kg/concept/frontend> ;
      skos:prefLabel "React" .

    <http://secondbrain.ai/kg/concept/vue>
      skos:broader <http://secondbrain.ai/kg/concept/frontend> ;
      skos:prefLabel "Vue" .

    <http://secondbrain.ai/kg/concept/backend>
      skos:broader <http://secondbrain.ai/kg/concept/programming> ;
      skos:prefLabel "Backend" ;
      skos:altLabel "server-side" .
  }
""")
```

### Query entire subtree

Find everything under "programming" at any depth:

```sparql
PREFIX sbkg: <http://secondbrain.ai/kg/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT DISTINCT ?title ?url WHERE {
  ?tag skos:broader* <http://secondbrain.ai/kg/concept/programming> .
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
    <http://secondbrain.ai/kg/project/my-app> a doap:Project ;
      doap:name "my-app" ;
      doap:shortdesc "A web application for task management" ;
      doap:programming-language "Python" ;
      doap:homepage <https://github.com/user/my-app> ;
      doap:bug-database <https://github.com/user/my-app/issues> ;
      doap:license <https://opensource.org/licenses/MIT> ;
      doap:repository [
        a doap:GitRepository ;
        doap:location <https://github.com/user/my-app.git> ;
        doap:browse <https://github.com/user/my-app>
      ] ;
      doap:maintainer [
        a foaf:Person ;
        foaf:name "Jane Developer"
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
User: Find my recent emails from the client and summarize
      them in my knowledge graph.

Step 1 — LLM calls email MCP:
  gmail_search(query="from:client@acme.com", max_results=10)
  → Returns 4 emails about project requirements

Step 2 — LLM synthesizes and calls SBKG:
  sbkg_add_note(
    title="Client Requirements Summary - Acme Corp",
    content="""
    Summary of recent emails with Acme:
    - 2/5: Confirmed OAuth2 requirement for SSO
    - 2/8: Need CSV export by end of March
    - 2/12: Performance requirement: < 200ms API response
    - 2/14: Asked about multi-tenant support — confirmed needed
    """,
    tags=["client", "requirements", "acme"],
    project="webapp-v2",
    note_type="ProjectNote"
  )

Step 3 — LLM extracts action items:
  sbkg_add_note(
    title="TODO: Scope multi-tenant architecture",
    content="Acme confirmed multi-tenant is required. Need to evaluate ...",
    tags=["architecture", "multi-tenant", "todo"],
    project="webapp-v2"
  )
```

### GitHub → Knowledge Graph

**Setup**: SBKG + GitHub MCP server (or `gh` CLI)

```
User: Track the open issues for our app repo in the knowledge graph.

Step 1 — LLM calls GitHub:
  gh_list_issues(repo="user/my-app", state="open")
  → Returns 3 open issues

Step 2 — LLM batch-imports into SBKG:
  sbkg_update_sparql("""
    PREFIX sbkg: <http://secondbrain.ai/kg/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    INSERT DATA {
      <http://secondbrain.ai/kg/note/gh-issue-12> a sbkg:Note ;
        sbkg:title "GH #12: Add CSV export endpoint" ;
        sbkg:content "Users need to export their data as CSV files" ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/my-app> ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/feature-request> ;
        sbkg:belongsToProject <http://secondbrain.ai/kg/project/my-app> ;
        dcterms:source <https://github.com/user/my-app/issues/12> ;
        sbkg:hasStatus <http://secondbrain.ai/kg/Open> .

      <http://secondbrain.ai/kg/note/gh-issue-15> a sbkg:Note ;
        sbkg:title "GH #15: Rate limiting for public API" ;
        sbkg:content "Need to implement rate limiting before GA launch" ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/my-app> ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/feature-request> ;
        sbkg:belongsToProject <http://secondbrain.ai/kg/project/my-app> ;
        dcterms:source <https://github.com/user/my-app/issues/15> ;
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
User: Add my upcoming project-related meetings to the knowledge graph.

Step 1 — LLM calls calendar MCP:
  gcal_list_events(query="webapp", days_ahead=30)
  → Returns 2 events

Step 2 — LLM stores them:
  sbkg_update_sparql("""
    PREFIX sbkg: <http://secondbrain.ai/kg/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    INSERT DATA {
      <http://secondbrain.ai/kg/note/sprint-demo-feb20> a sbkg:Note ;
        sbkg:title "Sprint Demo - Feb 20" ;
        sbkg:content "Demo the auth service and CSV export to stakeholders. ..." ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/meeting> ;
        sbkg:hasTag <http://secondbrain.ai/kg/concept/sprint> ;
        sbkg:belongsToProject <http://secondbrain.ai/kg/project/webapp-v2> ;
        dcterms:issued "2026-02-20T14:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime> .
    }
  """)
```

### Web Research Pipeline

**Setup**: SBKG + web search/fetch MCP

```
User: Research Python async frameworks and save what you find.

Step 1 — LLM searches the web:
  web_search(query="Python async web framework comparison 2026")
  → Returns 5 results

Step 2 — LLM fetches and summarizes key pages:
  web_fetch(url="https://example.com/async-frameworks",
            prompt="Extract framework names, key features, and benchmarks")
  → "FastAPI, Starlette, Litestar — comparison of features and performance"

Step 3 — LLM bulk-imports findings:
  sbkg_bulk_import(data="""
    @prefix sbkg: <http://secondbrain.ai/kg/> .

    <http://secondbrain.ai/kg/bookmark/fastapi-docs>
      a sbkg:Bookmark ;
      sbkg:title "FastAPI Documentation" ;
      sbkg:sourceUrl "https://fastapi.tiangolo.com/" ;
      sbkg:content "Modern async Python web framework with automatic OpenAPI docs" ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/python> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/async> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/framework> ;
      sbkg:hasStatus sbkg:Reference .

    <http://secondbrain.ai/kg/bookmark/litestar-docs>
      a sbkg:Bookmark ;
      sbkg:title "Litestar Documentation" ;
      sbkg:sourceUrl "https://litestar.dev/" ;
      sbkg:content "High-performance async framework, successor to Starlite" ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/python> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/async> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/framework> ;
      sbkg:hasStatus sbkg:ToRead .
  """, format="turtle")

Step 4 — LLM creates a summary note:
  sbkg_add_note(
    title="Async Framework Research - Python",
    content="Researched 5 async frameworks. Top options: FastAPI, Litestar ...",
    tags=["python", "async", "framework", "research"],
    project="webapp-v2"
  )
```

### Browser Bookmarks Import

**Setup**: SBKG + filesystem access (read Chrome bookmarks JSON)

```
User: Import my Chrome bookmarks from the "Dev Resources" folder.

Step 1 — LLM reads the Chrome bookmarks file:
  read_file("~/Library/Application Support/Google/Chrome/Default/Bookmarks")
  → Parses JSON, extracts the target folder

Step 2 — LLM generates Turtle and bulk-imports:
  sbkg_bulk_import(data="""
    @prefix sbkg: <http://secondbrain.ai/kg/> .

    <http://secondbrain.ai/kg/bookmark/mdn-web-docs>
      a sbkg:Bookmark ;
      sbkg:title "MDN Web Docs" ;
      sbkg:sourceUrl "https://developer.mozilla.org/" ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/javascript> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/reference> ;
      sbkg:hasStatus sbkg:Reference .

    <http://secondbrain.ai/kg/bookmark/can-i-use>
      a sbkg:Bookmark ;
      sbkg:title "Can I Use" ;
      sbkg:sourceUrl "https://caniuse.com/" ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/frontend> ;
      sbkg:hasTag <http://secondbrain.ai/kg/concept/reference> ;
      sbkg:hasStatus sbkg:Reference .

    ... (more bookmarks)
  """, format="turtle")
```

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
  ?proj sbkg:title "webapp-v2" .
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
DESCRIBE <http://secondbrain.ai/kg/bookmark/fastapi-docs>
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
  ?n sbkg:belongsToProject <http://secondbrain.ai/kg/project/webapp-v2> .
}
ORDER BY ?date
```
