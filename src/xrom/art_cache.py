"""Cover-art disk cache: url -> ~/.xrom/art/<sha1>.jpg."""
from __future__ import annotations

import hashlib
from pathlib import Path

import requests

from .ia_auth import UA


def cached_art(url: str, art_dir: Path) -> Path | None:
    if not url:
        return None
    art_dir.mkdir(parents=True, exist_ok=True)
    dest = art_dir / (hashlib.sha1(url.encode()).hexdigest() + ".jpg")
    if dest.exists() and dest.stat().st_size:
        return dest
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return dest
    except requests.RequestException:
        return None
