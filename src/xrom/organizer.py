"""Organizer: metadata-driven folder naming. No binary parsing in v1.

Pattern: "Title [Year] [TITLEID]" (parts omitted when unknown).
Sanitizing mirrors X-Store MakeSafeFolderName/IsInvalidFolderChar.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Game

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize(name: str) -> str:
    name = _INVALID.sub("", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name or "Unknown Game"


def build_folder_name(game: Game) -> str:
    parts = [sanitize(game.title)]
    if game.year:
        parts.append(f"[{game.year}]")
    if game.title_id:
        parts.append(f"[{game.title_id.upper()}]")
    return sanitize(" ".join(parts))


def unique(path: Path) -> Path:
    """X-Store MakeDuplicateOutputFolderUnique: 'Name (2)', 'Name (3)'..."""
    if not path.exists():
        return path
    i = 2
    while True:
        cand = path.parent / f"{path.name} ({i})"
        if not cand.exists():
            return cand
        i += 1


def organize(game: Game, library_root: str | Path,
             cover_path: str = "", local_path: str = "") -> Path:
    """Create the game folder + .xrom.json sidecar. Returns folder path."""
    root = Path(library_root)
    root.mkdir(parents=True, exist_ok=True)
    folder = unique(root / build_folder_name(game))
    folder.mkdir(parents=True, exist_ok=True)
    sidecar = {
        "title": game.title, "platform": game.platform, "year": game.year,
        "genres": game.genres, "summary": game.summary,
        "cover_url": game.cover_url, "cover_path": cover_path,
        "local_path": local_path,  # Hydra-style linked local ROM (iso/...)
        "companies": game.companies, "ids": game.ids,
        "title_id": game.title_id,
        "links": [{"title": d.title, "uris": d.uris,
                   "file_size": d.file_size, "source": d.source}
                  for d in game.links],
    }
    (folder / ".xrom.json").write_text(json.dumps(sidecar, indent=2),
                                       encoding="utf-8")
    return folder
