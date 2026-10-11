"""Hydra-compatible JSON file source (user-provided, Hydra-style).

Format (see https://docs.hydralauncher.gg/download-sources):
  {"name": "...",
   "downloads": [{"title": "...", "fileSize": "...",
                  "uris": ["..."], "uploadDate": "..."}]}
fileSize like "15.2 GB" is parsed to bytes (best effort).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import Downloadable, Game
from .base import SourceProvider

_SIZE = re.compile(r"^\s*([\d.,]+)\s*([KMGT]?B)\s*$", re.IGNORECASE)
_MULT = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}


def parse_size(s: str) -> int | None:
    m = _SIZE.match(s or "")
    if not m:
        return None
    try:
        return int(float(m.group(1).replace(",", ".")) * _MULT[m.group(2).upper()])
    except (ValueError, KeyError):
        return None


class HydraJsonProvider(SourceProvider):
    name = "hydra-json"

    def __init__(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.source_name = data.get("name", Path(path).stem)
        self._downloads = data.get("downloads", [])

    def search(self, query: str, platform: str = "") -> list[Game]:
        q = query.lower()
        return [Game(title=d.get("title", "Unknown"), platform=platform,
                     ids={"hydra_source": self.source_name})
                for d in self._downloads
                if q in str(d.get("title", "")).lower()]

    def resolve(self, game: Game) -> list[Downloadable]:
        out: list[Downloadable] = []
        for d in self._downloads:
            if str(d.get("title", "")).lower() != game.title.lower():
                continue
            uris = d.get("uris") or []
            if isinstance(uris, str):
                uris = [uris]
            out.append(Downloadable(title=d.get("title", "Unknown"),
                                    uris=list(uris),
                                    file_size=parse_size(d.get("fileSize", "")),
                                    upload_date=d.get("uploadDate", ""),
                                    source=self.source_name))
        return out
