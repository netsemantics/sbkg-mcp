"""Tests for MCP tool functions."""

import json
import textwrap
from pathlib import Path

import pytest

from sbkg_mcp.store import KnowledgeStore
import sbkg_mcp.server as srv


@pytest.fixture(autouse=True)
def temp_store(tmp_path):
    """Replace global store with a temp one for each test."""
    store = KnowledgeStore(path=tmp_path / "test_db")
    srv._store = store
    yield store
    srv._store = None


class TestAddNote:
    def test_basic(self):
        result = json.loads(srv.sbkg_add_note("Hello World"))
        assert result["title"] == "Hello World"
        assert result["uri"].endswith("/note/hello-world")
        assert result["triples_added"] > 0

    def test_with_tags_and_project(self):
        result = json.loads(srv.sbkg_add_note(
            "Tagged Note",
            tags=["python", "rdf"],
            project="sbkg",
        ))
        assert result["tags"] == ["python", "rdf"]
        # Verify in store
        sparql = json.loads(srv.sbkg_query_sparql(
            "PREFIX sbkg: <http://sb.ai/kg/> "
            "SELECT ?tag WHERE { <http://sb.ai/kg/note/tagged-note> sbkg:hasTag ?tag }"
        ))
        assert len(sparql) == 2


class TestAddBookmark:
    def test_basic(self):
        result = json.loads(srv.sbkg_add_bookmark(
            "Example Site", "https://example.com",
        ))
        assert result["url"] == "https://example.com"
        assert result["status"] == "ToRead"
        assert result["triples_added"] > 0

    def test_bookmark_uses_model(self):
        """Verify bookmark uses the Bookmark model + extract_bookmark_triples."""
        result = json.loads(srv.sbkg_add_bookmark(
            "Model BM", "https://example.com",
            tags=["test"],
            status="Read",
        ))
        assert result["triples_added"] > 0
        # Verify SKOS prefLabel was emitted (from extract_bookmark_triples)
        sparql = json.loads(srv.sbkg_query_sparql(
            "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
            "SELECT ?label WHERE { ?c skos:prefLabel ?label }"
        ))
        labels = [r["label"] for r in sparql]
        assert "test" in labels
        # Verify status is a NamedNode
        sparql2 = json.loads(srv.sbkg_query_sparql(
            "PREFIX sbkg: <http://sb.ai/kg/> "
            "SELECT ?status WHERE { <http://sb.ai/kg/bookmark/model-bm> sbkg:hasStatus ?status }"
        ))
        assert len(sparql2) == 1
        assert sparql2[0]["status"] == "http://sb.ai/kg/Read"


class TestExtractFromMarkdown:
    def test_basic(self, tmp_path):
        md = tmp_path / "note.md"
        md.write_text(
            "---\ntitle: Parsed Note\ntags:\n  - test\n---\nContent with [[link]].\n",
            encoding="utf-8",
        )
        result = json.loads(srv.sbkg_extract_from_markdown(str(md)))
        assert result["title"] == "Parsed Note"
        assert "test" in result["tags"]
        assert "link" in result["links"]


class TestQuerySparql:
    def test_select(self):
        srv.sbkg_add_note("Query Test")
        result = json.loads(srv.sbkg_query_sparql(
            "PREFIX sbkg: <http://sb.ai/kg/> "
            "SELECT ?title WHERE { ?n a sbkg:Note . ?n sbkg:title ?title }"
        ))
        titles = [r["title"] for r in result]
        assert "Query Test" in titles


class TestQueryNatural:
    def test_returns_context(self):
        result = json.loads(srv.sbkg_query_natural("What notes do I have?"))
        assert "ontology" in result
        assert "instructions" in result
        assert "example_queries" in result


class TestGetRelatedNotes:
    def test_shared_tag(self):
        srv.sbkg_add_note("Note A", tags=["shared"])
        srv.sbkg_add_note("Note B", tags=["shared"])
        result = json.loads(srv.sbkg_get_related_notes("Note A"))
        titles = [r["relTitle"] for r in result]
        assert "Note B" in titles


class TestGetStats:
    def test_returns_stats(self):
        result = json.loads(srv.sbkg_get_stats())
        assert "total_triples" in result
        assert "entity_counts" in result


class TestExportTriples:
    def test_export_string(self):
        srv.sbkg_add_note("Export Test")
        result = json.loads(srv.sbkg_export_triples(format="turtle"))
        assert "content" in result
        assert "Export Test" in result["content"]

    def test_export_file(self, tmp_path):
        srv.sbkg_add_note("File Export")
        out = str(tmp_path / "export.ttl")
        result = json.loads(srv.sbkg_export_triples(format="turtle", path=out))
        assert result["exported_to"] == out
        assert Path(out).exists()


class TestImportTriples:
    def test_import(self, tmp_path):
        ttl = tmp_path / "data.ttl"
        ttl.write_text(
            '<http://sb.ai/kg/note/ext> <http://sb.ai/kg/title> "External" .\n',
            encoding="utf-8",
        )
        result = json.loads(srv.sbkg_import_triples(str(ttl), format="turtle"))
        assert result["triples_added"] >= 1


class TestDeleteNote:
    def test_delete_existing(self):
        srv.sbkg_add_note("To Delete", tags=["temp"])
        result = json.loads(srv.sbkg_delete_note("To Delete"))
        assert result["deleted"] is True
        assert result["triples_removed"] > 0
        # Verify it's gone
        sparql = json.loads(srv.sbkg_query_sparql(
            "PREFIX sbkg: <http://sb.ai/kg/> "
            "SELECT ?t WHERE { <http://sb.ai/kg/note/to-delete> sbkg:title ?t }"
        ))
        assert len(sparql) == 0

    def test_delete_nonexistent(self):
        result = json.loads(srv.sbkg_delete_note("Does Not Exist"))
        assert result["deleted"] is False

    def test_delete_removes_incoming_links(self):
        srv.sbkg_add_note("Source", links=["Target"])
        srv.sbkg_add_note("Target")
        result = json.loads(srv.sbkg_delete_note("Target"))
        assert result["deleted"] is True
        # The linksTo triple pointing to Target should also be gone
        sparql = json.loads(srv.sbkg_query_sparql(
            "PREFIX sbkg: <http://sb.ai/kg/> "
            "SELECT ?o WHERE { <http://sb.ai/kg/note/source> sbkg:linksTo ?o }"
        ))
        assert len(sparql) == 0


class TestDeleteBookmark:
    def test_delete_existing(self):
        srv.sbkg_add_bookmark("Test BM", "https://example.com")
        result = json.loads(srv.sbkg_delete_bookmark("Test BM"))
        assert result["deleted"] is True
        assert result["triples_removed"] > 0

    def test_delete_nonexistent(self):
        result = json.loads(srv.sbkg_delete_bookmark("Nope"))
        assert result["deleted"] is False


class TestClearAll:
    def test_safety_check(self):
        result = json.loads(srv.sbkg_clear_all(confirm=False))
        assert result["cleared"] is False

    def test_clear_and_reload_ontology(self):
        srv.sbkg_add_note("Temp Note")
        result = json.loads(srv.sbkg_clear_all(confirm=True))
        assert result["cleared"] is True
        assert result["triples_removed"] > 0
        # Ontology should be reloaded
        assert result["ontology_triples_reloaded"] > 0
        # User data should be gone
        sparql = json.loads(srv.sbkg_query_sparql(
            "PREFIX sbkg: <http://sb.ai/kg/> "
            "SELECT ?n WHERE { ?n a sbkg:Note }"
        ))
        assert len(sparql) == 0


class TestUpdateSparql:
    _BM = "http://sb.ai/kg/bookmark/"
    _NS = "http://sb.ai/kg/"

    def test_insert_data(self):
        result = json.loads(srv.sbkg_update_sparql(
            f'INSERT DATA {{ '
            f'  <{self._BM}test-a> a <{self._NS}Bookmark> ; <{self._NS}title> "A" ; <{self._NS}sourceUrl> "https://a.com" . '
            f'  <{self._BM}test-b> a <{self._NS}Bookmark> ; <{self._NS}title> "B" ; <{self._NS}sourceUrl> "https://b.com" . '
            f'}}'
        ))
        assert result["success"] is True
        assert result["triples_delta"] == 6
        # Verify both bookmarks exist
        rows = json.loads(srv.sbkg_query_sparql(
            'PREFIX sbkg: <http://sb.ai/kg/> '
            'SELECT ?title WHERE { ?b a sbkg:Bookmark . ?b sbkg:title ?title } ORDER BY ?title'
        ))
        titles = [r["title"] for r in rows]
        assert "A" in titles
        assert "B" in titles

    def test_delete_data(self):
        # Insert then delete
        srv.sbkg_update_sparql(
            f'INSERT DATA {{ <{self._BM}gone> a <{self._NS}Bookmark> ; <{self._NS}title> "Gone" . }}'
        )
        result = json.loads(srv.sbkg_update_sparql(
            f'DELETE DATA {{ <{self._BM}gone> a <{self._NS}Bookmark> ; <{self._NS}title> "Gone" . }}'
        ))
        assert result["success"] is True
        assert result["triples_delta"] == -2

    def test_delete_insert_where(self):
        # Insert, then rename via DELETE/INSERT WHERE
        srv.sbkg_update_sparql(
            f'INSERT DATA {{ <{self._BM}rename> a <{self._NS}Bookmark> ; <{self._NS}title> "Old Name" . }}'
        )
        srv.sbkg_update_sparql(
            f'DELETE {{ <{self._BM}rename> <{self._NS}title> "Old Name" }} '
            f'INSERT {{ <{self._BM}rename> <{self._NS}title> "New Name" }} '
            f'WHERE {{ <{self._BM}rename> <{self._NS}title> "Old Name" }}'
        )
        rows = json.loads(srv.sbkg_query_sparql(
            f'SELECT ?title WHERE {{ <{self._BM}rename> <{self._NS}title> ?title }}'
        ))
        assert rows[0]["title"] == "New Name"


class TestBulkImport:
    def test_turtle_string(self):
        ttl = (
            '<http://sb.ai/kg/bookmark/bulk-a> a <http://sb.ai/kg/Bookmark> ;\n'
            '  <http://sb.ai/kg/title> "Bulk A" ;\n'
            '  <http://sb.ai/kg/sourceUrl> "https://a.com" .\n'
            '<http://sb.ai/kg/bookmark/bulk-b> a <http://sb.ai/kg/Bookmark> ;\n'
            '  <http://sb.ai/kg/title> "Bulk B" ;\n'
            '  <http://sb.ai/kg/sourceUrl> "https://b.com" .\n'
            '<http://sb.ai/kg/bookmark/bulk-c> a <http://sb.ai/kg/Bookmark> ;\n'
            '  <http://sb.ai/kg/title> "Bulk C" ;\n'
            '  <http://sb.ai/kg/sourceUrl> "https://c.com" .\n'
        )
        result = json.loads(srv.sbkg_bulk_import(data=ttl, format="turtle"))
        assert result["success"] is True
        assert result["triples_added"] == 9  # 3 bookmarks x 3 triples each
        # Verify all three exist
        rows = json.loads(srv.sbkg_query_sparql(
            'PREFIX sbkg: <http://sb.ai/kg/> '
            'SELECT ?title WHERE { ?b a sbkg:Bookmark . ?b sbkg:title ?title } ORDER BY ?title'
        ))
        titles = [r["title"] for r in rows]
        assert titles == ["Bulk A", "Bulk B", "Bulk C"]

    def test_ntriples_string(self):
        nt = (
            '<http://sb.ai/kg/bookmark/nt-test> '
            '<http://www.w3.org/1999/02/22-rdf-syntax-ns#type> '
            '<http://sb.ai/kg/Bookmark> .\n'
            '<http://sb.ai/kg/bookmark/nt-test> '
            '<http://sb.ai/kg/title> '
            '"NT Test" .\n'
        )
        result = json.loads(srv.sbkg_bulk_import(data=nt, format="ntriples"))
        assert result["success"] is True
        assert result["triples_added"] == 2


class TestUsageGuide:
    def test_returns_markdown(self):
        result = srv.sbkg_usage_guide()
        assert "# SBKG MCP" in result
        assert "sbkg_query_sparql" in result
        assert "sbkg_bulk_import" in result
        assert "sbkg_update_sparql" in result


class TestGetOntology:
    def test_summary(self):
        result = json.loads(srv.sbkg_get_ontology(format="summary"))
        assert "sbkg:Note" in result["content"]

    def test_turtle(self):
        result = json.loads(srv.sbkg_get_ontology(format="turtle"))
        assert "@prefix" in result["content"]


class TestAddProject:
    def test_basic(self):
        result = json.loads(srv.sbkg_add_project("my-project"))
        assert result["name"] == "my-project"
        assert result["uri"].endswith("/project/my-project")
        assert result["triples_added"] > 0

    def test_with_doap_properties(self):
        result = json.loads(srv.sbkg_add_project(
            name="sbkg-mcp",
            description="Knowledge graph MCP server",
            homepage="https://example.com/sbkg",
            repository="https://github.com/example/sbkg-mcp",
            programming_language="Python",
            platform="Linux",
            maintainers=["Alice"],
            developers=["Bob", "Charlie"],
            tags=["python", "rdf"],
        ))
        assert result["triples_added"] > 0
        # Verify DOAP name in store
        sparql = json.loads(srv.sbkg_query_sparql(
            "PREFIX doap: <http://usefulinc.com/ns/doap#> "
            "SELECT ?name WHERE { ?p doap:name ?name }"
        ))
        names = [r["name"] for r in sparql]
        assert "sbkg-mcp" in names
        # Verify maintainer person
        sparql2 = json.loads(srv.sbkg_query_sparql(
            "PREFIX doap: <http://usefulinc.com/ns/doap#> "
            "PREFIX foaf: <http://xmlns.com/foaf/0.1/> "
            "SELECT ?name WHERE { ?p doap:maintainer ?m . ?m foaf:name ?name }"
        ))
        assert any(r["name"] == "Alice" for r in sparql2)

    def test_repository_creates_git_repo(self):
        srv.sbkg_add_project(
            name="repo-test",
            repository="https://github.com/test/repo",
        )
        sparql = json.loads(srv.sbkg_query_sparql(
            "PREFIX doap: <http://usefulinc.com/ns/doap#> "
            "SELECT ?loc WHERE { ?r a doap:GitRepository . ?r doap:location ?loc }"
        ))
        locs = [r["loc"] for r in sparql]
        assert "https://github.com/test/repo" in locs


class TestGetNote:
    def test_existing_note(self):
        srv.sbkg_add_note("Fetch Me", content="Hello world", tags=["test"])
        result = json.loads(srv.sbkg_get_note("Fetch Me"))
        assert result["found"] is True
        assert result["title"] == "Fetch Me"
        assert result["content"] == "Hello world"
        assert "test" in result["tags"]

    def test_nonexistent_note(self):
        result = json.loads(srv.sbkg_get_note("Does Not Exist"))
        assert result["found"] is False

    def test_note_with_project_and_links(self):
        srv.sbkg_add_note("Linked Note", project="my-project", links=["Target"])
        result = json.loads(srv.sbkg_get_note("Linked Note"))
        assert result["found"] is True
        assert result["project_uri"] is not None
        assert "my-project" in result["project_uri"]
        assert len(result["links"]) == 1


class TestUpdateNote:
    def test_update_content(self):
        srv.sbkg_add_note("Update Me", content="old")
        result = json.loads(srv.sbkg_update_note("Update Me", content="new"))
        assert result["updated"] is True
        # Verify content changed
        note = json.loads(srv.sbkg_get_note("Update Me"))
        assert note["content"] == "new"

    def test_update_tags(self):
        srv.sbkg_add_note("Tag Note", tags=["old-tag"])
        srv.sbkg_update_note("Tag Note", tags=["new-tag", "another"])
        note = json.loads(srv.sbkg_get_note("Tag Note"))
        assert "new-tag" in note["tags"]
        assert "another" in note["tags"]
        assert "old-tag" not in note["tags"]

    def test_update_status(self):
        srv.sbkg_add_note("Status Note", status="draft")
        srv.sbkg_update_note("Status Note", status="published")
        note = json.loads(srv.sbkg_get_note("Status Note"))
        assert note["status"] == "published"

    def test_update_nonexistent(self):
        result = json.loads(srv.sbkg_update_note("Ghost Note", content="nope"))
        assert result["updated"] is False

    def test_modified_at_refresh(self):
        srv.sbkg_add_note("Mod Note")
        note_before = json.loads(srv.sbkg_get_note("Mod Note"))
        srv.sbkg_update_note("Mod Note", content="changed")
        note_after = json.loads(srv.sbkg_get_note("Mod Note"))
        assert note_after["modified_at"] is not None
        # modified_at should be set after update
        assert note_after["modified_at"] != note_before.get("created_at")


class TestSearch:
    def test_basic_search(self):
        srv.sbkg_add_note("Python Tutorial")
        srv.sbkg_add_note("Rust Guide")
        result = json.loads(srv.sbkg_search("Python"))
        titles = [r["title"] for r in result]
        assert "Python Tutorial" in titles
        assert "Rust Guide" not in titles

    def test_case_insensitive(self):
        srv.sbkg_add_note("Case Test Note")
        result = json.loads(srv.sbkg_search("case test"))
        assert len(result) > 0
        assert result[0]["title"] == "Case Test Note"

    def test_filter_by_type_note(self):
        srv.sbkg_add_note("Search Note")
        srv.sbkg_add_bookmark("Search Bookmark", "https://example.com")
        result = json.loads(srv.sbkg_search("Search", entity_type="note"))
        titles = [r["title"] for r in result]
        assert "Search Note" in titles
        assert "Search Bookmark" not in titles

    def test_filter_by_type_bookmark(self):
        srv.sbkg_add_note("Filter Note")
        srv.sbkg_add_bookmark("Filter Bookmark", "https://example.com")
        result = json.loads(srv.sbkg_search("Filter", entity_type="bookmark"))
        titles = [r["title"] for r in result]
        assert "Filter Bookmark" in titles
        assert "Filter Note" not in titles

    def test_filter_by_tag(self):
        srv.sbkg_add_note("Tagged A", tags=["target"])
        srv.sbkg_add_note("Tagged B", tags=["other"])
        result = json.loads(srv.sbkg_search("Tagged", tag="target"))
        titles = [r["title"] for r in result]
        assert "Tagged A" in titles
        assert "Tagged B" not in titles

    def test_no_results(self):
        result = json.loads(srv.sbkg_search("zzzznonexistentzzzz"))
        assert result == []

    def test_limit(self):
        for i in range(5):
            srv.sbkg_add_note(f"Limit Note {i}")
        result = json.loads(srv.sbkg_search("Limit Note", limit=3))
        assert len(result) <= 3


class TestEmailMboxTriples:
    def test_email_mbox_end_to_end(self):
        """End-to-end: email → foaf:mbox triples in store."""
        raw = textwrap.dedent("""\
            From: Alice Smith <alice@example.com>
            To: Bob Jones <bob@example.com>
            Subject: Mbox E2E Test

            Body content.
        """)
        srv.sbkg_add_note_from_email(raw)
        # Verify foaf:mbox for mention
        sparql = json.loads(srv.sbkg_query_sparql(
            "PREFIX foaf: <http://xmlns.com/foaf/0.1/> "
            "SELECT ?mbox WHERE { ?p foaf:name \"Bob Jones\" . ?p foaf:mbox ?mbox }"
        ))
        assert len(sparql) > 0
        assert sparql[0]["mbox"] == "mailto:bob@example.com"
        # Verify foaf:mbox for creator
        sparql2 = json.loads(srv.sbkg_query_sparql(
            "PREFIX foaf: <http://xmlns.com/foaf/0.1/> "
            "SELECT ?mbox WHERE { ?p foaf:name \"Alice Smith\" . ?p foaf:mbox ?mbox }"
        ))
        assert len(sparql2) > 0
        assert sparql2[0]["mbox"] == "mailto:alice@example.com"


class TestAddNoteFromEmail:
    def test_basic_email(self):
        raw = textwrap.dedent("""\
            From: Alice Smith <alice@example.com>
            To: Bob Jones <bob@example.com>
            Subject: Meeting Notes
            Date: Mon, 15 Jan 2024 10:30:00 +0000

            Here are the notes from today's meeting.
        """)
        result = json.loads(srv.sbkg_add_note_from_email(raw))
        assert result["title"] == "Meeting Notes"
        assert result["creator"] == "Alice Smith"
        assert "email" in result["tags"]
        assert result["triples_added"] > 0

    def test_email_creates_mentions(self):
        raw = textwrap.dedent("""\
            From: Alice <alice@example.com>
            To: Bob <bob@example.com>, Charlie <charlie@example.com>
            Subject: Team Update

            Update body.
        """)
        srv.sbkg_add_note_from_email(raw)
        # Verify mentions in store
        sparql = json.loads(srv.sbkg_query_sparql(
            "PREFIX sbkg: <http://sb.ai/kg/> "
            "PREFIX foaf: <http://xmlns.com/foaf/0.1/> "
            "SELECT ?name WHERE { ?n sbkg:mentions ?p . ?p foaf:name ?name }"
        ))
        names = [r["name"] for r in sparql]
        assert "Bob" in names
        assert "Charlie" in names
