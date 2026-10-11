"""Provider interface. Every metadata source maps into models.Game.

Priority default (RomM-style): igdb (text) -> thegamesdb -> screenscraper,
artwork prefers screenscraper when available. Reorder in app config later.
"""
from __future__ import annotations

from ..models import Game


class MetadataProvider:
    name = "base"

    def search(self, query: str, platform: str = "") -> list[Game]:
        raise NotImplementedError
