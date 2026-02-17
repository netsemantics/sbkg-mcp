"""Ontology loading and retrieval."""

from pathlib import Path

# Resolve the ontology directory bundled with the package
_ONTOLOGY_DIR = Path(__file__).resolve().parent.parent.parent / "ontology"
_ONTOLOGY_FILE = _ONTOLOGY_DIR / "sbkg.ttl"


def get_ontology_dir() -> Path:
    """Return the path to the ontology directory."""
    return _ONTOLOGY_DIR


def get_ontology_path() -> Path:
    """Return the path to the core SBKG ontology Turtle file."""
    return _ONTOLOGY_FILE


def get_all_ontology_paths() -> list[Path]:
    """Return paths to all .ttl files in the ontology directory, sbkg.ttl first."""
    files = sorted(_ONTOLOGY_DIR.glob("*.ttl"))
    # Ensure sbkg.ttl is loaded first so other files can reference its terms
    result = [f for f in files if f.name == "sbkg.ttl"]
    result.extend(f for f in files if f.name != "sbkg.ttl")
    return result


def get_ontology_turtle() -> str:
    """Return the combined Turtle content of all ontology files."""
    parts = []
    for path in get_all_ontology_paths():
        parts.append(f"# --- {path.name} ---\n")
        parts.append(path.read_text(encoding="utf-8"))
        parts.append("\n")
    return "\n".join(parts)


def get_ontology_summary() -> str:
    """Return a human-readable summary of the SBKG ontology and extensions."""
    return (
        "SBKG Ontology — namespace: http://secondbrain.ai/kg/\n"
        "\n"
        "Core Classes:\n"
        "  sbkg:Note (subtypes: DailyNote, ProjectNote, AreaNote, ResourceNote, FleetingNote)\n"
        "  sbkg:Bookmark, sbkg:Concept, sbkg:Project, sbkg:Area, sbkg:Person, sbkg:Tool\n"
        "\n"
        "Core Properties:\n"
        "  sbkg:title, sbkg:content, sbkg:hasTag, sbkg:linksTo, sbkg:mentions,\n"
        "  sbkg:belongsToProject, sbkg:belongsToArea, sbkg:createdAt, sbkg:modifiedAt,\n"
        "  sbkg:hasStatus, sbkg:sourceUrl, sbkg:markdownPath\n"
        "\n"
        "Bookmark statuses: sbkg:ToRead, sbkg:Reading, sbkg:Read, sbkg:Reference\n"
        "\n"
        "Extended Vocabularies:\n"
        "  SKOS (skos:) — concept hierarchies: broader, narrower, related, prefLabel, altLabel,\n"
        "    ConceptScheme, inScheme, hasTopConcept, definition\n"
        "    sbkg:Concept is a subclass of skos:Concept\n"
        "\n"
        "  Dublin Core Terms (dcterms:) — resource metadata: title, description, creator,\n"
        "    contributor, subject, created, modified, issued, license, format, language,\n"
        "    isPartOf, hasPart, references, identifier, source, publisher\n"
        "\n"
        "  DOAP (doap:) — software projects: Project, Repository, GitRepository, Version,\n"
        "    name, description, homepage, programming-language, platform, license,\n"
        "    repository, release, revision, maintainer, developer, bug-database,\n"
        "    implements, Specification\n"
        "    Includes minimal FOAF: foaf:Person, foaf:name, foaf:mbox, foaf:homepage\n"
        "\n"
        "Prefixes:\n"
        "  PREFIX sbkg:    <http://secondbrain.ai/kg/>\n"
        "  PREFIX skos:    <http://www.w3.org/2004/02/skos/core#>\n"
        "  PREFIX dcterms: <http://purl.org/dc/terms/>\n"
        "  PREFIX doap:    <http://usefulinc.com/ns/doap#>\n"
        "  PREFIX foaf:    <http://xmlns.com/foaf/0.1/>\n"
    )
