"""Dataclasses for notes, bookmarks, projects, people, and tools."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Note:
    title: str
    content: str = ""
    note_type: str = "Note"  # Note, DailyNote, ProjectNote, AreaNote, etc.
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    project: str | None = None
    area: str | None = None
    status: str | None = None
    markdown_path: str | None = None
    created_at: str | None = None
    modified_at: str | None = None
    # Dublin Core metadata
    description: str | None = None
    creator: str | None = None
    language: str | None = None
    license: str | None = None
    # Mentions (e.g. from email To/CC)
    mentions: list[str] = field(default_factory=list)
    # Email addresses (populated by email_parser)
    creator_email: str | None = None
    mention_emails: dict[str, str] = field(default_factory=dict)  # name → email


@dataclass
class Bookmark:
    title: str
    url: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    status: str = "ToRead"  # ToRead, Reading, Read, Reference
    created_at: str | None = None
    modified_at: str | None = None


@dataclass
class Project:
    """DOAP-backed first-class project entity."""
    name: str
    description: str = ""
    homepage: str | None = None
    repository: str | None = None
    programming_language: str | None = None
    platform: str | None = None
    maintainers: list[str] = field(default_factory=list)
    developers: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str | None = None


@dataclass
class Person:
    name: str
    email: str | None = None
    homepage: str | None = None


@dataclass
class Tool:
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
