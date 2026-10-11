"""Persistent download manager: queue, retry w/ backoff, resume, mirrors.

Design note: Hydra-style UX (queue + multi-mirror fallback), X-Store-derived
semantics (streaming chunks, Content-Length validation, identity encoding).
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

import requests

from .ia_auth import new_session
from .library import Library

ProgressCb = Callable[[int, int | None, str], None]  # done, total, status
CHUNK = 4 * 1024 * 1024


class DownloadManager:
    def __init__(self, library: Library, max_retries: int = 3,
                 on_change: Callable[[], None] | None = None,
                 auth_headers: dict | None = None,
                 cookies: dict | None = None) -> None:
        self.library = library
        self.max_retries = max_retries
        self.on_change = on_change
        self.auth_headers = dict(auth_headers or {})
        self.cookies = dict(cookies or {})
        self._lock = threading.Lock()
        self._cancel: set[int] = set()
        self._pause: set[int] = set()
        self._mirrors: dict[int, list[str]] = {}
        self._worker: threading.Thread | None = None

    # -- queue API ------------------------------------------------------
    def enqueue(self, game_title: str, url: str, dest: str,
                mirrors: list[str] | None = None) -> int:
        from .models import QueueItem

        item_id = self.library.enqueue(QueueItem(game_title, url, dest))
        if mirrors:
            self._mirrors[item_id] = [m for m in mirrors if m != url]
        self._notify()
        self.start()
        return item_id

    def start(self) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._worker = threading.Thread(target=self._loop, daemon=True)
            self._worker.start()

    def cancel(self, item_id: int) -> None:
        self._cancel.add(item_id)
        self.library.update_queue(item_id, status="cancelled")
        self._notify()

    def pause(self, item_id: int) -> None:
        self._pause.add(item_id)
        self.library.update_queue(item_id, status="paused")
        self._notify()

    def resume(self, item_id: int) -> None:
        self._pause.discard(item_id)
        self.library.update_queue(item_id, status="queued")
        self._notify()
        self.start()

    # -- auth ---------------------------------------------------------
    def sync_auth(self, session) -> None:
        """Copy auth (S3 header + cookies) from a metadata session.

        X-Store uses the same IA headers for metadata AND downloads
        (constructIAHeaders); requests Sessions just don't share them.
        Cookies are copied as full morsels: get_dict() would drop the
        cookie domain (.archive.org) and dn*. hosts would 401.
        """
        from requests.cookies import RequestsCookieJar

        if "Authorization" in session.headers:
            self.auth_headers["Authorization"] = session.headers["Authorization"]
        jar: RequestsCookieJar = RequestsCookieJar()
        try:
            for c in session.cookies:
                jar.set_cookie(c)
        except Exception:
            pass
        self.cookies = jar

    def _notify(self) -> None:
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass

    # -- worker ---------------------------------------------------------
    def _loop(self) -> None:
        while True:
            pending = [q for q in self.library.list_queue(active_only=True)
                       if q["status"] == "queued"]
            if not pending:
                break
            item = pending[0]
            self._run(item)
        self._notify()

    def _run(self, item: dict) -> None:
        item_id = item["id"]
        self.library.update_queue(item_id, status="active")
        self._notify()
        uris = [item["url"]] + self._mirrors.get(item_id, [])
        error = ""
        for attempt in range(self.max_retries + 1):
            if item_id in self._cancel:
                return
            for url in uris:
                if item_id in self._cancel or item_id in self._pause:
                    return
                try:
                    self._fetch(item_id, url,
                                lambda d, t, st: self._progress(item_id, d, t))
                    self.library.update_queue(item_id, status="done",
                                              error="")
                    self._notify()
                    return
                except (requests.RequestException, OSError) as e:
                    error = f"{type(e).__name__}: {e}"
            self.library.update_queue(item_id, attempts=attempt + 1,
                                      error=error)
            time.sleep(min(2 ** attempt, 30))
        self.library.update_queue(item_id, status="error", error=error)
        self._notify()

    def _progress(self, item_id: int, done: int, total: int | None) -> None:
        self.library.update_queue(item_id, bytes_done=done,
                                  total=total if total is not None else -1)

    def _fetch(self, item_id: int, url: str, cb: ProgressCb) -> None:
        row = next(q for q in self.library.list_queue()
                   if q["id"] == item_id)
        dest = Path(row["dest"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        done = dest.stat().st_size if dest.exists() else 0
        headers = {"Accept-Encoding": "identity"}
        headers.update(self.auth_headers)
        if done:
            headers["Range"] = f"bytes={done}-"
        s = new_session()
        if self.cookies:
            s.cookies.update(self.cookies)
        with s.get(url, stream=True, headers=headers, timeout=60) as r:
            if r.status_code == 416:  # already complete
                cb(done, done, "done")
                return
            r.raise_for_status()
            total = r.headers.get("Content-Length")
            total = (int(total) + done) if total is not None else None
            mode = "ab" if done and r.status_code == 206 else "wb"
            if mode == "wb":
                done = 0
            with open(dest, mode) as f:
                for chunk in r.iter_content(CHUNK):
                    if item_id in self._cancel or item_id in self._pause:
                        cb(done, total, "paused")
                        return
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    cb(done, total, "active")
        if total is not None and done != total:
            raise OSError(f"size mismatch: got {done}, expected {total}")
        cb(done, total, "done")
