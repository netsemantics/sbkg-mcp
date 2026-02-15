"""Dataclasses for notes, bookmarks, and tool results."""

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


@dataclass
class Bookmark:
    title: str
    url: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    status: str = "ToRead"  # ToRead, Reading, Read, Reference
    created_at: str | None = None
