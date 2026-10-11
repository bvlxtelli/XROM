"""archive.org source: matches metadata-found games to IA files.

Uses ia_catalog.candidates(); the GAME (from metadata providers) is the
query, archive.org only answers "exists / url / size".
"""
from __future__ import annotations

from pathlib import Path

import requests

from .. import ia_catalog
from ..models import Downloadable, Game
from .base import SourceProvider


class ArchiveOrgProvider(SourceProvider):
    name = "archive.org"

    def __init__(self, session: requests.Session, cache_dir: Path) -> None:
        self.session = session
        self.cache_dir = cache_dir

    def search(self, query: str, platform: str = "") -> list[Game]:
        plats = [platform] if platform else ["xbox", "xbox360", "xbla"]
        out: list[Game] = []
        for plat in plats:
            for c in ia_catalog.candidates(query, plat, self.session,
                                           self.cache_dir):
                out.append(Game(title=c["name"], platform=plat,
                                ids={"archive": c["ident"],
                                     "archive_url": c["url"],
                                     "archive_size": c["size"],
                                     "archive_format": c["format"]}))
        return out

    def resolve(self, game: Game) -> list[Downloadable]:
        plats = [game.platform] if game.platform else ["xbox", "xbox360",
                                                       "xbla"]
        out: list[Downloadable] = []
        for plat in plats:
            for c in ia_catalog.candidates(game.title, plat, self.session,
                                           self.cache_dir):
                out.append(Downloadable(
                    title=c["name"], uris=[c["url"]], file_size=c["size"],
                    source=f"archive.org/{c['ident']}",
                    extra={"ident": c["ident"], "format": c["format"],
                           "filename": c["name"]}))
        return out
