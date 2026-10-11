# CREDITS — XROM attributions

Every project, tool, database or snippet reused or referenced by XROM **must** be
listed here. License: XROM itself is **AGPL-3.0-or-later** (copyleft inherited from
the X-Store logic it ports, §13 network clause applies).

## Direct ports / logic sources

| Project | Author(s) | License | What we use |
|---|---|---|---|
| [X-Store](https://github.com/951261/X-Store) | 951261 + contributors | **AGPL-3.0** | archive.org auth (CSRF login, S3 keys), collection IDs (`microsoft_xbox_*`, `microsoft_xbox360_*`, digital/DLC/XBLIG), metadata→download-URL logic, filename sanitizing, XBLA title-dir detection, queue/download UX ideas |
| [extract-xiso-gui](https://github.com/KilLo445/extract-xiso-gui) | KilLo445, batch mode by bvlxtelli | **MIT** | CLI flag mapping (`-c/-l/-r/-x/-d/-D/-m/-s`), batch scan + unique-dir logic (future extractor integration) |
| [extract-xiso (XboxDev)](https://github.com/XboxDev/extract-xiso), orig. by `in <in@fishtank.com>` | in@fishtank.com, XboxDev | **BSD 4-clause** (keep copyright + acknowledgement `This product includes software developed by in <in@fishtank.com>`) | External XISO backend (never bundled; fetched at runtime) |
| [Hydra Launcher](https://github.com/hydralauncher/hydra) | Hydra team (open source) | verify SPDX at build | Download-source JSON format idea (`{name, downloads:[{title,fileSize,uris,uploadDate}]}`), download-manager UX (queue/retry/multi-host) — no Hydra code vendored |

## External (closed) tools — called, never bundled

| Tool | Status | Note |
|---|---|---|
| ISO2GOD | **Freeware, closed source** | Called via subprocess only; user-provided path or runtime download. Open alternative under evaluation: Velocity (verify license at build) |
| abgx360 + `GameNameLookup.csv` | **Freeware, closed source** | CSV used at runtime only if terms allow; otherwise community title-ID dumps |

## Metadata providers (proprietary services — your keys, their terms)

- **IGDB (Twitch)**: free non-commercial under Twitch Developer Services Agreement, 4 req/s, Apicalypse query language. Attribution required.
- **ScreenScraper.fr**: free account, ~20k req/day registered. Do not redistribute DB dumps.
- **TheGamesDB**: free API key, monthly per-IP quota. Community-run.
- Design reference for provider ranking/fallback: [RomM](https://github.com/rommapp/romm).

## Parsing references

- [Deterous/ParseXboxMetadata](https://github.com/Deterous/ParseXboxMetadata) — XBE cert / XEX ExecutionInfo field layout (future validator).
- `badgio/xbox360iso.py` — XEX `ExecutionInfo` walk + `media_id → name` CSV approach (idea only).
- [Team-Resurgent/XexTool](https://github.com/Team-Resurgent/XexTool) — XEX inspection flags (future validator).
- [`xex2` crate + PyPI bindings](https://pypi.org/project/xex2/) — optional XEX parser (future validator).

## Libraries bundled as dependencies

- `requests` (Apache-2.0), `CustomTkinter` (verify SPDX), `Pillow` (HPND), `py7zr` (verify SPDX) — see `docs/THIRD_PARTY.md`.
- X-Store third-party heritage (for the record): XboxTLS (MIT, JakobRangel), LZMA SDK (public domain-ish), miniz (MIT, richgel999), cJSON (MIT, DaveGamble).

## Rule

**Anything new used inside XROM gets a row here + `docs/THIRD_PARTY.md` before merge.**
