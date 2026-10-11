"""Persistent sqlite store: library games + download queue."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .models import Game, QueueItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games(
  title TEXT, platform TEXT, year INTEGER, genres TEXT, summary TEXT,
  cover_path TEXT, companies TEXT, ids TEXT, title_id TEXT, folder TEXT,
  updated REAL,
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

    # -- games ----------------------------------------------------------
    def upsert_game(self, game: Game, folder: str = "", cover_path: str = "") -> None:
        self._con.execute(
            "INSERT INTO games VALUES(?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(title, platform) DO UPDATE SET year=excluded.year,"
            " genres=excluded.genres, summary=excluded.summary,"
            " cover_path=excluded.cover_path, companies=excluded.companies,"
            " ids=excluded.ids, title_id=excluded.title_id,"
            " folder=excluded.folder, updated=excluded.updated",
            (game.title, game.platform, game.year, json.dumps(game.genres),
             game.summary, cover_path, json.dumps(game.companies),
             json.dumps(game.ids), game.title_id, folder, time.time()))
        self._con.commit()

    def list_games(self) -> list[dict]:
        cur = self._con.execute("SELECT * FROM games ORDER BY title")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    # -- queue ----------------------------------------------------------
    def enqueue(self, item: QueueItem) -> int:
        self._con.execute(
            "INSERT OR IGNORE INTO queue(game_title,url,dest,status,attempts,"
            "bytes_done,total,error) VALUES(?,?,?,?,?,?,?,?)",
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
