"""Tests for the markdown parser."""

import textwrap

import pytest

from sbkg_mcp.markdown_parser import extract_triples, note_to_markdown, parse_markdown
from sbkg_mcp.utils import SBKG_NS


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
        from sbkg_mcp.models import Note
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
