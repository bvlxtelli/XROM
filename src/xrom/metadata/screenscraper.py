"""ScreenScraper.fr provider — richest artwork (box 2D/3D, wheel, screenshot).

Needs the USER's account (ssid/sspassword) + a dev id/password pair.
Free tier ~20k req/day registered. Terms: no DB redistribution.
"""
from __future__ import annotations

import requests

from ..models import Game
from .base import MetadataProvider

API = "https://www.screenscraper.fr/api2/jeuInfos.php"
PLATFORM_MAP = {"xbox": 32, "xbox360": 33, "xbla": 33}  # verify ids in UI


class ScreenScraperProvider(MetadataProvider):
    name = "screenscraper"

    def __init__(self, dev_id: str, dev_password: str, user: str,
                 password: str) -> None:
        self.dev_id = dev_id
        self.dev_password = dev_password
        self.user = user
        self.password = password

    def search(self, query: str, platform: str = "") -> list[Game]:
        params = {"devid": self.dev_id, "devpassword": self.dev_password,
                  "ssid": self.user, "sspassword": self.password,
                  "output": "json", "romnom": query}
        if platform in PLATFORM_MAP:
            params["systemeid"] = PLATFORM_MAP[platform]
        r = requests.get(API, params=params, timeout=30)
        r.raise_for_status()
        jeux = r.json().get("response", {}).get("jeux") or []
        out: list[Game] = []
        for j in jeux:
            noms = j.get("noms") or []
            title = next((n.get("text") for n in noms
                          if n.get("region") in (None, "us", "eu", "wor")),
                         query)
            cover = ""
            for m in j.get("medias") or []:
                if m.get("type") in ("box-2D", "box-3D"):
                    cover = m.get("url", "")
                    break
            genres = [g.get("principal", "") or g.get("text", "")
                      for g in (j.get("genres") or [])]
            dates = j.get("dates") or []
            year = None
            for d in dates:
                try:
                    year = int(str(d.get("text", ""))[:4])
                    break
                except (ValueError, TypeError):
                    continue
            out.append(Game(title=title or query, platform=platform,
                            year=year, genres=[g for g in genres if g],
                            summary=(j.get("synopsis") or [{}])[0].get("text", ""),
                            cover_url=cover,
                            ids={"screenscraper": j.get("id")}))
        return out[:20]
