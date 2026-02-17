"""Oxigraph wrapper for the SBKG triple store."""

from __future__ import annotations

import io
from pathlib import Path

from pyoxigraph import (
    DefaultGraph,
    Literal,
    NamedNode,
    Quad,
    RdfFormat,
    Store,
)

from .ontology import get_all_ontology_paths
from .paths import get_db_path
from .utils import SBKG_NS


_RDF_TYPE = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
_RDFS_LABEL = NamedNode("http://www.w3.org/2000/01/rdf-schema#label")

_FORMAT_MAP: dict[str, RdfFormat] = {
    "turtle": RdfFormat.TURTLE,
    "ttl": RdfFormat.TURTLE,
    "ntriples": RdfFormat.N_TRIPLES,
    "nt": RdfFormat.N_TRIPLES,
    "nquads": RdfFormat.N_QUADS,
    "nq": RdfFormat.N_QUADS,
    "trig": RdfFormat.TRIG,
    "rdfxml": RdfFormat.RDF_XML,
    "xml": RdfFormat.RDF_XML,
}


def _resolve_format(fmt: str) -> RdfFormat:
    fmt_lower = fmt.lower().strip()
    if fmt_lower in _FORMAT_MAP:
        return _FORMAT_MAP[fmt_lower]
    raise ValueError(f"Unsupported RDF format: {fmt}. Supported: {list(_FORMAT_MAP.keys())}")


class KnowledgeStore:
    """Persistent RDF triple store backed by Oxigraph."""

    def __init__(self, path: Path | None = None):
        db_path = path or get_db_path()
        self._store = Store(str(db_path))
        self._ensure_ontology()

    def _ensure_ontology(self) -> None:
        """Load all ontology .ttl files if the store is empty."""
        # Check if ontology classes are present
        results = list(self._store.quads_for_pattern(
            NamedNode(f"{SBKG_NS}Note"), _RDF_TYPE, None, None
        ))
        if not results:
            for path in get_all_ontology_paths():
                ttl = path.read_text(encoding="utf-8")
                self._store.load(ttl, format=RdfFormat.TURTLE)

    def insert_triples(self, quads: list[Quad]) -> int:
        """Batch insert quads. Returns number inserted."""
        self._store.extend(quads)
        return len(quads)

    def add_quad(self, subject: NamedNode, predicate: NamedNode, obj, graph=None) -> None:
        """Add a single triple (as a quad in the default graph)."""
        graph = graph or DefaultGraph()
        if isinstance(obj, str):
            obj = Literal(obj)
        self._store.add(Quad(subject, predicate, obj, graph))

    def remove_triples(
        self,
        subject: NamedNode | None = None,
        predicate: NamedNode | None = None,
        obj=None,
    ) -> int:
        """Remove all triples matching the pattern. Returns count removed."""
        quads = list(self._store.quads_for_pattern(subject, predicate, obj, None))
        for q in quads:
            self._store.remove(q)
        return len(quads)

    def query_sparql(self, sparql: str) -> list[dict]:
        """Execute a SPARQL SELECT query and return list of binding dicts."""
        results = self._store.query(sparql)
        rows = []
        for solution in results:
            row = {}
            for var in results.variables:
                val = solution[var]
                if val is not None:
                    row[var.value] = _term_to_value(val)
            rows.append(row)
        return rows

    def query_sparql_raw(self, sparql: str) -> str:
        """Execute any SPARQL query and return serialized results."""
        results = self._store.query(sparql)
        # SELECT queries
        if hasattr(results, "variables"):
            rows = []
            for solution in results:
                row = {}
                for var in results.variables:
                    val = solution[var]
                    if val is not None:
                        row[var.value] = _term_to_value(val)
                rows.append(row)
            return rows
        # ASK queries
        if isinstance(results, bool):
            return results
        # CONSTRUCT/DESCRIBE queries — return as triples
        triples = []
        for triple in results:
            triples.append({
                "subject": _term_to_value(triple.subject),
                "predicate": _term_to_value(triple.predicate),
                "object": _term_to_value(triple.object),
            })
        return triples

    def export(self, fmt: str = "turtle", path: str | None = None) -> str:
        """Export the store to a file or return as string."""
        rdf_format = _resolve_format(fmt)
        # Graph formats (turtle, ntriples, rdfxml) need from_graph;
        # dataset formats (nquads, trig) do not.
        graph_formats = {RdfFormat.TURTLE, RdfFormat.N_TRIPLES, RdfFormat.RDF_XML}
        kwargs = {"format": rdf_format}
        if rdf_format in graph_formats:
            kwargs["from_graph"] = DefaultGraph()
        if path:
            self._store.dump(path, **kwargs)
            return path
        result = self._store.dump(**kwargs)
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return str(result)

    def import_rdf(self, path: str, fmt: str = "turtle") -> int:
        """Import triples from an RDF file. Returns approximate count."""
        rdf_format = _resolve_format(fmt)
        before = self._count_triples()
        self._store.load(path=path, format=rdf_format)
        after = self._count_triples()
        return after - before

    def bulk_load_string(self, data: str, fmt: str = "turtle") -> int:
        """Bulk-load RDF from an in-memory string. Returns approximate count added."""
        rdf_format = _resolve_format(fmt)
        before = self._count_triples()
        self._store.bulk_load(input=data, format=rdf_format)
        after = self._count_triples()
        return after - before

    def sparql_update(self, update: str) -> None:
        """Execute a SPARQL 1.1 UPDATE (INSERT DATA, DELETE DATA, DELETE/INSERT WHERE, etc.)."""
        self._store.update(update)

    def get_stats(self) -> dict:
        """Return graph statistics: triple count, entity counts by type."""
        total = self._count_triples()

        type_counts = {}
        sparql = (
            "SELECT ?type (COUNT(?s) AS ?count) WHERE { "
            f"?s <{_RDF_TYPE.value}> ?type . "
            "} GROUP BY ?type"
        )
        for row in self.query_sparql(sparql):
            type_name = row.get("type", "")
            if type_name.startswith(SBKG_NS):
                type_name = "sbkg:" + type_name[len(SBKG_NS):]
            type_counts[type_name] = int(row.get("count", 0))

        return {
            "total_triples": total,
            "entity_counts": type_counts,
        }

    def _count_triples(self) -> int:
        result = self.query_sparql("SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }")
        if result:
            return int(result[0].get("c", 0))
        return 0


def _term_to_value(term) -> str:
    """Convert an RDF term to a simple string value."""
    if hasattr(term, "value"):
        return term.value
    return str(term)
