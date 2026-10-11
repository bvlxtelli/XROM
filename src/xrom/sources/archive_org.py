"""archive.org source: matches metadata-found games to IA files.

Games carry their links (Game.links, grouped by normalized name).
archive.org is never browsed directly — it only answers per game.
"""

from __future__ import annotations

from pathlib import Path

import requests

from .. import ia_catalog, linker
from ..models import Downloadable, Game
from .base import SourceProvider


class ArchiveOrgProvider(SourceProvider):
    name = "archive.org"

    def __init__(self, session: requests.Session, cache_dir: Path) -> None:
        self.session = session
        self.cache_dir = cache_dir

    def files_for(self, query: str, platform: str) -> list[Downloadable]:
        plats = [platform] if platform else ["xbox", "xbox360", "xbla"]
        out: list[Downloadable] = []
        for plat in plats:
            for c in ia_catalog.candidates(query, plat, self.session, self.cache_dir):
                out.append(
                    Downloadable(
                        title=c["name"],
                        uris=[c["url"]],
                        file_size=c["size"],
                        source=f"archive.org/{c['ident']}",
                        extra={
                            "ident": c["ident"],
                            "format": c["format"],
                            "filename": c["name"],
                            "platform": plat,
                        },
                    )
                )
        return out

    def search(self, query: str, platform: str = "") -> list[Game]:
        """One Game per normalized name, files attached as links."""
        plats = [platform] if platform else ["xbox", "xbox360", "xbla"]
        groups: dict[str, Game] = {}
        for plat in plats:
            for c in ia_catalog.candidates(query, plat, self.session, self.cache_dir):
                key = linker.normalize(c["name"]) + "|" + plat
                game = groups.get(key)
                if game is None:
                    game = groups[key] = Game(
                        title=c["name"].rsplit(".", 1)[0],
                        platform=plat,
                        ids={"archive": c["ident"]},
                    )
                game.links.append(
                    Downloadable(
                        title=c["name"],
                        uris=[c["url"]],
                        file_size=c["size"],
                        source=f"archive.org/{c['ident']}",
                        extra={"ident": c["ident"], "format": c["format"], "filename": c["name"]},
                    )
                )
        return list(groups.values())

    def resolve(self, game: Game) -> list[Downloadable]:
        if game.links:
            return list(game.links)
        found = self.files_for(game.title, game.platform)
        return linker.attach(game, found).links
