"""CustomTkinter GUI: Search / Queue / Library / Sources / Config+FTP.

All network runs in daemon threads; GUI polls via `after`. Covers lazy-load
from art_cache. No credentials or links ship with the app (Hydra-style).
"""
from __future__ import annotations

import threading
from pathlib import Path

from . import art_cache, ia_auth, organizer
from .config import XromConfig, get_ia_password, set_ia_password
from .downloader import DownloadManager
from .ftp_client import test_connection, upload_tree
from .library import Library
from .metadata.igdb import IgdbProvider
from .metadata.thegamesdb import TheGamesDbProvider
from .models import Game
from .sources.archive_org import ArchiveOrgProvider
from .sources.hydra_json import HydraJsonProvider

PLATFORMS = ["xbox", "xbox360", "xbla"]


class App:
    def __init__(self) -> None:
        import customtkinter as ctk

        self.ctk = ctk
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        self.cfg = XromConfig.load()
        self.cfg.ensure_dirs()
        self.lib = Library(self.cfg.db_path)
        self.session = ia_auth.new_session()
        self._session_secret = ""  # S3 secret: memory only, never saved
        self.dm = DownloadManager(self.lib, self.cfg.max_retries,
                                  on_change=self._dirty_queue)
        self._queue_dirty = False
        self._row_platform: dict[int, str] = {}
        self.results: list[Game] = []

        self.root = ctk.CTk()
        self.root.title("XROM 0.1.0 — Xbox ROM Manager")
        self.root.geometry("1000x680")
        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        for name in ("Search", "Queue", "Library", "Sources", "Config"):
            self.tabs.add(name)
        self._build_search()
        self._build_queue()
        self._build_library()
        self._build_sources()
        self._build_config()
        self.root.after(1000, self._poll)

    # -- search ---------------------------------------------------------
    def _build_search(self) -> None:
        ctk = self.ctk
        f = self.tabs.tab("Search")
        top = ctk.CTkFrame(f)
        top.pack(fill="x", padx=6, pady=6)
        self.q_entry = ctk.CTkEntry(top, placeholder_text="Game title...",
                                    width=380)
        self.q_entry.pack(side="left", padx=6)
        self.q_entry.bind("<Return>", lambda _e: self.do_search())
        self.plat = ctk.CTkOptionMenu(top, values=PLATFORMS)
        self.plat.pack(side="left", padx=6)
        ctk.CTkButton(top, text="Search metadata",
                      command=self.do_search).pack(side="left", padx=6)
        self.status = ctk.CTkLabel(top, text="")
        self.status.pack(side="left", padx=6)
        self.cards = ctk.CTkScrollableFrame(f)
        self.cards.pack(fill="both", expand=True, padx=6, pady=6)

    def _providers(self):
        provs = []
        if self.cfg.igdb_client_id and self.cfg.igdb_client_secret:
            provs.append(IgdbProvider(self.cfg.igdb_client_id,
                                      self.cfg.igdb_client_secret))
        if self.cfg.tgdb_api_key:
            provs.append(TheGamesDbProvider(self.cfg.tgdb_api_key))
        if not provs:
            provs.append(ArchiveOrgProvider(self.session, self.cfg.cache_dir))
        return provs

    def do_search(self) -> None:
        q = self.q_entry.get().strip()
        if not q:
            return
        plat = self.plat.get()
        self.status.configure(text="Searching...")
        threading.Thread(target=self._search_bg, args=(q, plat),
                         daemon=True).start()

    def _search_bg(self, q: str, plat: str) -> None:
        out: list[Game] = []
        for p in self._providers():
            try:
                out.extend(p.search(q, plat))
            except Exception as e:  # keep other providers alive
                out.append(Game(title=f"[{p.name} error: {e}]",
                                platform=plat))
        self.results = out[:60]
        self.root.after(0, self._render_results)

    def _render_results(self) -> None:
        for w in self.cards.winfo_children():
            w.destroy()
        self.status.configure(text=f"{len(self.results)} result(s)")
        for g in self.results:
            row = self.ctk.CTkFrame(self.cards)
            row.pack(fill="x", padx=4, pady=4)
            subtitle = " | ".join(x for x in
                                  [str(g.year or ""),
                                   ", ".join(g.genres[:3]),
                                   g.platform] if x)
            self.ctk.CTkLabel(row, text=g.title,
                              font=("Segoe UI", 14, "bold")).pack(
                                  side="left", padx=8)
            self.ctk.CTkLabel(row, text=subtitle).pack(side="left", padx=8)
            self.ctk.CTkButton(row, text="Resolve",
                               command=lambda g=g: self.do_resolve(g)).pack(
                                   side="right", padx=4)
            self.ctk.CTkButton(row, text="+ Library",
                               command=lambda g=g: self.add_library(g)).pack(
                                   side="right", padx=4)
            threading.Thread(target=self._cover_bg, args=(g,),
                             daemon=True).start()

    def _cover_bg(self, g: Game) -> None:
        art_cache.cached_art(g.cover_url, self.cfg.art_dir)

    def do_resolve(self, g: Game) -> None:
        self.status.configure(text=f"Resolving {g.title} on archive.org...")
        threading.Thread(target=self._resolve_bg, args=(g,),
                         daemon=True).start()

    def _resolve_bg(self, g: Game) -> None:
        try:
            files = ArchiveOrgProvider(self.session,
                                       self.cfg.cache_dir).resolve(g)
        except Exception as e:
            self._set_status(f"Resolve failed: {e}")
            return
        if not files:
            self._set_status("No ZIP/7Z found on archive.org for this title.")
            return
        f = files[0]
        dest = str(Path(self.cfg.downloads_dir or self.cfg.home / "downloads")
                   / (f.extra.get("filename") or f.title))
        self.dm.enqueue(g.title, f.uris[0], dest, mirrors=f.uris[1:])
        self._set_status(f"Queued: {f.title}")
        self.tabs.set("Queue")

    def _set_status(self, msg: str) -> None:
        self.root.after(0, lambda: self.status.configure(text=msg))

    def add_library(self, g: Game) -> None:
        cover = art_cache.cached_art(g.cover_url, self.cfg.art_dir)
        folder = organizer.organize(
            g, self.cfg.library_dir or self.cfg.home / "library",
            str(cover) if cover else "")
        self.lib.upsert_game(g, folder=str(folder),
                             cover_path=str(cover) if cover else "")
        self._set_status(f"Organized: {folder}")
        self.refresh_library()

    # -- queue ----------------------------------------------------------
    def _build_queue(self) -> None:
        ctk = self.ctk
        f = self.tabs.tab("Queue")
        bar = ctk.CTkFrame(f)
        bar.pack(fill="x", padx=6, pady=6)
        ctk.CTkButton(bar, text="Refresh",
                      command=self.refresh_queue).pack(side="left", padx=4)
        self.qlist = ctk.CTkScrollableFrame(f)
        self.qlist.pack(fill="both", expand=True, padx=6, pady=6)

    def _dirty_queue(self) -> None:
        self._queue_dirty = True

    def _poll(self) -> None:
        if self._queue_dirty:
            self._queue_dirty = False
            self.refresh_queue()
        self.root.after(1000, self._poll)

    def refresh_queue(self) -> None:
        for w in self.qlist.winfo_children():
            w.destroy()
        for q in self.lib.list_queue():
            total = q["total"] or 0
            pct = f"{100 * q['bytes_done'] / total:.1f}%" if total and total > 0 else f"{q['bytes_done'] // 1024} KiB"
            row = self.ctk.CTkFrame(self.qlist)
            row.pack(fill="x", padx=4, pady=3)
            self.ctk.CTkLabel(
                row, text=f"[{q['status']}] {q['game_title']} — {pct}").pack(
                    side="left", padx=8)
            if q["error"]:
                self.ctk.CTkLabel(row, text=q["error"][:80],
                                  text_color="orange").pack(side="left")
            plat = self.ctk.CTkOptionMenu(row, values=PLATFORMS, width=100)
            plat.set(self._row_platform.get(q["id"], "xbox360"))
            plat.configure(command=lambda v, i=q["id"]: self._row_platform.__setitem__(i, v))
            plat.pack(side="right", padx=2)
            for label, fn in (
                    ("Extract", lambda i=q["id"]: self.do_extract(i)),
                    ("Pause", lambda i=q["id"]: self.dm.pause(i)),
                    ("Resume", lambda i=q["id"]: self.dm.resume(i)),
                    ("Cancel", lambda i=q["id"]: self.dm.cancel(i))):
                self.ctk.CTkButton(row, text=label, width=70,
                                   command=fn).pack(side="right", padx=2)

    def do_extract(self, item_id: int) -> None:
        rows = [q for q in self.lib.list_queue() if q["id"] == item_id]
        if not rows:
            return
        plat = self._row_platform.get(item_id, "xbox360")
        threading.Thread(target=self._extract_bg,
                         args=(rows[0], plat), daemon=True).start()

    def _extract_bg(self, row: dict, platform: str) -> None:
        from . import extractor
        from .tools_fetch import TOOLS

        # Honor explicit tool paths from Config (local only, never bundled).
        if self.cfg.extract_xiso_exe:
            import shutil

            self.cfg.bin_dir.mkdir(parents=True, exist_ok=True)
            target = self.cfg.bin_dir / TOOLS["extract-xiso"]["exe"]
            if not target.exists():
                try:
                    shutil.copy2(self.cfg.extract_xiso_exe, target)
                except OSError as e:
                    self._set_status(f"Tool copy failed: {e}")
                    return

        def log(msg: str) -> None:
            self._set_status(msg.splitlines()[-1][:120] if msg else "")

        try:
            out = extractor.extract_download(
                row["dest"], platform,
                self.cfg.library_dir or self.cfg.home / "library",
                self.cfg.bin_dir, self.cfg.iso2god_exe, log)
        except Exception as e:
            self._set_status(f"Extract failed: {e}")
            return
        self._set_status(f"Extracted → {out}")
        self.refresh_library()

    # -- library --------------------------------------------------------
    def _build_library(self) -> None:
        ctk = self.ctk
        f = self.tabs.tab("Library")
        bar = ctk.CTkFrame(f)
        bar.pack(fill="x", padx=6, pady=6)
        ctk.CTkButton(bar, text="Refresh",
                      command=self.refresh_library).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Send selected via FTP",
                      command=self.ftp_send_first).pack(side="left", padx=4)
        self.glist = ctk.CTkScrollableFrame(f)
        self.glist.pack(fill="both", expand=True, padx=6, pady=6)
        self.refresh_library()

    def refresh_library(self) -> None:
        if not hasattr(self, "glist"):
            return
        for w in self.glist.winfo_children():
            w.destroy()
        for g in self.lib.list_games():
            row = self.ctk.CTkFrame(self.glist)
            row.pack(fill="x", padx=4, pady=3)
            self.ctk.CTkLabel(
                row, text=f"{g['title']} [{g['platform']}] {g['year'] or ''}").pack(
                    side="left", padx=8)
            self.ctk.CTkLabel(row, text=g["folder"] or "").pack(side="left")

    def ftp_send_first(self) -> None:
        games = self.lib.list_games()
        if not games or not games[0]["folder"]:
            return
        f = self.cfg.ftp
        ok, msg = test_connection(f.host, f.port, f.user, f.password)
        if not ok:
            self._set_status(f"FTP failed: {msg}")
            self.tabs.set("Config")
            return
        try:
            n = upload_tree(games[0]["folder"], f.remote_dir, f.host, f.port,
                            f.user, f.password, f.passive)
        except Exception as e:
            self._set_status(f"FTP upload failed: {e}")
            return
        self._set_status(f"FTP: {n} file(s) sent.")
        if self.cfg.delete_after_ftp:
            import shutil

            shutil.rmtree(games[0]["folder"], ignore_errors=True)
            self.refresh_library()

    # -- sources --------------------------------------------------------
    def _build_sources(self) -> None:
        ctk = self.ctk
        f = self.tabs.tab("Sources")
        ctk.CTkLabel(f, text="archive.org: uses YOUR account from Config tab.").pack(
            padx=8, pady=4, anchor="w")
        row = ctk.CTkFrame(f)
        row.pack(fill="x", padx=6, pady=6)
        self.hydra_entry = ctk.CTkEntry(row, placeholder_text="Hydra JSON path...",
                                        width=420)
        self.hydra_entry.pack(side="left", padx=6)
        ctk.CTkButton(row, text="Search file",
                      command=self.hydra_search).pack(side="left", padx=6)
        self.hydra_box = ctk.CTkScrollableFrame(f)
        self.hydra_box.pack(fill="both", expand=True, padx=6, pady=6)

    def hydra_search(self) -> None:
        q = self.q_entry.get().strip()
        path = self.hydra_entry.get().strip()
        if not path:
            return
        try:
            prov = HydraJsonProvider(path)
            games = prov.search(q, self.plat.get())
        except Exception as e:
            self._set_status(f"Hydra JSON error: {e}")
            return
        for w in self.hydra_box.winfo_children():
            w.destroy()
        for g in games:
            row = self.ctk.CTkFrame(self.hydra_box)
            row.pack(fill="x", padx=4, pady=3)
            self.ctk.CTkLabel(row, text=g.title).pack(side="left", padx=8)
            for dl in prov.resolve(g):
                self.ctk.CTkButton(
                    row, text=f"Queue ({dl.file_size or '?'} B)",
                    command=lambda g=g, dl=dl: self.dm.enqueue(
                        g.title, dl.uris[0],
                        str(Path(self.cfg.downloads_dir or self.cfg.home / "downloads") / dl.title),
                        mirrors=dl.uris[1:])).pack(side="right", padx=4)
        self._set_status(f"{len(games)} match(es) in {prov.source_name}")

    # -- config ---------------------------------------------------------
    def _build_config(self) -> None:
        ctk = self.ctk
        f = self.tabs.tab("Config")
        self.entries: dict[str, ctk.CTkEntry] = {}

        def row(label: str, key: str, secret: bool = False,
                default: str = "") -> None:
            r = ctk.CTkFrame(f)
            r.pack(fill="x", padx=6, pady=3)
            ctk.CTkLabel(r, text=label, width=180).pack(side="left", padx=6)
            e = ctk.CTkEntry(r, width=380, show="*" if secret else "")
            e.insert(0, default)
            e.pack(side="left", padx=6)
            self.entries[key] = e

        c = self.cfg
        row("archive.org email", "ia_email", default=c.ia_email)
        row("archive.org password", "ia_password", secret=True,
            default=get_ia_password(c.ia_email))
        row("IA S3 access", "ia_s3_access", default=c.ia_s3_access)
        row("IA S3 secret", "ia_s3_secret", secret=True,
            default=c.ia_s3_secret)
        row("IGDB client id", "igdb_client_id", default=c.igdb_client_id)
        row("IGDB client secret", "igdb_client_secret", secret=True,
            default=c.igdb_client_secret)
        row("TheGamesDB key", "tgdb_api_key", default=c.tgdb_api_key)
        row("Library dir", "library_dir",
            default=c.library_dir or str(c.home / "library"))
        row("Downloads dir", "downloads_dir",
            default=c.downloads_dir or str(c.home / "downloads"))
        row("FTP host", "ftp_host", default=c.ftp.host)
        row("FTP user", "ftp_user", default=c.ftp.user)
        row("FTP password", "ftp_password", secret=True,
            default=c.ftp.password)
        row("FTP remote dir", "ftp_remote", default=c.ftp.remote_dir)
        row("X-Store keys file (local only)", "xstore_keys_file",
            default=c.xstore_keys_file)
        row("extract-xiso exe (optional)", "extract_xiso_exe",
            default=c.extract_xiso_exe)
        row("Iso2God exe (optional)", "iso2god_exe",
            default=c.iso2god_exe)
        self.del_ftp = ctk.CTkCheckBox(f, text="Delete local copy after FTP OK")
        if c.delete_after_ftp:
            self.del_ftp.select()
        self.del_ftp.pack(padx=8, pady=4, anchor="w")
        btns = ctk.CTkFrame(f)
        btns.pack(fill="x", padx=6, pady=6)
        ctk.CTkButton(btns, text="Save",
                      command=self.save_config).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Test archive.org login",
                      command=self.test_ia).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Test FTP",
                      command=self.test_ftp).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Import X-Store keys",
                      command=self.import_keys).pack(side="left", padx=4)
        self.cfg_status = ctk.CTkLabel(f, text="")
        self.cfg_status.pack(padx=8, anchor="w")

    def import_keys(self) -> None:
        """Local-only: read X-Store ArchiveOrgKeys.txt into this session.

        The file stays where it is; only the keys enter memory + local
        config (~/.xrom, never the repo). Mirrors X-Store S3 auth.
        """
        path = self.entries["xstore_keys_file"].get().strip()
        if not path:
            self.cfg_status.configure(text="Set the keys file path first.")
            return
        try:
            access, secret = ia_auth.import_xstore_keys(path)
        except (OSError, ValueError) as e:
            self.cfg_status.configure(text=f"Keys import failed: {e}")
            return
        self.cfg.xstore_keys_file = path
        self.cfg.ia_s3_access = access
        self.cfg.ia_s3_secret = ""  # secret stays in memory only
        self.entries["ia_s3_access"].delete(0, "end")
        self.entries["ia_s3_access"].insert(0, access)
        self.entries["ia_s3_secret"].delete(0, "end")
        ia_auth.apply_s3(self.session, access, secret)
        self._session_secret = secret
        self.cfg_status.configure(text="Keys imported (local session only).")

    def save_config(self) -> None:
        e = self.entries
        c = self.cfg
        c.ia_email = e["ia_email"].get().strip()
        pw = e["ia_password"].get()
        if pw:
            set_ia_password(c.ia_email, pw)
        c.ia_s3_access = e["ia_s3_access"].get().strip()
        c.ia_s3_secret = e["ia_s3_secret"].get().strip()
        c.igdb_client_id = e["igdb_client_id"].get().strip()
        c.igdb_client_secret = e["igdb_client_secret"].get().strip()
        c.tgdb_api_key = e["tgdb_api_key"].get().strip()
        c.library_dir = e["library_dir"].get().strip()
        c.downloads_dir = e["downloads_dir"].get().strip()
        c.ftp.host = e["ftp_host"].get().strip()
        c.ftp.user = e["ftp_user"].get().strip()
        c.ftp.password = e["ftp_password"].get()
        c.ftp.remote_dir = e["ftp_remote"].get().strip()
        c.delete_after_ftp = bool(self.del_ftp.get())
        c.xstore_keys_file = e["xstore_keys_file"].get().strip()
        c.extract_xiso_exe = e["extract_xiso_exe"].get().strip()
        c.iso2god_exe = e["iso2god_exe"].get().strip()
        c.save()
        if c.ia_s3_access and c.ia_s3_secret:
            ia_auth.apply_s3(self.session, c.ia_s3_access, c.ia_s3_secret)
        self.cfg_status.configure(text="Saved.")

    def test_ia(self) -> None:
        self.save_config()
        pw = get_ia_password(self.cfg.ia_email)

        def bg() -> None:
            try:
                if self.cfg.ia_s3_access:
                    ok, msg = True, "S3 keys set."
                elif self.cfg.ia_email and pw:
                    s = ia_auth.new_session()
                    ok = ia_auth.login(s, self.cfg.ia_email, pw)
                    msg = "Login OK." if ok else "Login failed."
                    if ok:
                        self.session = s
                else:
                    ok, msg = False, "Fill email+password or S3 keys."
            except Exception as ex:
                ok, msg = False, str(ex)
            self.root.after(0, lambda: self.cfg_status.configure(text=msg))

        threading.Thread(target=bg, daemon=True).start()

    def test_ftp(self) -> None:
        self.save_config()
        f = self.cfg.ftp

        def bg() -> None:
            ok, msg = test_connection(f.host, f.port, f.user, f.password)
            self.root.after(
                0, lambda: self.cfg_status.configure(
                    text=f"FTP: {'OK — ' + msg[:60] if ok else msg}"))

        threading.Thread(target=bg, daemon=True).start()

    def run(self) -> None:
        self.dm.start()
        self.root.mainloop()


def main() -> None:
    App().run()
