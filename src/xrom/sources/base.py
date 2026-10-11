"""File-source interface. Sources RESOLVE files; metadata FINDS games.

v1: ArchiveOrgProvider (user's account) + HydraJsonProvider (user's file).
Future: TorrentProvider, LocalFolderProvider — one file each, no GUI touch.
"""

from __future__ import annotations

from ..models import Downloadable, Game


class SourceProvider:
    name = "base"

    def search(self, query: str, platform: str = "") -> list[Game]:
        raise NotImplementedError

    def resolve(self, game: Game) -> list[Downloadable]:
        raise NotImplementedError
