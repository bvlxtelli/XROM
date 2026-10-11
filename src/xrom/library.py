"""Persistent sqlite store: library games + download queue."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .models import Downloadable, Game, QueueItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games(
  title TEXT, platform TEXT, year INTEGER, genres TEXT, summary TEXT,
  cover_path TEXT, companies TEXT, ids TEXT, title_id TEXT, folder TEXT,
  updated REAL, links TEXT,
  UNIQUE(title, platform));
CREATE TABLE IF NOT EXISTS queue(
  id INTEGER PRIMARY KEY AUTOINCREMENT, game_title TEXT, url TEXT UNIQUE,
  dest TEXT, status TEXT, attempts INTEGER, bytes_done INTEGER,
  total INTEGER, error TEXT);
"""


class Library:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._con.executescript(_SCHEMA)
        # Migrate older DBs (first releases lacked the links column).
        try:
            self._con.execute("ALTER TABLE games ADD COLUMN links TEXT")
        except sqlite3.OperationalError:
            pass

    # -- games ----------------------------------------------------------
    @staticmethod
    def _links_json(game: Game) -> str:
        return json.dumps([{"title": d.title, "uris": d.uris,
                            "file_size": d.file_size,
                            "upload_date": d.upload_date,
                            "source": d.source, "extra": d.extra}
                           for d in game.links])

    @staticmethod
    def game_from_row(row: dict) -> Game:
        """Rehydrate a Game (with links) from a list_games() row.

        Lets library entries download LATER: links survive restarts.
        """
        links = []
        try:
            raw = json.loads(row.get("links") or "[]")
        except ValueError:
            raw = []
        for d in raw:
            try:
                links.append(Downloadable(
                    title=d.get("title", ""), uris=d.get("uris") or [],
                    file_size=d.get("file_size"),
                    upload_date=d.get("upload_date", ""),
                    source=d.get("source", ""), extra=d.get("extra") or {}))
            except (TypeError, AttributeError):
                continue
        return Game(
            title=row.get("title", ""), platform=row.get("platform", ""),
            year=row.get("year"),
            genres=_loads_list(row.get("genres")),
            summary=row.get("summary") or "",
            cover_url="", companies=_loads_list(row.get("companies")),
            ids=_loads_dict(row.get("ids")),
            title_id=row.get("title_id") or "", links=links)

    def upsert_game(self, game: Game, folder: str = "", cover_path: str = "") -> None:
        self._con.execute(
            "INSERT INTO games VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(title, platform) DO UPDATE SET year=excluded.year,"
            " genres=excluded.genres, summary=excluded.summary,"
            " cover_path=excluded.cover_path, companies=excluded.companies,"
            " ids=excluded.ids, title_id=excluded.title_id,"
            " folder=excluded.folder, updated=excluded.updated,"
            " links=excluded.links",
            (game.title, game.platform, game.year, json.dumps(game.genres),
             game.summary, cover_path, json.dumps(game.companies),
             json.dumps(game.ids), game.title_id, folder, time.time(),
             self._links_json(game)))
        self._con.commit()

    def list_games(self) -> list[dict]:
        cur = self._con.execute("SELECT * FROM games ORDER BY title")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    # -- queue ----------------------------------------------------------
    def enqueue(self, item: QueueItem) -> int:
        """Insert, or re-queue an existing URL (reset status/attempts).

        Re-adding a failed/done URL must retry it — silently returning a
        stale 'error' row would make the manager look broken.
        """
        self._con.execute(
            "INSERT INTO queue(game_title,url,dest,status,attempts,"
            "bytes_done,total,error) VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(url) DO UPDATE SET game_title=excluded.game_title,"
            " dest=excluded.dest, status='queued', attempts=0, error=''",
            (item.game_title, item.url, item.dest, item.status, item.attempts,
             item.bytes_done, item.total, item.error))
        self._con.commit()
        row = self._con.execute("SELECT id FROM queue WHERE url=?",
                                (item.url,)).fetchone()
        return row[0] if row else -1

    def update_queue(self, item_id: int, **fields) -> None:
        sets = ", ".join(f"{k}=?" for k in fields)
        self._con.execute(f"UPDATE queue SET {sets} WHERE id=?",
                          (*fields.values(), item_id))
        self._con.commit()

    def list_queue(self, active_only: bool = False) -> list[dict]:
        q = "SELECT * FROM queue"
        if active_only:
            q += " WHERE status IN ('queued','active','paused')"
        q += " ORDER BY id"
        cur = self._con.execute(q)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self) -> None:
        self._con.close()

    def remove_queue(self, item_id: int) -> None:
        self._con.execute("DELETE FROM queue WHERE id=?", (item_id,))
        self._con.commit()

    def remove_game(self, title: str, platform: str) -> None:
        self._con.execute("DELETE FROM games WHERE title=? AND platform=?",
                          (title, platform))
        self._con.commit()


def _loads_list(raw) -> list:
    try:
        data = json.loads(raw or "[]")
        return data if isinstance(data, list) else []
    except ValueError:
        return []


def _loads_dict(raw) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}
