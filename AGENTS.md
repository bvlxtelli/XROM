# AGENTS.md — XROM contributor guide

## Idea

XROM is an **Xbox ROM download manager and organizer for PC**
(Original Xbox, Xbox 360, XBLA), in the spirit of
[Hydra Launcher](https://github.com/hydralauncher/hydra):
the app ships **no games, no links, no accounts, no keys**.
The user brings their own archive.org account and Hydra-JSON source files;
XROM manages search, queue, extraction, library and FTP sending.

## Source of truth

**Metadata (the Game record) is the source of truth — never archive.org.**
Users see games + covers; download links live **ON the game**
(`Game.links: list[Downloadable]`), matched by normalized name
(`linker.normalize`: lowercase, strip extensions/`(tags)`, ASCII-fold).
File sources are never browsed directly — they only *attach* links.

## Architecture (front != back, in progress)

- `src/xrom/` — backend, UI-agnostic (must never import customtkinter):
  - `models.py` — `Game` (with `links`), `Downloadable`, `QueueItem`
  - `linker.py` — normalize/score/attach links by name
  - `ia_auth.py` — archive.org CSRF login + S3 header (ported X-Store `ia.cpp`)
  - `ia_catalog.py` — collection IDs verbatim from X-Store `ui.h`
    (34 Xbox + 37 X360 + 18 XBLA/DLC/XBLIG), metadata cache, ZIP|7Z filter,
    `quote(name, safe="-_.~")` URL building
  - `downloader.py` — persistent queue worker: retry+backoff, resume via
    `Range`, mirror fallback, `sync_auth()` copies S3 header + cookie jar
  - `extractor.py` — zip/7z unpack → `extract-xiso` (Xbox) / `Iso2God` (360,
    user exe) / XBLA title-dir detect+copy (ported `xblaParsing.cpp`)
  - `ftp_client.py` — ftplib to console FTPDs: **POSIX paths** (`Hdd1/Games`),
    `latin-1` listings, cancel support
  - `library.py` — sqlite (`~/.xrom/xrom.db`): games (+ persisted `links`,
    migrated via ALTER), queue (re-queue resets stale rows)
  - `metadata/` — IGDB / TheGamesDB / ScreenScraper providers (user keys);
    empty keys fall back to archive.org search
  - `sources/` — `SourceProvider` interface; `archive_org` + `hydra_json`
    (`{name, downloads:[{title,fileSize,uris,uploadDate}]}`)
  - `organizer.py` — `Title [Year] [TitleID]` folders, X-Store sanitizing,
    `.xrom.json` sidecar (links + local_path)
  - `config.py` — `~/.xrom/config.json`; secrets in keyring/env/memory only
  - `tools_fetch.py` — external binaries fetched at runtime, **never bundled**
- `src/xrom/app.py` — CustomTkinter frontend (being split into `ui/` +
  `controller.py`; new UI code must not do I/O directly)
- `src/xrom/__main__.py` — entry (`uv run xrom`, PyInstaller-safe)

## Validated live (don't regress)

- Cookie login (`logged-in-sig`) downloads gated items; **S3 keys alone 401**
  on `dn*` hosts. Cookie jar must keep `domain=.archive.org` (`get_dict()`
  drops it → 401).
- Queue re-add of a failed URL retries (no silent stale rows).
- Console FTPD needs `/` paths and `latin-1`; test box: Aurora, `Hdd1/Games`.
- E2E proven: login → 46 KB XBLA zip → title-dir `584E07D2` extract →
  FTP to `/Hdd1/Games/Dot_World_XBLIG/`.

## Rules

1. **No ROMs, links, credentials, keys** in code, issues, PRs, releases.
   Secrets live in env/keyring/`~/.xrom` (gitignored) or Temp scripts only.
2. **Credit everything**: new dep/logic → row in `docs/CREDITS.md` +
   `docs/THIRD_PARTY.md` before merge. Repo is AGPL-3.0-or-later.
3. `tests/` stays local-only (gitignored) but must pass: `pytest -q`.
   CI covers `src` only (ruff + format + smoke import) for this reason.
4. Lint is law: `ruff check`, `ruff format --check` (CI enforces on `src`).
   Config: `pyproject.toml` (`E4/E7/E9/F/I/UP/B`).
5. Threads for all I/O; UI updates via `after()`; missing art is normal
   (placeholder, silent).
6. Build: PyInstaller onefile (`XROM.spec` ignored); release via
   `gh release create vX.Y.Z dist\XROM.exe`.
