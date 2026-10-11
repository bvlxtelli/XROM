# XROM — Xbox ROM Download Manager & Organizer (PC)

**XROM** is a download manager and ROM organizer for Original Xbox, Xbox 360 and XBLA
collections on PC. Search game metadata (covers, genres, year), resolve files from
sources **you** configure, download with queue/retry/resume, organize the library with
clean folder names, and optionally send games to a modded console over FTP.

Python + CustomTkinter, managed with `uv`. See `docs/CREDITS.md` for all attributions.

## Vision (v1)

**ONLY a download manager + ROM organizer.** Metadata is the source of truth
(IGDB / ScreenScraper / TheGamesDB + local cache); file sources only *resolve*
what the metadata found. Extraction to GOD/XEX and console-side tooling are
explicitly out of scope for v1 (see Roadmap).

## Important: your links, your account (Hydra-style)

- XROM ships with **no ROMs, no download links, no credentials, no API keys**.
- `archive.org` access uses **your own free account** (email/password login or your
  S3 keys), entered in the Config tab and stored locally (password in OS keyring
  when available, never in the repo).
- Extra file sources can be imported as **Hydra-compatible JSON**
  (`{name, downloads:[{title,fileSize,uris,uploadDate}]}`) — again, yours.
- Metadata APIs (IGDB via your Twitch app, ScreenScraper/TheGamesDB accounts) also
  use keys you provide. Respect each provider's terms (non-commercial, attribution,
  rate limits) — details in `docs/CREDITS.md`.

## Features (v0.1.0)

- Metadata search: IGDB (genres/year/companies/platforms 11=Xbox, 12=X360),
  TheGamesDB + ScreenScraper fallback, cover-art cache, sqlite library.
- archive.org resolver: collection IDs ported from X-Store (`microsoft_xbox_*`,
  `microsoft_xbox360_*`, digital/DLC/XBLIG), CSRF login + S3 auth, metadata cache.
- Download manager: persistent queue (sqlite), retry w/ backoff, resume via
  `Range`, mirror fallback, pause/cancel, per-item log.
- Organizer: `Title [Year] [TitleID]` folders, sanitized (X-Store rules), unique
  names, `.xrom.json` sidecar per game; optional delete-after-FTP.
- Extractor (user's files only): unzip/7z + `extract-xiso` (Xbox),
  `Iso2God` (X360, user-provided exe), XBLA title-dir copy. Per-item platform
  picker in Queue; external binaries never bundled.
- X-Store keys import: point Config at your local `ArchiveOrgKeys.txt`
  (stays on your disk — secret kept in memory, never saved to repo).
- FTP: `ftplib` + Aurora/DashLaunch presets, recursive upload, test connection.
- External binaries (extract-xiso, ISO2GOD) are **never bundled** — fetched at
  runtime or user-provided (see `src/xrom/tools_fetch.py`).

## Quickstart

```powershell
uv venv
uv pip install -e ".[dev]"
uv run xrom        # GUI
uv run pytest      # tests
```

No `uv`? `python -m venv .venv && .venv\Scripts\pip install -e ".[dev]"`.

## Credits

XROM unifies Xbox open-source knowledge Hydra-style — every source is credited
in [`docs/CREDITS.md`](docs/CREDITS.md) (licenses in [`docs/THIRD_PARTY.md`](docs/THIRD_PARTY.md)):

| Source | Author(s) | License | Used for |
|---|---|---|---|
| [X-Store](https://github.com/951261/X-Store) | 951261 + contributors | AGPL-3.0 | archive.org auth, collection IDs, download + sanitize + XBLA logic |
| [extract-xiso-gui](https://github.com/KilLo445/extract-xiso-gui) | KilLo445, batch by bvlxtelli | MIT | extractor flags + batch logic |
| [extract-xiso](https://github.com/XboxDev/extract-xiso) | `in <in@fishtank.com>`, XboxDev | BSD | XISO backend (runtime-fetched, never bundled) |
| [Hydra Launcher](https://github.com/hydralauncher/hydra) | Hydra team | open source | source model + download-manager UX (see below) |
| IGDB / ScreenScraper / TheGamesDB | Twitch / community | service terms | metadata + covers (your keys) |

XROM itself is **AGPL-3.0-or-later** (`LICENSE`). Rule: anything new used inside
XROM gets a credit row before merge.

## Relationship with Hydra

[Hydra](https://github.com/hydralauncher/hydra) is the model for XROM: a
launcher/manager that ships **no games, no links, no accounts** — the user
brings their own download sources as JSON files
(`{name, downloads:[{title,fileSize,uris,uploadDate}]}`), and the app manages
queue, retry, extraction and library. XROM applies exactly that philosophy to
the Xbox (Original / 360 / XBLA) scene, unifying the scene's open-source pieces
(X-Store download logic, extract-xiso extraction, community metadata DBs) under
one manager. XROM can **import Hydra-format source files** (Sources tab) and
credits the Hydra team for the format and UX ideas — no Hydra code is vendored.

## Open source & community 🤝

**XROM is 100% open source (AGPL-3.0-or-later) and we count on the community.**
There is no company behind this — every improvement comes from people who use it.

Ways to help (no coding required for most):

- **Test & report**: open an issue with your platform, steps and logs.
- **New file sources**: a `SourceProvider` is a single file (~60 lines) —
  see `src/xrom/sources/hydra_json.py` for the template.
- **Metadata & art**: IGDB/ScreenScraper/TheGamesDB are community databases;
  correcting a cover or genre there improves XROM for everyone.
- **Docs & translations**: README, guides, UI strings.
- **Code**: PRs welcome — run `uv run pytest` + `ruff check src tests` first.

Rules for contributions: keep it legal and clean — **no ROMs, no download links,
no credentials, no API keys** in issues, PRs or code (same Hydra-style policy as
the app itself). By contributing you agree your work lands under AGPL-3.0-or-later
and gets a credit row in `docs/CREDITS.md`.

## Keywords

xbox 360 rom manager pc, archive.org xbox downloader python, iso2god gui python,
extract-xiso gui python, xbox ftp aurora customtkinter, xbla organizer.

## License

AGPL-3.0-or-later (inherited from X-Store logic). See `LICENSE`, `docs/CREDITS.md`,
`docs/THIRD_PARTY.md`.
