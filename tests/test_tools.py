"""Tests for MCP tool functions."""

import json
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
            "PREFIX sbkg: <http://secondbrain.ai/kg/> "
            "SELECT ?tag WHERE { <http://secondbrain.ai/kg/note/tagged-note> sbkg:hasTag ?tag }"
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
            "PREFIX sbkg: <http://secondbrain.ai/kg/> "
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
            '<http://secondbrain.ai/kg/note/ext> <http://secondbrain.ai/kg/title> "External" .\n',
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
            "PREFIX sbkg: <http://secondbrain.ai/kg/> "
            "SELECT ?t WHERE { <http://secondbrain.ai/kg/note/to-delete> sbkg:title ?t }"
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
            "PREFIX sbkg: <http://secondbrain.ai/kg/> "
            "SELECT ?o WHERE { <http://secondbrain.ai/kg/note/source> sbkg:linksTo ?o }"
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
            "PREFIX sbkg: <http://secondbrain.ai/kg/> "
            "SELECT ?n WHERE { ?n a sbkg:Note }"
        ))
        assert len(sparql) == 0


class TestGetOntology:
    def test_summary(self):
        result = json.loads(srv.sbkg_get_ontology(format="summary"))
        assert "sbkg:Note" in result["content"]

    def test_turtle(self):
        result = json.loads(srv.sbkg_get_ontology(format="turtle"))
        assert "@prefix" in result["content"]
