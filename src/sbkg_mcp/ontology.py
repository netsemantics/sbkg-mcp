"""Ontology loading and retrieval."""

from importlib import resources
from pathlib import Path

# Resolve the ontology file bundled with the package
_ONTOLOGY_DIR = Path(__file__).resolve().parent.parent.parent / "ontology"
_ONTOLOGY_FILE = _ONTOLOGY_DIR / "sbkg.ttl"


def get_ontology_path() -> Path:
    """Return the path to the ontology Turtle file."""
    return _ONTOLOGY_FILE


def get_ontology_turtle() -> str:
    """Return the raw Turtle content of the SBKG ontology."""
    return _ONTOLOGY_FILE.read_text(encoding="utf-8")


def get_ontology_summary() -> str:
    """Return a human-readable summary of the SBKG ontology."""
    return (
        "SBKG Ontology — namespace: http://secondbrain.ai/kg/\n"
        "\n"
        "Classes:\n"
        "  sbkg:Note (subtypes: DailyNote, ProjectNote, AreaNote, ResourceNote, FleetingNote)\n"
        "  sbkg:Bookmark, sbkg:Concept, sbkg:Project, sbkg:Area, sbkg:Person, sbkg:Tool\n"
        "\n"
        "Properties:\n"
        "  sbkg:title, sbkg:content, sbkg:hasTag, sbkg:linksTo, sbkg:mentions,\n"
        "  sbkg:belongsToProject, sbkg:belongsToArea, sbkg:createdAt, sbkg:modifiedAt,\n"
        "  sbkg:hasStatus, sbkg:sourceUrl, sbkg:markdownPath\n"
        "\n"
        "Bookmark statuses: sbkg:ToRead, sbkg:Reading, sbkg:Read, sbkg:Reference\n"
        "\n"
        "Prefix: PREFIX sbkg: <http://secondbrain.ai/kg/>\n"
    )
