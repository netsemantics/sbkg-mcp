"""Tests for the markdown parser."""

import textwrap

import pytest

from sbkg_mcp.markdown_parser import (
    extract_bookmark_triples,
    extract_project_triples,
    extract_triples,
    note_to_markdown,
    parse_markdown,
)
from sbkg_mcp.models import Bookmark, Note, Project
from sbkg_mcp.utils import DCTERMS_NS, DOAP_NS, FOAF_NS, SBKG_NS, SKOS_NS


def _pred_values(quads, predicate_fragment):
    """Helper: return object values for quads whose predicate contains fragment."""
    return [
        q.object.value
        for q in quads
        if predicate_fragment in q.predicate.value
    ]


@pytest.fixture
def sample_md(tmp_path):
    md = tmp_path / "sample.md"
    md.write_text(textwrap.dedent("""\
        ---
        title: My Test Note
        type: ProjectNote
        tags:
          - python
          - testing
        project: sbkg-mcp
        area: development
        status: active
        created: "2025-01-01T00:00:00Z"
        ---

        This is a test note with a [[wikilink]] and a #tag reference.
        It also links to [[Another Note]].
    """), encoding="utf-8")
    return md


class TestParseMarkdown:
    def test_basic_parse(self, sample_md):
        note = parse_markdown(sample_md)
        assert note.title == "My Test Note"
        assert note.note_type == "ProjectNote"
        assert "python" in note.tags
        assert "testing" in note.tags
        assert note.project == "sbkg-mcp"
        assert note.area == "development"

    def test_wikilinks_extracted(self, sample_md):
        note = parse_markdown(sample_md)
        assert "wikilink" in note.links
        assert "Another Note" in note.links

    def test_inline_tags_merged(self, sample_md):
        note = parse_markdown(sample_md)
        assert "tag" in note.tags

    def test_no_frontmatter(self, tmp_path):
        md = tmp_path / "plain.md"
        md.write_text("Just plain content with a [[link]].", encoding="utf-8")
        note = parse_markdown(md)
        assert note.title == "plain"  # stem of filename
        assert "link" in note.links

    def test_extract_triples(self, sample_md):
        note = parse_markdown(sample_md)
        quads = extract_triples(note)
        assert len(quads) > 0
        # Should contain type triple
        type_quads = [q for q in quads if "rdf-syntax-ns#type" in q.predicate.value]
        assert len(type_quads) > 0

    def test_note_to_markdown(self):
        note = Note(
            title="Roundtrip",
            content="Some content here.",
            tags=["a", "b"],
            project="proj",
        )
        md = note_to_markdown(note)
        assert "title: Roundtrip" in md
        assert "Some content here." in md
        assert "---" in md

    def test_dc_metadata_in_frontmatter(self, tmp_path):
        md = tmp_path / "dc.md"
        md.write_text(textwrap.dedent("""\
            ---
            title: DC Note
            description: A test note with DC metadata
            creator: Jane Doe
            language: en
            license: MIT
            ---

            Content here.
        """), encoding="utf-8")
        note = parse_markdown(md)
        assert note.description == "A test note with DC metadata"
        assert note.creator == "Jane Doe"
        assert note.language == "en"
        assert note.license == "MIT"

    def test_dc_metadata_triples(self):
        note = Note(
            title="DC Triple Test",
            description="A description",
            creator="Alice",
            language="en",
            license="Apache-2.0",
        )
        quads = extract_triples(note)
        descriptions = _pred_values(quads, f"{DCTERMS_NS}description")
        assert "A description" in descriptions
        creators = _pred_values(quads, f"{DCTERMS_NS}creator")
        assert "Alice" in creators
        languages = _pred_values(quads, f"{DCTERMS_NS}language")
        assert "en" in languages
        licenses = _pred_values(quads, f"{DCTERMS_NS}license")
        assert "Apache-2.0" in licenses

    def test_skos_preflabel_on_concepts(self):
        note = Note(title="Tag Test", tags=["python", "rdf"])
        quads = extract_triples(note)
        pref_labels = _pred_values(quads, f"{SKOS_NS}prefLabel")
        assert "python" in pref_labels
        assert "rdf" in pref_labels

    def test_status_named_node_for_known(self):
        note = Note(title="Status Test", status="ToRead")
        quads = extract_triples(note)
        status_quads = [q for q in quads if "hasStatus" in q.predicate.value]
        assert len(status_quads) == 1
        # Known status should be a NamedNode
        assert status_quads[0].object.value == f"{SBKG_NS}ToRead"

    def test_status_literal_for_freeform(self):
        note = Note(title="Freeform Status", status="in-progress")
        quads = extract_triples(note)
        status_quads = [q for q in quads if "hasStatus" in q.predicate.value]
        assert len(status_quads) == 1
        # Freeform status should be a Literal
        assert status_quads[0].object.value == "in-progress"

    def test_note_to_markdown_dc_fields(self):
        note = Note(
            title="DC Roundtrip",
            content="Body.",
            description="Desc",
            creator="Bob",
            language="fr",
            license="GPL-3.0",
        )
        md = note_to_markdown(note)
        assert "description: Desc" in md
        assert "creator: Bob" in md
        assert "language: fr" in md
        assert "license: GPL-3.0" in md

    def test_mentions_triples(self):
        note = Note(
            title="Mention Test",
            mentions=["Alice Smith", "Bob Jones"],
        )
        quads = extract_triples(note)
        mention_quads = [q for q in quads if "mentions" in q.predicate.value]
        assert len(mention_quads) == 2
        # Should create foaf:Person nodes
        person_type_quads = [
            q for q in quads
            if q.predicate.value == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
            and q.object.value == f"{FOAF_NS}Person"
        ]
        assert len(person_type_quads) == 2

    def test_full_content_stored(self):
        """Content longer than 500 chars should NOT be truncated."""
        long_content = "x" * 1000
        note = Note(title="Long Content", content=long_content)
        quads = extract_triples(note)
        content_values = _pred_values(quads, f"{SBKG_NS}content")
        assert len(content_values) == 1
        assert len(content_values[0]) == 1000

    def test_wikilink_alias_stripped(self, tmp_path):
        """[[Real Target|display text]] should link to 'Real Target', not 'Real Target|display text'."""
        md = tmp_path / "alias.md"
        md.write_text("Check out [[Real Target|display text]] for details.", encoding="utf-8")
        note = parse_markdown(md)
        assert "Real Target" in note.links
        assert "Real Target|display text" not in note.links

    def test_image_embed_skipped(self, tmp_path):
        """![[diagram.png]] should not be captured as a wikilink."""
        md = tmp_path / "embed.md"
        md.write_text("See ![[diagram.png]] and [[real link]].", encoding="utf-8")
        note = parse_markdown(md)
        assert "real link" in note.links
        assert "diagram.png" not in note.links

    def test_mention_mbox_triple_emitted(self):
        """foaf:mbox triple should be created for mentions with emails."""
        note = Note(
            title="Mbox Test",
            mentions=["Alice Smith"],
            mention_emails={"Alice Smith": "alice@example.com"},
        )
        quads = extract_triples(note)
        mbox_quads = [q for q in quads if "foaf/0.1/mbox" in q.predicate.value]
        assert len(mbox_quads) == 1
        assert mbox_quads[0].object.value == "mailto:alice@example.com"

    def test_creator_with_email_becomes_person_node(self):
        """dcterms:creator should be a Person URI (not Literal) when creator_email is set."""
        note = Note(
            title="Creator Email Test",
            creator="Jane Doe",
            creator_email="jane@example.com",
        )
        quads = extract_triples(note)
        # dcterms:creator should point to a NamedNode (not Literal)
        creator_quads = [q for q in quads if f"{DCTERMS_NS}creator" in q.predicate.value]
        assert len(creator_quads) == 1
        # The object should be a URI (NamedNode), not a plain string Literal
        assert "person/" in creator_quads[0].object.value
        # foaf:mbox should be emitted for the creator
        mbox_quads = [q for q in quads if "foaf/0.1/mbox" in q.predicate.value]
        assert any(q.object.value == "mailto:jane@example.com" for q in mbox_quads)


class TestExtractBookmarkTriples:
    def test_basic_bookmark(self):
        bm = Bookmark(title="Example", url="https://example.com", tags=["web"])
        quads = extract_bookmark_triples(bm)
        # Should have type, title, sourceUrl, tag triples, status, createdAt
        types = [q for q in quads if "rdf-syntax-ns#type" in q.predicate.value]
        assert any(q.object.value == f"{SBKG_NS}Bookmark" for q in types)

    def test_bookmark_skos_preflabel(self):
        bm = Bookmark(title="Labeled", url="https://x.com", tags=["ai", "ml"])
        quads = extract_bookmark_triples(bm)
        pref_labels = _pred_values(quads, f"{SKOS_NS}prefLabel")
        assert "ai" in pref_labels
        assert "ml" in pref_labels

    def test_bookmark_status_named_node(self):
        bm = Bookmark(title="Status BM", url="https://x.com", status="Read")
        quads = extract_bookmark_triples(bm)
        status_quads = [q for q in quads if "hasStatus" in q.predicate.value]
        assert len(status_quads) == 1
        assert status_quads[0].object.value == f"{SBKG_NS}Read"

    def test_bookmark_status_literal_freeform(self):
        bm = Bookmark(title="Custom", url="https://x.com", status="archived")
        quads = extract_bookmark_triples(bm)
        status_quads = [q for q in quads if "hasStatus" in q.predicate.value]
        assert len(status_quads) == 1
        assert status_quads[0].object.value == "archived"


class TestExtractProjectTriples:
    def test_basic_project(self):
        proj = Project(name="my-project", description="A test project")
        quads = extract_project_triples(proj)
        types = [q for q in quads if "rdf-syntax-ns#type" in q.predicate.value]
        # Should have both sbkg:Project and doap:Project
        type_values = {q.object.value for q in types}
        assert f"{SBKG_NS}Project" in type_values
        assert f"{DOAP_NS}Project" in type_values

    def test_doap_properties(self):
        proj = Project(
            name="test-proj",
            description="Desc",
            homepage="https://example.com",
            repository="https://github.com/test/repo",
            programming_language="Python",
            platform="Linux",
        )
        quads = extract_project_triples(proj)
        names = _pred_values(quads, f"{DOAP_NS}name")
        assert "test-proj" in names
        descs = _pred_values(quads, f"{DOAP_NS}description")
        assert "Desc" in descs
        homepages = _pred_values(quads, f"{DOAP_NS}homepage")
        assert "https://example.com" in homepages
        langs = _pred_values(quads, f"{DOAP_NS}programming-language")
        assert "Python" in langs
        platforms = _pred_values(quads, f"{DOAP_NS}platform")
        assert "Linux" in platforms

    def test_repository_creates_git_repo_node(self):
        proj = Project(name="repo-proj", repository="https://github.com/x/y")
        quads = extract_project_triples(proj)
        git_repo_types = [
            q for q in quads
            if q.predicate.value == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
            and q.object.value == f"{DOAP_NS}GitRepository"
        ]
        assert len(git_repo_types) == 1
        locations = _pred_values(quads, f"{DOAP_NS}location")
        assert "https://github.com/x/y" in locations

    def test_maintainers_and_developers(self):
        proj = Project(
            name="team-proj",
            maintainers=["Alice"],
            developers=["Bob", "Charlie"],
        )
        quads = extract_project_triples(proj)
        maintainer_quads = [q for q in quads if f"{DOAP_NS}maintainer" in q.predicate.value]
        assert len(maintainer_quads) == 1
        developer_quads = [q for q in quads if f"{DOAP_NS}developer" in q.predicate.value]
        assert len(developer_quads) == 2
        # foaf:name should be emitted
        foaf_names = _pred_values(quads, f"{FOAF_NS}name")
        assert "Alice" in foaf_names
        assert "Bob" in foaf_names
        assert "Charlie" in foaf_names

    def test_project_tags_with_skos(self):
        proj = Project(name="tagged-proj", tags=["python", "ml"])
        quads = extract_project_triples(proj)
        pref_labels = _pred_values(quads, f"{SKOS_NS}prefLabel")
        assert "python" in pref_labels
        assert "ml" in pref_labels
