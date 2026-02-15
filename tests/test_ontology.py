"""Tests for ontology loading."""

from sbkg_mcp.ontology import get_ontology_summary, get_ontology_turtle


def test_get_ontology_turtle():
    ttl = get_ontology_turtle()
    assert "sbkg:Note" in ttl
    assert "sbkg:Bookmark" in ttl
    assert "sbkg:Concept" in ttl


def test_get_ontology_summary():
    summary = get_ontology_summary()
    assert "sbkg:Note" in summary
    assert "secondbrain.ai" in summary
