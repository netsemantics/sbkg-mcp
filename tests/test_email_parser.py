"""Tests for the email parser."""

import textwrap

from sbkg_mcp.email_parser import parse_email


class TestParseEmail:
    def test_basic_email(self):
        raw = textwrap.dedent("""\
            From: Alice Smith <alice@example.com>
            To: Bob Jones <bob@example.com>
            Subject: Meeting Notes
            Date: Mon, 15 Jan 2024 10:30:00 +0000

            Here are the notes from today's meeting.
            Action items listed below.
        """)
        note = parse_email(raw)
        assert note.title == "Meeting Notes"
        assert note.creator == "Alice Smith"
        assert note.note_type == "FleetingNote"
        assert "email" in note.tags
        assert "Here are the notes" in note.content
        assert note.created_at is not None
        assert "2024-01-15" in note.created_at

    def test_subject_body_from_extraction(self):
        raw = textwrap.dedent("""\
            From: jane@example.com
            To: team@example.com
            Subject: Project Update

            The project is on track.
        """)
        note = parse_email(raw)
        assert note.title == "Project Update"
        # No display name, so address is used
        assert note.creator == "jane@example.com"
        assert "The project is on track." in note.content

    def test_to_and_cc_mentions(self):
        raw = textwrap.dedent("""\
            From: Alice <alice@example.com>
            To: Bob <bob@example.com>, Charlie <charlie@example.com>
            CC: Dave <dave@example.com>
            Subject: Group Thread

            Hello everyone.
        """)
        note = parse_email(raw)
        assert "Bob" in note.mentions
        assert "Charlie" in note.mentions
        assert "Dave" in note.mentions

    def test_date_extraction(self):
        raw = textwrap.dedent("""\
            From: test@example.com
            Subject: Dated
            Date: Tue, 25 Dec 2024 08:00:00 -0500

            Body.
        """)
        note = parse_email(raw)
        assert note.created_at is not None
        assert "2024-12-25" in note.created_at

    def test_multipart_email(self):
        raw = (
            "From: sender@example.com\r\n"
            "To: receiver@example.com\r\n"
            "Subject: Multipart Test\r\n"
            "MIME-Version: 1.0\r\n"
            'Content-Type: multipart/mixed; boundary="boundary123"\r\n'
            "\r\n"
            "--boundary123\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            "\r\n"
            "This is the plain text body.\r\n"
            "--boundary123\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            "\r\n"
            "<html><body><p>HTML version</p></body></html>\r\n"
            "--boundary123--\r\n"
        )
        note = parse_email(raw)
        assert note.title == "Multipart Test"
        # Should prefer text/plain
        assert "plain text body" in note.content

    def test_attachment_filenames(self):
        raw = (
            "From: sender@example.com\r\n"
            "Subject: With Attachment\r\n"
            "MIME-Version: 1.0\r\n"
            'Content-Type: multipart/mixed; boundary="bnd"\r\n'
            "\r\n"
            "--bnd\r\n"
            "Content-Type: text/plain\r\n"
            "\r\n"
            "See attached.\r\n"
            "--bnd\r\n"
            "Content-Type: application/pdf\r\n"
            'Content-Disposition: attachment; filename="report.pdf"\r\n'
            "\r\n"
            "PDF_CONTENT_HERE\r\n"
            "--bnd\r\n"
            "Content-Type: image/png\r\n"
            'Content-Disposition: attachment; filename="screenshot.png"\r\n'
            "\r\n"
            "PNG_CONTENT_HERE\r\n"
            "--bnd--\r\n"
        )
        note = parse_email(raw)
        assert "report.pdf" in note.content
        assert "screenshot.png" in note.content
        assert "Attachments:" in note.content

    def test_html_only_body(self):
        raw = textwrap.dedent("""\
            From: html@example.com
            Subject: HTML Only
            Content-Type: text/html

            <html><body><p>Hello <b>World</b></p></body></html>
        """)
        note = parse_email(raw)
        assert "Hello" in note.content
        assert "World" in note.content
        # Tags should not be present
        assert "<p>" not in note.content

    def test_missing_subject(self):
        raw = textwrap.dedent("""\
            From: test@example.com

            Body without subject.
        """)
        note = parse_email(raw)
        assert note.title == "Untitled Email"

    def test_auto_tag_and_type(self):
        raw = textwrap.dedent("""\
            From: test@example.com
            Subject: Tag Check

            Body.
        """)
        note = parse_email(raw)
        assert "email" in note.tags
        assert note.note_type == "FleetingNote"

    def test_creator_email_captured(self):
        raw = textwrap.dedent("""\
            From: Alice Smith <alice@example.com>
            Subject: Email Test

            Body.
        """)
        note = parse_email(raw)
        assert note.creator_email == "alice@example.com"

    def test_mention_emails_captured(self):
        raw = textwrap.dedent("""\
            From: Alice <alice@example.com>
            To: Bob <bob@example.com>, Charlie <charlie@example.com>
            CC: Dave <dave@example.com>
            Subject: Group Thread

            Hello everyone.
        """)
        note = parse_email(raw)
        assert note.mention_emails["Bob"] == "bob@example.com"
        assert note.mention_emails["Charlie"] == "charlie@example.com"
        assert note.mention_emails["Dave"] == "dave@example.com"

    def test_no_display_name_uses_address(self):
        raw = textwrap.dedent("""\
            From: sender@example.com
            To: recipient@example.com
            Subject: No Names

            Body.
        """)
        note = parse_email(raw)
        assert note.creator == "sender@example.com"
        assert note.creator_email == "sender@example.com"
        assert note.mention_emails["recipient@example.com"] == "recipient@example.com"
