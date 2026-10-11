"""TheGamesDB provider — fallback metadata + boxart. Free API key (user's)."""

from __future__ import annotations

import requests

from ..models import Game
from .base import MetadataProvider

API = "https://api.thegamesdb.net/v1"


class TheGamesDbProvider(MetadataProvider):
    name = "thegamesdb"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, query: str, platform: str = "") -> list[Game]:
        r = requests.get(
            f"{API}/Games/ByGameName", params={"apikey": self.api_key, "name": query}, timeout=30
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        games = data.get("games", [])
        images = data.get("images") or {}
        out: list[Game] = []
        for g in games:
            gid = str(g.get("id"))
            cover = ""
            for img in images.get(gid) or []:
                if img.get("type") in ("boxart", "clearlogo"):
                    base = img.get("base_url", {}).get("original", "")
                    if base and img.get("filename"):
                        cover = base + img["filename"]
                        break
            year = None
            if g.get("release_date"):
                try:
                    year = int(str(g["release_date"])[:4])
                except ValueError:
                    pass
            genres = [x for x in (g.get("genres") or []) if x]
            out.append(
                Game(
                    title=g.get("game_title", "Unknown"),
                    platform=platform,
                    year=year,
                    genres=genres,
                    summary=g.get("overview", ""),
                    cover_url=cover,
                    ids={"tgdb": g.get("id")},
                )
            )
        return out[:20]
