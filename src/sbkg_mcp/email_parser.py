"""Parse RFC 2822 email into a Note for knowledge graph ingestion."""

from __future__ import annotations

import email
import email.policy
import re
from email.utils import parseaddr, parsedate_to_datetime

from .models import Note


def _extract_name_email_pairs(header_value: str | None) -> list[tuple[str, str]]:
    """Extract (display_name, email_address) pairs from an email header value."""
    if not header_value:
        return []
    pairs: list[tuple[str, str]] = []
    for part in header_value.split(","):
        display_name, addr = parseaddr(part.strip())
        if addr:
            name = display_name if display_name else addr
            pairs.append((name, addr))
    return pairs


def _extract_names(header_value: str | None) -> list[str]:
    """Extract display names (or addresses) from an email header value."""
    return [name for name, _addr in _extract_name_email_pairs(header_value)]


def _strip_html(html: str) -> str:
    """Minimal HTML tag stripping for fallback body extraction."""
    text = re.sub(r"<[^>]+>", "", html)
    return re.sub(r"\s+", " ", text).strip()


def parse_email(raw: str) -> Note:
    """Parse an RFC 2822 raw email string into a Note.

    - Subject → title
    - Body (text/plain preferred, fallback stripped text/html) → content
    - From → creator
    - To + CC → mentions
    - Date → created_at
    - Attachment filenames → appended to content
    - Auto-tagged with "email", note_type = "FleetingNote"
    """
    msg = email.message_from_string(raw, policy=email.policy.default)

    # Title
    title = msg.get("Subject", "Untitled Email")

    # Creator from From header
    from_header = msg.get("From", "")
    display_name, from_addr = parseaddr(from_header)
    creator = display_name if display_name else from_addr
    creator_email = from_addr or None

    # Mentions from To + CC
    mentions: list[str] = []
    mention_emails: dict[str, str] = {}
    for hdr in ("To", "CC"):
        for name, addr in _extract_name_email_pairs(msg.get(hdr)):
            mentions.append(name)
            mention_emails[name] = addr

    # Date
    created_at: str | None = None
    date_header = msg.get("Date")
    if date_header:
        try:
            dt = parsedate_to_datetime(date_header)
            created_at = dt.isoformat()
        except (ValueError, TypeError):
            pass

    # Body and attachments
    body = ""
    attachment_names: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in disposition:
                filename = part.get_filename()
                if filename:
                    attachment_names.append(filename)
                continue

            if content_type == "text/plain" and not body:
                payload = part.get_content()
                if isinstance(payload, str):
                    body = payload
            elif content_type == "text/html" and not body:
                payload = part.get_content()
                if isinstance(payload, str):
                    body = _strip_html(payload)
    else:
        content_type = msg.get_content_type()
        payload = msg.get_content()
        if isinstance(payload, str):
            if content_type == "text/html":
                body = _strip_html(payload)
            else:
                body = payload

    # Append attachment list to content
    content = body.strip()
    if attachment_names:
        att_list = "\n".join(f"- {fn}" for fn in attachment_names)
        content += f"\n\nAttachments:\n{att_list}"

    return Note(
        title=title,
        content=content,
        note_type="FleetingNote",
        tags=["email"],
        creator=creator or None,
        mentions=mentions,
        created_at=created_at,
        creator_email=creator_email,
        mention_emails=mention_emails,
    )
