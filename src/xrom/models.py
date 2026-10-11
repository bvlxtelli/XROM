"""Shared data models. Pure dataclasses — no I/O, no network."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Game:
    """Metadata-first record. Source of truth for search/cards/organizer.

    Download links live ON the game (links), matched by name from the
    user's file sources. File sources are never browsed directly.
    """

    title: str
    platform: str = ""  # "xbox" | "xbox360" | "xbla"
    year: int | None = None
    genres: list[str] = field(default_factory=list)
    summary: str = ""
    cover_url: str = ""
    companies: list[str] = field(default_factory=list)
    ids: dict = field(default_factory=dict)  # e.g. {"igdb": 123, "tgdb": 456}
    title_id: str = ""  # Xbox title id when known (e.g. "4D5307E6")
    links: list[Downloadable] = field(default_factory=list)


@dataclass
class Downloadable:
    """One resolvable file from a user-configured source."""

    title: str
    uris: list[str] = field(default_factory=list)  # mirrors, first = primary
    file_size: int | None = None
    upload_date: str = ""
    source: str = ""
    extra: dict = field(default_factory=dict)  # ident, format, filename...


@dataclass
class QueueItem:
    game_title: str
    url: str
    dest: str
    status: str = "queued"  # queued|active|paused|done|error|cancelled
    attempts: int = 0
    bytes_done: int = 0
    total: int | None = None
    error: str = ""
    id: int | None = None
