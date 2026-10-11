"""Link association: download links live ON the game record, matched by name.

Source of truth = metadata (Game). File sources (user's own) only ATTACH
Downloadables to Game.links via normalized title matching. archive.org (or
any source) is never browsed directly by the user in this flow.
"""
from __future__ import annotations

import re
import unicodedata

from .models import Downloadable, Game

_EXT = re.compile(r"\.(zip|7z|iso|iso\.001|rar)$", re.IGNORECASE)
_PARENS = re.compile(r"\([^)]*\)")
_NONALNUM = re.compile(r"[^a-z0-9]+")


def normalize(name: str) -> str:
    """'Halo 3 (USA).zip' and 'Halo 3' both -> 'halo 3'."""
    name = _EXT.sub(" ", name or "")
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = _PARENS.sub(" ", name)
    name = _NONALNUM.sub(" ", name.lower()).strip()
    return re.sub(r"\s+", " ", name)


def score(game_title: str, file_name: str) -> int:
    """2 = exact, 1 = file starts with game (region/tagged variants), else 0."""
    g, f = normalize(game_title), normalize(file_name)
    if not g or not f:
        return 0
    if g == f:
        return 2
    if f == g or f.startswith(g + " "):
        return 1
    return 0


def attach(game: Game, downloadables: list[Downloadable],
           replace: bool = False) -> Game:
    """Rank matching files and attach them to game.links (best first)."""
    ranked = sorted(((score(game.title, d.title), d) for d in downloadables),
                    key=lambda t: -t[0])
    matched = [d for s, d in ranked if s > 0]
    if replace:
        game.links = matched
    else:
        seen = {u for d in game.links for u in d.uris}
        game.links.extend(d for d in matched
                          if not any(u in seen for u in d.uris))
    return game
