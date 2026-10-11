"""archive.org collection catalog ported from X-Store ui.h/ui.cpp + JSON_parser.

Original arrays XBOX_URL_PATHS[34], X360_URL_PATHS[37], XBLA_URL_PATHS[18]
copied verbatim (credit 951261/X-Store, AGPL-3.0).
URL building: base = alternate_locations.workable[0].server+dir (fallback
server+dir) + "/" + quote(name, safe="-_.~")  == X-Store UrlEncodeQuery.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import quote

import requests

from .ia_auth import BASE

# --- verbatim from user interface/ui.h ---------------------------------
XBOX_IDS = [
    "microsoft_xbox_numberssymbols",
    "microsoft_xbox_a",
    "microsoft_xbox_b",
    "microsoft_xbox_c_part1",
    "microsoft_xbox_c_part2",
    "microsoft_xbox_d_part1",
    "microsoft_xbox_d_part2",
    "microsoft_xbox_e",
    "microsoft_xbox_f",
    "microsoft_xbox_g",
    "microsoft_xbox_h",
    "microsoft_xbox_i",
    "microsoft_xbox_j",
    "microsoft_xbox_k",
    "microsoft_xbox_l",
    "microsoft_xbox_m_part1",
    "microsoft_xbox_m_part2",
    "microsoft_xbox_n_part1",
    "microsoft_xbox_n_part2",
    "microsoft_xbox_o_part1",
    "microsoft_xbox_o_part2",
    "microsoft_xbox_p",
    "microsoft_xbox_q",
    "microsoft_xbox_r",
    "microsoft_xbox_s_part1",
    "microsoft_xbox_s_part2",
    "microsoft_xbox_t_part1",
    "microsoft_xbox_t_part2",
    "microsoft_xbox_u",
    "microsoft_xbox_v",
    "microsoft_xbox_w",
    "microsoft_xbox_x",
    "microsoft_xbox_y",
    "microsoft_xbox_z",
]
X360_IDS = [
    "microsoft_xbox360_numberssymbols",
    "microsoft_xbox360_a_part1",
    "microsoft_xbox360_a_part2",
    "microsoft_xbox360_b_part1",
    "microsoft_xbox360_b_part2",
    "microsoft_xbox360_c_part1",
    "microsoft_xbox360_c_part2",
    "microsoft_xbox360_d_part1",
    "microsoft_xbox360_d_part2",
    "microsoft_xbox360_d_part3",
    "microsoft_xbox360_e",
    "microsoft_xbox360_f_part1",
    "microsoft_xbox360_f_part2",
    "microsoft_xbox360_g",
    "microsoft_xbox360_h",
    "microsoft_xbox360_i",
    "microsoft_xbox360_j",
    "microsoft_xbox360_k",
    "microsoft_xbox360_l",
    "microsoft_xbox360_m_part1",
    "microsoft_xbox360_m_part2",
    "microsoft_xbox360_n_part1",
    "microsoft_xbox360_n_part2",
    "microsoft_xbox360_o",
    "microsoft_xbox360_p",
    "microsoft_xbox360_q",
    "microsoft_xbox360_r",
    "microsoft_xbox360_s_part1",
    "microsoft_xbox360_s_part2",
    "microsoft_xbox360_t_part1",
    "microsoft_xbox360_t_part2",
    "microsoft_xbox360_u",
    "microsoft_xbox360_v",
    "microsoft_xbox360_w",
    "microsoft_xbox360_x_part1",
    "microsoft_xbox360_x_part2",
    "microsoft_xbox360_y",
    "microsoft_xbox360_z",
]
XBLA_IDS = [
    "microsoft_xbox360_digital_part1",
    "microsoft_xbox360_digital_part2",
    "microsoft_xbox360_digital_part3",
    "microsoft_xbox360_digital_part4",
    "microsoft_xbox360_digital_part5",
    "microsoft_xbox360_digital_part6",
    "microsoft_xbox360_digital_part7",
    "microsoft_xbox360_title-updates",
    "XBOX_360_DLC_1",
    "XBOX_360_DLC_2",
    "XBOX_360_DLC_3",
    "XBOX_360_DLC_4",
    "XBOX_360_DLC_5",
    "XBOX_360_DLC_6",
    "XBOX_360_XBLIG_1",
    "XBOX_360_XBLIG_2",
    "XBOX_360_XBLIG_3",
    "XBOX_360_XBLIG_4",
]

PLATFORM_IDS = {"xbox": XBOX_IDS, "xbox360": X360_IDS, "xbla": XBLA_IDS}
CACHE_TTL = 24 * 3600


def _cache_path(cache_dir: Path, ident: str) -> Path:
    return cache_dir / f"{ident}.json"


def fetch_metadata(ident: str, s: requests.Session, cache_dir: Path, force: bool = False) -> dict:
    """GET /metadata/<ident> with local cache (X-Store game:\\cache behavior)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cp = _cache_path(cache_dir, ident)
    if not force and cp.exists() and time.time() - cp.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except ValueError:
            pass
    r = s.get(f"{BASE}/metadata/{ident}", headers={"Referer": f"{BASE}/"}, timeout=60)
    if r.status_code in (401, 403):  # X-Store clears cache on auth failure
        cp.unlink(missing_ok=True)
    r.raise_for_status()
    data = r.json()
    cp.write_text(json.dumps(data), encoding="utf-8")
    return data


def download_base(meta: dict) -> str:
    """alternate_locations.workable[0] server+dir, fallback server+dir."""
    try:
        loc = meta["alternate_locations"]["workable"][0]
        return f"https://{loc['server']}{loc['dir']}"
    except (KeyError, IndexError, TypeError):
        return f"https://{meta['server']}{meta['dir']}"


def file_url(base: str, name: str) -> str:
    return base + "/" + quote(name, safe="-_.~")


def candidates(query: str, platform: str, s: requests.Session, cache_dir: Path) -> list[dict]:
    """Filter files by name substring + format ZIP|7Z (X-Store parse logic)."""
    out: list[dict] = []
    q = query.lower()
    for ident in PLATFORM_IDS[platform]:
        try:
            meta = fetch_metadata(ident, s, cache_dir)
        except requests.RequestException:
            continue
        try:
            base = download_base(meta)
        except KeyError:
            continue
        for f in meta.get("files", []):
            name = f.get("name", "")
            if q in name.lower() and f.get("format") in ("ZIP", "7Z"):
                size = f.get("size")
                try:
                    size = int(size) if size is not None else None
                except (ValueError, TypeError):
                    size = None
                out.append(
                    {
                        "name": name,
                        "url": file_url(base, name),
                        "size": size,
                        "format": f.get("format"),
                        "ident": ident,
                    }
                )
    return out
