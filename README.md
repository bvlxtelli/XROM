# XROM

Your Xbox collection manager for PC: find games with covers, download them, organize everything and send to your console over FTP.

[Report Bug](https://github.com/bvlxtelli/XROM/issues/new?labels=bug&title=%5BBug%5D+Simple+description+of+the+bug) · [Request Feature](https://github.com/bvlxtelli/XROM/issues/new?labels=enhancement&title=%5BFeature%5D+Simple+description+of+your+request)

[![Forks](https://img.shields.io/github/forks/bvlxtelli/XROM?style=for-the-badge)](https://github.com/bvlxtelli/XROM/network/members) [![Stargazers](https://img.shields.io/github/stars/bvlxtelli/XROM?style=for-the-badge)](https://github.com/bvlxtelli/XROM/stargazers) [![Issues](https://img.shields.io/github/issues/bvlxtelli/XROM?style=for-the-badge)](https://github.com/bvlxtelli/XROM/issues)
[![Downloads](https://img.shields.io/github/downloads/bvlxtelli/XROM/total?style=for-the-badge&label=Downloads&color=2EA430)](https://github.com/bvlxtelli/XROM/releases/latest)

## About The Project

XROM is a download manager and organizer for Original Xbox, Xbox 360 and XBLA games on PC. Search a game, see its cover and info, download it, keep your library tidy and send games to a modded console — all in one window.

Works like [Hydra Launcher](https://github.com/hydralauncher/hydra): the app ships with **no games, no links, no accounts**. You add your own archive.org account (free) and your own source files, and XROM does the rest.

Features:

-   Search
    -   Find games with cover art, year and genres.
    -   Links travel with the game: each result shows how many downloads it has.
-   Download
    -   Queue with pause, resume, retry and speed/ETA.
    -   Links break? XROM tries mirrors automatically.
-   Library
    -   Games get clean folders: `Title [Year] [ID]`.
    -   Add games first, download later — entries can wait as a wishlist.
    -   Link a ROM file you already have (iso/zip/7z) without downloading.
-   Extract
    -   Unpacks zip/7z, Xbox ISOs (extract-xiso) and Xbox 360 ISOs (Iso2God).
    -   XBLA titles are detected and copied to the right layout.
-   Send to console
    -   One click sends a game over FTP (Aurora/DashLaunch presets).
    -   Optionally deletes the local copy after a successful send.

### Built With

-   [![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
-   [![CustomTkinter](https://img.shields.io/badge/CustomTkinter-GUI-2EA430?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
-   [![uv](https://img.shields.io/badge/uv-packages-4B275F?style=for-the-badge)](https://docs.astral.sh/uv/)

## Changelog

### v0.2.0

-   New: library as wishlist (add now, download later, per-game send/remove).
-   New: progress dialogs for FTP and extraction (bar + log + cancel).
-   New: queue speed/ETA, icon buttons, covers in the library.

### v0.1.0

-   First release: search, queue, organizer, extractor, FTP, single-file `.exe`.

## Getting Started

### Prerequisites

-   Windows 10 or newer.
-   A free [archive.org](https://archive.org/account/signup) account (for downloads).
-   A modded Xbox 360 on the same network (only if you want FTP sending).

### Installation

1.  Head over to the [latest release](https://github.com/bvlxtelli/XROM/releases/latest)
2.  Download `XROM.exe`
3.  Run it — no install needed

### First steps

1.  Open the **Config** tab and log in with your archive.org account
    (or import your X-Store `ArchiveOrgKeys.txt` — it never leaves your PC).
2.  Go to **Search**, type a game, pick Xbox / Xbox 360 / XBLA.
3.  Click **Download** on a result, or **🔗 Links** to choose between versions.
4.  Watch it in **Queue**, then find it organized in **Library**.
5.  Select a game in **Library** and hit **⬆** to send it to your console.

### Installation (from source)

1.  Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
2.  `uv venv && uv pip install -e ".[dev]"`
3.  `uv run xrom` to open the app

Developers: `uv run ruff check src tests`, `uv run ruff format --check src tests`,
`uv run pytest -q` (CI runs all three).

## Help links

-   Create your archive.org account: [archive.org/account/signup](https://archive.org/account/signup)
-   Richer covers/info (optional keys): [IGDB via Twitch](https://api-docs.igdb.com/#account-creation), [ScreenScraper](https://www.screenscraper.fr/), [TheGamesDB](https://thegamesdb.net/)
-   The projects XROM builds on: [X-Store](https://github.com/951261/X-Store), [extract-xiso-gui](https://github.com/KilLo445/extract-xiso-gui), [Hydra Launcher](https://github.com/hydralauncher/hydra)
-   Stuck? [Open an issue](https://github.com/bvlxtelli/XROM/issues) — logs from `~/.xrom` help a lot

## License

Distributed under the AGPL-3.0 License (inherited from X-Store). See `LICENSE` for more information.

## Credits

-   Download logic: [X-Store](https://github.com/951261/X-Store) by [@951261](https://github.com/951261)
-   Extractor UI logic + batch mode: [extract-xiso-gui](https://github.com/KilLo445/extract-xiso-gui) by [@KilLo445](https://github.com/KilLo445) and [@bvlxtelli](https://github.com/bvlxtelli)
-   Source model + manager idea: [Hydra Launcher](https://github.com/hydralauncher/hydra)
-   XISO backend: [extract-xiso](https://github.com/XboxDev/extract-xiso)
-   Full list with licenses: [`docs/CREDITS.md`](docs/CREDITS.md)

## Community

XROM is 100% open source and counts on you: testing, issues, new file sources
(one file each — see `src/xrom/sources/hydra_json.py`), docs and code.
Rule for contributions: no ROMs, no links, no credentials, no keys — same as the app.

## Contact

-   Issues: [bvlxtelli/XROM](https://github.com/bvlxtelli/XROM/issues)
-   More: [@bvlxtelli](https://github.com/bvlxtelli)
