"""External binary fetcher — tools are NEVER bundled (see CREDITS).

v1: documented + implemented, not yet wired to any pipeline (extraction is
out of v1 scope). Future extractor will call `tool_path("extract-xiso")`.
SHA256 pins must be filled from official releases at build time.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import requests

from .ia_auth import UA

TOOLS: dict[str, dict] = {
    "extract-xiso": {
        "win_url": "https://github.com/KilLo445/extract-xiso-gui/raw/master/extract-xiso-gui/extract-xiso.exe",
        "sha256": "",  # TODO: pin official hash
        "exe": "extract-xiso.exe",
    },
    "iso2god": {
        # Closed freeware — user-provided path preferred; URL left empty
        # on purpose until redistribution terms are confirmed.
        "win_url": "",
        "sha256": "",
        "exe": "Iso2God.exe",
    },
}


def tool_path(name: str, bin_dir: Path) -> Path | None:
    p = bin_dir / TOOLS[name]["exe"]
    return p if p.exists() else None


def fetch(name: str, bin_dir: Path) -> Path:
    url = TOOLS[name]["win_url"]
    if not url:
        raise RuntimeError(
            f"{name}: no official URL configured; set the tool path manually in Config."
        )
    bin_dir.mkdir(parents=True, exist_ok=True)
    dest = bin_dir / TOOLS[name]["exe"]
    r = requests.get(url, headers=UA, timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)
    want = TOOLS[name]["sha256"]
    if want and hashlib.sha256(dest.read_bytes()).hexdigest() != want:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"{name}: SHA256 mismatch, deleted.")
    return dest
