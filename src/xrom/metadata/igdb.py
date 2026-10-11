"""IGDB (Twitch) provider — primary TEXT metadata.

Auth: OAuth client-credentials with the USER's Twitch app keys.
Terms: free non-commercial, 4 req/s, attribution. See docs/CREDITS.md.
Platforms: 11 = Xbox, 12 = Xbox 360.
"""
from __future__ import annotations

import time

import requests

from ..models import Game
from .base import MetadataProvider

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
API = "https://api.igdb.com/v4"
IMG = "https://images.igdb.com/igdb/image/upload/t_cover_big/{}.jpg"
PLATFORM_MAP = {"xbox": 11, "xbox360": 12, "xbla": 12}


class IgdbProvider(MetadataProvider):
    name = "igdb"

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = ""
        self._token_exp = 0.0

    def _auth(self) -> dict:
        if time.time() > self._token_exp - 60:
            r = requests.post(TOKEN_URL, params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials"}, timeout=30)
            r.raise_for_status()
            data = r.json()
            self._token = data["access_token"]
            self._token_exp = time.time() + int(data.get("expires_in", 0))
        return {"Client-ID": self.client_id,
                "Authorization": f"Bearer {self._token}"}

    def search(self, query: str, platform: str = "") -> list[Game]:
        headers = self._auth()
        plat = PLATFORM_MAP.get(platform, "")
        where = f"where platforms = ({plat});" if plat else ""
        body = (f'search "{query}"; '
                "fields name,first_release_date,genres.name,"
                "involved_companies.company.name,cover.image_id,summary;"
                f"{where} limit 20;")
        r = requests.post(f"{API}/games", headers=headers, data=body,
                          timeout=30)
        r.raise_for_status()
        out: list[Game] = []
        for g in r.json():
            year = None
            if g.get("first_release_date"):
                year = time.gmtime(g["first_release_date"]).tm_year
            genres = [x.get("name", "") for x in g.get("genres", [])]
            companies = [c.get("company", {}).get("name", "")
                         for c in g.get("involved_companies", [])]
            cover = IMG.format(g["cover"]["image_id"]) if g.get("cover") else ""
            out.append(Game(title=g.get("name", "Unknown"),
                            platform=platform, year=year, genres=genres,
                            summary=g.get("summary", ""), cover_url=cover,
                            companies=[c for c in companies if c],
                            ids={"igdb": g.get("id")}))
        return out
