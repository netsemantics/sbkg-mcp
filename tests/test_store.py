"""Tests for the KnowledgeStore."""

import tempfile
from pathlib import Path

import pytest
from pyoxigraph import DefaultGraph, Literal, NamedNode, Quad

from sbkg_mcp.store import KnowledgeStore
from sbkg_mcp.utils import SBKG_NS


@pytest.fixture
def store(tmp_path):
    return KnowledgeStore(path=tmp_path / "test_db")


def _quad(s, p, o):
    return Quad(NamedNode(s), NamedNode(p), Literal(o) if isinstance(o, str) else NamedNode(o), DefaultGraph())


class TestKnowledgeStore:
    def test_ontology_loaded(self, store):
        """Ontology should be loaded automatically on init."""
        stats = store.get_stats()
        assert stats["total_triples"] > 0

    def test_insert_and_query(self, store):
        uri = f"{SBKG_NS}note/test"
        store.insert_triples([
            _quad(uri, f"{SBKG_NS}title", "Test Note"),
            _quad(uri, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", f"{SBKG_NS}Note"),
        ])
        results = store.query_sparql(
            f"PREFIX sbkg: <{SBKG_NS}> SELECT ?title WHERE {{ <{uri}> sbkg:title ?title }}"
        )
        assert len(results) == 1
        assert results[0]["title"] == "Test Note"

    def test_remove_triples(self, store):
        uri = NamedNode(f"{SBKG_NS}note/removeme")
        store.add_quad(uri, NamedNode(f"{SBKG_NS}title"), "Remove Me")
        removed = store.remove_triples(subject=uri)
        assert removed >= 1
        results = store.query_sparql(
            f"SELECT ?p ?o WHERE {{ <{uri.value}> ?p ?o }}"
        )
        assert len(results) == 0

    def test_get_stats(self, store):
        stats = store.get_stats()
        assert "total_triples" in stats
        assert "entity_counts" in stats

    def test_export_turtle(self, store):
        content = store.export(fmt="turtle")
        assert "secondbrain" in content

    def test_export_ntriples(self, store):
        content = store.export(fmt="ntriples")
        assert "<http://secondbrain.ai/kg/" in content

    def test_import_rdf(self, store, tmp_path):
        ttl_file = tmp_path / "import.ttl"
        ttl_file.write_text(
            f'<{SBKG_NS}note/imported> <{SBKG_NS}title> "Imported Note" .\n',
            encoding="utf-8",
        )
        count = store.import_rdf(str(ttl_file), fmt="turtle")
        assert count >= 1
        results = store.query_sparql(
            f"SELECT ?title WHERE {{ <{SBKG_NS}note/imported> <{SBKG_NS}title> ?title }}"
        )
        assert results[0]["title"] == "Imported Note"

    def test_sparql_raw_select(self, store):
        results = store.query_sparql_raw("SELECT * WHERE { ?s ?p ?o } LIMIT 1")
        assert isinstance(results, list)
        assert len(results) == 1
