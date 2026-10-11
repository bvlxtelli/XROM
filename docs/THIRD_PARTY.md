# THIRD_PARTY — licenses of everything XROM depends on or calls

XROM itself: **AGPL-3.0-or-later** (`LICENSE`).

| Component | License (verify SPDX at release) | Notes |
|---|---|---|
| X-Store logic (archive.org auth, catalog IDs, sanitize, XBLA detect) | AGPL-3.0 (951261) | Ported logic; copyleft applies to XROM |
| extract-xiso-gui flag/batch logic | MIT (KilLo445, bvlxtelli) | Logic only |
| extract-xiso binary (`in@fishtank.com`, XboxDev) | BSD 4-clause | Runtime-fetched, never bundled; keep acknowledgement |
| ISO2GOD binary | Closed freeware | User-provided path only; never bundled |
| `requests` | Apache-2.0 | |
| `customtkinter` | verify | GUI |
| `Pillow` | HPND | Cover thumbnails |
| `py7zr` (+ pyppmd/pyzstd backends) | verify | `.7z` unpack |
| `pytest`, `ruff` | MIT | Dev-only |
| IGDB / ScreenScraper / TheGamesDB | Proprietary services, user keys | Terms in `docs/CREDITS.md`; no DB redistribution |
| `keyring` (optional) | MIT | Password storage when installed |

**Rule: new dependency → row here + `docs/CREDITS.md` before merge.**
