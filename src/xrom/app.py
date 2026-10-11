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
from .ftp_client import test_connection
from .library import Library
from .metadata.igdb import IgdbProvider
from .metadata.thegamesdb import TheGamesDbProvider
from .models import Game
from .sources.archive_org import ArchiveOrgProvider
from .sources.hydra_json import HydraJsonProvider

PLATFORMS = ["xbox", "xbox360", "xbla"]


def _fmt_size(n: int | None) -> str:
    if not n:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


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
        self._thumbs: list = []  # keep PhotoImage refs alive
        self.results: list[Game] = []

        self.root = ctk.CTk()
        self.root.title("XROM 0.1.0 — Xbox ROM Manager")
        self.root.geometry("1000x680")
        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=(8, 2))
        for name in ("Search", "Queue", "Library", "Sources", "Config"):
            self.tabs.add(name)
        self.statusbar = ctk.CTkLabel(self.root, text="Ready.", anchor="w")
        self.statusbar.pack(fill="x", padx=12, pady=(0, 6))
        self._card_widgets: list = []  # (game, subtitle label, dl button)
        self._qrows: dict = {}  # queue id -> widgets (in-place updates)
        self._speed: dict = {}  # queue id -> (timestamp, bytes) for B/s + ETA
        self._searching = False
        self._build_search()
        self._build_queue()
        self._build_library()
        self._build_sources()
        self._build_config()
        self.root.after(1500, self._poll)

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
        self.search_btn = ctk.CTkButton(top, text="Search",
                                        command=self.do_search)
        self.search_btn.pack(side="left", padx=6)
        self.status = ctk.CTkLabel(top, text="")
        self.status.pack(side="left", padx=6)
        self.cards = ctk.CTkScrollableFrame(f)
        self.cards.pack(fill="both", expand=True, padx=6, pady=6)
        ctk.CTkLabel(self.cards,
                     text="Search for a game above — covers, genres and links show up here.").pack(
                         padx=8, pady=20)

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
        if self._searching:
            return
        q = self.q_entry.get().strip()
        if not q:
            return
        plat = self.plat.get()
        self._searching = True
        self.search_btn.configure(state="disabled", text="Searching…")
        self.status.configure(text="Searching...")
        threading.Thread(target=self._search_bg, args=(q, plat),
                         daemon=True).start()

    @staticmethod
    def _subtitle(g: Game) -> str:
        return " | ".join(x for x in
                          [str(g.year or ""),
                           ", ".join(g.genres[:3]),
                           g.platform,
                           f"{len(g.links)} link(s)"] if x)

    def _search_bg(self, q: str, plat: str) -> None:
        from . import linker

        out: list[Game] = []
        for p in self._providers():
            try:
                out.extend(p.search(q, plat))
            except Exception as e:  # keep other providers alive
                out.append(Game(title=f"[{p.name} error: {e}]",
                                platform=plat))
        self.results = out[:60]
        # Render immediately (covers/links fill in progressively).
        self.root.after(0, self._render_results)
        # Links live ON the game: match user's file sources by name.
        try:
            arch = ArchiveOrgProvider(self.session, self.cfg.cache_dir)
            for i, g in enumerate(self.results):
                if g.links or g.title.startswith("["):
                    continue
                self._set_status(f"Linking {i + 1}/{len(self.results)}...")
                linker.attach(g, arch.files_for(g.title, plat or g.platform))
                self.root.after(0, lambda i=i: self._update_card(i))
        except Exception as e:
            self._set_status(f"Link attach failed: {e}")
        finally:
            self.root.after(0, self._search_done)

    def _search_done(self) -> None:
        self._searching = False
        self.search_btn.configure(state="normal", text="Search")

    def _update_card(self, index: int) -> None:
        """Refresh one card after its links arrived (no full rebuild)."""
        if index >= len(self._card_widgets):
            return
        g, sub, dl = self._card_widgets[index]
        sub.configure(text=self._subtitle(g))
        if g.links:
            dl.configure(state="normal")

    def _render_results(self) -> None:
        for w in self.cards.winfo_children():
            w.destroy()
        self._card_widgets = []
        self.status.configure(text=f"{len(self.results)} result(s)")
        if not self.results:
            self.ctk.CTkLabel(self.cards, text="No results.").pack(padx=8,
                                                                   pady=20)
            return
        for g in self.results:
            row = self.ctk.CTkFrame(self.cards)
            row.pack(fill="x", padx=4, pady=4)
            icon = self.ctk.CTkLabel(row, text="🎮",
                                     font=("Segoe UI", 28), width=64,
                                     height=64)
            icon.pack(side="left", padx=8)
            txt = self.ctk.CTkFrame(row, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True)
            self.ctk.CTkLabel(txt, text=g.title,
                              font=("Segoe UI", 14, "bold"),
                              anchor="w").pack(fill="x")
            sub = self.ctk.CTkLabel(txt, text=self._subtitle(g), anchor="w")
            sub.pack(fill="x")
            self.ctk.CTkButton(row, text="🔗 Links", width=80,
                               command=lambda g=g: self.open_game_dialog(g)).pack(
                                   side="right", padx=2)
            dl = self.ctk.CTkButton(row, text="Download", width=90,
                                    command=lambda g=g: self.do_download(g))
            if not g.links:
                dl.configure(state="disabled")
            dl.pack(side="right", padx=2)
            self.ctk.CTkButton(row, text="+ Library", width=90,
                               command=lambda g=g: self.add_library(g)).pack(
                                   side="right", padx=2)
            self._card_widgets.append((g, sub, dl))
            row.bind("<Button-1>",
                     lambda _e, g=g: self.open_game_dialog(g))
            threading.Thread(target=self._cover_bg, args=(g, icon),
                             daemon=True).start()

    def _cover_bg(self, g: Game, icon) -> None:
        """Missing art is normal — keep the placeholder, move on."""
        try:
            p = art_cache.cached_art(g.cover_url, self.cfg.art_dir)
            if not p:
                return
            from PIL import Image

            img = Image.open(p)
            img.thumbnail((64, 64))
            photo = self.ctk.CTkImage(light_image=img, dark_image=img,
                                      size=(64, 64))
            self._thumbs.append(photo)
            self.root.after(0, lambda: icon.configure(image=photo, text=""))
        except Exception:
            pass

    def do_download(self, g: Game) -> None:
        if not g.links:
            return
        d = g.links[0]
        dest = str(Path(self.cfg.downloads_dir or self.cfg.home / "downloads")
                   / (d.extra.get("filename") or d.title))
        self.dm.enqueue(g.title, d.uris[0], dest, mirrors=d.uris[1:])
        self._set_status(f"Queued: {d.title} ({len(g.links)} link(s) on game)")
        self.tabs.set("Queue")

    def _set_status(self, msg: str) -> None:
        def _apply() -> None:
            self.statusbar.configure(text=msg or "Ready.")
            try:
                self.status.configure(text=msg)
            except Exception:
                pass

        self.root.after(0, _apply)

    # -- tracked jobs (bar + % + log + cancel, never blocks UI) ------------
    def run_tracked(self, title: str, worker) -> None:
        """Run worker(prog, log, is_cancelled)->str in a thread with a dialog.

        prog(frac|None, text): None = indeterminate spinner.
        """
        ctk = self.ctk
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(title)
        dlg.geometry("540x360")
        bar = ctk.CTkProgressBar(dlg, width=480)
        bar.pack(padx=20, pady=(14, 4))
        bar.set(0.0)
        lab = ctk.CTkLabel(dlg, text="Starting…", anchor="w")
        lab.pack(padx=20, fill="x")
        logbox = ctk.CTkTextbox(dlg, height=170)
        logbox.pack(padx=20, pady=6, fill="both", expand=True)
        logbox.configure(state="disabled")
        cancelled = threading.Event()
        ctk.CTkButton(dlg, text="Cancel",
                      command=cancelled.set).pack(pady=(0, 12))

        def prog(frac, text: str = "") -> None:
            def _u() -> None:
                try:
                    if frac is None:
                        bar.configure(mode="indeterminate")
                        bar.start()
                    else:
                        bar.stop()
                        bar.configure(mode="determinate")
                        bar.set(max(0.0, min(1.0, frac)))
                    if text:
                        lab.configure(text=text)
                except Exception:
                    pass

            self.root.after(0, _u)

        def log(msg: str) -> None:
            def _u() -> None:
                try:
                    logbox.configure(state="normal")
                    logbox.insert("end", (msg or "")[-500:] + "\n")
                    logbox.see("end")
                    logbox.configure(state="disabled")
                except Exception:
                    pass

            self.root.after(0, _u)

        def bg() -> None:
            try:
                result = worker(prog, log, cancelled.is_set)
            except Exception as e:
                log(f"{type(e).__name__}: {e}")
                err = e
                self.root.after(
                    0, lambda _e=err: (bar.stop(),
                                       lab.configure(text=f"Failed: {_e}")))
                self._set_status(f"{title} failed: {err}")
                return
            self.root.after(
                0, lambda: (bar.stop(), bar.configure(mode="determinate"),
                            bar.set(1.0), lab.configure(text=result)))
            self._set_status(result)

        threading.Thread(target=bg, daemon=True).start()

    # -- game dialog (Hydra-style: pick a link or link a local ROM) ------
    def open_game_dialog(self, g: Game) -> None:
        ctk = self.ctk
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(g.title)
        dlg.geometry("620x480")
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=g.title,
                     font=("Segoe UI", 16, "bold")).pack(padx=10, pady=(10, 2),
                                                         anchor="w")
        info = " | ".join(x for x in [str(g.year or ""),
                                      ", ".join(g.genres[:4]),
                                      g.platform] if x)
        ctk.CTkLabel(dlg, text=info).pack(padx=10, anchor="w")
        if g.summary:
            box = ctk.CTkTextbox(dlg, height=90)
            box.pack(padx=10, pady=6, fill="x")
            box.insert("1.0", g.summary[:800])
            box.configure(state="disabled")

        ctk.CTkLabel(dlg, text="Download links on this game:").pack(
            padx=10, pady=(6, 2), anchor="w")
        choice = ctk.IntVar(value=0)
        links_frame = ctk.CTkScrollableFrame(dlg, height=140)
        links_frame.pack(padx=10, fill="x")
        if g.links:
            for i, d in enumerate(g.links):
                ctk.CTkRadioButton(
                    links_frame, variable=choice, value=i,
                    text=f"{d.title}  [{_fmt_size(d.file_size)}]  ({d.source})"
                ).pack(anchor="w", padx=6, pady=2)
        else:
            ctk.CTkLabel(links_frame,
                         text="No links — link a local ROM below.").pack(
                             padx=6, pady=6)

        ctk.CTkLabel(dlg, text="Or link a local ROM (iso/zip/7z/...):").pack(
            padx=10, pady=(6, 2), anchor="w")
        local_row = ctk.CTkFrame(dlg, fg_color="transparent")
        local_row.pack(padx=10, fill="x")
        local_entry = ctk.CTkEntry(local_row, width=380,
                                   placeholder_text="C:\\...\\game.iso")
        local_entry.pack(side="left", padx=(0, 6))

        def browse() -> None:
            from tkinter import filedialog

            path = filedialog.askopenfilename(
                title=f"Link local ROM — {g.title}",
                filetypes=[("Disc/archive images",
                            "*.iso *.zip *.7z *.rar *.001"),
                           ("All files", "*.*")])
            if path:
                local_entry.delete(0, "end")
                local_entry.insert(0, path)

        ctk.CTkButton(local_row, text="Browse...",
                      command=browse).pack(side="left")

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack(padx=10, pady=10, fill="x")

        def download_selected() -> None:
            if g.links:
                self.do_download_index(g, choice.get())
                dlg.destroy()

        def link_local() -> None:
            path = local_entry.get().strip()
            if not path:
                return
            cover = art_cache.cached_art(g.cover_url, self.cfg.art_dir)
            organizer.organize(
                g, self.cfg.library_dir or self.cfg.home / "library",
                str(cover) if cover else "", local_path=path)
            self.lib.upsert_game(g, folder=str(Path(path).parent),
                                 cover_path=str(cover) if cover else "")
            self._set_status(f"Linked local ROM: {path}")
            self.refresh_library()
            dlg.destroy()

        if g.links:
            ctk.CTkButton(btns, text="Download selected",
                          command=download_selected).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Link local file",
                      command=link_local).pack(side="left", padx=4)

    def do_download_index(self, g: Game, index: int) -> None:
        if not g.links or index >= len(g.links):
            return
        d = g.links[index]
        dest = str(Path(self.cfg.downloads_dir or self.cfg.home / "downloads")
                   / (d.extra.get("filename") or d.title))
        self.dm.enqueue(g.title, d.uris[0], dest, mirrors=d.uris[1:])
        self._set_status(f"Queued: {d.title}")
        self.tabs.set("Queue")

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
            try:
                if self.tabs.get() == "Queue":
                    self.refresh_queue()
            except Exception:
                pass
        self.root.after(1500, self._poll)

    def _thumb(self, path: str, size: tuple[int, int] = (48, 48)):
        """Local cover -> CTkImage, or None (caller keeps placeholder)."""
        try:
            if not path:
                return None
            from PIL import Image

            img = Image.open(path)
            img.thumbnail((size[0] * 2, size[1] * 2))
            photo = self.ctk.CTkImage(light_image=img, dark_image=img,
                                      size=size)
            self._thumbs.append(photo)
            return photo
        except Exception:
            return None

    def refresh_queue(self) -> None:
        """Reconcile rows in place: no flicker, progress bars keep flowing."""
        items = {q["id"]: q for q in self.lib.list_queue()}
        for qid in list(self._qrows):
            if qid not in items:
                self._qrows.pop(qid)["frame"].destroy()
        if not items and not self._qrows:
            if not getattr(self, "_qempty", None):
                self._qempty = self.ctk.CTkLabel(
                    self.qlist, text="Queue empty — download something from Search.")
                self._qempty.pack(padx=8, pady=20)
        elif getattr(self, "_qempty", None):
            self._qempty.destroy()
            self._qempty = None
        for qid, q in items.items():
            import time as _time

            total = q["total"] or 0
            now, done = _time.time(), q["bytes_done"]
            prev = self._speed.get(qid)
            rate_txt, eta_txt = "", ""
            if prev and q["status"] == "active" and now > prev[0]:
                rate = max(0.0, (done - prev[1]) / (now - prev[0]))
                if rate > 0:
                    rate_txt = f" — {_fmt_size(int(rate))}/s"
                    if total and total > 0 and done < total:
                        eta = int((total - done) / rate)
                        eta_txt = f" — ETA {eta // 60}m {eta % 60:02d}s"
            self._speed[qid] = (now, done)
            if total and total > 0:
                frac = min(1.0, done / total)
                pct = f"{100 * frac:.1f}%"
            else:
                # Unknown size: pulse while active so it looks alive.
                frac = (now * 0.6) % 1.0 if q["status"] == "active" else 0.0
                pct = f"{done // 1024} KiB"
            if qid not in self._qrows:
                row = self.ctk.CTkFrame(self.qlist)
                row.pack(fill="x", padx=4, pady=3)
                left = self.ctk.CTkFrame(row, fg_color="transparent")
                left.pack(side="left", fill="x", expand=True, padx=8)
                title = self.ctk.CTkLabel(left, text="", anchor="w")
                title.pack(fill="x")
                bar = self.ctk.CTkProgressBar(left, width=300)
                bar.pack(fill="x", pady=(2, 0))
                bar.set(0.0)
                err = self.ctk.CTkLabel(left, text="", anchor="w",
                                        text_color="orange")
                err.pack(fill="x")
                plat = self.ctk.CTkOptionMenu(row, values=PLATFORMS, width=100)
                plat.set(self._row_platform.get(qid, "xbox360"))
                plat.configure(
                    command=lambda v, i=qid: self._row_platform.__setitem__(i, v))
                plat.pack(side="right", padx=2)
                for emoji, fn in (
                        ("🗑", lambda i=qid: self.delete_queue_item(i)),
                        ("▶", lambda i=qid: self.dm.resume(i)),
                        ("⏸", lambda i=qid: self.dm.pause(i)),
                        ("📦", lambda i=qid: self.do_extract(i))):
                    self.ctk.CTkButton(row, text=emoji, width=36,
                                       command=fn).pack(side="right", padx=1)
                self._qrows[qid] = {"frame": row, "title": title,
                                    "bar": bar, "err": err}
            w = self._qrows[qid]
            w["title"].configure(
                text=f"[{q['status']}] {q['game_title']} — {pct}{rate_txt}{eta_txt}")
            w["bar"].set(frac)
            w["err"].configure(text=(q["error"] or "")[:100])

    def delete_queue_item(self, item_id: int) -> None:
        self.dm.cancel(item_id)
        self.lib.remove_queue(item_id)
        self.refresh_queue()

    def do_extract(self, item_id: int) -> None:
        rows = [q for q in self.lib.list_queue() if q["id"] == item_id]
        if not rows:
            return
        row = rows[0]
        plat = self._row_platform.get(item_id, "xbox360")

        def worker(prog, log, _cancelled) -> str:
            from . import extractor
            from .tools_fetch import TOOLS

            if self.cfg.extract_xiso_exe:
                import shutil

                self.cfg.bin_dir.mkdir(parents=True, exist_ok=True)
                target = self.cfg.bin_dir / TOOLS["extract-xiso"]["exe"]
                if not target.exists():
                    shutil.copy2(self.cfg.extract_xiso_exe, target)
            prog(None, "Starting extraction…")

            def _prog(done: int, total: int) -> None:
                prog(done / total if total else None,
                     f"Unpacking {done}/{total}…")

            out = extractor.extract_download(
                row["dest"], plat,
                self.cfg.library_dir or self.cfg.home / "library",
                self.cfg.bin_dir, self.cfg.iso2god_exe, log, _prog)
            self.root.after(0, self.refresh_library)
            return f"Extracted → {out}"

        self.run_tracked(f"Extract — {row['game_title']}", worker)

    def _extract_bg(self, row: dict, platform: str) -> None:
        """Legacy direct entry (kept for API compat); prefer do_extract."""
        self.do_extract(row["id"])

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
        games = self.lib.list_games()
        if not games:
            self.ctk.CTkLabel(
                self.glist,
                text="Library empty — search a game and + Library it.").pack(
                    padx=8, pady=20)
            return
        for g in games:
            row = self.ctk.CTkFrame(self.glist)
            row.pack(fill="x", padx=4, pady=3)
            icon = self.ctk.CTkLabel(row, text="🎮",
                                     font=("Segoe UI", 22), width=56)
            icon.pack(side="left", padx=6)
            photo = self._thumb(g["cover_path"] or "", (48, 48))
            if photo is not None:
                icon.configure(image=photo, text="")
            txt = self.ctk.CTkFrame(row, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True)
            self.ctk.CTkLabel(
                txt, text=f"{g['title']} [{g['platform']}] {g['year'] or ''}",
                font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x")
            self.ctk.CTkLabel(txt, text=g["folder"] or "",
                              anchor="w").pack(fill="x")
            self.ctk.CTkButton(
                row, text="🗑", width=36,
                command=lambda t=g["title"], p=g["platform"]: self.delete_game(t, p)
            ).pack(side="right", padx=4)

    def delete_game(self, title: str, platform: str) -> None:
        """Removes the library ENTRY (files on disk are kept)."""
        self.lib.remove_game(title, platform)
        self._set_status(f"Removed from library: {title} (files kept)")
        self.refresh_library()

    def ftp_send_first(self) -> None:
        games = self.lib.list_games()
        if not games or not games[0]["folder"]:
            self._set_status("Library empty — nothing to send.")
            return
        folder = Path(games[0]["folder"])
        title = games[0]["title"]
        f = self.cfg.ftp
        host, port, user, password = f.host, f.port, f.user, f.password

        def worker(prog, log, is_cancelled) -> str:
            from .ftp_client import TransferAborted, upload_tree

            prog(None, f"Connecting to {host}…")
            ok, msg = test_connection(host, port, user, password)
            if not ok:
                raise RuntimeError(msg)
            log(f"Connected: {msg[:80]}")
            files = [p for p in sorted(folder.rglob("*")) if p.is_file()]
            total_bytes = sum(p.stat().st_size for p in files)
            seen: dict[str, int] = {}

            def _cb(path: str, done: int, _total) -> None:
                seen[path] = done
                frac = sum(seen.values()) / total_bytes if total_bytes else 0
                prog(frac, f"{Path(path).name} — {100 * frac:.1f}% "
                           f"({_fmt_size(sum(seen.values()))} / "
                           f"{_fmt_size(total_bytes)})")

            try:
                n = upload_tree(folder, f.remote_dir, host, port, user,
                                password, f.passive, _cb, is_cancelled)
            except TransferAborted:
                return "FTP cancelled."
            log(f"Sent {n} file(s) to {f.remote_dir}.")
            if self.cfg.delete_after_ftp:
                import shutil

                shutil.rmtree(folder, ignore_errors=True)
                self.root.after(0, self.refresh_library)
                return f"FTP: {n} file(s) sent, local copy deleted."
            return f"FTP: {n} file(s) sent."

        self.run_tracked(f"FTP — {title}", worker)

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
        self.dm.sync_auth(self.session)
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
        self.dm.sync_auth(self.session)
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
                        self.dm.sync_auth(self.session)
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
